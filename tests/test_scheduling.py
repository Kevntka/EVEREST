"""
Scheduling and availability.

EVEREST has no calendar/booking module. Its scheduling rules are on events:
- event date + start/end time; events auto-close once their end time passes,
- a registration window (registration_start .. registration_end) -> Upcoming / Open / Closed,
- capacity: an event with enrolled == capacity is fully booked ("Full").
"""

import threading
from datetime import date, datetime, timedelta

import pytest

from helpers import db as dbh
from helpers.api import ApiClient, event_form

pytestmark = pytest.mark.scheduling


def _enroll(client, event):
    return client.post(f"/api/events/{event['id']}/enroll")


# ---------------------------------------------------------------- registration window
def test_open_event_accepts_enrollment(engine, organizer_user, new_client):
    event = dbh.create_event(engine, organizer_user)
    assert _enroll(new_client().login_as(dbh.create_user(engine, "student")), event).status_code == 200


def test_upcoming_event_rejects_enrollment_until_registration_starts(engine, organizer_user, student_client):
    event = dbh.create_event(engine, organizer_user, days_from_now=20, registration_start_days=5)
    response = _enroll(student_client, event)
    assert response.status_code == 400
    opens = date.today() + timedelta(days=5)
    assert response.json()["detail"] == f"Registration for this event opens on {opens.strftime('%B')} {opens.day}, {opens.year}"


def test_no_registration_start_opens_on_event_date(engine, organizer_user, student_client):
    event = dbh.create_event(engine, organizer_user, days_from_now=3, registration_start_days=None)
    assert "opens on" in _enroll(student_client, event).json()["detail"]


def test_registration_ended_rejects_enrollment(engine, organizer_user, student_client):
    event = dbh.create_event(engine, organizer_user, days_from_now=10, registration_start_days=-5, registration_end_days=-1)
    response = _enroll(student_client, event)
    assert response.status_code == 400
    assert "Registration for this event ended" in response.json()["detail"]


def test_participant_can_enroll_too(engine, organizer_user, participant_client):
    event = dbh.create_event(engine, organizer_user)
    assert _enroll(participant_client, event).status_code == 200


# ---------------------------------------------------------------- capacity (fully booked)
def test_full_event_rejects_enrollment(engine, organizer_user, new_client):
    event = dbh.create_event(engine, organizer_user, capacity=2)
    for _ in range(2):
        dbh.enroll(engine, event["id"], dbh.create_user(engine, "student")["id"])
    response = _enroll(new_client().login_as(dbh.create_user(engine, "student")), event)
    assert response.status_code == 400
    assert response.json()["detail"] == "This event is already full"


def test_capacity_cannot_go_below_enrolled(engine, organizer_user, organizer_client):
    event = dbh.create_event(engine, organizer_user, capacity=5)
    for _ in range(3):
        dbh.enroll(engine, event["id"], dbh.create_user(engine, "student")["id"])
    response = organizer_client.put(f"/api/events/{event['id']}", data=event_form(capacity="2"))
    assert response.status_code == 400
    assert "3 people already enrolled" in response.json()["detail"]


def test_last_slot_is_not_overbooked_under_concurrent_enrollment(engine, organizer_user, api_url):
    """Ten students press Enroll on the last free slot at the same moment: exactly one may get it."""
    event = dbh.create_event(engine, organizer_user, capacity=1)
    clients = [ApiClient(api_url).login_as(dbh.create_user(engine, "student")) for _ in range(10)]
    for c in clients:
        c.csrf_token()
    results, barrier = [], threading.Barrier(len(clients))

    def go(client):
        barrier.wait()
        results.append(_enroll(client, event).status_code)

    threads = [threading.Thread(target=go, args=(c,)) for c in clients]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    for c in clients:
        c.close()

    enrolled = dbh.scalar(engine, "SELECT COUNT(*) FROM registrations WHERE event_id = :e", e=event["id"])
    assert results.count(200) == 1, f"responses: {sorted(results)}"
    assert enrolled == 1, f"{enrolled} registrations for a capacity of 1 (overbooked)"


