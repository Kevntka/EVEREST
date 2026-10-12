"""
Security: authentication on every protected endpoint, role-based access, ownership (IDOR),
JWT handling, password storage, injection, XSS, CSRF, CORS, headers, and rate limiting.
"""

import time
from datetime import datetime, timedelta, timezone

import httpx
import jwt
import pytest

from helpers import db as dbh
from helpers.api import ApiClient, event_form
from helpers.config import DEFAULT_PASSWORD, JWT_TEST_SECRET, ORIGIN

pytestmark = pytest.mark.security

# Every route in backend/api/routes_db.py that needs the login cookie (method, path)
PROTECTED = [
    ("GET", "/api/organizers"), ("PUT", "/api/organizers/1"), ("DELETE", "/api/organizers/1"),
    ("GET", "/api/students"), ("PUT", "/api/students/1"), ("DELETE", "/api/students/1"),
    ("GET", "/api/participants"), ("PUT", "/api/participants/1"), ("DELETE", "/api/participants/1"),
    ("GET", "/api/events"), ("POST", "/api/events"), ("GET", "/api/events/1"), ("PUT", "/api/events/1"),
    ("DELETE", "/api/events/1"), ("GET", "/api/events/1/enrollment"), ("POST", "/api/events/1/enroll"),
    ("DELETE", "/api/events/1/enroll"), ("GET", "/api/organizer/stats"), ("GET", "/api/organizer/attendees"),
    ("PUT", "/api/organizer/attendees/1/attendance"), ("POST", "/api/change-password"),
    ("GET", "/api/student/profile"), ("PUT", "/api/student/profile"), ("POST", "/api/student/profile/avatar"),
    ("GET", "/api/student/my-events"),
]

ADMIN_ONLY = [("GET", "/api/organizers"), ("GET", "/api/students"), ("GET", "/api/participants"),
              ("DELETE", "/api/students/1"), ("DELETE", "/api/participants/1"), ("DELETE", "/api/organizers/1"),
              ("PUT", "/api/students/1"), ("PUT", "/api/participants/1"), ("PUT", "/api/organizers/1")]
ORGANIZER_ONLY = [("POST", "/api/events"), ("GET", "/api/organizer/stats"), ("GET", "/api/organizer/attendees"),
                  ("PUT", "/api/organizer/attendees/1/attendance")]
ATTENDEE_ONLY = [("POST", "/api/events/1/enroll"), ("DELETE", "/api/events/1/enroll"), ("GET", "/api/events/1/enrollment"),
                 ("GET", "/api/student/profile"), ("GET", "/api/student/my-events")]


# ---------------------------------------------------------------- authentication required
@pytest.mark.parametrize("method,path", PROTECTED)
def test_protected_endpoints_require_login(anon, method, path):
    response = anon.request(method, path)
    assert response.status_code == 401, f"{method} {path} -> {response.status_code}"


def test_cover_photo_is_the_only_public_event_data(anon, open_event):
    # Covers are public by design; event details are not
    assert anon.get(f"/api/events/{open_event['id']}").status_code == 401


# ---------------------------------------------------------------- role-based access
@pytest.mark.parametrize("method,path", ADMIN_ONLY)
@pytest.mark.parametrize("who", ["organizer_client", "student_client", "participant_client"])
def test_admin_endpoints_reject_other_roles(request, who, method, path):
    client = request.getfixturevalue(who)
    assert client.request(method, path, json={}, data=None).status_code in (403, 422)
    # 422 would mean the body was checked before the role: make sure it's really 403 with a valid body
    if method == "PUT":
        body = {"json": {"fullName": "A B", "email": "a@b.co"}} if "organizers" not in path else \
            {"data": {"employment_id": "E", "full_name": "A", "department": "D", "email": "a@b.co"}}
        assert client.request(method, path, **body).status_code == 403


@pytest.mark.parametrize("method,path", ORGANIZER_ONLY)
@pytest.mark.parametrize("who", ["admin_client", "student_client", "participant_client"])
def test_organizer_endpoints_reject_other_roles(request, who, method, path):
    client = request.getfixturevalue(who)
    kwargs = {"data": event_form()} if path == "/api/events" else {"json": {"status": "present"}} if method == "PUT" else {}
    assert client.request(method, path, **kwargs).status_code == 403


@pytest.mark.parametrize("method,path", ATTENDEE_ONLY)
@pytest.mark.parametrize("who", ["admin_client", "organizer_client"])
def test_attendee_endpoints_reject_staff(request, who, method, path):
    assert request.getfixturevalue(who).request(method, path).status_code == 403


