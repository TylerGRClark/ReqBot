"""A plain record of what the network door was asked: one JSON line per tool call.

Each line says when, which access code (by name, never the code), which tool, a shortened copy of the arguments, whether it worked and how long it took. A failed call also
carries the real error text, which is kept here and never sent to the caller (an error message can name an internal address or a folder). The file is private to its owner,
and rotates once at 5 MB (the last file is kept as requests.jsonl.1). Writing it never fails a request.
"""
import json
import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)

MAX_BYTES = 5 * 1024 * 1024
TEXT_LIMIT = 200
LIST_LIMIT = 10


def _short(value):
    if isinstance(value, str):
        return value if len(value) <= TEXT_LIMIT else value[:TEXT_LIMIT] + "…"
    if isinstance(value, (list, tuple)):
        items = [_short(v) for v in value[:LIST_LIMIT]]
        return items + ["…"] if len(value) > LIST_LIMIT else items
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return type(value).__name__


def summarize_arguments(arguments: dict) -> dict:
    """The arguments of a call as the log keeps them: long text and long lists cut short."""
    return {str(k): _short(v) for k, v in (arguments or {}).items()}


class RequestLog:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self._lock = threading.Lock()
        self._warned = False

    def record(self, *, code: str, tool: str, arguments: dict | None = None, ok: bool, ms: int = 0, error: str = "", reference: str = "") -> None:
        entry = {
            "time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            "code": code,
            "tool": tool,
            "arguments": summarize_arguments(arguments or {}),
            "ok": bool(ok),
            "ms": int(ms),
        }
        if error:
            entry["error"] = error[:500]
        if reference:
            entry["reference"] = reference
        try:
            with self._lock:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                try:
                    if self.path.stat().st_size > MAX_BYTES:
                        os.replace(self.path, self.path.with_name(self.path.name + ".1"))
                except FileNotFoundError:
                    pass
                fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
                try:
                    if hasattr(os, "fchmod"):
                        os.fchmod(fd, 0o600)  # a file that already existed keeps its old mode otherwise (REQBOT_MCP_LOG may point at one)
                except OSError:
                    os.close(fd)
                    raise  # cannot make it private: do not write questions into it
                with os.fdopen(fd, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError as exc:
            if not self._warned:  # once: a full disk must not flood the console or fail a search
                self._warned = True
                log.warning("Could not write the MCP request log %s: %s", self.path, exc)
