import logging
import secrets
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from backend.config import settings
from backend.middleware.access_key import COOKIE_NAME, session_token

logger = logging.getLogger(__name__)
router = APIRouter()

_LOGIN_HTML = Path(__file__).parent.parent.parent / "frontend" / "login.html"
_COOKIE_MAX_AGE = 60 * 60 * 12  # 12 hours


def _safe_next(next_path: str) -> str:
    """Only redirect to local paths — blocks open-redirect to other sites."""
    if next_path and next_path.startswith("/") and not next_path.startswith("//"):
        return next_path
    return "/app"


@router.get("/login", response_class=HTMLResponse)
async def login_page():
    if _LOGIN_HTML.exists():
        return _LOGIN_HTML.read_text()
    return "<h1>Login page not found</h1>"


@router.post("/login")
async def login_submit(
    access_code: str = Form(""),
    next_path: str = Form("/app", alias="next"),
):
    target = _safe_next(next_path)
    if settings.access_key and secrets.compare_digest(access_code, settings.access_key):
        response = RedirectResponse(url=target, status_code=303)
        response.set_cookie(
            COOKIE_NAME,
            session_token(),
            max_age=_COOKIE_MAX_AGE,
            httponly=True,
            samesite="lax",
            path="/",
        )
        return response
    logger.warning("Failed login attempt")
    return RedirectResponse(
        url=f"/login?error=1&next={quote(target, safe='')}", status_code=303
    )


@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(COOKIE_NAME, path="/")
    return response
