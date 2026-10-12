"""Which way admin actions are protected here, so a screen knows whether to ask for a code. Public on purpose; it never returns the code."""
from fastapi import APIRouter

from core import access

router = APIRouter()


@router.get("/access")
def get_access() -> dict:
    """`{"admin": "unconfigured" | "code" | "open"}`: no admin actions are possible, a code is needed, or none is needed (trusted-network mode)."""
    return {"admin": access.admin_mode()}
