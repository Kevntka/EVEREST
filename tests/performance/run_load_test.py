"""
Run the load test safely against the TEST database.

    tests/.venv/Scripts/python tests/performance/run_load_test.py --steps 5,10,20,40 --step-seconds 60
    # 1000+ users: token sign-in, 4 Locust worker processes, bulk-seeded accounts
    tests/.venv/Scripts/python tests/performance/run_load_test.py --steps 100,250,500,750,1000         --spawn-rate 20 --attendees 1200 --login token --locust-workers 4

1. checks the test database guard (name ends in _test, not the one in backend/.env),
2. resets the test database and starts a backend on TEST_BACKEND_PORT,
3. seeds attendee/organizer accounts and open events,
4. runs Locust headless with a step ramp, writing CSV + HTML to tests/reports/load/,
5. prints a per-step summary (requests/s, median and p95 response time, error rate).
"""

import argparse
import csv
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from helpers import db as dbh  # noqa: E402
from helpers.config import BACKEND_PORT, DEFAULT_PASSWORD, JWT_TEST_SECRET, REPORTS_DIR, TESTS_DIR  # noqa: E402
from helpers.server import BackendProcess  # noqa: E402

OUT = REPORTS_DIR / "load"


def bulk_users(engine, role_for, count: int, prefix: str) -> list[dict]:
    """Insert many verified accounts fast: one bcrypt hash shared by all (hashing each
    one separately takes ~0.25 s, minutes for 1000 users). Returns what the locustfile
    needs, including the password fingerprint the login cookie carries."""
    password_hash = dbh.hash_password(DEFAULT_PASSWORD)
    fingerprint = hashlib.sha256(password_hash.encode()).hexdigest()[:16]
    accounts = []
    with engine.begin() as conn:
        dept_id = conn.execute(text("""
            INSERT INTO departments (department_name) VALUES ('Information Technology')
            ON CONFLICT (department_name) DO UPDATE SET department_name = EXCLUDED.department_name RETURNING id
        """)).scalar()
        for i in range(count):
            role = role_for(i)
            email = f"load.{prefix}.{i}@example.com"
            user_id = conn.execute(text("""
                INSERT INTO users (email, password, full_name, role, is_active)
                VALUES (:e, :pw, :n, :r, TRUE) RETURNING id
            """), {"e": email, "pw": password_hash, "n": f"LOAD {role.upper()} {i}", "r": role}).scalar()
            role_row = conn.execute(text("""
                INSERT INTO user_roles (user_id, role_type, department_id, employment_id)
                VALUES (:u, :r, :d, :emp) RETURNING id
            """), {"u": user_id, "r": role, "d": dept_id,
                     "emp": f"LOAD-{user_id:05d}" if role == "organizer" else None}).scalar()
            accounts.append({"id": user_id, "email": email, "role": role, "pwd": fingerprint,
                             "user_role_id": role_row})
    return accounts


def main():
    # The test suite is deactivated (tests/conftest.py); the load test follows the same switch
    if os.getenv("EVEREST_TESTS_ENABLED") != "1":
        print("Tests are deactivated. Set EVEREST_TESTS_ENABLED=1 to run the load test.")
        return
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", default="5,10,20,40", help="users per step, e.g. 5,10,20,40,80")
    parser.add_argument("--step-seconds", type=int, default=60)
    parser.add_argument("--spawn-rate", type=float, default=2)
    parser.add_argument("--attendees", type=int, default=120)
    parser.add_argument("--organizers", type=int, default=10)
    parser.add_argument("--events", type=int, default=30)
    parser.add_argument("--login", choices=["password", "token"], default="password",
                        help="token: signed-in users without the per-IP login limit (see locustfile.py)")
    parser.add_argument("--locust-workers", type=int, default=0,
                        help="extra Locust processes (one Python process can't drive 1000 users)")
    parser.add_argument("--backend-workers", type=int, default=1, help="uvicorn --workers for the test backend")
    args = parser.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    dbh.create_database_if_missing()
    engine = dbh.make_engine()
    dbh.reset_schema(engine)
    started = time.monotonic()
    organizers = bulk_users(engine, lambda i: "organizer", args.organizers, "org")
    attendees = bulk_users(engine, lambda i: "student" if i % 2 else "participant", args.attendees, "att")
    event_ids = [dbh.create_event(engine, organizers[i % len(organizers)], capacity=50)["id"] for i in range(args.events)]
    print(f"Seeded {len(attendees)} attendees, {len(organizers)} organizers, {len(event_ids)} events "
          f"in {time.monotonic() - started:.0f} s")

    server = BackendProcess(BACKEND_PORT, "backend-load.log", workers=args.backend_workers).start()
    workers = []
    try:
        env = dict(os.environ)
        env.update({
            "EVEREST_LOAD_ACCOUNTS": json.dumps({"attendees": attendees, "organizers": organizers}),
            "EVEREST_LOAD_EVENT_IDS": json.dumps(event_ids),
            "EVEREST_LOAD_PASSWORD": DEFAULT_PASSWORD,
            "EVEREST_LOAD_JWT_SECRET": JWT_TEST_SECRET,  # the test backend's random per-run secret
            "LOGIN_MODE": args.login,
            "LOAD_STEPS": args.steps, "STEP_SECONDS": str(args.step_seconds), "SPAWN_RATE": str(args.spawn_rate),
        })
        locustfile = str(TESTS_DIR / "performance" / "locustfile.py")
        cmd = [sys.executable, "-m", "locust", "-f", locustfile,
               "--headless", "--host", server.url, "--csv", str(OUT / "everest"), "--csv-full-history",
               "--html", str(OUT / "report.html"), "--only-summary"]
        if args.locust_workers:
            # --processes isn't available on Windows: start the workers ourselves
            cmd += ["--master", "--expect-workers", str(args.locust_workers)]
            for _ in range(args.locust_workers):
                workers.append(subprocess.Popen(
                    [sys.executable, "-m", "locust", "-f", locustfile, "--worker", "--host", server.url],
                    env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        subprocess.run(cmd, env=env, check=False)
    finally:
        for w in workers:
            try:
                w.wait(timeout=15)
            except subprocess.TimeoutExpired:
                w.kill()
        server.stop()
        engine.dispose()
    summarize(args)


def summarize(args):
    history = OUT / "everest_stats_history.csv"
    if not history.exists():
        print("No Locust history file was written.")
        return
    rows = [r for r in csv.DictReader(history.open(encoding="utf-8")) if r["Name"] == "Aggregated"]
    steps = [int(s) for s in args.steps.split(",")]
    print("\nPer-step results (Aggregated, last sample of each step):")
    print(f"{'users':>6} {'req/s':>8} {'fail/s':>8} {'median ms':>10} {'p95 ms':>8} {'total req':>10} {'total fail':>10}")
    by_users = {}
    for r in rows:
        by_users[int(r["User Count"])] = r
    for users in steps:
        r = by_users.get(users)
        if not r:
            continue
        print(f"{users:>6} {float(r['Requests/s']):>8.1f} {float(r['Failures/s']):>8.1f} "
              f"{r['50%']:>10} {r['95%']:>8} {r['Total Request Count']:>10} {r['Total Failure Count']:>10}")
    failures = OUT / "everest_failures.csv"
    if failures.exists():
        print("\nFailures by type:")
        for r in csv.DictReader(failures.open(encoding="utf-8")):
            print(f"  {r['Occurrences']:>6} x {r['Method']} {r['Name']}: {r['Error'][:80]}")
    print(f"\nFull report: {OUT / 'report.html'}")


if __name__ == "__main__":
    main()
