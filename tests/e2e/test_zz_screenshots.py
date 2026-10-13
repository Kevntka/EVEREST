"""
Screenshots for the QA Test Case Matrix (tests/EVEREST_QA_Test_Case_Matrix.xlsx, Image column).

Each test runs one matrix case in the real Angular app against the TEST backend/database
and saves tests/reports/screenshots/EVR_xxx.png. Accounts use the same emails and password
as the matrix's Test Data. Run only this file:

    tests/.venv/Scripts/python -m pytest tests/e2e/test_zz_screenshots.py -m screenshots
"""

import re
import secrets
from datetime import date, timedelta
from pathlib import Path

import pytest
from playwright.sync_api import expect

from helpers import db as dbh
from helpers.config import REPORTS_DIR

pytestmark = [pytest.mark.e2e, pytest.mark.screenshots]
SHOTS = REPORTS_DIR / "screenshots"
PWD = "Everest@2026"


def mail(tag):
    return f"{tag}@example.com"


@pytest.fixture(scope="session")
def acc(engine):
    """The matrix's test accounts, created once in the test database."""
    a = {
        "admin": dbh.create_user(engine, "admin", email=mail("admin"), password=PWD, full_name="EVEREST ADMIN",
                                 with_role_row=False),
        "org": dbh.create_user(engine, "organizer", email=mail("organizer"), password=PWD, full_name="ANA REYES",
                               department="Office of Student Affairs", employment_id="EMP-0101",
                               contact_number="0917-555-0101"),
        "org2": dbh.create_user(engine, "organizer", email=mail("organizer2"), password=PWD, full_name="CARLO MENDOZA",
                                department="College of Engineering", employment_id="EMP-0102"),
        "stu": dbh.create_user(engine, "student", email=mail("student"), password=PWD, full_name="JUAN DELA CRUZ",
                               student_number="23-30046", program="BS INFORMATION TECHNOLOGY", year_level="2ND YEAR",
                               gender="MALE", contact_number="0917-123-4567"),
        "stu2": dbh.create_user(engine, "student", email=mail("student2"), password=PWD, full_name="BEA VILLANUEVA"),
        "par": dbh.create_user(engine, "participant", email=mail("participant"), password=PWD, full_name="MARIA SANTOS",
                               department=None, address="BATANGAS CITY", gender="FEMALE",
                               contact_number="0918-222-3344"),
    }
    for extra in ("stu3", "par2", "org3"):
        role = {"stu3": "student", "par2": "participant", "org3": "organizer"}[extra]
        a[extra] = dbh.create_user(engine, role, email=mail(extra), password=PWD,
                                   full_name={"stu3": "MARK LOPEZ", "par2": "LEA BAUTISTA", "org3": "RAMON AQUINO"}[extra])
    a["seminar"] = dbh.create_event(engine, a["org"], name="Cybersecurity Awareness Seminar", venue="CICS AVR",
                                    capacity=50, days_from_now=10, start="13:00", end="16:00")
    dbh.create_event(engine, a["org2"], name="Engineering Career Fair", venue="Gymnasium", capacity=200, days_from_now=14)
    dbh.create_event(engine, a["org"], name="Leadership Training Workshop", venue="Function Hall", capacity=40,
                     days_from_now=20, registration_start_days=7)
    return a


def shot(app, case_id):
    SHOTS.mkdir(parents=True, exist_ok=True)
    if app.page.url.rstrip("/").endswith("/login"):
        # after a failed login the app resets the checkbox; wait until it's drawn again
        expect(app.page.locator("iframe[title='reCAPTCHA']:visible")).to_have_count(1, timeout=20_000)
        app.page.wait_for_timeout(1500)
    app.page.wait_for_timeout(400)  # let animations finish
    app.page.screenshot(path=str(SHOTS / f"{case_id}.png"))


# Google's documented reCAPTCHA v2 TEST site key: the real "I'm not a robot" widget, which a
# script can tick (no picture puzzle). It pairs with the test secret the test backend uses.
# https://developers.google.com/recaptcha/docs/faq
GOOGLE_TEST_SITE_KEY = "6LeIxAcTAAAAAJcZVRqyHh71UMIEGNQ_MXjiZKhI"
LOGIN_TS = Path(__file__).resolve().parents[2] / "frontend/event-registration/src/app/components/login/login.ts"
APP_SITE_KEY = re.search(r"recaptchaSiteKey: string = '([^']+)'", LOGIN_TS.read_text(encoding="utf-8")).group(1)


