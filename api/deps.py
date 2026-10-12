"""Shared request checks for the API routes."""
import time

from fastapi import HTTPException, Request

from core import access


def _presented_code(request: Request) -> str | None:
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip() or None
    return (request.headers.get("x-reqbot-token") or "").strip() or None


def require_admin(request: Request) -> None:
    """Admin routes: refuse unless the request carries the configured admin code.

    No code configured -> 403 (the API stays read-only, as before). A missing or wrong code -> 401, after a short delay on a wrong one."""
    result = access.check_admin(_presented_code(request))
    if result == "ok":
        return
    if result == "not-configured":
        raise HTTPException(status_code=403, detail="No admin access code is configured on this server. Run `reqbot token` on the server to create one.")
    if result == "wrong":
        time.sleep(access.FAILED_ATTEMPT_DELAY_SECONDS)
    raise HTTPException(
        status_code=401,
        detail="An admin access code is required." if result == "missing" else "The admin access code is not correct.",
        headers={"WWW-Authenticate": "Bearer"},
    )
