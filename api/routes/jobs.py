"""Job routes (docs/WEB_UI_PARITY_PLAN.md, stage 3): read-only, admin only.

Starting, cancelling and retrying come with the screens that use them (stage 4)."""
from fastapi import APIRouter, Depends, HTTPException, Query

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