@pytest.fixture
def app(app, context):
    """Same as the e2e `app`, but with Google's real reCAPTCHA widget (test site key) instead
    of the stand-in, so screenshots show the real checkbox. Only the browser's copy of the
    app's JavaScript is changed (site key swapped); the source files are not touched."""
    context.route(re.compile(r"^https://www\.google\.com/recaptcha/api\.js.*"), lambda route: route.continue_())

    def swap_site_key(route):
        response = route.fetch()
        body = response.text()
        if APP_SITE_KEY in body:
            route.fulfill(response=response, body=body.replace(APP_SITE_KEY, GOOGLE_TEST_SITE_KEY))
        else:
            route.fulfill(response=response)

    context.route(re.compile(r"^http://localhost:4200/.*\.js(\?.*)?$"), swap_site_key)
    return app


def tick_recaptcha(app):
    """Click the visible "I'm not a robot" checkbox and wait for the green tick."""
    frames = app.page.locator("iframe[title='reCAPTCHA']")
    frames.first.wait_for(state="attached", timeout=20_000)
    for i in range(frames.count()):
        if frames.nth(i).is_visible():
            box = frames.nth(i).content_frame.locator("#recaptcha-anchor")
            box.click()
            expect(box).to_have_attribute("aria-checked", "true", timeout=20_000)
            return
    raise AssertionError("no visible reCAPTCHA widget")


def fill_login(app, email, password, *, tick=True):
    app.goto("/login")
    app.page.fill("#email", email)
    app.page.fill("#password", password)
    app.page.locator("iframe[title='reCAPTCHA']").first.wait_for(state="attached", timeout=20_000)
    if tick:
        tick_recaptcha(app)


def login_as(app, user, landing):
    fill_login(app, user["email"], PWD)
    app.page.click("button.btn-login")
    app.page.wait_for_url(f"**{landing}")


def assert_email_sent(to, subject_word):
    """The backend really sent it: the local test mail server (TEST_MAIL_SINK=1) caught it."""
    from helpers.mailsink import MailSink
    for _ in range(40):
        found = [m for m in MailSink.messages(to) if subject_word.lower() in str(m["Subject"]).lower()]
        if found:
            return found[-1]
        import time; time.sleep(0.25)
    raise AssertionError(f"no '{subject_word}' email to {to} was caught")


# ---------------------------------------------------------------- Login
@pytest.mark.parametrize("cid,who,landing", [("EVR_001", "admin", "/dashboard"),
                                              ("EVR_002", "org", "/organizer-dashboard"),
                                              ("EVR_003", "stu", "/student-dashboard"),
                                              ("EVR_004", "par", "/student-dashboard")])
def test_login_each_role(app, acc, cid, who, landing):
    login_as(app, acc[who], landing)
    app.page.wait_for_load_state("networkidle")
    shot(app, cid)


def test_005_wrong_password(app, acc):
    fill_login(app, acc["stu"]["email"], "Wrong@2026")
    app.page.click("button.btn-login")
    expect(app.page.locator(".error-message")).to_contain_text("Invalid email or password")
    shot(app, "EVR_005")


def test_006_unregistered(app, acc):
    fill_login(app, mail("notregistered"), PWD)
    app.page.click("button.btn-login")
    expect(app.page.locator(".error-message")).to_be_visible()
    shot(app, "EVR_006")


def test_007_no_recaptcha(app, acc):
    fill_login(app, acc["stu"]["email"], PWD, tick=False)
    app.page.click("button.btn-login")
    expect(app.page.locator(".error-message")).to_contain_text("reCAPTCHA")
    shot(app, "EVR_007")


def test_008_empty_fields(app, acc):
    app.goto("/login")
    app.page.locator("iframe[title='reCAPTCHA']").first.wait_for(state="attached", timeout=20_000)
    expect(app.page.locator("button.btn-login")).to_be_disabled()
    shot(app, "EVR_008")


def test_009_invalid_email(app, acc):
    fill_login(app, "juandelacruz.gmail.com", PWD)
    if app.page.locator("button.btn-login").is_enabled():
        app.page.click("button.btn-login")
    shot(app, "EVR_009")


def test_010_lockout(app, acc):
    for _ in range(5):
        fill_login(app, acc["stu2"]["email"], "Wrong@2026")
        app.page.click("button.btn-login")
        expect(app.page.locator(".error-message")).to_be_visible()
    fill_login(app, acc["stu2"]["email"], PWD)
    app.page.click("button.btn-login")
    expect(app.page.locator(".error-message")).to_contain_text("Too many failed login attempts")
    # the app resets the checkbox after a failed login; wait until it has re-appeared
    expect(app.page.locator("iframe[title='reCAPTCHA']:visible")).to_have_count(1, timeout=20_000)
    app.page.wait_for_timeout(1500)
    shot(app, "EVR_010")


