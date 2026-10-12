"""
One command to run the automated tests and see which ones failed.

    tests/.venv/Scripts/python tests/run_tests.py              # everything
    tests/.venv/Scripts/python tests/run_tests.py security     # one area: auth, api, functional,
                                                                #   scheduling, security, e2e
    tests/.venv/Scripts/python tests/run_tests.py --failed     # rerun only what failed last time
    tests/.venv/Scripts/python tests/run_tests.py --open       # open the HTML report afterwards
    (on Windows you can also double-click run_tests.bat in the repo root)

After the run it prints a table of every failed/error test with the reason, and writes:
    tests/reports/summary.txt   the same table, readable in any editor
    tests/reports/history.csv   one line per run (date, passed, failed, ...) to track progress
    tests/reports/report.html   full pytest-html report (click a test to see its log)
    tests/reports/e2e/          screenshot + browser console of each failed browser test
    tests/reports/backend.log   what the test backend printed (look here for server errors)
Extra arguments after "--" go straight to pytest, e.g.  run_tests.py -- -k login -x
"""

import argparse
import csv
import socket
import subprocess
import sys
import time
import webbrowser
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
ROOT = TESTS_DIR.parent
REPORTS = TESTS_DIR / "reports"
JUNIT = REPORTS / "junit.xml"
AREAS = {"auth", "api", "functional", "scheduling", "security", "e2e"}


def frontend_running() -> bool:
    try:
        with socket.create_connection(("localhost", 4200), timeout=1):
            return True
    except OSError:
        return False


def last_failed_ids() -> list[str]:
    """Test ids that failed or errored in the previous run (from junit.xml)."""
    if not JUNIT.exists():
        return []
    ids = []
    for case in ET.parse(JUNIT).getroot().iter("testcase"):
        if case.find("failure") is not None or case.find("error") is not None:
            path = case.get("classname", "").replace(".", "/")
            ids.append(f"{TESTS_DIR.name}/{path.removeprefix('tests/')}.py::{case.get('name')}")
    return ids


def summarize(started: float) -> tuple[dict, list[tuple[str, str, str]]]:
    """Counts and (status, test, reason) rows for every non-passing test."""
    root = ET.parse(JUNIT).getroot()
    counts = {"passed": 0, "failed": 0, "error": 0, "skipped": 0, "xfail": 0}
    rows = []
    for case in root.iter("testcase"):
        test = f"{case.get('classname', '').split('.')[-1]}::{case.get('name')}"
        for tag, status in (("failure", "FAILED"), ("error", "ERROR"), ("skipped", "SKIPPED")):
            node = case.find(tag)
            if node is None:
                continue
            message = (node.get("message") or node.text or "").strip().splitlines()
            reason = message[0][:160] if message else ""
            if tag == "skipped" and node.get("type") == "pytest.xfail":
                counts["xfail"] += 1
                rows.append(("XFAIL", test, reason))
            else:
                counts[{"failure": "failed", "error": "error", "skipped": "skipped"}[tag]] += 1
                rows.append((status, test, reason))
            break
        else:
            counts["passed"] += 1
    counts["seconds"] = round(time.time() - started)
    return counts, rows


