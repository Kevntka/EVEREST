"""Functional: CRUD for every admin table and organizer events, dashboards, data persistence."""

import pytest

from helpers import db as dbh
from helpers.api import event_form

pytestmark = pytest.mark.functional


# ---------------------------------------------------------------- events (organizer)
def test_event_crud_by_organizer(engine, new_client):
    organizer = dbh.create_user(engine, "organizer")
    client = new_client().login_as(organizer)

    created = client.post("/api/events", data=event_form(event_name="CRUD Event", capacity="3"))
    assert created.status_code == 201
    event_id = created.json()["event"]["id"]
    assert dbh.scalar(engine, "SELECT event_name FROM events WHERE id = :i", i=event_id) == "CRUD Event"

    listed = client.get("/api/events").json()["events"]
    assert [e["id"] for e in listed] == [event_id]  # an organizer sees only their own events

    updated = client.put(f"/api/events/{event_id}", data=event_form(event_name="CRUD Event v2", capacity="7", venue="Gym"))
    assert updated.status_code == 200
    event = client.get(f"/api/events/{event_id}").json()["event"]
    assert (event["event_name"], event["capacity"], event["venue"]) == ("CRUD Event v2", 7, "Gym")

    assert client.delete(f"/api/events/{event_id}").status_code == 200
    assert client.get(f"/api/events/{event_id}").status_code == 404
    assert dbh.scalar(engine, "SELECT COUNT(*) FROM events WHERE id = :i", i=event_id) == 0


def test_edit_keeps_cover_photo_when_none_uploaded(organizer_client):
    png = b"\x89PNG\r\n\x1a\n" + b"\x01" * 32
    event = organizer_client.post("/api/events", data=event_form(), files={"cover_photo": ("c.png", png, "image/png")}).json()["event"]
    assert organizer_client.put(f"/api/events/{event['id']}", data=event_form(event_name="Renamed")).status_code == 200
    assert organizer_client.get(f"/api/events/{event['id']}").json()["event"]["cover_photo"] == event["cover_photo"]


def test_deleting_event_removes_its_registrations(engine, organizer_user, organizer_client, student_user):
    event = dbh.create_event(engine, organizer_user)
    registration_id = dbh.enroll(engine, event["id"], student_user["id"])
    assert organizer_client.delete(f"/api/events/{event['id']}").status_code == 200
    assert dbh.scalar(engine, "SELECT COUNT(*) FROM registrations WHERE id = :r", r=registration_id) == 0


# ---------------------------------------------------------------- admin tables: view, edit, delete
def test_admin_lists_every_role(admin_client, organizer_user, student_user, participant_user):
    organizers = admin_client.get("/api/organizers").json()["organizers"]
    students = admin_client.get("/api/students").json()["students"]
    participants = admin_client.get("/api/participants").json()["participants"]
    assert organizer_user["email"] in {o["email"] for o in organizers}
    assert student_user["email"] in {s["email"] for s in students}
    assert participant_user["email"] in {p["email"] for p in participants}
    assert {"id", "full_name", "email", "avatar_url"} <= set(students[0])


def test_admin_sees_all_events(engine, admin_client, organizer_user, organizer2_user):
    a = dbh.create_event(engine, organizer_user)
    b = dbh.create_event(engine, organizer2_user)
    ids = {e["id"] for e in admin_client.get("/api/events").json()["events"]}
    assert {a["id"], b["id"]} <= ids


def test_admin_edits_student(engine, admin_client):
    student = dbh.create_user(engine, "student")
    body = {"fullName": "Maria Clara", "email": dbh.unique_email("edited"), "srCode": "21-12345",
            "collegeDepartment": "Engineering", "program": "Civil Engineering", "yearLevel": "3rd",
            "gender": "Female", "contactNumber": "09123456789"}
    assert admin_client.put(f"/api/students/{student['id']}", json=body).status_code == 200
    saved = next(s for s in admin_client.get("/api/students").json()["students"] if s["id"] == student["id"])
    assert saved["full_name"] == "MARIA CLARA" and saved["email"] == body["email"]
    assert (saved["sr_code"], saved["year_level"], saved["contact_number"]) == ("21-12345", "3RD YEAR", "0912-345-6789")


