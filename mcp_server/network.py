"""The network door: the same seven read-only tools as `reqbot mcp`, served over HTTP to AI tools on other machines (docs/WEB_UI_PARITY_PLAN.md, section 4).

`reqbot mcp --http` starts it; it is never on unless asked for. It wraps the functions of mcp_server/server.py, so there is one implementation of every tool, and it differs
from the stdio server only where a remote caller changes what is safe:

  * Only the seven read-only tools exist. Nothing here can add, change or remove a document, start a job or read a setting.
  * Every request needs one of the access codes of core/mcp_codes.py (Authorization: Bearer <code>), checked on every request, so a revoked code stops at once.
  * The tools run in worker threads, so one slow search never stops another caller, and at most N run at once (REQBOT_MCP_MAX_CONCURRENT, default 4); a caller that
    cannot be served within 30 seconds is told the server is busy. Each search costs two language-model calls and an embedding on the model machine.
  * No synthesis: `map_evidence` has no `synthesize` argument here. The connected AI tool writes its own answer from the returned quotes.
  * Nothing about the server's layout is returned: `get_status` says only what is reachable and how much there is, `list_documents` leaves out folders, the payload fields
    and warnings that name the server's models are removed from every answer, and an error that
    would name an address or a folder is replaced by a short sentence and a reference to the line in the request log (core and services messages are written for an operator).
  * Every call is written to the request log (mcp_server/request_log.py) under the name of the code that made it.

TLS and any company sign-in belong to the gateway in front of this service (docs/DEPLOYMENT.md); the transport here is plain HTTP and is meant for a trusted network or a proxy.
"""
import asyncio
import functools
import logging
import os
import re
import secrets
import time
from pathlib import Path

import anyio
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.responses import JSONResponse

from core import config as _config
from core import mcp_codes
from mcp_server import server as _stdio
from mcp_server.request_log import RequestLog
from services import audit_questions

log = logging.getLogger(__name__)

DEFAULT_PORT = 8765
DEFAULT_MAX_CONCURRENT = 4
ENV_MAX_CONCURRENT = "REQBOT_MCP_MAX_CONCURRENT"
ENV_LOG_PATH = "REQBOT_MCP_LOG"
BUSY_WAIT_SECONDS = 30.0
FAILED_CODE_DELAY_SECONDS = 1.0
SCOPE_KEY = "reqbot.mcp_code"
LOOPBACK_HOSTS = ("127.0.0.1", "localhost", "::1")

# The whole surface of the door. A test holds this list to read-only tools; adding a name here is a decision, not a side effect.
TOOL_NAMES = (
    "get_status",
    "list_documents",
    "search_requirements",
    "trace_requirement",
    "compare_documents",
    "map_evidence",
    "generate_checklist",
)

_LISTED_DOCUMENT_FIELDS = ("doc_key", "source_pdf", "count", "mode", "run_date", "profile")  # the names list_docs really emits
# Error texts the services write for the caller's own input: safe to pass on. Anything else is replaced.
_PASS_THROUGH = ("top_k must be", "Unknown document_ids", "No requirements found with source_ref", "No results found for", "Requirement not found")
_MISSING_DOC = re.compile(r"No requirements JSONL found for doc_key '([^']*)'")
BUSY_MESSAGE = "ReqBot is answering other requests right now. Try again in a moment."

# Payload fields that name the models this server runs (every indexed requirement carries them), and the sentence that would name them in a warning.
_MODEL_KEYS = frozenset({"extraction_model", "embedding_model", "enrichment_model", "rewrite_model", "synthesis_model", "question_model", "embedding_dim"})
_MODEL_WORDS = "a language model"
_EMBEDDING_WARNING = "Some results were indexed with a different embedding model than the server now uses and may be less reliable; the operator can rebuild the library."


class _Busy(Exception):
    pass


def client_message(exc: Exception) -> tuple[str, str]:
    """(what the caller is told, a reference for the log line). Input mistakes keep their wording; everything else is a short sentence with a reference."""
    text = str(exc)
    if isinstance(exc, ValueError):
        if text.startswith(_PASS_THROUGH):
            return text, ""
        missing = _MISSING_DOC.match(text)
        if missing:
            return f"No document with the key '{missing.group(1)}'. Call list_documents for the keys.", ""
        if text.startswith("Profile"):
            return "That profile is not available.", ""
    reference = secrets.token_hex(4)
    return f"ReqBot could not complete that request (reference {reference}). The details are in the server's request log.", reference


