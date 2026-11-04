#!/usr/bin/env python3
"""The Enquiry Desk board: a small local web server for watching the Desk and recording approvals.

Run from the project folder:

    python3 desk/board_server.py            then open http://127.0.0.1:8765 in your browser
    python3 desk/board_server.py --port 9000

What it does
  * Shows every enquiry in inbox/ and what the Desk has produced for it (packs, drafts, PDFs).
  * Lets Priya or Jun Wei approve things, and writes desk/approvals.json.
  * Enforces WHO may approve WHAT, in code. An approval by the wrong person is refused (HTTP 403).
What it never does: send a message, change a pack or change the calendar.

It listens on 127.0.0.1 only, so only this computer can reach it. Python standard library only.
"""
import hashlib
import json
import re
import sys
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path.cwd()
DESK = ROOT / "desk"
# Who may approve what. This table is the control: the page cannot override it.
AUTHORITY = {
    "reply": {"Priya": True},
    "quote_pdf": {"Priya": True},
    "capacity_exception": {"Jun Wei": True},
    "extra_van": {"Jun Wei": True},
}
LABEL = {"reply": "customer reply", "quote_pdf": "quote PDF", "capacity_exception": "capacity exception", "extra_van": "extra van (spending)"}
PEOPLE = ("Priya", "Jun Wei")


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None


def read(p):
    try:
        return p.read_text(encoding="utf-8")
    except OSError:
        return None


def read_json(p):
    t = read(p)
    try:
        return json.loads(t) if t else None
    except ValueError:
        return {"_error": "not valid JSON"}


def approvals():
    a = read_json(DESK / "approvals.json")
    return a if isinstance(a, list) else []


def artefact(enq, action):
    return {"reply": ROOT / "outputs/drafts" / f"{enq}-reply.md",
            "quote_pdf": ROOT / "outputs/quotes" / f"{enq}.pdf"}.get(action)


def enquiry_ids():
    ids = {}
    for f in sorted((ROOT / "inbox").glob("enq-*.txt")):
        m = re.match(r"enq-\d\d", f.name)
        ids.setdefault(m.group(0), []).append(f.name)
    return ids


def state():
    appr = approvals()
    out = []
    for enq, files in enquiry_ids().items():
        pack = DESK / "packs" / enq
        outcome = read_json(pack / "outcome.json")
        event = read_json(pack / "event.json")
        mine = [a for a in appr if a.get("enquiry") == enq]
        approved = {}
        for a in mine:
            art = artefact(enq, a["action"])
            current = (sha(art) == a.get("sha256")) if art else True
            approved[a["action"]] = {"by": a["approver"], "at": a["at"], "current": current}
        pdf = ROOT / "outputs/quotes" / f"{enq}.pdf"
        out.append({
            "id": enq, "files": files,
            "client": (event or {}).get("client") if isinstance(event, dict) else None,
            "has_pack": pack.exists(), "outcome": outcome, "event": event,
            "contact": read_json(pack / "contact.json"), "capacity": read_json(pack / "capacity.json"),
            "menu": read_json(pack / "menu.json"), "quote": read_json(pack / "quote.json"),
            "draft": read(ROOT / "outputs/drafts" / f"{enq}-reply.md"),
            "pdf": f"/files/outputs/quotes/{enq}.pdf" if pdf.exists() else None,
            "approved": approved,
        })
    return {"enquiries": out, "authority": {k: list(v) for k, v in AUTHORITY.items()}, "labels": LABEL, "people": PEOPLE}


def approve(body):
    enq, action, who = body.get("enquiry"), body.get("action"), body.get("approver")
    if enq not in enquiry_ids() or action not in AUTHORITY or who not in PEOPLE:
        return 400, {"error": "Unknown enquiry, action or approver."}
    if not AUTHORITY[action].get(who):
        allowed = " or ".join(AUTHORITY[action])
        return 403, {"error": f"Refused: {who} may not approve a {LABEL[action]}. Only {allowed} can."}
    art = artefact(enq, action)
    if art is not None and not art.exists():
        return 409, {"error": f"Nothing to approve yet: {art.relative_to(ROOT)} does not exist."}
    outcome = read_json(DESK / "packs" / enq / "outcome.json")
    if action in ("capacity_exception", "extra_van") and not (isinstance(outcome, dict) and outcome.get("owner") == "Jun Wei"):
        return 409, {"error": f"{enq} has not been escalated to Jun Wei, so there is nothing for him to decide."}
    record = {"enquiry": enq, "action": action, "approver": who, "at": datetime.now().isoformat(timespec="seconds"),
              "sha256": sha(art) if art else None, "note": str(body.get("note", ""))[:300]}
    allrecs = [a for a in approvals() if not (a.get("enquiry") == enq and a.get("action") == action)] + [record]
    (DESK / "approvals.json").write_text(json.dumps(allrecs, indent=2), encoding="utf-8")
    return 200, {"ok": True, "record": record}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = unquote(urlparse(self.path).path)
        if path == "/":
            return self.send(200, (DESK / "board.html").read_bytes(), "text/html; charset=utf-8")
        if path == "/api/state":
            return self.send(200, state())
        m = re.fullmatch(r"/files/outputs/quotes/(enq-\d\d)\.pdf", path)
        if m and (ROOT / "outputs/quotes" / f"{m.group(1)}.pdf").exists():
            return self.send(200, (ROOT / "outputs/quotes" / f"{m.group(1)}.pdf").read_bytes(), "application/pdf")
        self.send(404, {"error": "Not found"})

    def do_POST(self):
        if urlparse(self.path).path != "/api/approve":
            return self.send(404, {"error": "Not found"})
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        except ValueError:
            return self.send(400, {"error": "Bad request"})
        code, payload = approve(body)
        self.send(code, payload)


def main(argv):
    port = int(argv[argv.index("--port") + 1]) if "--port" in argv else 8765
    if not (DESK / "board.html").exists():
        print("Run this from the project folder (the one that contains desk/ and inbox/).")
        return 2
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Desk board running. Open http://127.0.0.1:{port} in your browser. Press Ctrl+C to stop.")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nBoard stopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
