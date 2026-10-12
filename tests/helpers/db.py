"""
Test database: create it if missing, load backend/database/schema.sql into it, and seed rows.

Only ever touches TEST_DB_URL, which config.assert_safe_test_database() has checked.
"""

import hashlib
import itertools
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
from sqlalchemy import create_engine, text

from .config import DEFAULT_PASSWORD, SCHEMA_SQL, TEST_DB_URL, assert_safe_test_database

_counter = itertools.count(1)


def create_database_if_missing() -> None:
    assert_safe_test_database()
    admin_engine = create_engine(TEST_DB_URL.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        exists = conn.execute(text("SELECT 1 FROM pg_database WHERE datname = :n"),
                              {"n": TEST_DB_URL.database}).first()
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{TEST_DB_URL.database}"'))
    admin_engine.dispose()


def reset_schema(engine) -> None:
    """Empty the test database and recreate the app's tables from schema.sql."""
    assert_safe_test_database()
    schema = SCHEMA_SQL.read_text(encoding="utf-8")
    raw = engine.raw_connection()
    try:
        cur = raw.cursor()
        cur.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
        cur.execute(schema)
        # Added at backend startup too (main.py add_missing_columns); idempotent
        cur.execute("ALTER TABLE pending_registrations ADD COLUMN IF NOT EXISTS employment_id VARCHAR(50)")
        raw.commit()
    finally:
        raw.close()


def make_engine():
    return create_engine(TEST_DB_URL, pool_pre_ping=True)


def unique_email(prefix: str = "user") -> str:
    return f"{prefix}.{next(_counter)}.{uuid.uuid4().hex[:6]}@example.com"


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode()[:72], bcrypt.gensalt(rounds=4)).decode()


def create_user(engine, role: str, *, email: str | None = None, password: str = DEFAULT_PASSWORD,
                full_name: str | None = None, department: str | None = "Information Technology",
                is_active: bool = True, with_role_row: bool = True, **profile) -> dict:
    """Insert a verified account the way /api/verify-email does (users + user_roles).
    Admins made by create_admin.py have no user_roles row: pass with_role_row=False."""
    email = email or unique_email(role)
    full_name = full_name or f"TEST {role.upper()} {next(_counter)}"
    with engine.begin() as conn:
        user_id = conn.execute(text("""
            INSERT INTO users (email, password, full_name, role, is_active)
            VALUES (:email, :pw, :name, :role, :active) RETURNING id
        """), {"email": email, "pw": hash_password(password), "name": full_name,
               "role": role, "active": is_active}).scalar()
        role_row_id = None
        if with_role_row:
            dept_id = None
            if department:
                dept_id = conn.execute(text("""
                    INSERT INTO departments (department_name) VALUES (:d)
                    ON CONFLICT (department_name) DO UPDATE SET department_name = EXCLUDED.department_name
                    RETURNING id
                """), {"d": department}).scalar()
            if role == "organizer":
                profile.setdefault("employment_id", f"EMP-{user_id:05d}")
            columns = ["user_id", "role_type", "department_id", *profile.keys()]
            role_row_id = conn.execute(text(f"""
                INSERT INTO user_roles ({", ".join(columns)})
                VALUES ({", ".join(":" + c for c in columns)}) RETURNING id
            """), {"user_id": user_id, "role_type": role, "department_id": dept_id, **profile}).scalar()
    return {"id": user_id, "email": email, "password": password, "full_name": full_name,
            "role": role, "user_role_id": role_row_id}


def create_event(engine, organizer: dict, *, name: str | None = None, days_from_now: int = 7,
                 start: str = "08:00", end: str | None = "17:00", capacity: int = 10,
                 registration_start_days: int | None = -1, registration_end_days: int | None = 0,
                 status: str = "open", venue: str = "Test Hall") -> dict:
    """Insert an event directly (for dates the API would reject or for speed).
    registration_*_days are relative to today; None leaves the column NULL.
    registration_end_days=0 means the registration ends on the event date."""
    today = datetime.now().date()
    event_date = today + timedelta(days=days_from_now)
    reg_start = today + timedelta(days=registration_start_days) if registration_start_days is not None else None
    reg_end = (event_date if registration_end_days == 0 else today + timedelta(days=registration_end_days)) \
        if registration_end_days is not None else None
    name = name or f"TEST EVENT {next(_counter)}"
    with engine.begin() as conn:
        event_id = conn.execute(text("""
            INSERT INTO events (user_role_id, event_name, event_description, event_date, event_time,
                                event_end_time, venue, capacity, status, department,
                                registration_start, registration_end)
            VALUES (:ur, :name, 'Created by the test suite', :d, :t, :te, :venue, :cap, :status,
                    'Information Technology', :rs, :re) RETURNING id
        """), {"ur": organizer["user_role_id"], "name": name, "d": event_date, "t": start, "te": end,
               "venue": venue, "cap": capacity, "status": status, "rs": reg_start, "re": reg_end}).scalar()
    return {"id": event_id, "name": name, "date": event_date.isoformat(), "capacity": capacity}


def enroll(engine, event_id: int, user_id: int) -> int:
    with engine.begin() as conn:
        return conn.execute(text("""
            INSERT INTO registrations (event_id, user_id, status) VALUES (:e, :u, 'confirmed') RETURNING id
        """), {"e": event_id, "u": user_id}).scalar()


def add_reset_token(engine, user_id: int, token: str, *, expires_in_minutes: int = 60, used: bool = False) -> None:
    """Stand-in for the emailed reset link: store the SHA-256 of a token we know (like the app does)."""
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO password_reset_tokens (user_id, token, expires_at, used)
            VALUES (:u, :t, :exp, :used)
        """), {"u": user_id, "t": sha256(token), "used": used,
               "exp": datetime.now(timezone.utc) + timedelta(minutes=expires_in_minutes)})


def create_pending(engine, role: str, email: str, token: str, *, password: str = DEFAULT_PASSWORD,
                   expired: bool = False, sent_seconds_ago: int = 0) -> None:
    """A sign-up waiting for its emailed link, as /api/register/<role> stores it. Inserted
    directly so verification tests don't use up the register rate limit (20 per IP / 10 min)."""
    with engine.begin() as conn:
        conn.execute(text(f"""
            INSERT INTO pending_registrations (email, full_name, role, password_hash, department,
                                               code_hash, expires_at, last_sent_at)
            VALUES (:e, 'PENDING USER', :role, :pw, :dept, :h,
                    NOW() {'-' if expired else '+'} INTERVAL '1 hour',
                    NOW() - make_interval(secs => :ago))
        """), {"e": email, "role": role, "pw": hash_password(password), "h": sha256(token), "ago": sent_seconds_ago,
               "dept": "Information Technology" if role == "student" else None})


def set_pending_token(engine, email: str, token: str, *, expired: bool = False) -> None:
    """Stand-in for the emailed verification link: replace the pending sign-up's token hash."""
    with engine.begin() as conn:
        conn.execute(text(f"""
            UPDATE pending_registrations SET code_hash = :h,
                   expires_at = NOW() {'-' if expired else '+'} INTERVAL '1 hour'
            WHERE email = :e
        """), {"h": sha256(token), "e": email})


def scalar(engine, sql: str, **params):
    with engine.connect() as conn:
        return conn.execute(text(sql), params).scalar()


def row(engine, sql: str, **params):
    with engine.connect() as conn:
        return conn.execute(text(sql), params).mappings().first()