def _model_names() -> list[str]:
    """The model names this server is configured with, longest first, so a name that contains another is replaced whole."""
    names = {audit_questions.MODEL}
    try:
        cfg = _config.load()
        names.update(str(getattr(cfg, k, "") or "") for k in ("embedding_model", "extraction_model", "enrichment_model", "rewrite_model", "synthesis_model"))
    except Exception:  # an unreadable config must not turn into an unscrubbed answer: the fixed names and keys still apply
        pass
    return sorted((n for n in names if n), key=len, reverse=True)


def scrub(value, names: list[str]):
    """A copy of a tool's answer without what names the server's models: the payload fields that carry them, a mismatch warning (rewritten whole), and the configured names
    wherever they appear in text (a draft question's note says which model wrote it). Everything else, the quotes and citations above all, is returned as it was."""
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if k in _MODEL_KEYS:
                continue
            if k == "warnings" and isinstance(v, list):
                out[k] = [_EMBEDDING_WARNING if isinstance(w, str) and "embedding model" in w else scrub(w, names) for w in v]
            else:
                out[k] = scrub(v, names)
        return out
    if isinstance(value, list):
        return [scrub(v, names) for v in value]
    if isinstance(value, str):
        for n in names:
            if n in value:
                value = value.replace(n, _MODEL_WORDS)
        return value
    return value


def public_status() -> dict:
    """get_status without the server's addresses, folders or model names: what is reachable and how much there is."""
    full = _stdio.get_status()
    qdrant = full.get("qdrant") or {}
    documents = full.get("processed_documents") or []
    return {
        "ollama": {"reachable": bool((full.get("ollama") or {}).get("reachable"))},
        "qdrant": {
            "reachable": bool(qdrant.get("reachable")),
            "collections": [{"name": c.get("name"), "points": c.get("points")} for c in qdrant.get("collections") or []],
        },
        "documents": {"count": len(documents), "requirements": sum(int(d.get("count") or 0) for d in documents)},
    }


def public_documents() -> dict:
    """list_documents with only the fields a caller needs (no folder paths)."""
    full = _stdio.list_documents()
    docs = [{k: d[k] for k in _LISTED_DOCUMENT_FIELDS if k in d} for d in full.get("docs") or []]
    return {**{k: v for k, v in full.items() if k != "docs"}, "docs": docs}


class _Door:
    """What the tools of one running door share: the call log, the cap on simultaneous calls, and the waiting limit."""

    def __init__(self, request_log: RequestLog, max_concurrent: int, wait_seconds: float = BUSY_WAIT_SECONDS):
        self.request_log = request_log
        self._slots = asyncio.Semaphore(max(1, max_concurrent))
        self._wait = wait_seconds

    @staticmethod
    def caller(ctx: Context) -> str:
        try:
            return str(ctx.request_context.request.scope.get(SCOPE_KEY) or "unknown")
        except Exception:  # not in an HTTP request (a test calling the tool directly)
            return "unknown"

    async def call(self, ctx: Context, tool: str, fn, **arguments):
        who = self.caller(ctx)
        started = time.monotonic()

        def took() -> int:
            return int((time.monotonic() - started) * 1000)

        try:
            try:
                await asyncio.wait_for(self._slots.acquire(), self._wait)
            except asyncio.TimeoutError:
                raise _Busy from None
            try:
                result = await anyio.to_thread.run_sync(functools.partial(fn, **arguments))
            finally:
                self._slots.release()
        except _Busy:
            self.request_log.record(code=who, tool=tool, arguments=arguments, ok=False, ms=took(), error="busy: no free slot")
            raise RuntimeError(BUSY_MESSAGE) from None
        except Exception as exc:
            message, reference = client_message(exc)
            self.request_log.record(code=who, tool=tool, arguments=arguments, ok=False, ms=took(), error=f"{type(exc).__name__}: {exc}", reference=reference)
            raise RuntimeError(message) from None
        self.request_log.record(code=who, tool=tool, arguments=arguments, ok=True, ms=took())
        return scrub(result, _model_names())


