"""
Browser tests (Playwright): login flows, route guards, navigation, dashboards, forms,
CRUD through the UI, search, persistence after reload, and XSS rendering.
"""

from datetime import date, timedelta

import pytest
from playwright.sync_api import expect

from helpers import db as dbh

pytestmark = pytest.mark.e2e


# ---------------------------------------------------------------- route guards + login
@pytest.mark.parametrize("path", ["/dashboard", "/organizer-events", "/student-dashboard", "/my-events", "/students"])
def test_protected_pages_redirect_to_login_when_signed_out(app, path):
    app.goto(path)
    app.page.wait_for_url("**/login")


def test_login_page_renders(app):
    app.goto("/login")
    expect(app.page.locator("#email")).to_be_visible()
    expect(app.page.locator("#password")).to_be_visible()
    expect(app.page.locator("button.btn-login")).to_be_disabled()  # empty form


def test_wrong_password_shows_error(app, engine):
    user = dbh.create_user(engine, "student")
    app.login({**user, "password": "Wrong-Pass1!"})
    expect(app.page.locator(".error-message")).to_contain_text("Invalid email or password")
    assert app.page.url.endswith("/login")


@pytest.mark.parametrize("role,landing", [("admin", "/dashboard"), ("organizer", "/organizer-dashboard"),
                                          ("student", "/student-dashboard"), ("participant", "/student-dashboard")])
def test_each_role_lands_on_its_dashboard(app, engine, role, landing):
    user = dbh.create_user(engine, role, with_role_row=role != "admin")
    app.login(user, expect_path=landing)


def test_role_guard_blocks_other_roles_pages(app, engine):
    app.login(dbh.create_user(engine, "student"), expect_path="/student-dashboard")
    app.goto("/dashboard")
    app.page.wait_for_url("**/student-dashboard")


def test_sign_out_ends_session(app, engine):
    app.login(dbh.create_user(engine, "student"), expect_path="/student-dashboard")
    app.sign_out()
    app.goto("/my-events")
    app.page.wait_for_url("**/login")


# ---------------------------------------------------------------- student flow
def test_student_enrolls_and_sees_event_after_reload(app, engine, organizer_user):
    event = dbh.create_event(engine, organizer_user, name="E2E Enroll Event")
    app.login(dbh.create_user(engine, "student"), expect_path="/student-dashboard")

    card = app.page.locator(".event-card", has_text="E2E Enroll Event")
    card.locator(".btn-view-details").click()
    app.page.wait_for_url(f"**/event/{event['id']}")
    app.page.click("button.enroll-btn")
    app.close_notice()
    expect(app.page.locator(".enrolled-note")).to_be_visible()

    app.page.reload()  # persisted on the server, not just in the page
    expect(app.page.locator(".enrolled-note")).to_be_visible()

    app.page.click(".nav-item:has-text('My Events')")
    app.page.wait_for_url("**/my-events")
    expect(app.page.locator(".my-events-table tbody tr", has_text="E2E Enroll Event")).to_have_count(1)


def test_full_event_cannot_be_enrolled_in_ui(app, engine, organizer_user):
    event = dbh.create_event(engine, organizer_user, name="E2E Full Event", capacity=1)
    dbh.enroll(engine, event["id"], dbh.create_user(engine, "student")["id"])
    app.login(dbh.create_user(engine, "student"), expect_path="/student-dashboard")
    app.goto(f"/event/{event['id']}")
    expect(app.page.locator("button.enroll-btn")).to_be_disabled()


def test_student_dashboard_search_filters_cards(app, engine, organizer_user):
    dbh.create_event(engine, organizer_user, name="Zebra Unique Search")
    dbh.create_event(engine, organizer_user, name="Other Search Event")
    app.login(dbh.create_user(engine, "student"), expect_path="/student-dashboard")
    search = app.page.locator(".search-input").first
    search.fill("  zebra unique ")
    expect(app.page.locator(".event-card", has_text="Zebra Unique Search").first).to_be_visible()
    expect(app.page.locator(".event-card", has_text="Other Search Event")).to_have_count(0)


# ---------------------------------------------------------------- organizer flow
def test_organizer_creates_event_through_form_and_it_persists(app, engine):
    organizer = dbh.create_user(engine, "organizer")
    app.login(organizer, expect_path="/organizer-dashboard")
    app.goto("/organizer-events")
    app.page.click("button.create-btn")

    event_day = date.today() + timedelta(days=10)
    form = app.page.locator(".create-event-modal")
    form.locator("input[name=title]").fill("UI Created Event")
    form.locator("textarea[name=description]").fill("Made by Playwright")
    form.locator("input[name=registrationStart]").fill(date.today().isoformat())
    form.locator("input[name=registrationEnd]").fill(event_day.isoformat())
    form.locator("input[name=time]").fill("09:00")
    form.locator("input[name=endTime]").fill("12:00")
    form.locator("input[name=date]").fill(event_day.isoformat())
    form.locator("input[name=capacity]").fill("25")
    form.locator("input[name=department]").fill("Information Technology")
    form.locator("input[name=venue]").fill("Room 101")
    form.locator("button.btn-create").click()
    expect(app.page.locator(".dialog-title")).to_have_text("Success!")
    app.close_notice()

    row = app.page.locator(".events-table tbody tr", has_text="UI Created Event")
    expect(row).to_have_count(1)
    app.page.reload()
    expect(row).to_have_count(1)
    assert dbh.scalar(engine, "SELECT capacity FROM events WHERE event_name = 'UI Created Event'") == 25


