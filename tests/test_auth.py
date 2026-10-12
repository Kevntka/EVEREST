"""Authentication: login, logout, registration, email verification, password reset."""

import secrets

import pytest

from helpers import db as dbh
from helpers.config import DEFAULT_PASSWORD

pytestmark = pytest.mark.auth


# ---------------------------------------------------------------- login
@pytest.mark.parametrize("role", ["admin", "organizer", "student", "participant"])
def test_login_each_role_sets_httponly_cookie(engine, new_client, role):
    user = dbh.create_user(engine, role, with_role_row=role != "admin")
    client = new_client()
    response = client.login(user["email"], user["password"])

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True and body["role"] == role and body["id"] == user["id"]
    assert "token" not in response.text.lower().replace("csrf", "")  # the JWT is only in the cookie
    set_cookie = response.headers["set-cookie"]
    assert "access_token=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "samesite=lax" in set_cookie.lower()


def test_login_email_is_case_insensitive(engine, new_client):
    user = dbh.create_user(engine, "student")
    response = new_client().login(user["email"].upper(), user["password"])
    assert response.status_code == 200


def test_login_wrong_password_is_generic_401(engine, new_client):
    user = dbh.create_user(engine, "student")
    response = new_client().login(user["email"], "Wrong-Pass1!")
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"
    assert "access_token" not in response.headers.get("set-cookie", "")


def test_login_unregistered_email_returns_404(new_client):
    # Product decision in routes_db.py: tells the user the account doesn't exist
    # (this reveals which emails are registered; see the security report).
    response = new_client().login(dbh.unique_email("nobody"), DEFAULT_PASSWORD)
    assert response.status_code == 404


def test_login_requires_recaptcha_token(engine, new_client):
    user = dbh.create_user(engine, "student")
    response = new_client().login(user["email"], user["password"], recaptcha=None)
    assert response.status_code == 400
    assert response.json()["detail"] == "Please complete the reCAPTCHA"


@pytest.mark.parametrize("data", [{"email": "a@b.co"}, {"password": "x"}, {}])
def test_login_missing_fields_is_422(new_client, data):
    # The login rate limit (a dependency) runs before body validation, so wait it out if needed
    response = new_client().request_waiting("POST", "/api/login", data=data)
    assert response.status_code == 422


def test_login_invalid_email_format_is_400(new_client):
    response = new_client().login("not-an-email", DEFAULT_PASSWORD)
    assert response.status_code == 400


def test_login_deactivated_account_is_403(engine, new_client):
    user = dbh.create_user(engine, "student", is_active=False)
    response = new_client().login(user["email"], user["password"])
    assert response.status_code == 403
    assert "deactivated" in response.json()["detail"]


def test_logout_clears_cookie_and_session(engine, new_client):
    user = dbh.create_user(engine, "student")
    client = new_client().login_as(user)
    assert client.get("/api/events").status_code == 200

    response = client.post("/api/logout")
    assert response.status_code == 200
    assert 'access_token=""' in response.headers["set-cookie"] or "Max-Age=0" in response.headers["set-cookie"]
    assert client.cookie("access_token") is None
    assert client.get("/api/events").status_code == 401


# ---------------------------------------------------------------- registration + verification
# The app allows 20 sign-ups per IP every 10 minutes (security/rate_limit.py), and each
# test run starts a fresh backend, so the API sign-ups below stay under that budget. Tests
# that only need a waiting sign-up insert it with dbh.create_pending() instead.
def _register(client, role: str, email: str, password: str = DEFAULT_PASSWORD, **extra):
    data = {"full_name": "Juan Dela Cruz", "email": email, "password": password, "role": role}
    if role == "student":
        data["department"] = "Information Technology"
    if role == "organizer":
        data.update(department="Office of Student Affairs", employment_id=f"EMP-{secrets.token_hex(3)}")
    data.update(extra)
    return client.post(f"/api/register/{role}", data=data)


