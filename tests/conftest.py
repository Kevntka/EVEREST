"""
Shared fixtures for the EVEREST test suite.

Session setup (once per run):
1. create the test database if it's missing (never the one in backend/.env),
2. wipe it and load backend/database/schema.sql,
3. start the real backend (uvicorn main:app) on TEST_BACKEND_PORT against that database,
4. seed one account per role and log each in once.
"""

import sys
from pathlib import Path

import os

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from helpers import db as dbh  # noqa: E402
from helpers.api import ApiClient  # noqa: E402
from helpers.config import BACKEND_PORT, FRESH_BACKEND_PORT, REPORTS_DIR  # noqa: E402
from helpers.server import BackendProcess  # noqa: E402


# ---------------------------------------------------------------- on/off switch
# The suite is turned OFF: every test is skipped before any fixture runs, so nothing
# touches the test database or starts a backend. Turn it back on for one run with
# EVEREST_TESTS_ENABLED=1 (see tests/README.md).
TESTS_ENABLED = os.getenv("EVEREST_TESTS_ENABLED") == "1"


def pytest_collection_modifyitems(config, items):
    if TESTS_ENABLED:
        return
    off = pytest.mark.skip(reason="tests are deactivated; set EVEREST_TESTS_ENABLED=1 to run them")
    for item in items:
        item.add_marker(off)


# ---------------------------------------------------------------- reports
@pytest.hookimpl(tryfirst=True)
def pytest_configure(config):
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    if hasattr(config.option, "htmlpath") and not config.option.htmlpath:
        config.option.htmlpath = str(REPORTS_DIR / "report.html")
        config.option.self_contained_html = True
    if not getattr(config.option, "xmlpath", None):
        config.option.xmlpath = str(REPORTS_DIR / "junit.xml")


# ---------------------------------------------------------------- database + backend
@pytest.fixture(scope="session")
def engine():
    dbh.create_database_if_missing()
    eng = dbh.make_engine()
    dbh.reset_schema(eng)
    yield eng
    eng.dispose()


@pytest.fixture(scope="session")
def mail_sink():
    """Local catch-all mail server, only when TEST_MAIL_SINK=1 (otherwise email stays off)."""
    if not os.getenv("TEST_MAIL_SINK"):
        yield None
        return
    from helpers.mailsink import MailSink
    sink = MailSink().start()
    yield sink
    sink.stop()


@pytest.fixture(scope="session")
def backend(engine, mail_sink):
    server = BackendProcess(BACKEND_PORT, "backend.log").start()
    yield server
    server.stop()


@pytest.fixture(scope="session")
def api_url(backend) -> str:
    return backend.url


@pytest.fixture
def fresh_backend(engine):
    """A brand-new backend process (empty in-memory rate-limit counters) for rate-limit tests."""
    server = BackendProcess(FRESH_BACKEND_PORT, "backend-fresh.log").start()
    yield server
    server.stop()


@pytest.fixture
def new_client(api_url):
    """Factory: new_client() -> logged-out ApiClient (closed after the test)."""
    clients = []

    def make(**kwargs) -> ApiClient:
        client = ApiClient(kwargs.pop("base_url", api_url), **kwargs)
        clients.append(client)
        return client

    yield make
    for client in clients:
        client.close()


@pytest.fixture
def anon(new_client) -> ApiClient:
    return new_client()


# ---------------------------------------------------------------- seeded accounts (one per role)
@pytest.fixture(scope="session")
def admin_user(engine):
    # Like create_admin.py: a users row with role 'admin' and no user_roles row
    return dbh.create_user(engine, "admin", with_role_row=False, department=None)


@pytest.fixture(scope="session")
def organizer_user(engine):
    return dbh.create_user(engine, "organizer", contact_number="0912-345-6789")


@pytest.fixture(scope="session")
def organizer2_user(engine):
    return dbh.create_user(engine, "organizer")


@pytest.fixture(scope="session")
def student_user(engine):
    return dbh.create_user(engine, "student", student_number="23-30046", year_level="2ND YEAR")


@pytest.fixture(scope="session")
def student2_user(engine):
    return dbh.create_user(engine, "student")


@pytest.fixture(scope="session")
def participant_user(engine):
    return dbh.create_user(engine, "participant", department=None)


def _logged_in(api_url, user):
    client = ApiClient(api_url).login_as(user)
    return client


@pytest.fixture(scope="session")
def admin_client(api_url, admin_user):
    client = _logged_in(api_url, admin_user)
    yield client
    client.close()


@pytest.fixture(scope="session")
def organizer_client(api_url, organizer_user):
    client = _logged_in(api_url, organizer_user)
    yield client
    client.close()


@pytest.fixture(scope="session")
def organizer2_client(api_url, organizer2_user):
    client = _logged_in(api_url, organizer2_user)
    yield client
    client.close()


@pytest.fixture(scope="session")
def student_client(api_url, student_user):
    client = _logged_in(api_url, student_user)
    yield client
    client.close()


@pytest.fixture(scope="session")
def student2_client(api_url, student2_user):
    client = _logged_in(api_url, student2_user)
    yield client
    client.close()


@pytest.fixture(scope="session")
def participant_client(api_url, participant_user):
    client = _logged_in(api_url, participant_user)
    yield client
    client.close()


# ---------------------------------------------------------------- events
@pytest.fixture
def open_event(engine, organizer_user):
    """An event in organizer_user's name, open for enrolling now, a week from today."""
    return dbh.create_event(engine, organizer_user)
