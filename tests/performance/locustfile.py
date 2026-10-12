"""
Load test for the EVEREST API (Locust).

Run it through tests/performance/run_load_test.py, which starts a backend on the TEST
database, seeds accounts and events, and runs this file headless with a step-by-step ramp.
Never point it at a backend that uses real data.

User mix (what the app's pages do):
- AttendeeUser (most traffic): logs in once, then polls GET /api/events like the Student
  Dashboard's 10-second auto-refresh, opens event details, checks My Events, and enrolls.
- OrganizerUser: Organizer Dashboard stats and their events.

Every simulated user comes from the same IP (this machine), so the backend's per-IP limits
apply to the whole test: 600 API requests/min and 20 logins/min. 429 responses are counted
as failures named "429 rate limited" so they're visible in the results, not hidden.
"""

import json
import os
import random

from locust import HttpUser, LoadTestShape, between, events, task

ORIGIN = "http://localhost:4200"
ACCOUNTS = json.loads(os.environ.get("EVEREST_LOAD_ACCOUNTS", '{"attendees": [], "organizers": []}'))
EVENT_IDS = json.loads(os.environ.get("EVEREST_LOAD_EVENT_IDS", "[]"))
PASSWORD = os.environ.get("EVEREST_LOAD_PASSWORD", "")
_next = {"attendees": 0, "organizers": 0}


def _take(kind: str) -> str:
    pool = ACCOUNTS[kind]
    email = pool[_next[kind] % len(pool)]
    _next[kind] += 1
    return email


class EverestUser(HttpUser):
    abstract = True
    kind = "attendees"

    def on_start(self):
        self.client.headers["Origin"] = ORIGIN
        token = self.client.get("/api/csrf-token", name="/api/csrf-token").json()["csrf_token"]
        self.client.headers["X-CSRF-Token"] = token
        self.email = _take(self.kind)
        with self.client.post("/api/login", name="/api/login", catch_response=True, data={
                "email": self.email, "password": PASSWORD, "recaptcha_token": "load-test"}) as r:
            if r.status_code == 429:
                r.failure("429 rate limited")
            elif r.status_code != 200:
                r.failure(f"login {r.status_code}")

    def _get(self, path, name):
        with self.client.get(path, name=name, catch_response=True) as r:
            if r.status_code == 429:
                r.failure("429 rate limited")
            elif r.status_code != 200:
                r.failure(f"HTTP {r.status_code}")


class AttendeeUser(EverestUser):
    weight = 4
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
            if r.status_code == 429:
                r.failure("429 rate limited")
            elif r.status_code in (200, 409, 400):  # 409 already enrolled, 400 full: correct answers
                r.success()
            else:
                r.failure(f"HTTP {r.status_code}")


class OrganizerUser(EverestUser):
    weight = 1
    kind = "organizers"
    wait_time = between(2, 5)

    @task(2)
    def stats(self):
        self._get("/api/organizer/stats", "/api/organizer/stats")

    @task(1)
    def own_events(self):
        self._get("/api/events", "/api/events (organizer)")


class StepLoad(LoadTestShape):
    """Raise the number of users in steps; each step lasts STEP_SECONDS.
    LOAD_STEPS, e.g. "5,10,20,40", comes from run_load_test.py."""
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
