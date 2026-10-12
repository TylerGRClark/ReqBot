"""Job routes (docs/WEB_UI_PARITY_PLAN.md, stages 3 and 4): list and read, cancel and retry. Admin only.

Starting a job is in `api/routes/intake.py`, next to the uploads that feed it."""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from api.deps import require_admin
from services import job_service

router = APIRouter(dependencies=[Depends(require_admin)])


@router.get("/jobs")
def list_jobs(limit: int = Query(50, ge=1, le=200)) -> dict:
    """The jobs, newest first, with what is running and how many are waiting."""
    store = job_service.default_store()
    jobs = store.list_jobs()
    running = next((j["id"] for j in jobs if j["state"] == "running"), None)
    return {
        "jobs": [job_service.summarize(j) for j in jobs[:limit]],
        "running": running,
        "queued": sum(1 for j in jobs if j["state"] == "queued"),
    }


@router.get("/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    """One job, with the tail of its log."""
    store = job_service.default_store()
    try:
        job = store.get(job_id)
    except ValueError:
        job = None
    if job is None:
        raise HTTPException(status_code=404, detail=f"No such job: {job_id}")
    return {**job_service.summarize(job), "log_tail": store.log_tail(job_id)}


@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str) -> dict:
    """Cancel a queued job at once, or ask a running one to stop (its runner ends the process within about a second)."""
    store = job_service.default_store()
    try:
        job = store.cancel(job_id)
    except ValueError:
        job = None
    if job is None:
        raise HTTPException(status_code=404, detail=f"No such job: {job_id}")
    return job_service.summarize(job)


@router.post("/jobs/{job_id}/retry", status_code=202)
def retry_job(job_id: str) -> dict:
    """Queue a failed, cancelled or interrupted job again, in the same run folder."""
    store = job_service.default_store()
    try:
        new = store.retry(job_id)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from None
    return job_service.summarize(new)


class QuestionsRequest(BaseModel):
    doc_key: str = Field(min_length=1, max_length=255)


class ReindexRequest(BaseModel):
    requirements_only: bool = False


def _queued(build) -> dict:
    """Run an enqueue; a job for the same thing already queued or running is "skipped", an unknown document is a 404, a bad key a 422."""
    try:
        return {"result": "queued", "job": job_service.summarize(build())}
    except job_service.JobAlreadyQueued as e:
        return {"result": "skipped", "reason": "queued", "job_id": e.job_id, "message": "That is already queued or running."}
    except LookupError as e:
        raise HTTPException(status_code=404, detail={"code": "no_such_document", "message": str(e)}) from None
    except ValueError as e:
        raise HTTPException(status_code=422, detail={"code": "bad_request", "message": str(e)}) from None


@router.post("/jobs/questions", status_code=202)
def start_questions(req: QuestionsRequest, request: Request) -> dict:
    """Write draft audit questions for one document (the model machine, in the background). 202 when queued; the same document already queued or running answers `skipped`."""
    who = request.client.host if request.client else ""
    return _queued(lambda: job_service.enqueue_questions(req.doc_key, requested_by=who))


@router.post("/jobs/reindex", status_code=202)
def start_reindex(req: ReindexRequest, request: Request) -> dict:
    """Rebuild the search library from the saved documents (no re-extraction). One rebuild at a time."""
    who = request.client.host if request.client else ""
    return _queued(lambda: job_service.enqueue_reindex(requirements_only=req.requirements_only, requested_by=who))