# ---------------------------------------------------------------- dates, times, auto-close
def test_finished_event_is_auto_closed(engine, organizer_user, student_client):
    event = dbh.create_event(engine, organizer_user, days_from_now=-1, registration_start_days=-5, registration_end_days=-1)
    assert student_client.get(f"/api/events/{event['id']}").json()["event"]["status"] == "closed"
    response = _enroll(student_client, event)
    assert response.status_code == 400 and "closed" in response.json()["detail"]


def test_event_today_closes_after_its_end_time(engine, organizer_user, student_client):
    now = datetime.now()
    if now.hour < 1 or now.hour >= 23:
        pytest.skip("needs an hour before and after now on the same day")
    earlier = (now - timedelta(minutes=30)).strftime("%H:%M")
    later = (now + timedelta(minutes=30)).strftime("%H:%M")
    start = (now - timedelta(minutes=60)).strftime("%H:%M")
    ended = dbh.create_event(engine, organizer_user, days_from_now=0, start=start, end=earlier, registration_start_days=-1)
    running = dbh.create_event(engine, organizer_user, days_from_now=0, start=start, end=later, registration_start_days=-1)
    assert student_client.get(f"/api/events/{ended['id']}").json()["event"]["status"] == "closed"
    assert student_client.get(f"/api/events/{running['id']}").json()["event"]["status"] == "open"


def test_moving_end_time_later_reopens_event(engine, organizer_user, organizer_client):
    event = dbh.create_event(engine, organizer_user, days_from_now=-1, registration_start_days=-5, registration_end_days=-1)
    assert organizer_client.get(f"/api/events/{event['id']}").json()["event"]["status"] == "closed"
    future = (date.today() + timedelta(days=3)).isoformat()
    response = organizer_client.put(f"/api/events/{event['id']}", data=event_form(event_date=future, registration_end=future))
    assert response.status_code == 200
    assert organizer_client.get(f"/api/events/{event['id']}").json()["event"]["status"] == "open"


@pytest.mark.parametrize("overrides,detail", [
    ({"event_time": "10:00", "event_end_time": "09:00"}, "End time must be after the start time"),
    ({"event_time": "10:00", "event_end_time": "10:00"}, "End time must be after the start time"),
    ({"registration_start": (date.today() + timedelta(days=30)).isoformat()}, "Registration must start on or before the event date"),
    ({"registration_end": (date.today() + timedelta(days=30)).isoformat()}, "Registration must end on or before the event date"),
    ({"registration_start": (date.today() + timedelta(days=5)).isoformat(),
      "registration_end": (date.today() + timedelta(days=2)).isoformat()}, "Registration end can't be before the registration start"),
    ({"registration_start": "2026-02-30"}, "Invalid registration start date"),
])
def test_schedule_validation(organizer_client, overrides, detail):
    response = organizer_client.post("/api/events", data=event_form(**overrides))
    assert response.status_code == 400
    assert response.json()["detail"] == detail


def test_event_in_the_past_is_rejected(organizer_client):
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    response = organizer_client.post("/api/events", data=event_form(
        event_date=yesterday, registration_start=yesterday, registration_end=yesterday))
    assert response.status_code == 400
    assert "already passed" in response.json()["detail"]


# ---------------------------------------------------------------- cancelling
def test_cancel_outside_registration_window_is_rejected(engine, organizer_user, new_client):
    student = dbh.create_user(engine, "student")
    event = dbh.create_event(engine, organizer_user, days_from_now=10, registration_start_days=-5, registration_end_days=-1)
    dbh.enroll(engine, event["id"], student["id"])
    response = new_client().login_as(student).delete(f"/api/events/{event['id']}/enroll")
    assert response.status_code == 400
    assert "registration period" in response.json()["detail"]


def test_cancel_after_attendance_recorded_is_rejected(engine, organizer_user, organizer_client, new_client):
    student = dbh.create_user(engine, "student")
    event = dbh.create_event(engine, organizer_user)
    registration_id = dbh.enroll(engine, event["id"], student["id"])
    organizer_client.put(f"/api/organizer/attendees/{registration_id}/attendance", json={"status": "present"})
    response = new_client().login_as(student).delete(f"/api/events/{event['id']}/enroll")
    assert response.status_code == 400


def test_cancel_when_not_enrolled_is_404(engine, organizer_user, student2_client):
    event = dbh.create_event(engine, organizer_user)
    assert student2_client.delete(f"/api/events/{event['id']}/enroll").status_code == 404