# ---------------------------------------------------------------- Registration / verification / password
def _register_step_one(app, name, role):
    app.goto("/register")
    app.page.fill("input[name=fullName]", name)
    app.page.click("app-select[name=role]")
    app.page.click(f"li[role=option]:has-text('{role}')")
    app.page.click("button.btn-continue")


def test_016_weak_password(app, acc):
    _register_step_one(app, "Lea Bautista", "Participant")
    app.page.fill("#email", mail("weakpw"))
    app.page.fill("input[name=password]", "everest")
    app.page.fill("input[name=confirmPassword]", "everest")
    app.page.click("button.btn-register")
    expect(app.page.locator(".error-message")).to_contain_text("Password must have")
    shot(app, "EVR_016")


def test_017_strong_password(app, acc):
    _register_step_one(app, "Lea Bautista", "Participant")
    app.page.fill("#email", mail("strongpw"))
    app.page.fill("input[name=password]", PWD)
    app.page.fill("input[name=confirmPassword]", PWD)
    expect(app.page.locator(".password-note.met")).to_be_visible()
    shot(app, "EVR_017")


def test_019_duplicate_email(app, acc):
    _register_step_one(app, "Maria Santos", "Participant")
    app.page.fill("#email", acc["par"]["email"])
    app.page.fill("input[name=password]", PWD)
    app.page.fill("input[name=confirmPassword]", PWD)
    app.page.click("button.btn-register")
    expect(app.page.locator(".error-message")).to_contain_text("already registered")
    shot(app, "EVR_019")


def test_020_duplicate_employment_id(app, acc):
    app.goto("/register/organizer")
    p = app.page
    p.fill("input[name=fullName]", "Joy Ramos")
    p.fill("input[name=employmentId]", "EMP-0101")
    p.fill("input[name=email]", mail("organizer3"))
    p.fill("input[name=department]", "Office of Student Affairs")
    p.fill("input[name=password]", PWD)
    p.fill("input[name=confirmPassword]", PWD)
    p.click("button[type=submit]")
    expect(p.locator(".error-message")).to_contain_text("Employment ID")
    shot(app, "EVR_020")


def test_021_invalid_email(app, acc):
    _register_step_one(app, "Maria Santos", "Participant")
    app.page.fill("#email", "maria.santos@gmail")
    app.page.fill("input[name=password]", PWD)
    app.page.fill("input[name=confirmPassword]", PWD)
    if app.page.locator("button.btn-register").is_enabled():
        app.page.click("button.btn-register")
    shot(app, "EVR_021")


def test_023_024_verify_link(app, engine, acc):
    token = secrets.token_urlsafe(32)
    dbh.create_pending(engine, "student", mail("newstudent"), token, password=PWD)
    app.goto(f"/verify-email?token={token}")
    app.page.wait_for_load_state("networkidle")
    app.page.wait_for_timeout(800)
    shot(app, "EVR_023")
    app.goto(f"/verify-email?token={token}")
    app.page.wait_for_load_state("networkidle")
    app.page.wait_for_timeout(800)
    shot(app, "EVR_024")


def test_025_026_login_before_verifying(app, engine, acc):
    dbh.create_pending(engine, "participant", mail("newparticipant"), secrets.token_urlsafe(32), password=PWD)
    fill_login(app, mail("newparticipant"), PWD)
    app.page.click("button.btn-login")
    app.page.wait_for_url("**/verify-email**")
    app.page.wait_for_load_state("networkidle")
    app.page.wait_for_timeout(800)
    shot(app, "EVR_025")
    resend = app.page.locator(".resend-link, .resend-wait").first
    if app.page.locator(".resend-link").count():
        app.page.click(".resend-link")
        app.page.wait_for_timeout(800)
    shot(app, "EVR_026")


def test_028_forgot_unregistered(app, acc):
    app.goto("/forgot-password")
    app.page.fill("#email", mail("notregistered"))
    app.page.click("button.btn-confirm")
    app.page.wait_for_timeout(1500)
    shot(app, "EVR_028")


def test_029_reset_password(app, engine, acc):
    token = secrets.token_urlsafe(32)
    dbh.add_reset_token(engine, acc["stu3"]["id"], token)
    app.goto(f"/reset-password?token={token}")
    app.page.fill("input[name=newPassword]", "Everest@2027")
    app.page.fill("input[name=confirmPassword]", "Everest@2027")
    app.page.click("button.btn-submit")
    expect(app.page.locator(".dialog-title")).to_be_visible()
    shot(app, "EVR_029")


# ---------------------------------------------------------------- Admin
def _admin(app, acc):
    login_as(app, acc["admin"], "/dashboard")