@pytest.mark.parametrize("role", ["student", "participant", "organizer"])
def test_registration_creates_pending_signup_only(engine, anon, role):
    email = dbh.unique_email(f"reg-{role}")
    response = _register(anon, role, email)

    assert response.status_code == 200
    body = response.json()
    assert body["verification_required"] is True
    assert body["email_sent"] is False  # EMAIL_ENABLED=false in the test backend
    pending = dbh.row(engine, "SELECT role, password_hash, code_hash FROM pending_registrations WHERE email = :e", e=email)
    assert pending["role"] == role
    assert pending["password_hash"].startswith("$2")  # bcrypt, never the plain password
    assert len(pending["code_hash"]) == 64             # SHA-256 of the emailed token
    assert dbh.scalar(engine, "SELECT COUNT(*) FROM users WHERE email = :e", e=email) == 0


def test_registration_ignores_role_field_mass_assignment(engine, anon):
    email = dbh.unique_email("massassign")
    response = anon.post("/api/register/student", data={
        "full_name": "Juan Dela Cruz", "email": email, "password": DEFAULT_PASSWORD,
        "department": "Information Technology", "role": "admin"})
    assert response.status_code == 200
    assert dbh.scalar(engine, "SELECT role FROM pending_registrations WHERE email = :e", e=email) == "student"


def test_registration_duplicate_email_is_409(engine, anon):
    existing = dbh.create_user(engine, "student")
    response = _register(anon, "participant", existing["email"])
    assert response.status_code == 409


def test_registration_repeat_within_60s_is_409(anon):
    email = dbh.unique_email("twice")
    assert _register(anon, "participant", email).status_code == 200
    response = _register(anon, "participant", email)
    assert response.status_code == 409
    assert response.json()["verification_required"] is True


def test_organizer_registration_duplicate_employment_id_is_409(organizer_user, engine, anon):
    emp_id = dbh.scalar(engine, "SELECT employment_id FROM user_roles WHERE user_id = :u", u=organizer_user["id"])
    response = _register(anon, "organizer", dbh.unique_email("dupemp"), employment_id=emp_id)
    assert response.status_code == 409


@pytest.mark.parametrize("password", ["Sh0rt!", "alllowercase1!", "NoSymbol123", "Passw0rd "])
def test_registration_rejects_weak_password(anon, password):
    response = _register(anon, "participant", dbh.unique_email("weak"), password=password)
    assert response.status_code == 400
    assert "Password must have" in response.json()["detail"]


@pytest.mark.parametrize("email", ["plainaddress", "<script>@x.com", "' OR 1=1 --@x.com"])
def test_registration_rejects_invalid_email(anon, email):
    assert _register(anon, "participant", email).status_code == 400


def test_registration_missing_required_field_is_422(anon):
    response = anon.post("/api/register/student", data={"full_name": "X", "email": dbh.unique_email(), "role": "student"})
    assert response.status_code == 422


def test_unverified_login_points_to_verify_page(engine, new_client):
    email = dbh.unique_email("unverified")
    dbh.create_pending(engine, "participant", email, secrets.token_urlsafe(32))
    response = new_client().login(email, DEFAULT_PASSWORD)
    assert response.status_code == 403
    assert response.json()["verification_required"] is True


def test_verify_email_creates_account_once(engine, anon, new_client):
    email = dbh.unique_email("verify")
    token = secrets.token_urlsafe(32)  # the token the emailed link would contain
    dbh.create_pending(engine, "student", email, token)

    response = anon.post("/api/verify-email", data={"token": token})
    assert response.status_code == 200
    assert dbh.scalar(engine, "SELECT role FROM users WHERE email = :e", e=email) == "student"
    assert dbh.scalar(engine, "SELECT COUNT(*) FROM pending_registrations WHERE email = :e", e=email) == 0
    assert new_client().login(email, DEFAULT_PASSWORD).status_code == 200

    reused = anon.post("/api/verify-email", data={"token": token})
    assert reused.status_code == 400


