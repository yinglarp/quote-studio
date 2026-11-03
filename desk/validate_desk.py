#!/usr/bin/env python3
"""Validate a batch of Enquiry Desk packs against the three desk rules.

Run from the project folder:

    python3 desk/validate_desk.py              check the packs that exist so far
    python3 desk/validate_desk.py --complete   also require a pack for every enquiry in inbox/

Rule 1  No date may have more than 18 jobs: jobs in desk/bookings.csv plus the dates the Desk proposes to hold.
Rule 2  Every quote comes from the Quote Studio engine, and nothing a customer sees contains internal costs or margins.
          - quote.json must match what quote-calculator/quote.py gives for the pack's event.json (total and deposit);
          - a quote needs its PDF in outputs/quotes/ (enq-NN.pdf), and the text of the PDF and of every draft reply is
            scanned for internal wording;
          - scripts/quote_check.py (your Lesson 3 checker) must pass. The result is remembered until a quote tool changes.
Rule 3  Every enquiry is accounted for as a quote, a clarification or an escalation.

Exit code 0 means the batch passed. Exit code 1 means it failed, and each problem is printed with what to do about it.
Python standard library only (pdftotext is used for the PDF text when it is installed).
"""
import csv
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

MAX_JOBS = 18
OUTCOMES = {"quote", "clarify", "escalate"}
OWNERS = {"Priya", "Jun Wei"}
ENGINE_KEYS = ("client", "date", "pax", "package", "zone", "add_ons", "repeat_client")
LEAK = [r"\bmargins?\b", r"\bmark-?ups?\b", r"\bprofit", r"\bfood[- ]cost", r"\bcost[- ]price", r"\bcosting\b", r"\bcogs\b",
        r"\bunit costs?\b", r"\bingredient costs?\b", r"\bstaff[- ]costs?\b", r"\blabou?r[- ]costs?\b", r"\bovertime\b",
        r"\bpayroll\b", r"\bsalar(y|ies)\b", r"\bwages?\b", r"\bsupplier\b", r"\bnorthgate\b", r"\bgross\b",
        r"costing-and-margins", r"overtime-sheet", r"\bstaff/"]


def nice(d):
    y, m, dd = map(int, d.split("-"))
    x = date(y, m, dd)
    return f"{x.strftime('%A')} {x.day} {x.strftime('%B %Y')}"


def dec(x):
    try:
        return Decimal(str(x).replace(",", "").replace("S$", "")).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return None


def leaks(text):
    low = text.lower()
    return sorted({m.group(0) for p in LEAK for m in re.finditer(p, low)})