def _describe(fn) -> str:
    return " ".join((fn.__doc__ or "").split())


def _register(server: FastMCP, door: _Door) -> None:
    """The seven tools, each a thin async call into the stdio implementation. The signatures match mcp_server/server.py (a test compares them), less `synthesize` and plus the context."""

    @server.tool(name="get_status", description="Report whether ReqBot's search index and model service are reachable, and how many documents and requirements it holds.")
    async def get_status(*, ctx: Context) -> dict:
        return await door.call(ctx, "get_status", public_status)

    @server.tool(name="list_documents", description=_describe(_stdio.list_documents))
    async def list_documents(*, ctx: Context) -> dict:
        return await door.call(ctx, "list_documents", public_documents)

    @server.tool(name="search_requirements", description=_describe(_stdio.search_requirements))
    async def search_requirements(
        question: str,
        top_k: int = 20,
        document_ids: list[str] | None = None,
        domain_tags: list[str] | None = None,
        requirement_types: list[str] | None = None,
        context: bool = False,
        *,
        ctx: Context,
    ) -> dict:
        return await door.call(
            ctx, "search_requirements", _stdio.search_requirements,
            question=question, top_k=top_k, document_ids=document_ids, domain_tags=domain_tags,
            requirement_types=requirement_types, context=context,
        )

    @server.tool(name="trace_requirement", description=_describe(_stdio.trace_requirement))
    async def trace_requirement(requirement_id: str, include_context: bool = False, *, ctx: Context) -> dict:
        return await door.call(ctx, "trace_requirement", _stdio.trace_requirement, requirement_id=requirement_id, include_context=include_context)

    @server.tool(name="compare_documents", description=_describe(_stdio.compare_documents))
    async def compare_documents(doc_id_1: str, doc_id_2: str, topic: str, top_k: int = 10, *, ctx: Context) -> dict:
        return await door.call(ctx, "compare_documents", _stdio.compare_documents, doc_id_1=doc_id_1, doc_id_2=doc_id_2, topic=topic, top_k=top_k)

    @server.tool(
        name="map_evidence",
        description=(
            "Build a compliance evidence pack for a topic, grouped by control ID (source_ref): each group carries its representative requirement and all matching sources. "
            "Retrieval only: no written summary is produced here; use the returned quotes. document_ids accepts a doc_key (\"afi17-101\") or a source PDF name "
            "(\"afi17-101.pdf\") from list_documents; an unknown value is an error that names it."
        ),
    )
    async def map_evidence(
        topic: str,
        document_ids: list[str] | None = None,
        domain_tags: list[str] | None = None,
        requirement_types: list[str] | None = None,
        top_k: int = 10,
        *,
        ctx: Context,
    ) -> dict:
        return await door.call(
            ctx, "map_evidence", _stdio.map_evidence,
            topic=topic, document_ids=document_ids, domain_tags=domain_tags, requirement_types=requirement_types, synthesize=False, top_k=top_k,
        )

    @server.tool(name="generate_checklist", description=_describe(_stdio.generate_checklist))
    async def generate_checklist(doc_key: str, profile: str = "cybersecurity", *, ctx: Context) -> dict:
        return await door.call(ctx, "generate_checklist", _stdio.generate_checklist, doc_key=doc_key, profile=profile)


class _CodeAuth:
    """Pure ASGI middleware: no valid access code, no answer. The check runs on every request and the name of the code travels in the request's scope for the log."""

    def __init__(self, app, verify=mcp_codes.verify, request_log: RequestLog | None = None, failed_delay: float = FAILED_CODE_DELAY_SECONDS):
        self.app = app
        self._verify = verify
        self._log = request_log
        self._delay = failed_delay

    async def __call__(self, scope, receive, send):
        if scope["type"] == "lifespan":
            await self.app(scope, receive, send)
            return
        name = None
        if scope["type"] == "http":
            header = ""
            for key, value in scope.get("headers") or []:
                if key == b"authorization":
                    header = value.decode("latin-1")
                    break
            scheme, _, token = header.partition(" ")
            if scheme.lower() == "bearer":
                name = self._verify(token.strip())
        if name is None:
            client = (scope.get("client") or ("?", 0))[0]
            log.warning("MCP request refused: no valid access code (from %s)", client)
            if self._log is not None:
                self._log.record(code="-", tool="(sign-in)", arguments={"client": client}, ok=False, error="no valid access code")
            await asyncio.sleep(self._delay)  # a wrong guess costs a second; the codes are long random strings anyway
            if scope["type"] == "http":
                response = JSONResponse({"error": "unauthorized"}, status_code=401, headers={"WWW-Authenticate": "Bearer"})
                await response(scope, receive, send)
            return
        scope[SCOPE_KEY] = name
        await self.app(scope, receive, send)