def test_034_admin_edits_event(app, engine, acc):
    dbh.create_event(engine, acc["org"], name="Sports Fest Opening", venue="Oval", capacity=300)
    _admin(app, acc)
    app.page.locator(".events-table tbody tr", has_text="Sports Fest Opening").locator(".edit-btn").click()
    modal = app.page.locator("app-event-edit-modal")
    modal.locator("input[name=venue]").fill("Gymnasium")
    modal.locator("button.btn-create").click()
    expect(app.page.locator(".dialog-title")).to_have_text("Success!")
    shot(app, "EVR_034")


def test_035_admin_deletes_event(app, engine, acc):
    dbh.create_event(engine, acc["org"], name="Sample Event", venue="Room 101")
    _admin(app, acc)
    app.page.locator(".events-table tbody tr", has_text="Sample Event").locator(".delete-btn").click()
    app.confirm_dialog()
    expect(app.page.locator(".dialog-title")).to_have_text("Deleted!")
    shot(app, "EVR_035")


def test_036_admin_cancels_delete(app, engine, acc):
    dbh.create_event(engine, acc["org"], name="Keep This Event", venue="Room 102")
    _admin(app, acc)
    app.page.locator(".events-table tbody tr", has_text="Keep This Event").locator(".delete-btn").click()
    app.page.click(".dialog-btn--cancel")
    expect(app.page.locator(".events-table tbody tr", has_text="Keep This Event")).to_have_count(1)
    shot(app, "EVR_036")


def _admin_page(app, acc, nav):
    _admin(app, acc)
    app.page.click(f".nav-item:has-text('{nav}')")
    app.page.wait_for_load_state("networkidle")


def test_037_view_student(app, acc):
    _admin_page(app, acc, "Students")
    app.page.locator(".students-table tbody tr", has_text="JUAN DELA CRUZ").locator(".view-btn").click()
    expect(app.page.locator(".details-modal")).to_be_visible()
    shot(app, "EVR_037")


def test_038_edit_student(app, acc):
    _admin_page(app, acc, "Students")
    app.page.locator(".students-table tbody tr", has_text="JUAN DELA CRUZ").locator(".edit-btn").click()
    modal = app.page.locator(".edit-modal")
    modal.locator("app-select[name=yearLevel]").click()
    modal.locator("li[role=option]:has-text('3RD YEAR')").click()
    modal.locator("input[name=contactNumber]").fill("0918-765-4321")
    modal.locator("button.btn-create").click()
    expect(app.page.locator(".dialog-title")).to_have_text("Success!")
    shot(app, "EVR_038")


def test_040_delete_student(app, acc):
    _admin_page(app, acc, "Students")
    app.page.locator(".students-table tbody tr", has_text="BEA VILLANUEVA").locator(".delete-btn").click()
    app.confirm_dialog()
    expect(app.page.locator(".dialog-title")).to_have_text("Deleted!")
    shot(app, "EVR_040")


def test_041_search_students(app, acc):
    _admin_page(app, acc, "Students")
    app.page.fill(".search-input", "  juan dela  ")
    expect(app.page.locator(".students-table tbody tr")).to_have_count(1)
    shot(app, "EVR_041")


def test_043_edit_participant(app, acc):
    _admin_page(app, acc, "Participants")
    app.page.locator(".participants-table tbody tr", has_text="MARIA SANTOS").locator(".edit-btn").click()
    modal = app.page.locator(".edit-modal")
    modal.locator("input[name=address]").fill("Lipa City, Batangas")
    modal.locator("button.btn-create").click()
    expect(app.page.locator(".dialog-title")).to_have_text("Success!")
    shot(app, "EVR_043")


def test_044_edit_organizer(app, acc):
    _admin_page(app, acc, "Organizer")
    app.page.locator(".organizers-table tbody tr", has_text="ANA REYES").locator(".edit-btn").click()
    app.page.fill("input[name=contactNumber]", "0920-111-2233")
    app.page.locator("button.btn-create").click()
    expect(app.page.locator(".dialog-title")).to_have_text("Success!")
    shot(app, "EVR_044")


def test_045_delete_organizer(app, acc):
    _admin_page(app, acc, "Organizer")
    app.page.locator(".organizers-table tbody tr", has_text="CARLO MENDOZA").locator(".delete-btn").click()
    app.confirm_dialog()
    expect(app.page.locator(".dialog-title")).to_have_text("Deleted!")
    shot(app, "EVR_045")


# ---------------------------------------------------------------- Organizer
def _org_events(app, acc, who="org"):
    login_as(app, acc[who], "/organizer-dashboard")
    app.goto("/organizer-events")
    app.page.wait_for_load_state("networkidle")