def test_organizer_form_validation_message(app, engine):
    app.login(dbh.create_user(engine, "organizer"), expect_path="/organizer-dashboard")
    app.goto("/organizer-events")
    app.page.click("button.create-btn")
    app.page.locator(".create-event-modal button.btn-create").click()
    expect(app.page.locator(".dialog-title")).to_have_text("Check your input")


def test_organizer_view_modal_shows_entered_fields(app, engine):
    organizer = dbh.create_user(engine, "organizer")
    dbh.create_event(engine, organizer, name="View Modal Event", venue="Auditorium X")
    app.login(organizer, expect_path="/organizer-dashboard")
    app.goto("/organizer-events")
    app.page.locator(".events-table tbody tr", has_text="View Modal Event").locator(".view-btn").click()
    modal = app.page.locator(".details-modal")
    expect(modal.locator(".details-name")).to_have_text("View Modal Event")
    expect(modal).to_contain_text("Auditorium X")
    app.page.keyboard.press("Escape")
    expect(modal).to_have_count(0)


# ---------------------------------------------------------------- admin flow
def test_admin_deletes_event_with_confirmation(app, engine, organizer_user):
    dbh.create_event(engine, organizer_user, name="Admin Delete Me")
    app.login(dbh.create_user(engine, "admin", with_role_row=False), expect_path="/dashboard")
    row = app.page.locator(".events-table tbody tr", has_text="Admin Delete Me")
    row.locator(".delete-btn").click()
    expect(app.page.locator(".dialog-message")).to_contain_text("delete this event")
    app.confirm_dialog()
    expect(app.page.locator(".dialog-title")).to_have_text("Deleted!")
    app.close_notice()
    expect(row).to_have_count(0)
    assert dbh.scalar(engine, "SELECT COUNT(*) FROM events WHERE event_name = 'Admin Delete Me'") == 0


def test_admin_cancel_keeps_event(app, engine, organizer_user):
    dbh.create_event(engine, organizer_user, name="Admin Keep Me")
    app.login(dbh.create_user(engine, "admin", with_role_row=False), expect_path="/dashboard")
    app.page.locator(".events-table tbody tr", has_text="Admin Keep Me").locator(".delete-btn").click()
    app.page.click(".dialog-btn--cancel")
    expect(app.page.locator(".events-table tbody tr", has_text="Admin Keep Me")).to_have_count(1)


def test_admin_students_search_and_view(app, engine):
    dbh.create_user(engine, "student", full_name="QUENTIN UNIQUE NAME")
    app.login(dbh.create_user(engine, "admin", with_role_row=False), expect_path="/dashboard")
    app.page.click(".nav-item:has-text('Students')")
    app.page.wait_for_url("**/students")
    app.page.fill(".search-input", " quentin unique ")
    rows = app.page.locator(".students-table tbody tr")
    expect(rows).to_have_count(1)
    rows.first.locator(".view-btn").click()
    expect(app.page.locator(".details-modal .details-name")).to_have_text("QUENTIN UNIQUE NAME")


# ---------------------------------------------------------------- registration form
def test_registration_requires_strong_password(app):
    app.goto("/register")
    app.page.fill("input[name=fullName]", "Juan Dela Cruz")
    app.page.click("app-select[name=role]")
    app.page.click("li[role=option]:has-text('Participant')")
    app.page.click("button.btn-continue")
    app.page.wait_for_url("**/register/participant")
    app.page.fill("#email", dbh.unique_email("e2ereg"))
    app.page.fill("input[name=password]", "weakpass")
    app.page.fill("input[name=confirmPassword]", "weakpass")
    expect(app.page.locator(".strength-label")).to_have_text("Weak")
    app.page.click("button.btn-register")
    expect(app.page.locator(".error-message")).to_contain_text("Password must have")


def test_registration_success_goes_to_verify_page(app, engine):
    email = dbh.unique_email("e2eok")
    app.goto("/register")
    app.page.fill("input[name=fullName]", "Maria Clara")
    app.page.click("app-select[name=role]")
    app.page.click("li[role=option]:has-text('Participant')")
    app.page.click("button.btn-continue")
    app.page.fill("#email", email)
    app.page.fill("input[name=password]", "Strong-Pass1!")
    app.page.fill("input[name=confirmPassword]", "Strong-Pass1!")
    expect(app.page.locator(".password-note.met")).to_be_visible()
    app.page.click("button.btn-register")
    app.page.wait_for_url("**/verify-email**")
    assert dbh.scalar(engine, "SELECT role FROM pending_registrations WHERE email = :e", e=email) == "participant"


# ---------------------------------------------------------------- XSS rendering
def test_event_name_with_html_renders_as_text(app, engine, organizer_user):
    payload = '<img src=x onerror="window.__xss=1">XSS Probe'
    dbh.create_event(engine, organizer_user, name=payload)
    dialogs = []
    app.page.on("dialog", lambda d: (dialogs.append(d.message), d.dismiss()))
    app.login(dbh.create_user(engine, "admin", with_role_row=False), expect_path="/dashboard")
    expect(app.page.locator(".events-table tbody tr", has_text="XSS Probe")).to_have_count(1)
    assert app.page.evaluate("window.__xss") is None
    assert app.page.locator(".events-table img[src=x]").count() == 0
    assert dialogs == []