def pdf_text(path):
    exe = shutil.which("pdftotext")
    if not exe:
        return None
    r = subprocess.run([exe, "-layout", str(path), "-"], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def tools_hash(root):
    h = hashlib.sha256()
    files = sorted((root / "quote-calculator").glob("*.py")) + [root / "quote-calculator/rates.json", root / "scripts/quote_check.py"]
    for f in files:
        if f.exists():
            h.update(f.name.encode()); h.update(f.read_bytes())
    return h.hexdigest()


def suite_passes(root, errors):
    qc = root / "scripts/quote_check.py"
    if not qc.exists():
        errors.append("Missing checker: scripts/quote_check.py does not exist. Build it as in Lesson 3 (or copy it from your Lesson 3 project) before any quote is accepted.")
        return
    cache = root / "desk/.suite-cache.json"
    key = tools_hash(root)
    try:
        if json.loads(cache.read_text()).get("passed_for") == key:
            return
    except (OSError, ValueError):
        pass
    r = subprocess.run([sys.executable, str(qc)], capture_output=True, text=True, cwd=str(root))
    if r.returncode == 0:
        try:
            cache.write_text(json.dumps({"passed_for": key}))
        except OSError:
            pass
    else:
        tail = [l for l in r.stdout.splitlines() if "FAIL" in l][:3]
        errors.append("Quote tools fail their own check: scripts/quote_check.py did not pass"
                      + (" (" + " | ".join(t.strip() for t in tail) + ")" if tail else "")
                      + ". Fix quote-calculator/ until the check passes; do not edit the check.")


def reprice(root, name, event, quote):
    enq = {k: event.get(k) for k in ENGINE_KEYS}
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "enq.json"
        f.write_text(json.dumps(enq))
        r = subprocess.run([sys.executable, str(root / "quote-calculator/quote.py"), "--input", str(f), "--json"],
                           capture_output=True, text=True, cwd=str(root))
    try:
        j = json.loads(r.stdout[r.stdout.find("{"):r.stdout.rfind("}") + 1])
    except ValueError:
        return f"Quote tool failure: quote.py gave no JSON for {name}'s event.json. Run it again and check the input."
    if j.get("status") not in (None, "ok") or r.returncode != 0:
        return (f"Unpriceable event: the engine refuses {name}'s event.json ({j.get('reason', 'no reason given')}). "
                f"A refused event can't be a quote. Mark the enquiry 'clarify' or 'escalate'.")
    if dec(j.get("total")) != dec(quote.get("total")) or dec(j.get("deposit")) != dec(quote.get("deposit")):
        return (f"Quote mismatch: {name}/quote.json says total {quote.get('total')} and deposit {quote.get('deposit')}, but the engine gives "
                f"total {j.get('total')} and deposit {j.get('deposit')} for its event.json. Re-run the engine and save its output unchanged.")
    return None


def main(argv):
    complete = "--complete" in argv
    skip_suite = "--no-suite" in argv
    root = Path(argv[argv.index("--root") + 1]) if "--root" in argv else Path(".")
    errors, notes = [], []
    packs, events = {}, {}
    for p in sorted((root / "desk/packs").glob("enq-*/outcome.json")):
        name = p.parent.name
        try:
            packs[name] = json.loads(p.read_text())
        except ValueError as e:
            errors.append(f"Invalid pack: {name}/outcome.json is not valid JSON ({e}). Rewrite the file.")
            continue
        ev = p.parent / "event.json"
        try:
            events[name] = json.loads(ev.read_text())
        except (OSError, ValueError):
            errors.append(f"Missing facts: {name} has an outcome but no readable event.json. Run the Reader for this enquiry again.")

    # Rule 3
    for name, o in packs.items():
        out = o.get("outcome")
        if out not in OUTCOMES:
            errors.append(f"Unaccounted enquiry: {name} has outcome {out!r}. Set outcome to one of: quote, clarify, escalate.")
            continue
        if out in ("clarify", "escalate") and not o.get("reason"):
            errors.append(f"Outcome without a reason: {name} is '{out}' but gives no reason. Add a 'reason' a person can act on.")
        if out == "escalate" and o.get("owner") not in OWNERS:
            errors.append(f"Escalation without an owner: {name} must name who decides, 'Priya' or 'Jun Wei', in 'owner'.")
    if complete:
        ids = {re.match(r"enq-\d\d", f.name).group(0) for f in (root / "inbox").glob("enq-*.txt")}
        for i in sorted(ids - set(packs)):
            errors.append(f"Missing pack: no outcome.json for {i}. Every enquiry must end as a quote, a clarification or an escalation.")

    # Rule 1, across the whole batch
    booked = defaultdict(int)
    with open(root / "desk/bookings.csv", newline="") as f:
        for r in csv.DictReader(f):
            booked[r["date"]] += 1
    holds = defaultdict(list)
    for name, o in packs.items():
        if o.get("date") and (o.get("outcome") == "quote" or o.get("holds_date")):
            holds[o["date"]].append((o.get("received") or events.get(name, {}).get("received") or "", name))
    for d, hs in sorted(holds.items()):
        total = booked.get(d, 0) + len(hs)
        if total > MAX_JOBS:
            hs.sort()
            names = " and ".join(n for _, n in hs)
            errors.append(
                f"Invalid batch: {nice(d)} would have {total} jobs ({booked.get(d, 0)} booked, plus holds for {names}), "
                f"exceeding the maximum of {MAX_JOBS}. Keep the hold for the enquiry received first, and mark the other as "
                f'"escalate" with a reason.')

    # Rule 2
    quotes = [n for n, o in packs.items() if o.get("outcome") == "quote"]
    if quotes and not skip_suite:
        suite_passes(root, errors)
    for name in quotes:
        qpath = root / "desk/packs" / name / "quote.json"
        try:
            quote = json.loads(qpath.read_text())
        except (OSError, ValueError):
            errors.append(f"Missing quote: {name} is marked 'quote' but has no readable quote.json from the Quote Studio engine. Run the engine on its event.json.")
            continue
        if name in events and (root / "quote-calculator/quote.py").exists():
            msg = reprice(root, name, events[name], quote)
            if msg:
                errors.append(msg)
        pdfs = sorted((root / "outputs/quotes").glob(f"{name}*.pdf"))
        if not pdfs:
            errors.append(f"Missing PDF: {name} is marked 'quote' but outputs/quotes/{name}.pdf does not exist. Make it with quote-calculator/make_pdf.py.")
        for pdf in pdfs:
            t = pdf_text(pdf)
            if t is None:
                notes.append(f"Note: pdftotext is not installed, so the text of {pdf.name} was not scanned.")
            elif leaks(t):
                errors.append(f"Internal wording on a customer PDF: {pdf.name} contains {', '.join(leaks(t))}. Rebuild the PDF; customers must never see costs or margins.")
    for name, o in packs.items():
        if o.get("outcome") != "quote" and list((root / "outputs/quotes").glob(f"{name}*.pdf")):
            notes.append(f"Note: outputs/quotes/{name}.pdf exists but {name} is '{o.get('outcome')}'. It must not go to the customer; remove it.")
    drafts = root / "outputs/drafts"
    if drafts.exists():
        for d in sorted(drafts.glob("*")):
            if d.is_file() and leaks(d.read_text(errors="ignore")):
                errors.append(f"Internal wording in a customer draft: {d.name} contains {', '.join(leaks(d.read_text(errors='ignore')))}. Rewrite the draft without it.")

    for n in sorted(set(notes)):
        print(n)
    if errors:
        print("VALIDATION FAILED", file=sys.stderr)
        for e in errors:
            print("- " + e, file=sys.stderr)
        return 1
    print(f"VALIDATION PASSED ({len(packs)} pack{'s' if len(packs) != 1 else ''})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
