"""
Test configuration and safety guards.

Everything the suite talks to is read here:
- backend/.env           -> only to find the PostgreSQL server and the *production* database
                            name (so the guard can refuse to touch it). Values are never printed.
- tests/.env.test        -> optional overrides (see tests/.env.test.example).

The suite never uses the production database: it runs its own backend process against a
separate database whose name must end in "_test" (default: <prod name>_test, e.g. ers_db_test).
"""

import os
import secrets
from pathlib import Path

from dotenv import dotenv_values, load_dotenv
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"
TESTS_DIR = ROOT / "tests"
REPORTS_DIR = TESTS_DIR / "reports"
SCHEMA_SQL = BACKEND_DIR / "database" / "schema.sql"

load_dotenv(TESTS_DIR / ".env.test")  # optional; real environment variables win

_backend_env = dotenv_values(BACKEND_DIR / ".env")
_prod_url_text = _backend_env.get("DATABASE_URL") or ""
if not _prod_url_text:
    raise RuntimeError("backend/.env has no DATABASE_URL; the tests need it to find the PostgreSQL server.")
PROD_DB_URL = make_url(_prod_url_text)

_test_url_text = os.getenv("TEST_DATABASE_URL")
TEST_DB_URL = make_url(_test_url_text) if _test_url_text else PROD_DB_URL.set(database=f"{PROD_DB_URL.database}_test")


def assert_safe_test_database() -> None:
    """Refuse to run against anything that could be real data."""
    name = TEST_DB_URL.database or ""
    if not name.endswith("_test"):
        raise RuntimeError(f"Refusing to use database '{name}': the test database name must end in '_test'.")
    if (TEST_DB_URL.host, TEST_DB_URL.port, name) == (PROD_DB_URL.host, PROD_DB_URL.port, PROD_DB_URL.database):
        raise RuntimeError("Refusing to run: the test database is the same as the one in backend/.env.")
    if TEST_DB_URL.host not in ("localhost", "127.0.0.1", "::1"):
        raise RuntimeError(f"Refusing to run: the test database host '{TEST_DB_URL.host}' is not local.")


assert_safe_test_database()

# The backend under test runs on its own port so the developer's backend (:8000) keeps running.
BACKEND_HOST = "127.0.0.1"
BACKEND_PORT = int(os.getenv("TEST_BACKEND_PORT", "8001"))
FRESH_BACKEND_PORT = int(os.getenv("TEST_FRESH_BACKEND_PORT", "8002"))  # rate-limit tests
API_URL = f"http://{BACKEND_HOST}:{BACKEND_PORT}"

# The Angular dev server (npm start). Its code calls http://localhost:8000 (hardcoded);
# browser tests reroute those calls to the test backend.
FRONTEND_URL = os.getenv("TEST_FRONTEND_URL", "http://localhost:4200").rstrip("/")
APP_API_PREFIX = "http://localhost:8000"
ORIGIN = "http://localhost:4200"  # an allowed origin (security/settings.py ALLOWED_ORIGINS default)

# Google's documented reCAPTCHA v2 *test* secret: every verification passes
# (https://developers.google.com/recaptcha/docs/faq). Used only by the test backend.
RECAPTCHA_TEST_SECRET = "6LeIxAcTAAAAAGG-vFI1TnRWxMZNFuojJ4WifJWe"
RECAPTCHA_TEST_TOKEN = "pytest-recaptcha-token"

# A random JWT secret per test run (never the real one from backend/.env).
JWT_TEST_SECRET = os.getenv("TEST_JWT_SECRET_KEY") or secrets.token_urlsafe(48)

# Password that meets every rule (8+ chars, upper, lower, number, symbol).
DEFAULT_PASSWORD = "Test-Pass1!"

BACKEND_PYTHON = BACKEND_DIR / "venv" / "Scripts" / "python.exe"
if not BACKEND_PYTHON.exists():  # macOS / Linux venv layout
    BACKEND_PYTHON = BACKEND_DIR / "venv" / "bin" / "python"


def backend_env() -> dict:
    """Environment for the backend under test. load_dotenv() in the backend doesn't override
    variables that are already set, so these win over backend/.env."""
    env = dict(os.environ)
    env.update({
        "DATABASE_URL": TEST_DB_URL.render_as_string(hide_password=False),
        "JWT_SECRET_KEY": JWT_TEST_SECRET,
        "RECAPTCHA_SECRET_KEY": RECAPTCHA_TEST_SECRET,
        "EMAIL_ENABLED": "false",      # no real emails; tests read tokens from the test DB
        "BREVO_API_KEY": "",
        "HTTPS_ONLY": "false",
        "FRONTEND_URL": "http://localhost:4200",
        "ALLOWED_ORIGINS": "http://localhost:4200,http://127.0.0.1:4200",
        "ENABLE_API_DOCS": "false",
        "SQL_ECHO": "false",
        "PYTHONIOENCODING": "utf-8",   # the routes print emoji (cp1252 would fail requests)
        "PYTHONUNBUFFERED": "1",
    })
    return env