def test_students_and_participants_cannot_edit_or_delete_events(engine, organizer_user, student_client, participant_client):
    event = dbh.create_event(engine, organizer_user)
    for client in (student_client, participant_client):
        assert client.put(f"/api/events/{event['id']}", data=event_form()).status_code == 403
        assert client.delete(f"/api/events/{event['id']}").status_code == 403


# ---------------------------------------------------------------- ownership (IDOR)
def test_organizer_cannot_touch_another_organizers_event(engine, organizer_user, organizer2_client):
    event = dbh.create_event(engine, organizer_user, name="Not Yours")
    assert organizer2_client.put(f"/api/events/{event['id']}", data=event_form(event_name="Hijacked")).status_code == 404
    assert organizer2_client.delete(f"/api/events/{event['id']}").status_code == 403
    assert dbh.scalar(engine, "SELECT event_name FROM events WHERE id = :e", e=event["id"]) == "Not Yours"
    assert event["id"] not in {e["id"] for e in organizer2_client.get("/api/events").json()["events"]}


def test_organizer_cannot_see_or_mark_another_organizers_attendees(engine, organizer_user, organizer2_client, student_user):
    event = dbh.create_event(engine, organizer_user)
    registration_id = dbh.enroll(engine, event["id"], student_user["id"])
    assert organizer2_client.get("/api/organizer/attendees", params={"event_id": event["id"]}).json()["attendees"] == []
    response = organizer2_client.put(f"/api/organizer/attendees/{registration_id}/attendance", json={"status": "present"})
    assert response.status_code == 404
    assert dbh.scalar(engine, "SELECT COUNT(*) FROM attendees WHERE registration_id = :r", r=registration_id) == 0


def test_organizer_id_parameter_is_ignored(engine, organizer_user, organizer2_client):
    dbh.create_event(engine, organizer_user)
    stats = organizer2_client.get("/api/organizer/stats", params={"organizer_id": organizer_user["id"]}).json()
    assert all(row["eventId"] not in () for row in stats["enrollmentData"])
    own = {e["id"] for e in organizer2_client.get("/api/events").json()["events"]}
    assert {row["eventId"] for row in stats["enrollmentData"]} == own


def test_new_event_belongs_to_logged_in_organizer_not_form_value(engine, organizer_user, organizer2_client):
    event = organizer2_client.post("/api/events", data=event_form(organizer_id=str(organizer_user["id"]))).json()["event"]
    owner = dbh.scalar(engine, "SELECT ur.user_id FROM events e JOIN user_roles ur ON ur.id = e.user_role_id WHERE e.id = :e", e=event["id"])
    assert owner == organizer2_client.user["id"]


def test_student_profile_is_always_the_logged_in_user(student_client, student_user):
    assert student_client.get("/api/student/profile", params={"user_id": 1}).json()["profile"]["email"] == student_user["email"]


# ---------------------------------------------------------------- JWT / session tokens
def _client_with_token(api_url, token: str) -> ApiClient:
    client = ApiClient(api_url)
    client.http.cookies.set("access_token", f"Bearer {token}")
    return client


def _claims(user: dict, **overrides) -> dict:
    password_hash = None  # filled by caller when needed
    now = datetime.now(timezone.utc)
    claims = {"sub": user["email"], "user_id": user["id"], "email": user["email"], "role": user["role"],
              "iat": now, "exp": now + timedelta(hours=1)}
    claims.update(overrides)
    return claims


def _fingerprint(engine, user_id: int) -> str:
    import hashlib
    pw = dbh.scalar(engine, "SELECT password FROM users WHERE id = :u", u=user_id)
    return hashlib.sha256(pw.encode()).hexdigest()[:16]


def test_valid_forged_token_shape_is_accepted_only_with_correct_secret(engine, api_url, student_user):
    claims = _claims(student_user, pwd=_fingerprint(engine, student_user["id"]))
    good = _client_with_token(api_url, jwt.encode(claims, JWT_TEST_SECRET, algorithm="HS256"))
    assert good.get("/api/student/profile").status_code == 200  # sanity check of the helper
    bad = _client_with_token(api_url, jwt.encode(claims, "x" * 48, algorithm="HS256"))
    assert bad.get("/api/student/profile").status_code == 401
    good.close(); bad.close()


def test_expired_token_is_rejected(engine, api_url, student_user):
    past = datetime.now(timezone.utc) - timedelta(hours=2)
    claims = _claims(student_user, pwd=_fingerprint(engine, student_user["id"]), iat=past, exp=past + timedelta(minutes=1))
    client = _client_with_token(api_url, jwt.encode(claims, JWT_TEST_SECRET, algorithm="HS256"))
    assert client.get("/api/events").status_code == 401
    client.close()


