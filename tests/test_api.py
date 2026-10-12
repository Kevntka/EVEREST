"""API contract: status codes, response formats, validation and error handling."""

import pytest

from helpers import db as dbh
from helpers.api import event_form

pytestmark = pytest.mark.api

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64  # the backend identifies images by their first bytes
EVENT_KEYS = {"id", "event_name", "event_description", "event_date", "event_time", "event_end_time", "venue",
              "capacity", "status", "cover_photo", "enrolled_count", "department", "about_event",
              "registration_start", "registration_end"}


def test_health_endpoints(anon):
    assert anon.get("/api/test").status_code == 200
    root = anon.get("/").json()
    assert root["status"] == "running"


def test_csrf_token_endpoint(anon):
    response = anon.get("/api/csrf-token")
    assert response.status_code == 200
    token = response.json()["csrf_token"]
    assert "." in token  # nonce.signature
    cookie = response.headers["set-cookie"]
    assert f"csrf_token={token}" in cookie and "HttpOnly" in cookie and "samesite=strict" in cookie.lower()


def test_unknown_endpoint_is_json_404(anon):
    response = anon.get("/api/does-not-exist")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")


def test_wrong_method_is_405(student_client):
    assert student_client.put("/api/events").status_code == 405


def test_api_docs_are_disabled_when_configured(anon):
    # The test backend runs with ENABLE_API_DOCS=false (what production should use)
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert anon.get(path).status_code == 404


def test_event_list_format(student_client, open_event):
    response = student_client.get("/api/events")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True and body["count"] == len(body["events"])
    event = next(e for e in body["events"] if e["id"] == open_event["id"])
    assert set(event) == EVENT_KEYS
    assert event["event_date"] == open_event["date"]  # YYYY-MM-DD string
    assert event["event_time"] == "08:00:00" and event["event_end_time"] == "17:00:00"


def test_get_event_by_id_and_404(student_client, open_event):
    assert student_client.get(f"/api/events/{open_event['id']}").json()["event"]["id"] == open_event["id"]
    assert student_client.get("/api/events/999999").status_code == 404
    assert student_client.get("/api/events/not-a-number").status_code == 422


def test_create_event_returns_201_and_body(organizer_client):
    response = organizer_client.post("/api/events", data=event_form(event_name="Contract Check"))
    assert response.status_code == 201
    event = response.json()["event"]
    assert event["event_name"] == "Contract Check" and event["status"] == "open" and event["enrolled_count"] == 0


@pytest.mark.parametrize("missing", ["event_name", "event_description", "event_date", "event_time", "venue", "capacity"])
def test_create_event_missing_required_field_is_422(organizer_client, missing):
    data = event_form()
    data.pop(missing)
    response = organizer_client.post("/api/events", data=data)
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)


@pytest.mark.parametrize("field,value", [
    ("capacity", "0"), ("capacity", "100001"), ("event_name", " "), ("event_name", "x" * 201),
    ("event_date", "2026-13-45"), ("event_time", "25:99"), ("department", ""),
])
def test_create_event_invalid_values_are_400(organizer_client, field, value):
    response = organizer_client.post("/api/events", data=event_form(**{field: value}))
    assert response.status_code == 400, response.text


def test_create_event_wrong_type_is_422(organizer_client):
    assert organizer_client.post("/api/events", data=event_form(capacity="ten")).status_code == 422


def test_cover_photo_upload_and_serve(organizer_client, anon):
    response = organizer_client.post("/api/events", data=event_form(), files={"cover_photo": ("c.png", PNG, "image/png")})
    assert response.status_code == 201
    cover_url = response.json()["event"]["cover_photo"]
    served = anon.get(cover_url)  # public on purpose (the <img> tag can't send the cookie cross-site)
    assert served.status_code == 200
    assert served.headers["content-type"] == "image/png" and served.content == PNG


@pytest.mark.parametrize("name,content,ctype", [
    ("x.svg", b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>", "image/svg+xml"),
    ("x.png", b"<html><script>alert(1)</script></html>", "image/png"),  # lies about its type
    ("big.png", PNG + b"\x00" * (5 * 1024 * 1024), "image/png"),       # over 5 MB
], ids=["svg-with-script", "html-disguised-as-png", "over-5mb"])
def test_cover_photo_rejects_bad_files(organizer_client, name, content, ctype):
    response = organizer_client.post("/api/events", data=event_form(), files={"cover_photo": (name, content, ctype)})
    assert response.status_code == 400


def test_cover_404_when_event_has_none(anon, open_event):
    assert anon.get(f"/api/events/{open_event['id']}/cover").status_code == 404


def test_duplicate_enrollment_is_409(engine, organizer_user, new_client):
    student = dbh.create_user(engine, "student")
    client = new_client().login_as(student)
    event = dbh.create_event(engine, organizer_user)
    assert client.post(f"/api/events/{event['id']}/enroll").status_code == 200
    assert client.post(f"/api/events/{event['id']}/enroll").status_code == 409


def test_enrollment_status_endpoint(engine, organizer_user, student_client, student_user):
    event = dbh.create_event(engine, organizer_user)
    assert student_client.get(f"/api/events/{event['id']}/enrollment").json() == {
        "success": True, "enrolled": False, "attendance": None}
    dbh.enroll(engine, event["id"], student_user["id"])
    assert student_client.get(f"/api/events/{event['id']}/enrollment").json()["attendance"] == "pending"


def test_profile_get_format(student_client):
    profile = student_client.get("/api/student/profile").json()["profile"]
    assert {"fullName", "srCode", "email"} <= set(profile)


@pytest.mark.parametrize("body,detail", [
    ({"fullName": "Juan", "srCode": "2330046"}, "SR-Code"),
    ({"fullName": "Juan", "contactNumber": "123"}, "11 digits"),
    ({"fullName": "Juan", "birthday": "2999-01-01"}, "future"),
    ({"fullName": "Juan", "birthday": "not-a-date"}, "valid birthday"),
    ({"fullName": "Juan123"}, "letters"),
])
def test_profile_validation_errors(participant_client, body, detail):
    response = participant_client.put("/api/student/profile", json=body)
    assert response.status_code == 400
    assert detail in response.json()["detail"]


def test_profile_missing_full_name_is_422(participant_client):
    assert participant_client.put("/api/student/profile", json={"gender": "MALE"}).status_code == 422


def test_attendance_invalid_status_is_422(organizer_client):
    response = organizer_client.put("/api/organizer/attendees/1/attendance", json={"status": "absent"})
    assert response.status_code == 422


def test_errors_do_not_leak_tracebacks(organizer_client, anon):
    for response in (
        organizer_client.post("/api/events", data=event_form(event_date="not-a-date")),
        anon.post("/api/verify-email", data={"token": "' OR 1=1 --"}),
    ):
        assert "Traceback" not in response.text and "sqlalchemy" not in response.text.lower()
