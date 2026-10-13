# EVEREST automated test suite

Pytest suite for the EVEREST event registration system (Angular 21 frontend, FastAPI +
PostgreSQL backend). It tests the **real backend code** running in its own process against a
**separate test database**, and drives the **real Angular app** in a browser with Playwright.

## Turned off by default

The suite is **deactivated**: every test is skipped and the load test exits, unless
`EVEREST_TESTS_ENABLED=1` is set for that run:

```bash
set EVEREST_TESTS_ENABLED=1          # Windows cmd (PowerShell: $env:EVEREST_TESTS_ENABLED="1")
tests/.venv/Scripts/python -m pytest tests
```

To turn it back on for good, remove the on/off switch at the top of `tests/conftest.py` and in
`tests/performance/run_load_test.py`.

## Safety

- Tests never use the database in `backend/.env` (`ers_db`). They use `ers_db_test` on the same
  PostgreSQL server, which they create if it's missing and **wipe at the start of every run**.
  The run stops before touching anything if the test database name doesn't end in `_test`, is the
  same as the one in `backend/.env`, or isn't on localhost (`helpers/config.py`).
- The backend under test runs on port **8001** (rate-limit tests briefly use **8002**), so your
  own backend on 8000 keeps running and keeps its data.
- Test-only settings for that process: a random `JWT_SECRET_KEY`, `EMAIL_ENABLED=false` (no real
  emails), and Google's documented reCAPTCHA **test** secret (every token passes). No security
  feature is turned off: CSRF, CORS, rate limits, lockout, role checks and validation all run as
  in development. Your `backend/.env` is only read, to find the PostgreSQL server; values are
  never printed.
- No application code was changed to make tests pass.

## Layout

| Path | What it covers |
|---|---|
| `conftest.py` | Creates/resets the test DB, starts the backend, seeds one account per role, logged-in clients |
| `helpers/` | Config and safety guards, DB seeding, backend process, API client (Origin + CSRF like the app) |
| `test_auth.py` | Login (each role, wrong password, reCAPTCHA, lockout states), logout, registration, email verification, password reset |
| `test_api.py` | Status codes, response formats, missing/invalid fields, duplicates, uploads, error handling |
| `test_functional.py` | CRUD for events and every admin table, dashboards, attendance, persistence |
| `test_scheduling.py` | Event dates/times, registration windows (Upcoming/Open/Closed), capacity (Full), auto-close, concurrency on the last slot |
| `test_security.py` | Auth on every protected endpoint, role matrix, IDOR, JWT tampering/expiry, password storage, SQLi, XSS, CSRF, CORS, headers, rate limits |
| `e2e/test_browser.py` | Playwright: route guards, login per role, sign out, enroll + reload, organizer create form + reload, admin delete with confirm, search, registration form, XSS rendering |
| `performance/` | Locust user mix + `run_load_test.py` (step ramp, CSV/HTML report, per-step summary) |

The app has no calendar/booking module, so "scheduling" covers what it does have: event dates
and times, registration windows, capacity ("fully booked"), and automatic closing.

## Install (once)

Requirements: Python 3.13, Node.js (for the Angular dev server), the backend venv already set up
(`backend/venv`), and PostgreSQL running locally.

```bash
# from the repo root
python -m venv tests/.venv
tests/.venv/Scripts/python -m pip install -r tests/requirements.txt     # Windows
tests/.venv/Scripts/python -m playwright install chromium
# macOS/Linux: use tests/.venv/bin/python
```

## Quick start: one script

```bash
run_tests.bat                     # Windows: double-click works too; opens the HTML report at the end
tests/.venv/Scripts/python tests/run_tests.py              # all tests
tests/.venv/Scripts/python tests/run_tests.py security     # one area: auth api functional scheduling security e2e
tests/.venv/Scripts/python tests/run_tests.py --failed     # rerun only what failed last time
tests/.venv/Scripts/python tests/run_tests.py -- -k login  # anything after -- goes to pytest
```