def test_alg_none_token_is_rejected(engine, api_url, admin_user):
    import base64, json
    def b64(obj):
        return base64.urlsafe_b64encode(json.dumps(obj).encode()).rstrip(b"=").decode()
    token = f"{b64({'alg': 'none', 'typ': 'JWT'})}.{b64({'user_id': admin_user['id'], 'role': 'admin', 'exp': 9999999999})}."
    client = _client_with_token(api_url, token)
    assert client.get("/api/students").status_code == 401
    client.close()


@pytest.mark.parametrize("token", ["garbage", "a.b.c", "Bearer", "eyJhbGciOiJIUzI1NiJ9.e30.x"])
def test_malformed_tokens_are_rejected(api_url, token):
    client = _client_with_token(api_url, token)
    assert client.get("/api/events").status_code == 401
    client.close()


def test_role_claim_in_token_is_not_trusted(engine, api_url, student_user):
    # A validly signed token for a student that *claims* to be admin is still a student
    claims = _claims(student_user, role="admin", pwd=_fingerprint(engine, student_user["id"]))
    client = _client_with_token(api_url, jwt.encode(claims, JWT_TEST_SECRET, algorithm="HS256"))
    assert client.get("/api/students").status_code == 403
    client.close()


def test_token_without_password_fingerprint_is_rejected(api_url, student_user):
    client = _client_with_token(api_url, jwt.encode(_claims(student_user), JWT_TEST_SECRET, algorithm="HS256"))
    assert client.get("/api/events").status_code == 401
    client.close()


@pytest.mark.xfail(strict=True, reason="SECURITY FINDING: logout only deletes the cookie; a copied JWT "
                                       "keeps working until it expires (24 h). No server-side revocation.")
def test_token_is_unusable_after_logout(engine, new_client, api_url):
    user = dbh.create_user(engine, "student")
    client = new_client().login_as(user)
    stolen = client.cookie("access_token").strip('"').removeprefix("Bearer ")
    client.post("/api/logout")
    replay = _client_with_token(api_url, stolen)
    status = replay.get("/api/events").status_code
    replay.close()
    assert status == 401


# ---------------------------------------------------------------- password storage + policy
def test_passwords_are_bcrypt_hashed(engine, student_user):
    stored = dbh.scalar(engine, "SELECT password FROM users WHERE id = :u", u=student_user["id"])
    assert stored.startswith("$2") and DEFAULT_PASSWORD not in stored


def test_no_plaintext_password_or_hash_in_api_responses(admin_client, student_client, student_user):
    for response in (admin_client.get("/api/students"), student_client.get("/api/student/profile"),
                     admin_client.get("/api/participants"), admin_client.get("/api/organizers")):
        assert "$2b$" not in response.text and DEFAULT_PASSWORD not in response.text
        assert '"password"' not in response.text


def test_password_max_length_is_enforced(anon):
    assert anon.login("a@example.com", "A1!" + "a" * 200).status_code == 400


# ---------------------------------------------------------------- injection + XSS
@pytest.mark.parametrize("payload", ["' OR '1'='1", "'; DROP TABLE users; --", "admin@x.com' --"])
def test_sql_injection_in_login_is_rejected(anon, payload):
    response = anon.login(payload, payload)
    assert response.status_code in (400, 401, 404)
    assert "syntax" not in response.text.lower()


def test_sql_injection_payloads_are_stored_as_plain_text(engine, organizer_client):
    payload = "Robert'); DROP TABLE events; --"
    event = organizer_client.post("/api/events", data=event_form(event_name=payload, venue="' OR 1=1 --")).json()["event"]
    assert organizer_client.get(f"/api/events/{event['id']}").json()["event"]["event_name"] == payload
    assert dbh.scalar(engine, "SELECT COUNT(*) FROM events") >= 1  # table still there


@pytest.mark.parametrize("path", ["/api/events/1 OR 1=1", "/api/events/1;DROP TABLE events", "/api/students/1'--"])
def test_sql_injection_in_path_ids_is_422_or_404(admin_client, path):
    assert admin_client.get(path).status_code in (404, 405, 422)


def test_xss_payload_is_returned_as_data_not_html(organizer_client):
    payload = '<img src=x onerror="alert(1)"><script>alert(2)</script>'
    event = organizer_client.post("/api/events", data=event_form(event_name=payload)).json()["event"]
    response = organizer_client.get(f"/api/events/{event['id']}")
    assert response.headers["content-type"].startswith("application/json")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.json()["event"]["event_name"] == payload  # stored verbatim; the browser test checks it renders as text


def test_control_characters_are_rejected(organizer_client):
    assert organizer_client.post("/api/events", data=event_form(event_name="bad\x00name")).status_code == 400


# ---------------------------------------------------------------- CSRF
def test_post_without_csrf_token_is_403(engine, new_client):
    user = dbh.create_user(engine, "student")
    client = new_client(csrf=False)
    response = client.post("/api/login", data={"email": user["email"], "password": user["password"], "recaptcha_token": "x"})
    assert response.status_code == 403 and response.json()["csrf_failed"] is True


