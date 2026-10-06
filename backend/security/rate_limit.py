"""
Rate limiting (in memory).

- rate_limit(...) is a FastAPI dependency for sensitive endpoints (login, register,
  forgot password, ...): at most `limit` requests per `seconds` from one IP address.
- LoginLockout locks an email for a while after too many wrong passwords, which stops
  password guessing even when the attacker spreads requests over many IPs.
- RateLimitMiddleware is a generous overall cap per IP for every API request.

Counters live in this process's memory: they reset when the server restarts and are
not shared between several server processes. That is fine for one uvicorn process;
a multi-server deployment would keep them in Redis instead.
"""

import time
import threading
from collections import defaultdict, deque
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


class SlidingWindow:
    """Remembers request times per key and answers 'is this key over the limit?'"""

    def __init__(self):
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: str, limit: int, seconds: int) -> int:
        """Record a request. Returns 0 if allowed, else the seconds to wait."""
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] <= now - seconds:
                hits.popleft()
            if len(hits) >= limit:
                return int(hits[0] + seconds - now) + 1
            hits.append(now)
            return 0

    def clear(self, key: str) -> None:
        with self._lock:
            self._hits.pop(key, None)


_windows = SlidingWindow()


def too_many_requests(wait: int) -> HTTPException:
    return HTTPException(
        status_code=429,
        detail=f"Too many requests. Please wait {wait} seconds and try again.",
        headers={"Retry-After": str(wait)},
    )


def rate_limit(name: str, limit: int, seconds: int):
    """Dependency: Depends(rate_limit("login", 10, 60)) = 10 requests a minute per IP."""
    def check(request: Request) -> None:
        wait = _windows.hit(f"{name}:{client_ip(request)}", limit, seconds)
        if wait:
            raise too_many_requests(wait)
    return check


class LoginLockout:
    """MAX_FAILURES wrong passwords for one email within WINDOW locks it for WINDOW."""

    MAX_FAILURES = 5
    WINDOW = 15 * 60  # seconds

    def __init__(self):
        self._failures = SlidingWindow()
        self._locked_until: dict[str, float] = {}
        self._lock = threading.Lock()

    def check(self, email: str) -> None:
        with self._lock:
            until = self._locked_until.get(email, 0)
        wait = int(until - time.monotonic()) + 1
        if until and wait > 0:
            minutes = max(1, round(wait / 60))
            raise HTTPException(
                status_code=429,
                detail=f"Too many failed login attempts. Try again in {minutes} minute(s), or use Forgot Password.",
                headers={"Retry-After": str(wait)},
            )

    def failed(self, email: str) -> None:
        if self._failures.hit(email, self.MAX_FAILURES - 1, self.WINDOW):
            with self._lock:
                self._locked_until[email] = time.monotonic() + self.WINDOW
            self._failures.clear(email)

    def succeeded(self, email: str) -> None:
        self._failures.clear(email)
        with self._lock:
            self._locked_until.pop(email, None)


login_lockout = LoginLockout()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Overall cap per IP on /api requests (the event pages poll every 10 seconds)."""

    def __init__(self, app, limit: int = 600, seconds: int = 60):
        super().__init__(app)
        self.limit, self.seconds = limit, seconds

    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/api") and request.method != "OPTIONS":
            wait = _windows.hit(f"global:{client_ip(request)}", self.limit, self.seconds)
            if wait:
                return JSONResponse(
                    status_code=429,
                    content={"detail": f"Too many requests. Please wait {wait} seconds and try again."},
                    headers={"Retry-After": str(wait)},
                )
        return await call_next(request)