def test_verify_email_expired_link(engine, anon):
    email = dbh.unique_email("expired")
    token = secrets.token_urlsafe(32)
    dbh.create_pending(engine, "participant", email, token, expired=True)
    response = anon.post("/api/verify-email", data={"token": token})
    assert response.status_code == 400
    assert response.json()["verification_required"] is True
    assert dbh.scalar(engine, "SELECT COUNT(*) FROM users WHERE email = :e", e=email) == 0


@pytest.mark.parametrize("token", ["short", "x" * 200, "bad token with spaces!!", "' OR '1'='1"])
def test_verify_email_rejects_malformed_tokens(anon, token):
    assert anon.post("/api/verify-email", data={"token": token}).status_code == 400


def test_resend_verification_too_soon_is_429(engine, anon):
    email = dbh.unique_email("resend")
    dbh.create_pending(engine, "participant", email, secrets.token_urlsafe(32), sent_seconds_ago=5)
    response = anon.post("/api/resend-verification", data={"email": email})
    assert response.status_code == 429


# ---------------------------------------------------------------- password reset
def test_forgot_password_unknown_email_is_404(anon):
    # Product decision (routes_db.py): reveals whether an email is registered.
    assert anon.post("/api/forgot-password", data={"email": dbh.unique_email("ghost")}).status_code == 404


def test_forgot_password_stores_only_token_hash(engine, anon):
    user = dbh.create_user(engine, "student")
    response = anon.post("/api/forgot-password", data={"email": user["email"]})
    # Email is disabled in the test backend, so the app reports it couldn't send (503)
    assert response.status_code == 503
    stored = dbh.scalar(engine, "SELECT token FROM password_reset_tokens WHERE user_id = :u", u=user["id"])
    assert stored is not None and len(stored) == 64 and all(c in "0123456789abcdef" for c in stored)


def test_reset_password_flow_and_old_sessions_end(engine, new_client):
    user = dbh.create_user(engine, "student")
    old_session = new_client().login_as(user)
    token, other_token = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    dbh.add_reset_token(engine, user["id"], token)
    dbh.add_reset_token(engine, user["id"], other_token)

    anon = new_client()
    response = anon.post("/api/reset-password", data={"token": token, "new_password": "Brand-New9?"})
    assert response.status_code == 200

    assert new_client().login(user["email"], "Brand-New9?").status_code == 200
    assert new_client().login(user["email"], user["password"]).status_code == 401
    assert old_session.get("/api/events").status_code == 401  # sessions from before the reset end
    # This link and the other unused one no longer work
    for used in (token, other_token):
        assert anon.post("/api/reset-password", data={"token": used, "new_password": "Another-1!"}).status_code == 400


def test_reset_password_expired_token(engine, anon):
    user = dbh.create_user(engine, "student")
    token = secrets.token_urlsafe(32)
    dbh.add_reset_token(engine, user["id"], token, expires_in_minutes=-5)
    response = anon.post("/api/reset-password", data={"token": token, "new_password": "Brand-New9?"})
    assert response.status_code == 400
    assert "expired" in response.json()["detail"]


def test_reset_password_rejects_weak_password(engine, anon):
    user = dbh.create_user(engine, "student")
    token = secrets.token_urlsafe(32)
    dbh.add_reset_token(engine, user["id"], token)
    response = anon.post("/api/reset-password", data={"token": token, "new_password": "weak"})
    assert response.status_code == 400
    assert dbh.scalar(engine, "SELECT used FROM password_reset_tokens WHERE token = :t", t=dbh.sha256(token)) is False


def test_reset_password_unknown_token(anon):
    response = anon.post("/api/reset-password", data={"token": secrets.token_urlsafe(32), "new_password": "Brand-New9?"})
    assert response.status_code == 400


def test_change_password_requires_login(anon):
    assert anon.post("/api/change-password").status_code == 401