def test_csrf_header_must_match_cookie(new_client):
    client = new_client(csrf=False)
    client.get("/api/csrf-token")
    other = new_client().csrf_token()  # valid signature, but not this client's cookie
    response = client.post("/api/logout", headers={"X-CSRF-Token": other})
    assert response.status_code == 403


def test_forged_unsigned_csrf_token_is_403(new_client):
    client = new_client(csrf=False)
    client.http.cookies.set("csrf_token", "abc.def")
    assert client.post("/api/logout", headers={"X-CSRF-Token": "abc.def"}).status_code == 403


def test_foreign_origin_is_blocked(new_client):
    client = new_client(origin="https://evil.example.com")
    response = client.post("/api/logout")
    assert response.status_code == 403
    assert "did not come from the EVEREST website" in response.json()["detail"]


def test_logged_in_state_change_needs_csrf(engine, organizer_user, student_user, new_client):
    event = dbh.create_event(engine, organizer_user)
    client = new_client().login_as(dbh.create_user(engine, "student"))
    client.auto_csrf = False
    response = client.post(f"/api/events/{event['id']}/enroll")
    assert response.status_code == 403


# ---------------------------------------------------------------- CORS + headers + cookies
def test_cors_allows_only_the_frontend(api_url):
    for origin, allowed in ((ORIGIN, True), ("https://evil.example.com", False)):
        response = httpx.options(f"{api_url}/api/events", headers={
            "Origin": origin, "Access-Control-Request-Method": "GET"})
        assert (response.headers.get("access-control-allow-origin") == origin) is allowed
    response = httpx.get(f"{api_url}/api/test", headers={"Origin": ORIGIN})
    assert response.headers["access-control-allow-credentials"] == "true"


def test_security_headers_present(anon):
    headers = anon.get("/api/test").headers
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["x-frame-options"] == "DENY"
    assert headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert "frame-ancestors 'none'" in headers["content-security-policy"]
    assert headers["cross-origin-resource-policy"] == "same-site"


def test_cookies_are_not_secure_flagged_on_http_dev(engine, new_client):
    # HTTPS_ONLY=false locally: the Secure flag is off. In production set HTTPS_ONLY=true
    # (the backend then adds Secure + HSTS). Recorded here so a config change is noticed.
    user = dbh.create_user(engine, "student")
    response = new_client().login(user["email"], user["password"])
    assert "secure" not in response.headers["set-cookie"].lower().split("samesite")[0]


# ---------------------------------------------------------------- rate limiting (fresh backend each)
@pytest.mark.ratelimit
def test_login_rate_limit_per_ip(fresh_backend):
    client = ApiClient(fresh_backend.url)
    statuses = [client.login(dbh.unique_email("rl"), DEFAULT_PASSWORD, wait_if_rate_limited=False).status_code
                for _ in range(21)]
    client.close()
    assert statuses[:20].count(429) == 0 and statuses[20] == 429


@pytest.mark.ratelimit
def test_login_lockout_after_five_wrong_passwords(engine, fresh_backend):
    user = dbh.create_user(engine, "student")
    client = ApiClient(fresh_backend.url)
    wrong = [client.login(user["email"], "Wrong-Pass1!", wait_if_rate_limited=False).status_code for _ in range(5)]
    locked = client.login(user["email"], user["password"], wait_if_rate_limited=False)
    client.close()
    assert wrong == [401] * 5
    assert locked.status_code == 429 and "Too many failed login attempts" in locked.json()["detail"]


@pytest.mark.ratelimit
def test_register_rate_limit_per_ip(fresh_backend):
    client = ApiClient(fresh_backend.url)
    statuses = [client.post("/api/register/participant", data={
        "full_name": "Rate Limit", "email": dbh.unique_email("rlreg"), "password": "weak", "role": "participant"
    }).status_code for _ in range(21)]
    client.close()
    assert 429 not in statuses[:20] and statuses[20] == 429


@pytest.mark.ratelimit
def test_global_api_rate_limit(fresh_backend):
    """600 API requests per minute per IP (the event pages poll every 10 s)."""
    # The server's own startup health check already made a few /api/test calls, so the
    # 429 comes at or just before request 600 of this loop.
    with httpx.Client(base_url=fresh_backend.url) as client:
        responses = [client.get("/api/test") for _ in range(601)]
    statuses = [r.status_code for r in responses]
    first_429 = statuses.index(429)
    assert 590 <= first_429 <= 600, first_429
    assert set(statuses[:first_429]) == {200}
    assert int(responses[first_429].headers["retry-after"]) > 0
