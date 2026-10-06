"""
CSRF protection: signed double-submit cookie plus an Origin check.

CSRF (cross-site request forgery) is another website making the user's browser send a
request to this API. The browser would attach the login cookie automatically, so the
request would run as the user. Two checks stop that, for every POST/PUT/PATCH/DELETE:

1. Origin check: browsers send an Origin header naming the site that made the request.
   It must be one of ALLOWED_ORIGINS (the Angular app).
2. Double-submit token: GET /api/csrf-token sets a `csrf_token` cookie and returns the
   same value in the body. The Angular app sends it back in the X-CSRF-Token header.
   Another site can't read the body (CORS blocks it) and can't set custom headers on a
   cross-site request, so it can't produce a matching header. The token is signed with
   JWT_SECRET_KEY, so a cookie planted by someone else is rejected too.
"""

import hashlib
import hmac
import secrets
from fastapi import Request
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware
from security.settings import ALLOWED_ORIGINS, HTTPS_ONLY, JWT_SECRET_KEY

CSRF_COOKIE_NAME = "csrf_token"
CSRF_HEADER_NAME = "X-CSRF-Token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}


def _signature(nonce: str) -> str:
    return hmac.new(JWT_SECRET_KEY.encode(), nonce.encode(), hashlib.sha256).hexdigest()


def generate_csrf_token() -> str:
    nonce = secrets.token_urlsafe(32)
    return f"{nonce}.{_signature(nonce)}"


def is_valid_token(token: str | None) -> bool:
    if not token or "." not in token:
        return False
    nonce, signature = token.rsplit(".", 1)
    return hmac.compare_digest(signature.encode(), _signature(nonce).encode())


def set_csrf_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=token,
        httponly=True,  # the app reads the token from the response body, not the cookie
        secure=HTTPS_ONLY,
        samesite="strict",
        max_age=60 * 60 * 24,
        path="/",
    )


def csrf_token_response(request: Request) -> JSONResponse:
    """Body of GET /api/csrf-token: reuse the cookie's token if it is still valid."""
    token = request.cookies.get(CSRF_COOKIE_NAME)
    if not is_valid_token(token):
        token = generate_csrf_token()
    response = JSONResponse({"csrf_token": token})
    set_csrf_cookie(response, token)  # also refreshes the expiry
    return response


def _forbidden(detail: str) -> JSONResponse:
    return JSONResponse(status_code=403, content={"detail": detail, "csrf_failed": True})


class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method in SAFE_METHODS or not request.url.path.startswith("/api"):
            return await call_next(request)

        origin = request.headers.get("origin")
        if origin and origin.rstrip("/") not in ALLOWED_ORIGINS:
            return _forbidden("Request blocked: it did not come from the EVEREST website.")

        cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
        header_token = request.headers.get(CSRF_HEADER_NAME)
        if not (is_valid_token(cookie_token) and header_token
                and hmac.compare_digest(cookie_token.encode(), header_token.encode())):
            return _forbidden("Security check failed (CSRF token). Please refresh the page and try again.")

        return await call_next(request)