def _fill_event(form, title, *, start="13:00", end="16:00", reg_end=None, venue="CICS AVR"):
    day = date.today() + timedelta(days=10)
    form.locator("input[name=title]").fill(title)
    form.locator("textarea[name=description]").fill("A seminar on staying safe online.")
    form.locator("input[name=registrationStart]").fill(date.today().isoformat())
    form.locator("input[name=registrationEnd]").fill(reg_end or day.isoformat())
    form.locator("input[name=time]").fill(start)
    form.locator("input[name=endTime]").fill(end)
    form.locator("input[name=date]").fill(day.isoformat())
    form.locator("input[name=capacity]").fill("50")
    form.locator("input[name=department]").fill("CICS")
    form.locator("input[name=venue]").fill(venue)


def test_047_create_event(app, acc):
    _org_events(app, acc)
    app.page.click("button.create-btn")
    form = app.page.locator(".create-event-modal")
    _fill_event(form, "Data Privacy Week Talk")
    form.locator("button.btn-create").click()
    expect(app.page.locator(".dialog-title")).to_have_text("Success!")
    shot(app, "EVR_047")


def test_048_missing_fields(app, acc):
    _org_events(app, acc)
    app.page.click("button.create-btn")
    app.page.locator(".create-event-modal button.btn-create").click()
    expect(app.page.locator(".dialog-title")).to_have_text("Check your input")
    shot(app, "EVR_048")


def test_049_end_before_start(app, acc):
    _org_events(app, acc)
    app.page.click("button.create-btn")
    form = app.page.locator(".create-event-modal")
    _fill_event(form, "Time Check Event", start="16:00", end="13:00")
    form.locator("button.btn-create").click()
    expect(app.page.locator(".dialog-message")).to_contain_text("End time must be after the start time")
    shot(app, "EVR_049")


def test_050_registration_after_event(app, acc):
    _org_events(app, acc)
    app.page.click("button.create-btn")
    form = app.page.locator(".create-event-modal")
    _fill_event(form, "Date Check Event")
    form.locator("input[name=registrationEnd]").fill((date.today() + timedelta(days=11)).isoformat())
    form.locator("button.btn-create").click()
    expect(app.page.locator(".dialog-title")).to_be_visible()
    shot(app, "EVR_050")


def test_051_non_image_cover(app, acc):
    _org_events(app, acc)
    app.page.click("button.create-btn")
    app.page.locator(".create-event-modal input[type=file]").set_input_files(
        files=[{"name": "syllabus.pdf", "mimeType": "application/pdf", "buffer": b"%PDF-1.4 test"}])
    expect(app.page.locator(".dialog-title")).to_be_visible()
    shot(app, "EVR_051")


def test_052_view_event(app, acc):
    _org_events(app, acc)
    app.page.locator(".events-table tbody tr", has_text="Cybersecurity Awareness Seminar").locator(".view-btn").click()
    expect(app.page.locator(".details-modal")).to_be_visible()
    shot(app, "EVR_052")


def test_053_edit_event(app, acc):
    _org_events(app, acc)
    app.page.locator(".events-table tbody tr", has_text="Cybersecurity Awareness Seminar").locator(".edit-btn").click()
    form = app.page.locator(".create-event-modal")
    form.locator("input[name=capacity]").fill("60")
    form.locator("button.btn-create").click()
    expect(app.page.locator(".dialog-title")).to_have_text("Success!")
    shot(app, "EVR_053")


def test_054_capacity_below_enrolled(app, engine, acc):
    event = dbh.create_event(engine, acc["org"], name="Small Group Workshop", venue="Room 201", capacity=5)
    for _ in range(3):
        dbh.enroll(engine, event["id"], dbh.create_user(engine, "student")["id"])
    _org_events(app, acc)
    app.page.locator(".events-table tbody tr", has_text="Small Group Workshop").locator(".edit-btn").click()
    form = app.page.locator(".create-event-modal")
    form.locator("input[name=capacity]").fill("2")
    form.locator("button.btn-create").click()
    expect(app.page.locator(".dialog-message")).to_contain_text("already enrolled")
    shot(app, "EVR_054")


def test_055_delete_event(app, engine, acc):
    dbh.create_event(engine, acc["org"], name="Cancelled Orientation", venue="Room 105")
    _org_events(app, acc)
    app.page.locator(".events-table tbody tr", has_text="Cancelled Orientation").locator(".delete-btn").click()
    app.confirm_dialog()
    expect(app.page.locator(".dialog-title")).to_have_text("Deleted!")
    shot(app, "EVR_055")


