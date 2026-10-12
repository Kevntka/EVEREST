"""
Run the load test safely against the TEST database.

    tests/.venv/Scripts/python tests/performance/run_load_test.py --steps 5,10,20,40 --step-seconds 60

1. checks the test database guard (name ends in _test, not the one in backend/.env),
2. resets the test database and starts a backend on TEST_BACKEND_PORT,
3. seeds attendee/organizer accounts and open events,
4. runs Locust headless with a step ramp, writing CSV + HTML to tests/reports/load/,
5. prints a per-step summary (requests/s, median and p95 response time, error rate).
"""

import argparse
import csv
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from helpers import db as dbh  # noqa: E402
from helpers.config import BACKEND_PORT, DEFAULT_PASSWORD, REPORTS_DIR, TESTS_DIR  # noqa: E402
from helpers.server import BackendProcess  # noqa: E402

OUT = REPORTS_DIR / "load"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", default="5,10,20,40", help="users per step, e.g. 5,10,20,40,80")
    parser.add_argument("--step-seconds", type=int, default=60)
    parser.add_argument("--spawn-rate", type=float, default=2)
    parser.add_argument("--attendees", type=int, default=120)
    parser.add_argument("--organizers", type=int, default=10)
    parser.add_argument("--events", type=int, default=30)
    args = parser.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    dbh.create_database_if_missing()
    engine = dbh.make_engine()
    dbh.reset_schema(engine)
    organizers = [dbh.create_user(engine, "organizer") for _ in range(args.organizers)]
    attendees = [dbh.create_user(engine, "student" if i % 2 else "participant") for i in range(args.attendees)]
    event_ids = [dbh.create_event(engine, organizers[i % len(organizers)], capacity=50)["id"] for i in range(args.events)]

    server = BackendProcess(BACKEND_PORT, "backend-load.log").start()
    try:
        env = dict(os.environ)
        env.update({
            "EVEREST_LOAD_ACCOUNTS": json.dumps({"attendees": [a["email"] for a in attendees],
                                                 "organizers": [o["email"] for o in organizers]}),
            "EVEREST_LOAD_EVENT_IDS": json.dumps(event_ids),
            "EVEREST_LOAD_PASSWORD": DEFAULT_PASSWORD,
            "LOAD_STEPS": args.steps, "STEP_SECONDS": str(args.step_seconds), "SPAWN_RATE": str(args.spawn_rate),
        })
        cmd = [sys.executable, "-m", "locust", "-f", str(TESTS_DIR / "performance" / "locustfile.py"),
               "--headless", "--host", server.url, "--csv", str(OUT / "everest"), "--csv-full-history",
               "--html", str(OUT / "report.html"), "--only-summary"]
        subprocess.run(cmd, env=env, check=False)
    finally:
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
