"""
Cap on how many API requests use the database at the same time.

Why: a request uses one pooled connection from its first query until get_db closes the
session, but it hops between FastAPI's worker threads (40 by default) on the way:
current_user runs in one thread, the route in another. Between hops it holds its
connection without holding a thread. Under load (found at ~250 users) every thread could
end up waiting for a connection while the connections were held by requests waiting for
a thread: a deadlock that ended in 30-second pool timeouts and HTTP 500s.

With at most MAX_DB_REQUESTS in flight (fewer than the pool's connections and no more
than the worker threads), a request never waits for a connection inside a thread. Extra
requests wait here, on the event loop, which costs neither a thread nor a connection.
"""

import asyncio

from database.config import MAX_DB_REQUESTS


class DatabaseConcurrencyLimit:
    """Pure ASGI middleware (cheaper than BaseHTTPMiddleware) for /api requests."""

    def __init__(self, app, limit: int = MAX_DB_REQUESTS):
        self.app = app
        self.limit = limit
        self._semaphore: asyncio.Semaphore | None = None  # created inside the running loop

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope["path"].startswith("/api"):
            await self.app(scope, receive, send)
            return
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self.limit)
        async with self._semaphore:
            await self.app(scope, receive, send)
