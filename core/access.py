"""The admin access code: who may start jobs (docs/WEB_UI_PARITY_PLAN.md, section 3, item 3).

ReqBot has no accounts. Until a customer's own sign-in layer is wired in, one secret code stands in for "this request is from the admin". It is created on the server with
`reqbot token` (or supplied by the environment variable REQBOT_ADMIN_TOKEN, for a container) and kept in its own file, never in config.json, so `GET /api/config` and
Settings cannot reveal it. Nothing here logs or returns the code, and comparison is in constant time.

Three modes, from `admin_mode()`:
  unconfigured  no code and not open: every admin route refuses (403) and the API behaves exactly as it did.
  code          a code is set: an admin request must present it.
  open          the operator said "this is a trusted network" (`reqbot token --open`, or REQBOT_ADMIN_OPEN=1): no code is asked for. Off unless asked for, and only the
                operator of the server can turn it on: there is no route for it, and Settings (a browser editing config.json) does not see this file.
"""
import hmac
import json
import os
import secrets
from pathlib import Path

ACCESS_PATH = Path.home() / ".config" / "reqbot" / "access.json"
ENV_ADMIN_TOKEN = "REQBOT_ADMIN_TOKEN"
ENV_ADMIN_OPEN = "REQBOT_ADMIN_OPEN"
FAILED_ATTEMPT_DELAY_SECONDS = 1.0


def _read() -> dict:
    try:
        data = json.loads(ACCESS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _write(data: dict) -> None:
    ACCESS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = ACCESS_PATH.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.replace(tmp, ACCESS_PATH)


def is_open() -> bool:
    """Trusted-network mode: set by the environment variable or by `reqbot token --open`."""
    env = (os.environ.get(ENV_ADMIN_OPEN) or "").strip().lower()
    if env in ("1", "true", "yes", "on"):
        return True
    return _read().get("open") is True


def admin_mode() -> str:
    """"open", "code" or "unconfigured" (see the module note). Never the code itself."""
    if is_open():
        return "open"
    return "code" if admin_token() else "unconfigured"


def set_open(flag: bool) -> None:
    """Turn trusted-network mode on or off in the access file (the code, if any, is kept)."""
    data = _read()
    data["open"] = bool(flag)
    _write(data)


def admin_token() -> str | None:
    """The configured admin code: the environment variable wins over the file; None when neither is set."""
    env = (os.environ.get(ENV_ADMIN_TOKEN) or "").strip()
    if env:
        return env
    value = _read().get("admin")
    return value.strip() if isinstance(value, str) and value.strip() else None


def source() -> str:
    """Where the code comes from: "environment", "file" or "none". For `reqbot token`'s message; never the code itself."""
    if (os.environ.get(ENV_ADMIN_TOKEN) or "").strip():
        return "environment"
    return "file" if admin_token() else "none"


def create_admin_token(rotate: bool = False) -> tuple[str, bool]:
    """(code, created). Keeps the code in the file when there is one unless `rotate`; writes a new random code with the file readable by its owner only."""
    data = _read()
    existing = data.get("admin")
    if isinstance(existing, str) and existing.strip() and not rotate:
        return existing.strip(), False
    token = secrets.token_urlsafe(32)
    _write({**data, "admin": token})
    return token, True


def check_admin(presented: str | None) -> str:
    """"ok", "not-configured" (no code is set, so no one is admin), "missing" (none presented) or "wrong". In open mode every request is "ok"."""
    if is_open():
        return "ok"
    expected = admin_token()
    if not expected:
        return "not-configured"
    if not presented:
        return "missing"
    return "ok" if hmac.compare_digest(presented.encode("utf-8"), expected.encode("utf-8")) else "wrong"
