"""
Load test for the EVEREST API (Locust).

Run it through tests/performance/run_load_test.py, which starts a backend on the TEST
database, seeds accounts and events, and runs this file headless with a step-by-step ramp.
Never point it at a backend that uses real data.

User mix (what the app's pages do):
- AttendeeUser (most traffic): signs in, then polls GET /api/events like the Student
  Dashboard's 10-second auto-refresh, opens event details, checks My Events, and enrolls.
- OrganizerUser: Organizer Dashboard stats and their events.

Signing in (LOGIN_MODE):
- "password": POST /api/login like the browser. Every simulated user comes from this one
  machine, so the per-IP login limit (100/min) caps how fast users can sign in.
- "token": each user gets a login cookie signed with the TEST backend's random JWT secret,
  with the same claims /api/login puts in it (user_id, role, pwd fingerprint, unique jti).
  The backend checks it exactly like a real login cookie. This measures the load of many
  signed-in users without waiting on the per-IP login limit; login itself is still
  exercised by LoginUser (a few users that keep logging in at a realistic rate).

Limits that still apply per IP: requests without a login cookie (csrf-token before login,
login) share 600/min. 429 responses are counted as failures named "429 rate limited", so
they're visible in the results, not hidden.
"""

import json
import os
import random
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from locust import HttpUser, LoadTestShape, between, events, task

ORIGIN = "http://localhost:4200"
ACCOUNTS = json.loads(os.environ.get("EVEREST_LOAD_ACCOUNTS", '{"attendees": [], "organizers": []}'))
EVENT_IDS = json.loads(os.environ.get("EVEREST_LOAD_EVENT_IDS", "[]"))
PASSWORD = os.environ.get("EVEREST_LOAD_PASSWORD", "")
LOGIN_MODE = os.environ.get("LOGIN_MODE", "password")
JWT_SECRET = os.environ.get("EVEREST_LOAD_JWT_SECRET", "")


def _check(r, ok=(200,)):
    if r.status_code == 429:
        r.failure("429 rate limited")
    elif r.status_code in ok:
        r.success()
    else:
        r.failure(f"HTTP {r.status_code}")


class EverestUser(HttpUser):
    abstract = True
    kind = "attendees"

    def on_start(self):
        self.client.headers["Origin"] = ORIGIN
        self.account = random.choice(ACCOUNTS[self.kind])
        if LOGIN_MODE == "token":
            now = datetime.now(timezone.utc)
            token = jwt.encode({
                "sub": self.account["email"], "user_id": self.account["id"], "email": self.account["email"],
                "role": self.account["role"], "pwd": self.account["pwd"], "jti": uuid.uuid4().hex,
                "iat": now, "exp": now + timedelta(hours=2),
            }, JWT_SECRET, algorithm="HS256")
            self.client.cookies.set("access_token", f"Bearer {token}")
        with self.client.get("/api/csrf-token", name="/api/csrf-token", catch_response=True) as r:
            _check(r)
            if r.status_code == 200:
                self.client.headers["X-CSRF-Token"] = r.json()["csrf_token"]
        if LOGIN_MODE != "token":
            self.login()

    def login(self):
        with self.client.post("/api/login", name="/api/login", catch_response=True, data={
                "email": self.account["email"], "password": PASSWORD, "recaptcha_token": "load-test"}) as r:
            _check(r)

    def _get(self, path, name):
        with self.client.get(path, name=name, catch_response=True) as r:
            _check(r)


class AttendeeUser(EverestUser):
    weight = 8
    kind = "attendees"
    wait_time = between(1, 3)

    @task(6)
    def dashboard_events(self):
        self._get("/api/events", "/api/events")

    @task(3)
    def event_details(self):
        if EVENT_IDS:
            self._get(f"/api/events/{random.choice(EVENT_IDS)}", "/api/events/[id]")

    @task(2)
    def my_events(self):
        self._get("/api/student/my-events", "/api/student/my-events")

    @task(1)
    def enroll(self):
        if not EVENT_IDS:
            return
        with self.client.post(f"/api/events/{random.choice(EVENT_IDS)}/enroll", name="/api/events/[id]/enroll",
                              catch_response=True) as r:
            _check(r, ok=(200, 409, 400))  # 409 already enrolled, 400 full/closed: correct answers


class OrganizerUser(EverestUser):
    weight = 2
    kind = "organizers"
    wait_time = between(2, 5)

    @task(2)
    def stats(self):
        self._get("/api/organizer/stats", "/api/organizer/stats")

    @task(1)
    def own_events(self):
        self._get("/api/events", "/api/events (organizer)")


if LOGIN_MODE == "token":
    class LoginUser(EverestUser):
        """Keeps the real login path (bcrypt + reCAPTCHA check) under load in token mode:
        5 users, about one login every 10 s each, so the per-IP login limit isn't reached."""
        fixed_count = 5
        kind = "attendees"
        wait_time = between(8, 12)

        @task
        def log_in_again(self):
            # Cookies are kept: the CSRF check needs the csrf cookie together with its header
            self.login()


class StepLoad(LoadTestShape):
    """Raise the number of users in steps; each step lasts STEP_SECONDS.
    LOAD_STEPS, e.g. "100,250,500,1000", comes from run_load_test.py."""
    steps = [int(s) for s in os.environ.get("LOAD_STEPS", "5,10,20,40").split(",")]
    step_seconds = int(os.environ.get("STEP_SECONDS", "60"))
    spawn_rate = float(os.environ.get("SPAWN_RATE", "2"))

    def tick(self):
        run_time = self.get_run_time()
        index = int(run_time // self.step_seconds)
        if index >= len(self.steps):
            return None
        return self.steps[index], self.spawn_rate


@events.quitting.add_listener
def _exit_code(environment, **_):
    # Don't fail the process on errors: the report is the result; run_load_test.py summarizes it.
    environment.process_exit_code = 0