def test_admin_edit_student_duplicate_email_is_409(engine, admin_client, student_user):
    other = dbh.create_user(engine, "student")
    response = admin_client.put(f"/api/students/{other['id']}", json={"fullName": "X Y", "email": student_user["email"]})
    assert response.status_code == 409


def test_admin_edit_wrong_role_id_is_404(admin_client, participant_user):
    # A participant's id on the Students endpoint is not found
    assert admin_client.put(f"/api/students/{participant_user['id']}", json={"fullName": "A B", "email": "a@b.co"}).status_code == 404


def test_admin_edits_participant(engine, admin_client):
    participant = dbh.create_user(engine, "participant", department=None)
    body = {"fullName": "Jose Rizal", "email": participant["email"], "address": "Calamba",
            "birthday": "2001-06-19", "gender": "MALE", "contactNumber": ""}
    assert admin_client.put(f"/api/participants/{participant['id']}", json=body).status_code == 200
    saved = next(p for p in admin_client.get("/api/participants").json()["participants"] if p["id"] == participant["id"])
    assert (saved["full_name"], saved["address"], saved["birthday"]) == ("JOSE RIZAL", "CALAMBA", "2001-06-19")


def test_admin_edits_organizer(engine, admin_client):
    organizer = dbh.create_user(engine, "organizer")
    form = {"employment_id": "EMP-EDIT-1", "full_name": "Andres B.", "department": "Registrar",
            "email": organizer["email"], "contact_number": "0917-111-2222"}
    assert admin_client.put(f"/api/organizers/{organizer['id']}", data=form).status_code == 200
    saved = next(o for o in admin_client.get("/api/organizers").json()["organizers"] if o["id"] == organizer["id"])
    assert (saved["employment_id"], saved["department"]) == ("EMP-EDIT-1", "Registrar")


def test_admin_edits_and_deletes_any_event(engine, admin_client, organizer2_user):
    event = dbh.create_event(engine, organizer2_user)
    assert admin_client.put(f"/api/events/{event['id']}", data=event_form(event_name="Admin Edit")).status_code == 200
    assert admin_client.get(f"/api/events/{event['id']}").json()["event"]["event_name"] == "Admin Edit"
    assert admin_client.delete(f"/api/events/{event['id']}").status_code == 200
    assert admin_client.get(f"/api/events/{event['id']}").status_code == 404


def test_admin_deletes_student_with_enrollments(engine, admin_client, organizer_user):
    student = dbh.create_user(engine, "student")
    event = dbh.create_event(engine, organizer_user)
    dbh.enroll(engine, event["id"], student["id"])
    assert admin_client.delete(f"/api/students/{student['id']}").status_code == 200
    assert dbh.scalar(engine, "SELECT COUNT(*) FROM users WHERE id = :u", u=student["id"]) == 0
    assert dbh.scalar(engine, "SELECT COUNT(*) FROM registrations WHERE user_id = :u", u=student["id"]) == 0
    assert admin_client.delete(f"/api/students/{student['id']}").status_code == 404


def test_admin_deletes_participant(engine, admin_client):
    participant = dbh.create_user(engine, "participant", department=None)
    assert admin_client.delete(f"/api/participants/{participant['id']}").status_code == 200
    assert dbh.scalar(engine, "SELECT COUNT(*) FROM users WHERE id = :u", u=participant["id"]) == 0


def test_admin_deletes_organizer_and_their_events(engine, admin_client):
    organizer = dbh.create_user(engine, "organizer")
    event = dbh.create_event(engine, organizer)
    assert admin_client.delete(f"/api/organizers/{organizer['id']}").status_code == 200
    assert dbh.scalar(engine, "SELECT COUNT(*) FROM events WHERE id = :e", e=event["id"]) == 0


