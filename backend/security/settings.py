"""
Security settings, read once from backend/.env.

Secrets have no fallback values in the code: if JWT_SECRET_KEY or DATABASE_URL is
missing (or still the placeholder), the server refuses to start instead of running
with a guessable key.
"""

import os
from dotenv import load_dotenv

load_dotenv()


def _flag(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


def _required(name: str) -> str:
    value = (os.getenv(name) or "").strip()
    if not value or value.startswith("your-") or "username:password" in value:
        raise RuntimeError(
            f"{name} is not set in backend/.env. Copy .env.example to .env and fill it in."
        )
    return value


JWT_SECRET_KEY = _required("JWT_SECRET_KEY")
if len(JWT_SECRET_KEY) < 32:
    raise RuntimeError(
        "JWT_SECRET_KEY must be at least 32 characters. Generate one with:\n"
        '  python -c "import secrets; print(secrets.token_urlsafe(48))"'
    )

DATABASE_URL = _required("DATABASE_URL")

# Where the Angular app runs. Used for CORS, the Origin check, and email links.
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:4200").rstrip("/")
ALLOWED_ORIGINS = [
    origin.strip().rstrip("/")
    for origin in os.getenv("ALLOWED_ORIGINS", f"{FRONTEND_URL},http://127.0.0.1:4200").split(",")
    if origin.strip()
]

# HTTPS_ONLY=true when the site is served over HTTPS: cookies get the Secure flag,
# browsers get HSTS, and plain-HTTP requests are redirected to HTTPS.
HTTPS_ONLY = _flag("HTTPS_ONLY", False)

# Interactive API docs (/docs, /redoc). Turn off in production.
ENABLE_API_DOCS = _flag("ENABLE_API_DOCS", True)

# Print every SQL statement (and its parameters) to the console. Off by default
# because the parameters include password hashes and personal data.
SQL_ECHO = _flag("SQL_ECHO", False)
