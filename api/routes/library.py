"""Remove a document (docs/WEB_UI_PARITY_PLAN.md, section 9, stage 6). Admin only, and never without a confirmation: see services/library_service.py."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.deps import require_admin
from core import config as _config
from services import job_service, library_service

router = APIRouter(dependencies=[Depends(require_admin)])


class RemoveRequest(BaseModel):
    doc_key: str = Field(min_length=1, max_length=255)
    confirm: bool = False
    confirm_name: str = Field(default="", max_length=255)


def _qdrant(url: str):
    from qdrant_client import QdrantClient

    return QdrantClient(url=url)


@router.post("/documents/remove")
def remove_document(req: RemoveRequest) -> dict:
    """Move the document's run folders to the trash and take its points out of search. Needs `confirm: true` and `confirm_name` equal to `doc_key`.

    404 not in the library; 409 a job for it is queued or running; 422 no confirmation (nothing was changed); 503 the search index could not be reached (nothing was moved)."""
    cfg = _config.load()
    processed = cfg.processed_dir_path()
    try:
        active = job_service.default_store(processed).list_jobs()
        return library_service.remove_document(processed, req.doc_key, confirm=req.confirm, confirm_name=req.confirm_name, active_jobs=active,
                                               client=_qdrant(cfg.qdrant_url))
    except library_service.ConfirmationRequired as e:
        raise HTTPException(status_code=422, detail={"code": "confirmation_required", "message": str(e)}) from None
    except ValueError as e:
        raise HTTPException(status_code=422, detail={"code": "bad_request", "message": str(e)}) from None
    except LookupError as e:
        raise HTTPException(status_code=404, detail={"code": "no_such_document", "message": str(e)}) from None
    except library_service.RemoveBlocked as e:
        raise HTTPException(status_code=409, detail={"code": "jobs_active", "message": "A job for this document is queued or running; cancel it or wait for it first.", "job_ids": e.job_ids}) from None
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail={"code": "index_unreachable", "message": str(e)}) from None
