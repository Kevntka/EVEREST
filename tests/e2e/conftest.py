"""
Playwright setup for the browser tests.

- The Angular dev server must be running (npm start -> http://localhost:4200). If it isn't,
  every e2e test is skipped with a message.
- The app's code calls http://localhost:8000/api/... (hardcoded). Each request is rerouted to
  the test backend (TEST_BACKEND_PORT, test database), so the developer's backend and real
  data are never used.
- Google's reCAPTCHA script is replaced by a small stand-in whose checkbox is always ticked.
  The test backend still verifies the token with Google (test secret key), so the login code
  path is the real one.
- On failure: a full-page screenshot and the browser console log are saved to
  tests/reports/e2e/ (plus pytest-playwright's own artifacts with --screenshot/--tracing).
"""

import re

import httpx
import pytest

from helpers.config import APP_API_PREFIX, FRONTEND_URL, REPORTS_DIR

E2E_REPORTS = REPORTS_DIR / "e2e"

RECAPTCHA_STUB = """
window.grecaptcha = {
  ready: function (cb) { cb(); },
  render: function (el) { el.innerHTML = '<div class="recaptcha-stub">reCAPTCHA (test stand-in)</div>'; return 0; },
  getResponse: function () { return 'e2e-recaptcha-token'; },
  reset: function () {}
};
"""


@pytest.fixture(scope="session")
def frontend_url():
    try:
        httpx.get(FRONTEND_URL, timeout=3)
    except httpx.TransportError:
        pytest.skip(f"Angular dev server not reachable at {FRONTEND_URL}. Start it with `npm start` "
                    "in frontend/event-registration, then rerun the e2e tests.")
    return FRONTEND_URL


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    return {**browser_context_args, "viewport": {"width": 1366, "height": 800}}


@pytest.fixture
def app(page, context, api_url, frontend_url, request):
    """The page with API calls rerouted to the test backend; yields a small helper."""
    test_api = api_url.replace("127.0.0.1", "localhost")  # same cookie host as the app's localhost:8000

    def reroute(route):
        url = route.request.url.replace(APP_API_PREFIX, test_api, 1)
        try:
            response = route.fetch(url=url)
        except Exception:
            route.abort()
            return
        route.fulfill(response=response)

    context.route(re.compile(r"^http://localhost:8000/.*"), reroute)
    context.route(re.compile(r"^https://www\.google\.com/recaptcha/api\.js.*"),
                  lambda route: route.fulfill(body=RECAPTCHA_STUB, content_type="application/javascript"))

    console: list[str] = []
    page.on("console", lambda msg: console.append(f"[{msg.type}] {msg.text}"))
    page.on("pageerror", lambda exc: console.append(f"[pageerror] {exc}"))
    page.set_default_timeout(10_000)

    yield App(page, frontend_url)

    report = getattr(request.node, "rep_call", None)
    if report is not None and report.failed:
        E2E_REPORTS.mkdir(parents=True, exist_ok=True)
        name = re.sub(r"[^\w.-]+", "_", request.node.nodeid)[-120:]
        try:
            page.screenshot(path=str(E2E_REPORTS / f"{name}.png"), full_page=True)
        except Exception:
            pass
        (E2E_REPORTS / f"{name}.console.log").write_text("\n".join(console), encoding="utf-8")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    setattr(item, f"rep_{report.when}", report)


class App:
    def __init__(self, page, base: str):
        self.page = page
        self.base = base

    def goto(self, path: str):
        self.page.goto(f"{self.base}{path}")

    def login(self, user: dict, expect_path: str | None = None):
        self.goto("/login")
        self.page.fill("#email", user["email"])
        self.page.fill("#password", user["password"])
        self.page.locator(".recaptcha-stub").first.wait_for()
        self.page.click("button.btn-login")
        if expect_path:
            self.page.wait_for_url(f"**{expect_path}")

    def sign_out(self):
        self.page.click("button.user-dropdown")
        self.page.click(".dropdown-item:has-text('Sign Out')")
        self.page.wait_for_url("**/login")

    def confirm_dialog(self):
        self.page.click(".dialog-btn--ok")

    def close_notice(self):
        self.page.locator(".dialog-overlay").click()