def test_056_attendance(app, engine, acc):
    event = dbh.create_event(engine, acc["org"], name="Attendance Demo Seminar", venue="CICS AVR")
    dbh.enroll(engine, event["id"], acc["stu"]["id"])
    _org_events(app, acc)
    app.page.locator(".events-table tbody tr", has_text="Attendance Demo Seminar").locator(".attendance-btn").click()
    row = app.page.locator(".attendance-table tbody tr", has_text="JUAN")
    row.locator(".present-btn").click()
    expect(row.locator(".present-btn.active")).to_be_visible()
    shot(app, "EVR_056")


def test_057_only_own_events(app, acc):
    _org_events(app, acc)
    expect(app.page.locator(".events-table tbody tr", has_text="Engineering Career Fair")).to_have_count(0)
    shot(app, "EVR_057")


# ---------------------------------------------------------------- Student / participant
def _event_page(app, acc, who, name):
    login_as(app, acc[who], "/student-dashboard")
    app.page.locator(".event-card", has_text=name).first.locator(".btn-view-details").click()
    app.page.wait_for_url("**/event/**")
    app.page.wait_for_load_state("networkidle")


def test_061_062_063_enroll_refresh_cancel(app, engine, acc):
    dbh.create_event(engine, acc["org"], name="Web Development Bootcamp", venue="Lab 3", capacity=30)
    _event_page(app, acc, "stu", "Web Development Bootcamp")
    app.page.click("button.enroll-btn")
    expect(app.page.locator(".dialog-title")).to_have_text("Success!")
    shot(app, "EVR_061")
    app.close_notice()
    app.page.reload()
    expect(app.page.locator(".enrolled-note")).to_be_visible()
    shot(app, "EVR_062")
    app.page.click("button.cancel-enroll-btn")
    app.confirm_dialog()
    expect(app.page.locator(".dialog-message")).to_contain_text("cancelled")
    shot(app, "EVR_063")


def test_064_full_event(app, engine, acc):
    event = dbh.create_event(engine, acc["org"], name="Exclusive Coding Clinic", venue="Lab 1", capacity=1)
    dbh.enroll(engine, event["id"], acc["stu3"]["id"])
    login_as(app, acc["par"], "/student-dashboard")
    app.goto(f"/event/{event['id']}")
    expect(app.page.locator("button.enroll-btn")).to_be_disabled()
    shot(app, "EVR_064")


def test_065_upcoming_event(app, acc):
    login_as(app, acc["stu"], "/student-dashboard")
    app.page.locator(".event-card", has_text="Leadership Training Workshop").first.locator(".btn-view-details").click()
    app.page.wait_for_url("**/event/**")
    expect(app.page.locator("button.enroll-btn")).to_be_disabled()
    shot(app, "EVR_065")


def test_067_edit_profile(app, acc):
    login_as(app, acc["stu"], "/student-dashboard")
    app.goto("/student-profile")
    app.page.wait_for_load_state("networkidle")
    app.page.click("button.edit-btn")
    app.page.locator("input.detail-input").nth(3).fill("BS Information Technology")
    app.page.click("button.edit-btn")
    expect(app.page.locator(".dialog-title")).to_have_text("Success!")
    shot(app, "EVR_067")


# ---------------------------------------------------------------- Security
def test_070_student_opens_admin_page(app, acc):
    login_as(app, acc["stu"], "/student-dashboard")
    app.goto("/students")
    app.page.wait_for_url("**/student-dashboard")
    shot(app, "EVR_070")


def test_071_after_sign_out(app, acc):
    login_as(app, acc["par"], "/student-dashboard")
    app.sign_out()
    app.goto("/my-events")
    app.page.wait_for_url("**/login")
    shot(app, "EVR_071")


def test_072_html_in_title(app, engine, acc):
    dbh.create_event(engine, acc["org"], name="<b>Bold</b><script>alert(1)</script>", venue="Room 300")
    dialogs = []
    app.page.on("dialog", lambda d: (dialogs.append(d.message), d.dismiss()))
    _admin(app, acc)
    expect(app.page.locator(".events-table tbody tr", has_text="<script>")).to_have_count(1)
    assert dialogs == []
    shot(app, "EVR_072")


def test_075_search_with_spaces(app, acc):
    _admin_page(app, acc, "Participants")
    app.page.fill(".search-input", " maria")
    expect(app.page.locator(".participants-table tbody tr", has_text="MARIA SANTOS")).to_have_count(1)
    shot(app, "EVR_074")



# ---------------------------------------------------------------- rows that were left for manual testing
def test_011_show_hide_password(app, acc):
    fill_login(app, acc["stu"]["email"], PWD, tick=False)
    app.page.click("button.password-toggle")
    expect(app.page.locator("#password")).to_have_attribute("type", "text")
    shot(app, "EVR_011")