def test_deleted_account_session_ends_immediately(engine, admin_client, new_client):
    student = dbh.create_user(engine, "student")
    session = new_client().login_as(student)
    admin_client.delete(f"/api/students/{student['id']}")
    assert session.get("/api/events").status_code == 401


# ---------------------------------------------------------------- dashboards + attendance
def test_organizer_dashboard_stats_and_attendance(engine, new_client):
    organizer = dbh.create_user(engine, "organizer")
    org_client = new_client().login_as(organizer)
    event = dbh.create_event(engine, organizer, capacity=5)
    students = [dbh.create_user(engine, "student") for _ in range(2)]
    registration_ids = [dbh.enroll(engine, event["id"], s["id"]) for s in students]

    stats = org_client.get("/api/organizer/stats").json()
    assert stats["stats"]["totalEnrollment"] == 2 and stats["stats"]["openEvents"] == 1
    assert stats["enrollmentData"] == [{"eventId": event["id"], "eventName": event["name"], "enrolled": 2, "capacity": 5, "present": 0}]

    attendees = org_client.get("/api/organizer/attendees", params={"event_id": event["id"]}).json()["attendees"]
    assert {a["id"] for a in attendees} == set(registration_ids)
    assert all(a["status"] == "pending" for a in attendees)

    assert org_client.put(f"/api/organizer/attendees/{registration_ids[0]}/attendance", json={"status": "present"}).status_code == 200
    assert org_client.put(f"/api/organizer/attendees/{registration_ids[1]}/attendance", json={"status": "not_recorded"}).status_code == 200
    stats = org_client.get("/api/organizer/stats").json()
    assert stats["attendanceData"] == {"present": 1, "notRecorded": 1}

    # The student sees the result on My Events
    student_view = new_client().login_as(students[0]).get("/api/student/my-events").json()["events"]
    assert [(e["id"], e["attendance"]) for e in student_view] == [(event["id"], "present")]


def test_my_events_lists_only_own_enrollments(engine, organizer_user, new_client):
    student = dbh.create_user(engine, "student")
    mine = dbh.create_event(engine, organizer_user)
    other = dbh.create_event(engine, organizer_user)
    dbh.enroll(engine, mine["id"], student["id"])
    dbh.enroll(engine, other["id"], dbh.create_user(engine, "student")["id"])
    events = new_client().login_as(student).get("/api/student/my-events").json()["events"]
    assert [e["id"] for e in events] == [mine["id"]]


# ---------------------------------------------------------------- persistence
def test_profile_update_persists_across_sessions(engine, new_client):
    student = dbh.create_user(engine, "student")
    body = {"fullName": "Persist Test", "srCode": "22-00001", "program": "BSIT", "yearLevel": "1ST YEAR",
            "gender": "FEMALE", "contactNumber": "0912-000-1111", "collegeDepartment": "CICS"}
    assert new_client().login_as(student).put("/api/student/profile", json=body).status_code == 200
    # A new session (like reloading the page or logging in again) reads the saved values
    profile = new_client().login_as(student).get("/api/student/profile").json()["profile"]
    assert (profile["fullName"], profile["srCode"], profile["program"]) == ("PERSIST TEST", "22-00001", "BSIT")


def test_enrollment_persists_and_cancel_frees_slot(engine, organizer_user, new_client):
    student = dbh.create_user(engine, "student")
    event = dbh.create_event(engine, organizer_user, capacity=1)
    client = new_client().login_as(student)
    assert client.post(f"/api/events/{event['id']}/enroll").status_code == 200
    assert client.get(f"/api/events/{event['id']}").json()["event"]["enrolled_count"] == 1
    assert client.delete(f"/api/events/{event['id']}/enroll").status_code == 200
    assert client.get(f"/api/events/{event['id']}").json()["event"]["enrolled_count"] == 0
    assert client.post(f"/api/events/{event['id']}/enroll").status_code == 200  # can enroll again
