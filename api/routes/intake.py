"""Getting PDFs in, as an admin (docs/WEB_UI_PARITY_PLAN.md, section 6, stage 4).

Every route here is admin only. A PDF arrives as the raw request body (no multipart library), is checked and stored by `services/intake_service.py`, and is started as an
ingest job by a second request, so the same-name question can be asked between the two. The server never takes a path from a caller: an upload is named by the id this module
made, and the only folder it reads from is the configured inbox."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from api.deps import require_admin
from core import config as _config
from services import intake_service, job_service
from services.intake_service import IntakeError
from services.job_service import JobAlreadyQueued

router = APIRouter(dependencies=[Depends(require_admin)])


class IngestRequest(BaseModel):
    upload_id: str = Field(min_length=1, max_length=64)
    if_exists: Literal["ask", "replace", "keep_both"] = "ask"


class InboxRequest(BaseModel):
    files: list[str] | None = Field(default=None, max_length=500)
    if_exists: Literal["ask", "replace", "keep_both"] = "ask"


def _refuse(e: IntakeError) -> HTTPException:
    return HTTPException(status_code=e.status, detail={"code": e.code, "message": e.message})


def _public(meta: dict) -> dict:
    return {k: meta[k] for k in ("upload_id", "filename", "stem", "size", "pages", "sha256") if k in meta}


def _client(request: Request) -> str:
    return request.client.host if request.client else ""


@router.post("/uploads", status_code=201)
async def upload_pdf(request: Request, filename: str = Query(..., min_length=1, max_length=255)) -> dict:
    """Store one PDF sent as the raw body. Returns what it is and where it stands against the library, so the screen can ask before starting anything."""
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > intake_service.max_upload_bytes():
        raise _refuse(IntakeError("too_large", f"The file is larger than the {intake_service.max_upload_bytes() // (1024 * 1024)} MB limit.", 413))
    processed_dir = _config.load().processed_dir_path()
    try:
        writer = intake_service.UploadWriter(processed_dir, filename)
    except IntakeError as e:
        raise _refuse(e) from None
    try:
        async for chunk in request.stream():
            writer.write(chunk)
        meta = await run_in_threadpool(writer.finish)
    except IntakeError as e:
        writer.abort()
        raise _refuse(e) from None
    except BaseException:
        writer.abort()
        raise
    jobs = job_service.default_store(processed_dir).list_jobs()
    return {**_public(meta), "library": intake_service.classify(processed_dir, meta["stem"], meta["sha256"], jobs)}


def _start(processed_dir, store, pdf_path, stem: str, sha256: str, if_exists: str, requested_by: str) -> dict:
    """Queue one ingest, or say why not. Returns {"result": "queued"|"skipped"|"needs_decision", ...}."""
    jobs = store.list_jobs()
    where = intake_service.classify(processed_dir, stem, sha256, jobs)
    status = where["status"]
    if status == "queued":
        return {"result": "skipped", "reason": "queued", "document": stem, "job_id": where.get("job_id"),
                "message": f"{stem} is already queued or running."}
    if status in ("same_content", "same_content_other_name"):
        return {"result": "skipped", "reason": status, "document": where["document"],
                "message": f"The same file is already in the library as {where['document']}; nothing to do."}
    run_path, run_stem = pdf_path, stem
    if status == "same_name_different_content":
        if if_exists == "ask":
            return {"result": "needs_decision", "reason": status, "document": stem, "options": ["replace", "keep_both"],
                    "message": f"{stem} is already in the library with different content. Replace it, or keep both?"}
        if if_exists == "keep_both":
            run_stem = intake_service.free_stem(processed_dir, stem, jobs)
            run_path = intake_service.renamed_copy(pdf_path, run_stem, processed_dir)
    try:
        job = job_service.enqueue_ingest(run_path, store=store, requested_by=requested_by,
                                         params_extra={"sha256": sha256, "if_exists": if_exists if status == "same_name_different_content" else "n/a"})
    except JobAlreadyQueued as e:  # another request got there between the check above and the write
        return {"result": "skipped", "reason": "queued", "document": run_stem, "job_id": e.job_id, "message": f"{run_stem} is already queued or running."}
    except ValueError as e:
        raise HTTPException(status_code=422, detail={"code": "not_startable", "message": str(e)}) from None
    return {"result": "queued", "document": run_stem, "job": job_service.summarize(job)}


@router.post("/jobs/ingest", status_code=202)
def start_ingest(req: IngestRequest, request: Request) -> dict:
    """Start the full pipeline for an uploaded PDF. 202 when queued; 200 when there is nothing to do; 409 when the same name needs a decision (replace or keep both)."""
    processed_dir = _config.load().processed_dir_path()
    try:
        meta = intake_service.read_upload(processed_dir, req.upload_id)
    except IntakeError as e:
        raise _refuse(e) from None
    out = _start(processed_dir, job_service.default_store(processed_dir), meta["path"], meta["stem"], meta["sha256"], req.if_exists, _client(request))
    if out["result"] == "needs_decision":
        raise HTTPException(status_code=409, detail={"code": out["reason"], **{k: out[k] for k in ("message", "options", "document")}})
    if out["result"] == "skipped":
        return JSONResponse(status_code=200, content=out)
    return out


@router.get("/inbox")
def get_inbox() -> dict:
    """The PDFs waiting in the inbox folder and where each stands against the library."""
    processed_dir = _config.load().processed_dir_path()
    return intake_service.list_inbox(processed_dir, job_service.default_store(processed_dir).list_jobs())


@router.post("/jobs/inbox", status_code=202)
def import_inbox(req: InboxRequest, request: Request) -> dict:
    """Start one ingest per PDF in the inbox (all of them, or the named ones). A file already in the library with the same content is skipped; a same-name file with different
    content is reported for a decision unless `if_exists` says what to do."""
    processed_dir = _config.load().processed_dir_path()
    store = job_service.default_store(processed_dir)
    folder = intake_service.inbox_dir(processed_dir)
    if not folder.is_dir():
        raise HTTPException(status_code=404, detail={"code": "no_inbox", "message": f"The inbox folder does not exist: {folder}"})
    available = intake_service.inbox_pdfs(folder)
    names = sorted(available) if req.files is None else req.files
    results = []
    for name in names:
        path = available.get(name)  # a name that is not a PDF directly in the inbox is simply not found: no path is ever built from the request
        if path is None:
            results.append({"file": name, "result": "refused", "code": "not_in_inbox", "message": "No such PDF in the inbox."})
            continue
        try:
            intake_service.check_pdf_file(path)
            out = _start(processed_dir, store, str(path), path.stem, intake_service.file_sha256(path), req.if_exists, _client(request))
        except IntakeError as e:
            results.append({"file": name, "result": "refused", "code": e.code, "message": e.message})
            continue
        results.append({"file": name, **out})
    return {"results": results, "queued": sum(1 for r in results if r["result"] == "queued")}