def write_reports(counts: dict, rows: list, args_used: str) -> str:
    order = {"ERROR": 0, "FAILED": 1, "SKIPPED": 2, "XFAIL": 3}
    rows = sorted(rows, key=lambda r: order[r[0]])
    lines = [
        f"EVEREST test run  {datetime.now():%Y-%m-%d %H:%M}   ({args_used or 'all tests'})",
        f"passed {counts['passed']}  |  failed {counts['failed']}  |  errors {counts['error']}  |  "
        f"skipped {counts['skipped']}  |  expected failures (known issues) {counts['xfail']}  |  "
        f"{counts['seconds']} s",
        "",
    ]
    if rows:
        lines.append(f"{'STATUS':<8} {'TEST':<70} REASON")
        lines.append("-" * 140)
        for status, test, reason in rows:
            lines.append(f"{status:<8} {test:<70} {reason}")
    else:
        lines.append("All tests passed.")
    lines += [
        "",
        "FAILED = the app did not do what the test expects (or a test needs updating).",
        "ERROR  = the test could not run (setup problem: database, backend, frontend not started).",
        "XFAIL  = known issue documented in tests/REPORT.md; not counted as a failure.",
        "Details: tests/reports/report.html | browser screenshots: tests/reports/e2e/ | "
        "server log: tests/reports/backend.log",
    ]
    text = "\n".join(lines)
    (REPORTS / "summary.txt").write_text(text + "\n", encoding="utf-8")

    history = REPORTS / "history.csv"
    new = not history.exists()
    with history.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if new:
            writer.writerow(["date", "selection", "passed", "failed", "errors", "skipped", "xfail", "seconds",
                             "failed_tests"])
        writer.writerow([f"{datetime.now():%Y-%m-%d %H:%M}", args_used or "all", counts["passed"],
                         counts["failed"], counts["error"], counts["skipped"], counts["xfail"], counts["seconds"],
                         "; ".join(t for s, t, _ in rows if s in ("FAILED", "ERROR"))])
    return text


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
                                     usage="run_tests.py [area] [--failed] [--open] [-- pytest options]")
    parser.add_argument("area", nargs="?", choices=sorted(AREAS), help="run only one area")
    parser.add_argument("--failed", action="store_true", help="rerun only the tests that failed last time")
    parser.add_argument("--open", action="store_true", help="open the HTML report when done")
    argv = sys.argv[1:]
    # Everything after "--" goes to pytest unchanged
    extra = argv[argv.index("--") + 1:] if "--" in argv else []
    args = parser.parse_args(argv[:argv.index("--")] if "--" in argv else argv)

    cmd = [sys.executable, "-m", "pytest", str(TESTS_DIR), "-p", "no:cacheprovider",
           "--screenshot", "only-on-failure", "--output", str(REPORTS / "playwright")]
    label = []
    if args.failed:
        ids = last_failed_ids()
        if not ids:
            print("Nothing failed in the last run (or there is no last run).")
            return 0
        cmd = cmd[:3] + ids + cmd[4:]
        label.append(f"rerun of {len(ids)} failed")
    elif args.area == "e2e":
        cmd[3] = str(TESTS_DIR / "e2e")
        label.append("e2e")
    elif args.area:
        cmd += ["-m", args.area, "--ignore", str(TESTS_DIR / "e2e")]
        label.append(args.area)

    runs_e2e = args.area in (None, "e2e") or args.failed
    if runs_e2e and not frontend_running():
        if args.area == "e2e":
            print("The Angular app is not running on http://localhost:4200.\n"
                  "Start it first:  cd frontend/event-registration && npm start")
            return 2
        print("NOTE: Angular app not running on :4200, so the browser tests (tests/e2e) are skipped.\n"
              "      Start it with  cd frontend/event-registration && npm start  to include them.\n")
        cmd += ["--ignore", str(TESTS_DIR / "e2e")]
        label.append("no e2e")

    cmd += extra
    if extra:
        label.append(" ".join(extra))
    REPORTS.mkdir(exist_ok=True)
    JUNIT.unlink(missing_ok=True)

    print("Running:", " ".join(cmd[1:]), "\n")
    started = time.time()
    code = subprocess.call(cmd, cwd=ROOT)

    if not JUNIT.exists():
        print("\nPytest did not produce a report (it stopped before running tests). See the output above.")
        return code or 1
    counts, rows = summarize(started)
    print("\n" + "=" * 140)
    print(write_reports(counts, rows, ", ".join(label)))
    print("=" * 140)
    if args.open:
        webbrowser.open((REPORTS / "report.html").as_uri())
    return code


if __name__ == "__main__":
    sys.exit(main())
