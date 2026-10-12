# EVEREST test report — 2026-10-12

Environment: Windows 11, Python 3.13, Angular dev server on :4200, the backend under test on :8001
(uvicorn, one process), and PostgreSQL `ers_db_test` (reset at the start of each run). Production
data (`ers_db`) was not touched; a read-only check after the runs found no test accounts or events in it.

## Results

| Area | File | Result |
|---|---|---|
| Authentication | `test_auth.py` | all passed |
| API contract | `test_api.py` | all passed |
| Functional / CRUD / persistence | `test_functional.py` | all passed |
| Scheduling / capacity | `test_scheduling.py` | all passed |
| Security | `test_security.py` | all passed, 1 xfail (finding #1) |
| Browser (Playwright) | `e2e/test_browser.py` | 25 passed |
| **Total** | | **261 passed, 1 xfailed, 0 failed** (238 s) |

During development the suite found only problems in the tests themselves (for example, rate-limit
budgets shared between tests), and they were fixed in the tests. No application code was changed.

## Checklist

- [x] Login for each role, wrong password, unregistered email, missing reCAPTCHA, missing/invalid fields, deactivated account, unverified sign-up
- [x] Logout clears the cookie; the next API call is 401
- [x] Registration for each role: pending only, bcrypt hash, token stored as SHA-256, role field can't be overridden, duplicate email/Employment ID 409, weak password 400, invalid email 400
- [x] Email verification: link creates the account once, reuse 400, expired 400, malformed token 400, resend within 60 s 429
- [x] Password reset: success, old password rejected, older sessions signed out, all unused links invalidated, expired/unknown/weak 400
- [x] CRUD: events (organizer, admin), students, participants, organizers (view, edit, delete), cascades on delete
- [x] Dashboards: organizer stats, attendance marking, My Events attendance
- [x] Persistence: profile and enrollment survive a new session; UI create/enroll survive page reload
- [x] Search: admin Students and Student Dashboard (spaces and case ignored); the Angular unit spec covers the rest
- [x] Scheduling: registration not open yet, registration ended, full event, capacity can't drop below enrolled, auto-close after end time, reopening by editing, time/date validation, cancel rules, 10 concurrent enrollments for 1 slot
- [x] Security: 401 on all 25 protected routes; role matrix (admin, organizer, attendee-only routes); IDOR on events and attendees; organizer_id ignored; JWT wrong secret / expired / alg=none / malformed / forged role claim / missing fingerprint; bcrypt; no hashes in responses; SQL injection in login, fields and path ids; XSS payload stored as data and rendered as text; control characters; CSRF (missing, mismatched, unsigned, foreign Origin, logged-in POST); CORS; security headers; login, register, lockout and global rate limits
- [x] Browser: route guards, each role's landing page, role guard, sign out, enroll + reload, full event disabled, organizer create form + reload, form validation, View modal, admin delete with confirm/cancel, admin search + View, registration password rule, registration success, XSS rendering
- [x] Load test with a step ramp (see below)

## Security findings

1. **Logout doesn't revoke the session token** (medium). `/api/logout` only deletes the cookie; a copied JWT
   still works until it expires (24 h). Test: `test_token_is_unusable_after_logout` (xfail, strict).
   Fix: store a per-user `token_version` (or a denylist of `jti`s) checked in `current_user`, and bump it on logout; or shorten the token lifetime.
2. **Per-IP limits vs. a shared campus IP** (high for real use). All limits are per client IP: 600 API requests/min
   and 20 logins/min. Users on the campus network likely share one public IP, and every open event page polls
   every 10 s, so about 100 open pages behind one IP use the whole 600/min budget and everyone gets 429.
   The load test shows exactly this from one IP (below). Fix: key the general limit by logged-in user (cookie)
   with a higher per-IP ceiling, keep strict per-IP/per-email limits only on login/register/reset, and
   move counters to Redis if you run more than one process.
3. **Capacity isn't enforced by the database** (medium, latent). `enroll_event` counts and then inserts. It's
   safe today only because the route is `async def` with blocking DB calls, so one uvicorn process handles
   enrollments one at a time (the concurrency test passed 4/4 runs). With several workers, two students could
   take the last slot. Fix: lock the event row (`SELECT ... FOR UPDATE`) or do the insert with a conditional
   `INSERT ... SELECT ... WHERE (SELECT COUNT(*) ...) < capacity` in one statement.
4. **Blocking database calls inside `async def` routes** (performance). Login, enroll, event create/update and
   others are `async def` but use the synchronous SQLAlchemy session, which blocks the event loop: one slow
   query stalls every request. Fix: make routes that don't `await` anything plain `def` (FastAPI runs them in a
   thread pool), or use an async driver.
5. **Account enumeration** (low, product decision). Login (404) and Forgot Password (404) say whether an email
   is registered. Documented as intentional in `routes_db.py`; tests assert the current behavior.
6. **Production configuration** (reminder). Over HTTP the cookies have no `Secure` flag (expected locally).
   In production set `HTTPS_ONLY=true` (adds Secure, HSTS, HTTPS redirect, and makes a missing reCAPTCHA
   secret block login instead of being skipped) and `ENABLE_API_DOCS=false` (it defaults to true).

## Load test (Locust)

`run_load_test.py --steps 5,10,20,40 --step-seconds 60` against `ers_db_test` (130 accounts, 30 events),
one backend process, all simulated users from 127.0.0.1. Mix: 80% attendees (dashboard polling, event
details, My Events, enroll), 20% organizers (stats, events).

| Users | Requests/s | Median | p95 | Failures |
|---|---|---|---|---|
| 5 | 2.3 | 12 ms | 18 ms | 0 |
| 10 | 4.3 | 11 ms | 15 ms | 0 |
| 20 | 9.1 | 11 ms | 18 ms | 0 |
| 40 | 17.8 attempted | 6 ms | 14 ms | 545 (27%): 429 rate limited, plus 401 for users whose login was rate limited |

What this shows: up to 20 concurrent users (about 9 requests/s) from one IP, there were no errors and
p95 stayed under 20 ms. At 40 users the traffic passed the 600 requests/min per-IP limit, so the backend
answered 429 (finding #2). The rate limiter was the bottleneck, not the server; this test doesn't show
the server's own limit. Measuring that needs traffic from many IPs (several machines) or a staging
build with a per-user limit. **This report does not claim the site can handle any particular number of
users beyond what's in the table.**

## Recommendations

1. Fix finding #2 before real use (per-user limits); it affects normal campus traffic.
2. Add server-side token revocation (#1) and a DB-level capacity guard (#3).
3. Convert blocking `async def` routes to `def` (#4), then repeat the load test from several machines.
4. Run `pytest tests --ignore=tests/e2e -m "not ratelimit"` on every change (about 3 minutes, mostly waiting
   for the login limit); run the full suite with e2e before releases.