def _security(host: str, allowed_hosts: list[str] | None) -> TransportSecuritySettings | None:
    """Host-header protection. Given names are allowed (with any port) beside the loopback ones; with none given, a loopback bind keeps the SDK's own default and any other
    bind relies on the access codes alone."""
    if allowed_hosts:
        names = [h.strip() for h in allowed_hosts if h and h.strip()] + ["127.0.0.1", "localhost"]
        hosts = sorted({v for n in names for v in (n, f"{n}:*")} | {"[::1]:*"})
        return TransportSecuritySettings(enable_dns_rebinding_protection=True, allowed_hosts=hosts, allowed_origins=[])
    if host in LOOPBACK_HOSTS:
        return None
    return TransportSecuritySettings(enable_dns_rebinding_protection=False)


def _max_concurrent() -> int:
    try:
        return min(32, max(1, int(os.environ.get(ENV_MAX_CONCURRENT, DEFAULT_MAX_CONCURRENT))))
    except ValueError:
        return DEFAULT_MAX_CONCURRENT


def _default_log_path() -> Path:
    env = (os.environ.get(ENV_LOG_PATH) or "").strip()
    if env:
        return Path(env)
    return Path(_config.load().processed_dir_path()) / ".mcp" / "requests.jsonl"


def build_app(
    *,
    host: str = "127.0.0.1",
    port: int = DEFAULT_PORT,
    allowed_hosts: list[str] | None = None,
    request_log: RequestLog | None = None,
    max_concurrent: int | None = None,
    verify=None,
    busy_wait_seconds: float = BUSY_WAIT_SECONDS,
    failed_code_delay: float = FAILED_CODE_DELAY_SECONDS,
):
    """The ASGI app of the door (endpoint /mcp). Stateless JSON over HTTP: a request stands alone, nothing is kept between requests."""
    request_log = request_log or RequestLog(_default_log_path())
    server = FastMCP(
        "reqbot",
        host=host,
        port=port,
        stateless_http=True,
        json_response=True,
        transport_security=_security(host, allowed_hosts),
    )
    _register(server, _Door(request_log, max_concurrent or _max_concurrent(), busy_wait_seconds))
    app = server.streamable_http_app()
    app.add_middleware(_CodeAuth, verify=verify or mcp_codes.verify, request_log=request_log, failed_delay=failed_code_delay)
    return app


def run(host: str = "127.0.0.1", port: int = DEFAULT_PORT, allowed_hosts: list[str] | None = None) -> int:
    """Serve the door until stopped. Refuses to start with no access code at all."""
    import uvicorn

    if mcp_codes.count() == 0:
        log.error("No access code exists, so nobody could connect. Create one first: reqbot mcp-code add NAME")
        return 1
    for name in mcp_codes.rejected_from_environment():
        log.warning("Ignored the code '%s' in %s: it needs a plain name and at least %d characters", name, mcp_codes.ENV_CODES, mcp_codes.MIN_ENV_CODE_LENGTH)
    app = build_app(host=host, port=port, allowed_hosts=allowed_hosts)
    if host not in LOOPBACK_HOSTS:
        log.warning("The door listens on %s:%s over plain HTTP. Put a proxy that terminates TLS in front of it before it leaves a trusted network (docs/DEPLOYMENT.md).", host, port)
    log.info("ReqBot MCP door on http://%s:%s/mcp (%d access code(s)); request log: %s", host, port, mcp_codes.count(), _default_log_path())
    uvicorn.run(app, host=host, port=port, log_level="info")
    return 0
