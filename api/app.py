"""ReqBot FastAPI application — Phase 22: checklist API endpoints added.

Start with: reqbot serve [--host 0.0.0.0] [--port 8000]

Endpoints (all prefixed /api/):
  GET  /api/status              — Ollama + Qdrant health checks + processed doc listing
  POST /api/ask                 — Hybrid vector search with optional synthesis
  GET  /api/trace/{req_id}      — Full requirement provenance by ID
  GET  /api/docs                — Indexed document listing
  POST /api/compare             — Cross-framework comparison for two documents on a topic
  POST /api/evidence            — Evidence mapping for a topic, grouped by control ID
  GET  /api/profiles            — List available domain profile names
  POST /api/checklist           — Generate a checklist for a document and profile
  POST /api/checklist/export    — Export a checklist as CSV, JSON, or Markdown
  GET  /api/config              — Effective config values + env-override flags
  POST /api/config              — Partial config.json update (loopback only)
  GET  /api/setup               — Is ReqBot set up yet (no config file saved)
  POST /api/setup/check         — Test a configuration: services, models, folder (loopback only)

GUI (when frontend/dist/ is built):
  GET  /{any}                — catch-all: serves real file if it exists in dist/,
                               otherwise index.html (React Router handles routing)

Swagger UI is at /api-docs.
"""
import logging
import sys
from pathlib import Path

# Ensure repo root is on sys.path when the app module is imported directly.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import (
    access,
    ask,
    checklist,
    compare,
    config,
    docs,
    evidence,
    intake,
    jobs,
    library,
    setup,
    status,
    trace,
)

log = logging.getLogger(__name__)

# Resolve frontend dist path relative to this file.
# Works identically in a dev checkout and the installed bundle because the
# bundler preserves this relative structure (api/app.py → frontend/dist/).
_DIST_DIR = Path(__file__).resolve().parent.parent / "frontend" / "dist"


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    _warm_reranker_if_configured()
    yield


def _warm_reranker_if_configured() -> None:
    """Fire-and-forget: if a reranker service is configured, ask it to load its
    model now, in parallel with this server starting up, instead of waiting for
    a user's first search to pay that cost. The reranker itself may be idle-
    unloaded later (rerank_server/server.py); this just avoids a cold first hit
    right after a restart. Never blocks server startup or raises on failure --
    a reranker that's slow or unreachable at boot just stays cold until first use."""
    import threading
    import urllib.request

    from core import config as _config
    rerank_url = _config.load().rerank_url
    if not rerank_url:
        return

    def _ping():
        try:
            urllib.request.urlopen(rerank_url.rstrip("/") + "/warm", data=b"{}", timeout=120)
        except Exception as exc:
            log.info("Reranker warm-up ping failed (%s) -- will load on first search instead", exc)

    threading.Thread(target=_ping, daemon=True).start()


app = FastAPI(
    title="ReqBot API",
    version="0.2.0",
    description="Read-only compliance requirements intelligence API.",
    docs_url="/api-docs",
    redoc_url="/api-redoc",
    lifespan=_lifespan,
)

# CORS — restricted to known local GUI origins.
# :5173 added for Vite dev server (Phase 18).
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# API routes — all under /api/ prefix so they don't shadow SPA client-side routes.
app.include_router(status.router, prefix="/api")
app.include_router(ask.router, prefix="/api")
app.include_router(trace.router, prefix="/api")
app.include_router(docs.router, prefix="/api")
app.include_router(compare.router, prefix="/api")
app.include_router(evidence.router, prefix="/api")
app.include_router(checklist.router, prefix="/api")
app.include_router(config.router, prefix="/api")
app.include_router(access.router, prefix="/api")  # public: which mode admin actions are in (never the code)
app.include_router(setup.router, prefix="/api")  # first-run setup: is it set up (public), test these values (loopback only)
app.include_router(jobs.router, prefix="/api")  # admin only: answers 403 until an admin access code is configured
app.include_router(library.router, prefix="/api")  # admin only: remove a document (to the trash, with a confirmation)
app.include_router(intake.router, prefix="/api")  # admin only: uploads, the inbox and starting an ingest

# SPA static file serving — only when the frontend build exists.
# Registered after all /api/ routes so it never shadows an API endpoint.
#
# The catch-all checks whether the requested path maps to a real file under
# dist/ first (favicon.ico, robots.txt, assets/*.js, assets/*.css, etc.).
# If it does, serve that file. Otherwise serve index.html so React Router
# handles the client-side route (/search, /trace/:id, etc.).
#
# A resolved-path check guards against directory traversal: only files that
# actually live under _DIST_DIR are served directly.
_INDEX_HTML = _DIST_DIR / "index.html"
_DIST_DIR_RESOLVED = _DIST_DIR.resolve()

# SPA route prefixes whose dynamic path segments may contain dots (e.g. doc_key
# values like "NIST.SP.800-53r5"). These must always serve index.html so that
# direct navigation and browser refresh work in the packaged app.
_SPA_PREFIXES = ("checklists/", "corpus/", "trace/")

if _INDEX_HTML.exists():
    from fastapi import HTTPException as _HTTPException
    from fastapi.responses import FileResponse as _FileResponse

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str) -> _FileResponse:
        candidate = (_DIST_DIR / full_path).resolve()
        if candidate.is_file() and candidate.is_relative_to(_DIST_DIR_RESOLVED):
            return _FileResponse(str(candidate))
        # Known SPA routes with dotted path params always get index.html.
        if any(full_path.startswith(p) for p in _SPA_PREFIXES):
            return _FileResponse(str(_INDEX_HTML))
        # Other paths with a file extension (assets/*.js, assets/*.css) that have
        # no matching file under dist/ return 404 — surfaces broken asset refs.
        # Bare paths (/search, /evidence) fall through to the SPA entry point.
        if Path(full_path).suffix:
            raise _HTTPException(status_code=404, detail="Not found")
        return _FileResponse(str(_INDEX_HTML))

else:
    log.info("Frontend build not found; serving API only")
