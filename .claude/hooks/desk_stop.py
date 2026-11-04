#!/usr/bin/env python3
"""Stop hook for the Enquiry Desk.

Runs when the main session tries to finish. Does nothing unless this session ran the Desk
(desk/.input-snapshot.json, written by Step 0 of /run-desk, is newer than the session's start). Then:

  1. python desk/validate_desk.py        (the packs in desk/packs/)
  2. python desk/check_inputs_unchanged.py

Both pass   -> allow the stop, reset the failure count.
A check fails, 1st time in a row -> block the stop and hand the check's message back to the Desk.
A check fails, 2nd time in a row -> stop retrying: append FAILED, the timestamp and the reason
                                    to outputs/run-log.md, reset the count, allow the stop.

The hook keeps its own count in desk/.stop-hook-state.json, per session. It does not rely on
the stop_hook_active flag. Python standard library only.
"""
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

MAX_FAILURES = 2
CHECK_TIMEOUT = 150  # seconds per check; the settings.json timeout is the outer limit
HEAD_LINES = 20  # the session's start time is read from the first lines of its transcript


def session_start(transcript_path):
    """Earliest timestamp in this session's transcript, as epoch seconds, or None."""
    try:
        with open(transcript_path, encoding="utf-8", errors="ignore") as f:
            head = [next(f, "") for _ in range(HEAD_LINES)]
    except (OSError, TypeError):
        return None
    times = []
    for line in head:
        try:
            ts = json.loads(line).get("timestamp")
            times.append(datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp())
        except (ValueError, AttributeError, TypeError):
            continue
    return min(times) if times else None


def ran_desk(root, transcript_path):
    """True if this session ran the Desk: the project's own desk/.input-snapshot.json
    (written only by desk/snapshot_inputs.py, Step 0 of /run-desk) was written after this
    session started. Text that merely mentions the script, or a snapshot written in another
    folder or by an earlier session, does not count."""
    start = session_start(transcript_path)
    try:
        written = (root / "desk/.input-snapshot.json").stat().st_mtime
    except OSError:
        return False
    return start is not None and written >= start


def run_check(root, script):
    """Run one Desk check. Returns None on pass, or its message on failure."""
    try:
        r = subprocess.run([sys.executable, str(root / script), "--root", str(root)] if script.endswith("validate_desk.py")
                           else [sys.executable, str(root / script), str(root)],
                           cwd=str(root), capture_output=True, text=True, timeout=CHECK_TIMEOUT)
    except subprocess.TimeoutExpired:
        return f"{script} did not finish within {CHECK_TIMEOUT} seconds."
    if r.returncode == 0:
        return None
    out = (r.stderr.strip() + "\n" + r.stdout.strip()).strip()
    return f"{script} failed (exit {r.returncode}):\n{out or '(no output)'}"


def load_state(path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


def save_state(path, state):
    try:
        path.write_text(json.dumps(state, indent=2))
    except OSError:
        pass


def log_failure(root, reason):
    log = root / "outputs/run-log.md"
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    flat = re.sub(r"\s*\n\s*", "; ", reason).replace("|", "/")
    log.parent.mkdir(parents=True, exist_ok=True)
    new = not log.exists()
    with open(log, "a", encoding="utf-8") as f:
        if new:
            f.write("| enquiry | agent | model | start | finish | tokens |\n|---|---|---|---|---|---|\n")
        f.write(f"| batch | Stop hook: FAILED | - | {stamp} | {stamp} | {flat} |\n")
    return stamp


def main():
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        payload = {}
    root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or ".").resolve()
    session = payload.get("session_id", "unknown")

    if not ran_desk(root, payload.get("transcript_path")):
        return 0  # not a Desk run: let the session finish

    failures = [m for m in (run_check(root, "desk/validate_desk.py"),
                            run_check(root, "desk/check_inputs_unchanged.py")) if m]

    state_path = root / "desk/.stop-hook-state.json"
    state = load_state(state_path)
    if not failures:
        state.pop(session, None)
        save_state(state_path, state)
        return 0

    reason = "\n\n".join(failures)
    count = state.get(session, 0) + 1

    if count >= MAX_FAILURES:
        state.pop(session, None)
        save_state(state_path, state)
        stamp = log_failure(root, reason)
        print(json.dumps({"systemMessage": f"Desk checks failed {count} times in a row. Recorded FAILED at {stamp} "
                                           f"in outputs/run-log.md. Stopping without further retries."}))
        return 0

    state[session] = count
    save_state(state_path, state)
    print(json.dumps({
        "decision": "block",
        "reason": (f"Desk Stop check {count} of {MAX_FAILURES} failed. Fix the problems below, following R8 in "
                   f"design/graph.md (re-run the node that owns each faulty file; never hand-edit an agent's file "
                   f"or a check script), then finish again. If it fails again the run is logged as FAILED.\n\n{reason}"),
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
