"""First-run setup (docs/WEB_UI_PARITY_PLAN.md, section 9a): is ReqBot set up, and what would a given configuration find?

Read-only. Saving what the wizard collects goes through the existing `POST /api/config` (same writer `reqbot init` uses), and admin protection is switched with
`reqbot token` on the server, never from a request: a route that could turn it off would be the one thing an attacker wants.
"""
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from api.routes.config import _is_loopback
from core import config as _config
from services import setup_service
from services.job_service import QUESTIONS_MODEL

router = APIRouter()

_NAME = Field(default=None, max_length=200)


class CheckRequest(BaseModel):
    """The values to test. Anything left out is taken from the configuration as it is now."""
    ollama_url: Optional[str] = Field(default=None, max_length=500)
    qdrant_url: Optional[str] = Field(default=None, max_length=500)
    embedding_model: Optional[str] = _NAME
    default_model: Optional[str] = _NAME
    extraction_model: Optional[str] = _NAME
    rewrite_model: Optional[str] = _NAME
    synthesis_model: Optional[str] = _NAME
    synthesis_backend: Optional[Literal["local", "remote", "none"]] = None


@router.get("/setup")
def get_setup() -> dict:
    """`needs_setup` is true when no configuration file has been saved yet (nothing has run `reqbot init` or the Settings page). Public: it carries no value from the file."""
    saved = _config.CONFIG_PATH.exists()
    return {"config_file": saved, "needs_setup": not saved, "questions_model": QUESTIONS_MODEL}


@router.post("/setup/check")
def post_setup_check(req: CheckRequest, request: Request) -> dict:
    """Test the given values (or the current ones): both services, every model, the documents folder. Loopback only, like `POST /api/config`: it makes this machine call the
    addresses it is given, so it is only offered to someone at the server itself. Writes nothing."""
    if not _is_loopback(request):
        raise HTTPException(status_code=403, detail="POST /setup/check is restricted to localhost")
    cfg = _config.load()
    current = {k: getattr(cfg, k) for k in ("ollama_url", "qdrant_url", "embedding_model", "default_model", "extraction_model", "rewrite_model", "synthesis_model",
                                            "synthesis_backend")}
    given = {k: v for k, v in req.model_dump(exclude_none=True).items() if v != ""}
    values = {**current, **given}
    if "default_model" in given:
        for role in ("extraction_model", "rewrite_model"):  # a role that was following the default keeps following it (config resolves it the same way)
            if role not in given and getattr(cfg, role) == cfg.default_model:
                values[role] = given["default_model"]
    return setup_service.run_check(values, cfg.processed_dir_path(), QUESTIONS_MODEL)
