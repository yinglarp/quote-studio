#!/usr/bin/env python3
"""Run the Enquiry Desk rule tests (desk/tests/) from a hook.

PostToolUse (Edit|Write|MultiEdit), no arguments:
    Reads the hook payload on stdin. When the edited file is a Desk pack, a draft reply, a quote
    PDF or a Desk test, runs the fast levels (unit and integration). On failure it exits 2, so
    Claude sees the failing tests straight after the edit that broke them. Other edits are ignored.

By hand, or from the Stop hook (desk_stop.py):
    python .claude/hooks/desk_tests.py --level all          unit + integration + e2e
    python .claude/hooks/desk_tests.py --level unit         one level: unit, integration or e2e

Exit 0 = passed or nothing to do, 2 = tests failed (PostToolUse), 1 = tests failed (--level).
Python standard library plus pytest (in requirements.txt).
"""
import json
import os
import subprocess
import sys
from pathlib import Path

WATCHED = ("desk/packs/", "outputs/drafts/", "outputs/quotes/", "desk/tests/", "desk/validate_desk.py",
           "desk/bookings.csv", "design/schemas/")
LEVELS = {"unit": "unit", "integration": "integration", "e2e": "e2e", "fast": "unit or integration", "all": None}
TIMEOUT = 120
MAX_LINES = 40


def run_tests(root, level):
    """Run one level of desk/tests. Returns None on pass, or a short failure report."""
    cmd = [sys.executable, "-m", "pytest", "desk/tests", "-p", "no:cacheprovider", "--tb=short", "-rf", "-vv",
           "--no-header", "-o", "console_output_style=classic"]
    if LEVELS[level]:
        cmd += ["-m", LEVELS[level]]
    try:
        r = subprocess.run(cmd, cwd=str(root), capture_output=True, text=True, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        return f"Desk tests ({level}) did not finish within {TIMEOUT} seconds."
    if r.returncode == 0 or r.returncode == 5:  # 5 = no tests collected for this level
        return None
    lines = [l for l in (r.stdout + r.stderr).splitlines() if l.strip()]
    if "No module named pytest" in r.stderr:
        return "pytest is not installed, so the Desk tests could not run. Install it with: python -m pip install -r requirements.txt"
    # FAILED lines carry the test name and its full message; skip pytest's diff blocks ("E  ...").
    keep = [l for l in lines if l.startswith(("FAILED", "ERROR")) or l.startswith("=") and " passed" in l]
    return f"Desk tests ({level}) failed:\n" + "\n".join((keep or lines)[:MAX_LINES])


def edited_path(payload, root):
    p = (payload.get("tool_input") or {}).get("file_path") or ""
    if not p:
        return None
    try:
        return Path(p).resolve().relative_to(root).as_posix()
    except ValueError:
        return None


def main(argv):
    root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or ".").resolve()
    if "--level" in argv:
        level = argv[argv.index("--level") + 1] if argv.index("--level") + 1 < len(argv) else ""
        if level not in LEVELS:
            print(f"Unknown level {level!r}. Use one of: {', '.join(LEVELS)}.", file=sys.stderr)
            return 1
        msg = run_tests(root, level)
        print(msg or f"Desk tests ({level}) passed.", file=sys.stderr if msg else sys.stdout)
        return 1 if msg else 0

    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        return 0
    rel = edited_path(payload, Path(payload.get("cwd") or root).resolve()) or edited_path(payload, root)
    if not rel or not rel.startswith(WATCHED):
        return 0
    msg = run_tests(root, "fast")
    if msg:
        print(f"After your edit to {rel}:\n{msg}\nFix the cause (re-run the node that owns the file), "
              f"don't edit the tests.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