def test_012_logged_in_opens_login(app, acc):
    login_as(app, acc["stu"], "/student-dashboard")
    app.goto("/login")
    app.page.wait_for_url("**/student-dashboard")
    app.page.wait_for_load_state("networkidle")
    shot(app, "EVR_012")


def test_013_register_student(app, acc, mail_sink):
    _register_step_one(app, "Paolo Garcia", "Student")
    app.page.wait_for_url("**/register/student")
    app.page.fill("#email", mail("newstudent2"))
    app.page.fill("#department", "Information Technology")
    app.page.fill("input[name=password]", PWD)
    app.page.fill("input[name=confirmPassword]", PWD)
    app.page.click("button.btn-register")
    app.page.wait_for_url("**/verify-email**")
    app.page.wait_for_load_state("networkidle")
    assert_email_sent(mail("newstudent2"), "verif")
    shot(app, "EVR_013")


def test_014_register_participant(app, acc, mail_sink):
    _register_step_one(app, "Lea Bautista", "Participant")
    app.page.fill("#email", mail("newparticipant2"))
    app.page.fill("input[name=contactNumber]", "09171234567")
    app.page.fill("input[name=password]", PWD)
    app.page.fill("input[name=confirmPassword]", PWD)
    app.page.click("button.btn-register")
    app.page.wait_for_url("**/verify-email**")
    app.page.wait_for_load_state("networkidle")
    assert_email_sent(mail("newparticipant2"), "verif")
    shot(app, "EVR_014")


def test_015_register_organizer(app, acc, mail_sink):
    app.goto("/login")
    app.page.click("a:has-text('Register here')")
    app.page.wait_for_url("**/register/organizer")
    p = app.page
    p.fill("input[name=fullName]", "Ramon Aquino")
    p.fill("input[name=employmentId]", "EMP-0103")
    p.fill("input[name=email]", mail("neworganizer"))
    p.fill("input[name=department]", "Office of Student Affairs")
    p.fill("input[name=password]", PWD)
    p.fill("input[name=confirmPassword]", PWD)
    p.click("button.btn-register")
    p.wait_for_url("**/verify-email**")
    p.wait_for_load_state("networkidle")
    assert_email_sent(mail("neworganizer"), "verif")
    shot(app, "EVR_015")


def test_018_passwords_do_not_match(app, acc):
    _register_step_one(app, "Lea Bautista", "Participant")
    app.page.fill("#email", mail("mismatch"))
    app.page.fill("input[name=password]", "Everest@2026")
    app.page.fill("input[name=confirmPassword]", "Everest@2027")
    if app.page.locator("button.btn-register").is_enabled():
        app.page.click("button.btn-register")
    shot(app, "EVR_018")


def test_022_empty_required_fields(app, acc):
    app.goto("/register")
    expect(app.page.locator("button.btn-continue")).to_be_disabled()
    shot(app, "EVR_022")


def test_027_forgot_password(app, acc, mail_sink):
    app.goto("/forgot-password")
    app.page.fill("#email", acc["stu"]["email"])
    app.page.click("button.btn-confirm")
    app.page.wait_for_url("**/check-email**")
    app.page.wait_for_load_state("networkidle")
    assert_email_sent(acc["stu"]["email"], "password")
    shot(app, "EVR_027")


def test_030_reuse_reset_link(app, engine, acc):
    token = secrets.token_urlsafe(32)
    dbh.add_reset_token(engine, acc["par2"]["id"], token, used=True)
    app.goto(f"/reset-password?token={token}")
    app.page.fill("input[name=newPassword]", "Everest@2028")
    app.page.fill("input[name=confirmPassword]", "Everest@2028")
    app.page.click("button.btn-submit")
    app.page.wait_for_timeout(1500)
    shot(app, "EVR_030")


def test_031_change_password(app, acc, mail_sink):
    login_as(app, acc["org"], "/organizer-dashboard")
    app.page.click("button.user-dropdown")
    app.page.click(".dropdown-item:has-text('Change Password')")
    expect(app.page.locator(".dialog-title")).to_be_visible()
    app.confirm_dialog()
    expect(app.page.locator(".dialog-title")).to_be_visible()
    app.page.wait_for_timeout(1000)
    assert_email_sent(acc["org"]["email"], "password")
    shot(app, "EVR_031")


def test_032_dashboard_stats(app, acc):
    _admin(app, acc)
    app.page.wait_for_load_state("networkidle")
    app.page.wait_for_timeout(1000)
    shot(app, "EVR_032")


def test_033_admin_views_event(app, acc):
    _admin(app, acc)
    row = app.page.locator(".events-table tbody tr", has_text="Cybersecurity Awareness Seminar")
    row.locator(".view-btn").click()
    app.page.wait_for_url("**/event/**")
    app.page.wait_for_load_state("networkidle")
    shot(app, "EVR_033")


