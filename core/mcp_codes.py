"""Access codes for the network MCP door (docs/WEB_UI_PARITY_PLAN.md, section 4).

The network door lets an AI tool on another machine search the library over HTTP. Each connected tool gets its own named code, so one can be cut off without touching the
others, and the request log says which code asked what. These codes are not the admin code (core/access.py): they live in their own file, open no admin route, and a leaked
one can only read what the read-only tools return.

Only a SHA-256 hash of a code is stored, so the file cannot be read back into a working code; the code is shown once, when it is created. Codes can also be supplied by the
environment variable REQBOT_MCP_CODES ("name=code,name2=code2"), for a container with no persistent config folder. Comparison is in constant time. Nothing here logs a code.
"""
import hashlib
import hmac
import json
import os
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path

CODES_PATH = Path.home() / ".config" / "reqbot" / "mcp_codes.json"
ENV_CODES = "REQBOT_MCP_CODES"
CODE_PREFIX = "rbmcp_"
MIN_ENV_CODE_LENGTH = 24  # a code in the environment is chosen by a person: refuse a short one
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,39}$")


def _hash(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def _read() -> list[dict]:
    try:
        data = json.loads(CODES_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    entries = data.get("codes") if isinstance(data, dict) else None
    out = []
    for e in entries if isinstance(entries, list) else []:
        if isinstance(e, dict) and isinstance(e.get("name"), str) and isinstance(e.get("hash"), str):
            out.append({"name": e["name"], "hash": e["hash"], "created": str(e.get("created") or "")})
    return out


def _write(entries: list[dict]) -> None:
    CODES_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = CODES_PATH.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    if hasattr(os, "fchmod"):
        os.fchmod(fd, 0o600)  # a leftover .tmp file keeps its old mode otherwise
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump({"codes": entries}, f)
    os.replace(tmp, CODES_PATH)


def _from_environment() -> tuple[list[dict], list[str]]:
    """(entries, rejected names): the usable "name=code" pairs of REQBOT_MCP_CODES, and the names of the ones refused (a bad name or a code that is too short)."""
    entries, rejected = [], []
    for part in (os.environ.get(ENV_CODES) or "").split(","):
        name, _, code = part.strip().partition("=")
        name, code = name.strip(), code.strip()
        if not name and not code:
            continue
        if _NAME.match(name) and len(code) >= MIN_ENV_CODE_LENGTH:
            entries.append({"name": name, "hash": _hash(code), "created": ""})
        else:
            rejected.append(name or "?")
    return entries, rejected


def valid_name(name: str) -> bool:
    return bool(_NAME.match(name or ""))


def listing() -> list[dict]:
    """[{name, created, source}] for every usable code, source "file" or "environment". Never the code or its hash."""
    env, _ = _from_environment()
    rows = [{"name": e["name"], "created": e["created"], "source": "file"} for e in _read()]
    rows += [{"name": e["name"], "created": "", "source": "environment"} for e in env]
    return sorted(rows, key=lambda r: r["name"].lower())


def rejected_from_environment() -> list[str]:
    return _from_environment()[1]


def count() -> int:
    return len(listing())


def add(name: str) -> str:
    """Create a code for a connected tool and return it. This is the only time it exists in readable form. ValueError when the name is not usable or already taken."""
    if not valid_name(name):
        raise ValueError("A name is letters, digits, dots, dashes and underscores (up to 40 characters), starting with a letter or digit.")
    if any(r["name"].lower() == name.lower() for r in listing()):
        raise ValueError(f"A code named '{name}' already exists. Revoke it first, or pick another name.")
    code = CODE_PREFIX + secrets.token_urlsafe(32)
    entries = _read()
    entries.append({"name": name, "hash": _hash(code), "created": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")})
    _write(entries)
    return code


def revoke(name: str) -> bool:
    """Remove the saved code with this name; True when there was one. ValueError when the name belongs to a code supplied by the environment (remove it there)."""
    entries = _read()
    kept = [e for e in entries if e["name"].lower() != (name or "").lower()]
    if len(kept) != len(entries):
        _write(kept)
        return True
    if any(e["name"].lower() == (name or "").lower() for e in _from_environment()[0]):
        raise ValueError(f"'{name}' comes from the environment variable {ENV_CODES}; remove it there and restart the server.")
    return False


def verify(presented: str | None) -> str | None:
    """The name of the code that was presented, or None. The file is read on every call, so a revoked code stops working at once. Constant-time on every stored code."""
    if not presented:
        return None
    digest = _hash(presented.strip()).encode("ascii")
    match = None
    for e in _read() + _from_environment()[0]:
        if hmac.compare_digest(digest, e["hash"].encode("ascii", "replace")):
            match = e["name"]
    return match
