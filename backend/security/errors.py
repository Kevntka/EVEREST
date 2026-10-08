"""
Unexpected errors -> a short JSON 500.

Without this, an unhandled exception reaches Starlette's outermost error handler, which
answers with plain-text "Internal Server Error" and no CORS headers, so the browser
hides the response and the frontend only sees "status 0". This middleware is added
first (innermost), so its JSON answer still passes through CORS and the security
headers. The traceback is printed in the server log only, never sent to the client.
"""

import traceback
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

SERVER_ERROR = "Something went wrong on our side. Please try again."


class ServerErrorMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except Exception:
            print(f"❌ Unhandled error on {request.method} {request.url.path}")
            traceback.print_exc()
            return JSONResponse(status_code=500, content={"detail": SERVER_ERROR})