It skips the browser tests (with a note) when the Angular app isn't running on :4200. When it
finishes it prints a table of every FAILED / ERROR test with the reason, and saves:

| File | Use it to |
|---|---|
| `tests/reports/summary.txt` | see this run's failures (same table as the console) |
| `tests/reports/history.csv` | track runs over time: date, passed, failed, errors, and which tests failed (opens in Excel) |
| `tests/reports/report.html` | read the full details of a test (assertion, captured output) |
| `tests/reports/e2e/` | see the screenshot and browser console of a failed browser test |
| `tests/reports/backend.log` | find server-side errors (tracebacks) behind a failure |

FAILED means the app didn't do what the test expects; ERROR means the test couldn't run
(database, backend or frontend not available); XFAIL is a known issue from `REPORT.md`.

## Screenshots for the QA Test Case Matrix

`tests/e2e/test_zz_screenshots.py` runs each row of `tests/EVEREST_QA_Test_Case_Matrix.xlsx` in the
real browser (Google's real reCAPTCHA widget with its test site key) and saves
`tests/reports/screenshots/EVR_xxx.png`. Normal runs skip it. With `TEST_MAIL_SINK=1` the test backend
sends real SMTP mail to a local catch-all server (`helpers/mailsink.py`, saved in
`tests/reports/mail/*.eml`; nothing leaves the computer), so registration and password emails work:

```bash
TEST_MAIL_SINK=1 tests/.venv/Scripts/python -m pytest tests/e2e/test_zz_screenshots.py -m screenshots
```

## Run with pytest directly

API, functional, scheduling and security tests (start the backend themselves):

```bash
tests/.venv/Scripts/python -m pytest tests --ignore=tests/e2e
tests/.venv/Scripts/python -m pytest tests -m security          # one area (auth, api, functional, scheduling, security)
tests/.venv/Scripts/python -m pytest tests/test_auth.py -k reset # one file / pattern
tests/.venv/Scripts/python -m pytest tests -m "not ratelimit"    # skip the slower rate-limit tests
```

Browser tests: start the Angular dev server first (your backend on :8000 is not needed for them):

```bash
cd frontend/event-registration && npm start          # http://localhost:4200, leave it running
tests/.venv/Scripts/python -m pytest tests/e2e --screenshot only-on-failure --output tests/reports/playwright
tests/.venv/Scripts/python -m pytest tests/e2e --headed --slowmo 300   # watch it
```

Everything:

```bash
tests/.venv/Scripts/python -m pytest tests --screenshot only-on-failure --output tests/reports/playwright
```

Load test (resets `ers_db_test`, starts its own backend, prints a per-step table):

```bash
tests/.venv/Scripts/python tests/performance/run_load_test.py --steps 5,10,20,40 --step-seconds 60
```

## Reports

- `tests/reports/report.html` – pytest-html report (pass/fail/xfail with details)
- `tests/reports/junit.xml` – for CI
- `tests/reports/backend.log` – the test backend's console output
- `tests/reports/e2e/` – screenshot + browser console log of each failed browser test
- `tests/reports/load/` – Locust CSV and HTML

## Things to know

- The app allows **20 logins per minute per IP**. Every test client is on 127.0.0.1, so setup
  logins wait for the limit to reset instead of failing. A full run takes several minutes for that
  reason, not because the app is slow.
- Sign-ups are limited to 20 per IP per 10 minutes; tests that only need a pending sign-up insert it
  into the test database.
- Emails aren't sent. Tests that need an emailed link store a known token's SHA-256 in the test
  database, exactly as the app stores real ones, and then call the real endpoint.
- `xfail` tests marked "SECURITY FINDING" document a known weakness. They are strict: once it's
  fixed they report XPASS, so remove the marker then.
- All load-test users come from one IP, so the per-IP limit (600 requests/min) caps the measured
  throughput. See the load-test notes in the latest test report before drawing capacity conclusions.
