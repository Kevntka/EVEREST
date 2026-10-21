"""
HTTP client for the API, acting like the Angular app does:
- every request carries Origin: http://localhost:4200,
- unsafe methods carry the X-CSRF-Token from GET /api/csrf-token (and its cookie),
- the login cookie (access_token) is kept in the client's cookie jar.
"""

import time

import httpx

from .config import ORIGIN, RECAPTCHA_TEST_TOKEN

UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}


class ApiClient:
    def __init__(self, base_url: str, *, csrf: bool = True, origin: str | None = ORIGIN):
        headers = {"Origin": origin} if origin else {}
        self.http = httpx.Client(base_url=base_url, headers=headers, timeout=30)
        self.auto_csrf = csrf
        self._csrf_token: str | None = None
        self.user: dict | None = None

    # --- plumbing
    def csrf_token(self) -> str:
        if not self._csrf_token:
            self._csrf_token = self.http.get("/api/csrf-token").json()["csrf_token"]
        return self._csrf_token

    def request(self, method: str, path: str, **kwargs) -> httpx.Response:
        headers = dict(kwargs.pop("headers", {}) or {})
        if self.auto_csrf and method.upper() in UNSAFE and "X-CSRF-Token" not in headers:
            headers["X-CSRF-Token"] = self.csrf_token()
        return self.http.request(method, path, headers=headers, **kwargs)

    def request_waiting(self, method: str, path: str, **kwargs) -> httpx.Response:
        """Like request(), but waits out a per-IP rate limit (429) and retries once it resets."""
        while True:
            response = self.request(method, path, **kwargs)
            if response.status_code != 429 or "failed login" in response.text:
                return response
            time.sleep(int(response.headers.get("Retry-After", "5")) + 1)

    def get(self, path, **kw): return self.request("GET", path, **kw)
    def post(self, path, **kw): return self.request("POST", path, **kw)
    def put(self, path, **kw): return self.request("PUT", path, **kw)
    def delete(self, path, **kw): return self.request("DELETE", path, **kw)

    # --- app actions
    def login(self, email: str, password: str, *, recaptcha: str | None = RECAPTCHA_TEST_TOKEN,
              wait_if_rate_limited: bool = True) -> httpx.Response:
        """POST /api/login. Setup logins wait out the per-IP login limit (20/min) instead
        of failing; tests that check the limit itself pass wait_if_rate_limited=False."""
        data = {"email": email, "password": password}
        if recaptcha is not None:
            data["recaptcha_token"] = recaptcha
        while True:
            response = self.post("/api/login", data=data)
            if response.status_code == 429 and wait_if_rate_limited and "failed login" not in response.text:
                time.sleep(int(response.headers.get("Retry-After", "5")) + 1)
                continue
            return response

    def login_as(self, user: dict) -> "ApiClient":
        response = self.login(user["email"], user["password"])
        assert response.status_code == 200, f"login as {user['email']} failed: {response.status_code} {response.text}"
        self.user = user
        return self

    def cookie(self, name: str) -> str | None:
        return self.http.cookies.get(name)

    def close(self) -> None:
        self.http.close()


def event_form(**overrides) -> dict:
    """Valid Create Event form fields (multipart/form-data, like the organizer form)."""
    from datetime import date, timedelta
    event_day = date.today() + timedelta(days=14)
    data = {
        "event_name": "Pytest Seminar",
        "event_description": "An event created by the API tests",
        "event_date": event_day.isoformat(),
        "event_time": "09:00",
        "event_end_time": "11:00",
        "venue": "Main Hall",
        "capacity": "5",
        "department": "Information Technology",
        "about_event": "About text",
        "registration_start": date.today().isoformat(),
        "registration_end": event_day.isoformat(),
    }
    data.update(overrides)
    return {k: v for k, v in data.items() if v is not None}
