"""
HTTPS enforcement and security response headers.
"""

from fastapi import Request
from fastapi.responses import RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
from security.settings import HTTPS_ONLY


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Adds browser security headers to every response, and with HTTPS_ONLY=true
    redirects plain-HTTP requests to HTTPS and sends HSTS.
    """

    async def dispatch(self, request: Request, call_next):
        # Behind a reverse proxy (nginx, Render, ...) the original scheme is in X-Forwarded-Proto
        scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
        if HTTPS_ONLY and scheme == "http":
            return RedirectResponse(str(request.url.replace(scheme="https")), status_code=308)

        response = await call_next(request)
        headers = response.headers
        # Don't guess file types: an uploaded file is only ever used as its declared type
        headers.setdefault("X-Content-Type-Options", "nosniff")
        # This API must never be shown inside a frame on another site (clickjacking)
        headers.setdefault("X-Frame-Options", "DENY")
        # API responses (JSON, images) never need to run scripts or load anything.
        # /docs and /redoc are HTML pages that load Swagger from a CDN, so they're skipped.
        if not request.url.path.startswith(("/docs", "/redoc")):
            headers.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
        headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        # Images are loaded by the Angular app on another port (localhost:4200)
        headers.setdefault("Cross-Origin-Resource-Policy", "same-site")
        if HTTPS_ONLY:
            # Browsers remember for a year to only use HTTPS for this site
            headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response