def test_039_invalid_sr_code(app, acc):
    _admin_page(app, acc, "Students")
    app.page.locator(".students-table tbody tr", has_text="JUAN DELA CRUZ").locator(".edit-btn").click()
    modal = app.page.locator(".edit-modal")
    modal.locator("input[name=srCode]").fill("2330046")
    if modal.locator("button.btn-create").is_enabled():
        modal.locator("button.btn-create").click()
    shot(app, "EVR_039")


def test_042_filter_department(app, engine, acc):
    dbh.create_user(engine, "student", email=mail("engstudent"), password=PWD, full_name="NICO RIVERA",
                    department="Mechanical Engineering")
    _admin_page(app, acc, "Students")
    app.page.click("app-select.department-select")
    app.page.click("li[role=option]:has-text('Information Technology')")
    expect(app.page.locator(".students-table tbody tr", has_text="NICO RIVERA")).to_have_count(0)
    shot(app, "EVR_042")


def test_046_pagination(app, engine, acc):
    for i in range(12):
        dbh.create_user(engine, "participant", email=mail(f"pagetest{i}"), password=PWD,
                        full_name=f"PAGE TEST PARTICIPANT {i + 1:02d}", department=None)
    _admin_page(app, acc, "Participants")
    app.page.locator(".pagination-btn[aria-label='Next page']").click()
    expect(app.page.locator(".pagination-info")).to_contain_text("2 of")
    shot(app, "EVR_046")


def test_058_org_search_filter(app, acc):
    _org_events(app, acc)
    app.page.fill(".search-input", "cyber")
    app.page.click("app-select.status-select")
    app.page.click("li[role=option]:has-text('Open')")
    expect(app.page.locator(".events-table tbody tr", has_text="Cybersecurity")).to_have_count(1)
    shot(app, "EVR_058")


def test_059_student_dashboard_lists(app, acc):
    login_as(app, acc["stu"], "/student-dashboard")
    app.page.wait_for_load_state("networkidle")
    app.page.wait_for_timeout(800)
    shot(app, "EVR_059")


def test_060_student_search_filter(app, acc):
    login_as(app, acc["stu"], "/student-dashboard")
    app.page.locator(".search-input").first.fill("seminar")
    app.page.locator("app-select.status-select").first.click()
    app.page.click("li[role=option]:has-text('Open')")
    app.page.wait_for_timeout(500)
    shot(app, "EVR_060")


def test_066_my_events_tabs(app, engine, acc, api_url):
    from helpers.api import ApiClient
    event = dbh.create_event(engine, acc["org"], name="Completed Orientation", venue="Main Hall", days_from_now=3)
    reg = dbh.enroll(engine, event["id"], acc["par"]["id"])
    organizer = ApiClient(api_url).login_as({"email": acc["org"]["email"], "password": PWD})
    assert organizer.put(f"/api/organizer/attendees/{reg}/attendance", json={"status": "present"}).status_code == 200
    organizer.close()
    login_as(app, acc["par"], "/student-dashboard")
    app.goto("/my-events")
    app.page.wait_for_load_state("networkidle")
    app.page.click("button.tab:has-text('Completed')")
    app.page.wait_for_timeout(500)
    shot(app, "EVR_066")


def _tiny_png(w=200, h=200):
    import struct
    import zlib
    raw = b"".join(b"\x00" + bytes([220, 53, 69]) * w for _ in range(h))

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def test_068_upload_profile_picture(app, acc):
    login_as(app, acc["stu"], "/student-dashboard")
    app.goto("/student-profile")
    app.page.wait_for_load_state("networkidle")
    app.page.locator("input[type=file]").set_input_files(
        files=[{"name": "juan.png", "mimeType": "image/png", "buffer": _tiny_png()}])
    expect(app.page.locator(".dialog-title")).to_be_visible()
    shot(app, "EVR_068")


def test_069_participant_profile(app, acc):
    login_as(app, acc["par"], "/student-dashboard")
    app.goto("/student-profile")
    app.page.wait_for_load_state("networkidle")
    app.page.wait_for_timeout(800)
    shot(app, "EVR_069")


def test_073_dark_mode(app, acc):
    login_as(app, acc["stu"], "/student-dashboard")
    app.page.click("button.user-dropdown")
    app.page.click(".dropdown-item:has-text('Dark Mode')")
    app.page.reload()
    app.page.wait_for_load_state("networkidle")
    expect(app.page.locator("body.dark-mode")).to_have_count(1)
    shot(app, "EVR_073")
