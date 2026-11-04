"""Integration tests: desk/validate_desk.py run on small test projects built in a temporary folder.

These prove the Stop hook's main check still catches each rule it is meant to catch, so a change to
the validator cannot quietly switch a rule off. Source: desk/desk-rules.md sections 1, 3 and 5.
"""
import json

import pytest

from desk_helpers import validate_desk

pytestmark = pytest.mark.integration

DATE = "2026-11-06"


def make_project(tmp_path, booked=0, packs=(), drafts=None, inbox=()):
    """A minimal project folder: bookings.csv with `booked` jobs on DATE, the given outcome.json packs."""
    desk = tmp_path / "desk"
    (desk / "packs").mkdir(parents=True)
    rows = ["job_id,date,customer,pax,status"] + [f"BK-{i:03},{DATE},Customer {i},30,confirmed" for i in range(booked)]
    (desk / "bookings.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    for o in packs:
        folder = desk / "packs" / o["enquiry_id"]
        folder.mkdir()
        (folder / "outcome.json").write_text(json.dumps(o), encoding="utf-8")
        (folder / "event.json").write_text(json.dumps({"enquiry_id": o["enquiry_id"], "date": o.get("date"),
                                                       "received": o.get("received")}), encoding="utf-8")
    (tmp_path / "outputs" / "quotes").mkdir(parents=True)
    for name, text in (drafts or {}).items():
        (tmp_path / "outputs" / "drafts").mkdir(parents=True, exist_ok=True)
        (tmp_path / "outputs" / "drafts" / name).write_text(text, encoding="utf-8")
    (tmp_path / "inbox").mkdir()
    for i in inbox:
        (tmp_path / "inbox" / f"{i}-customer.txt").write_text("Hello", encoding="utf-8")
    return tmp_path


def run(root, capsys, *flags):
    code = validate_desk.main(["--root", str(root), "--no-suite", *flags])
    out = capsys.readouterr()
    return code, out.out + out.err


def pack(n, outcome="clarify", received="2026-10-17T15:20", **kw):
    o = {"enquiry_id": f"enq-{n:02}", "outcome": outcome, "received": received, "date": DATE,
         "holds_date": outcome == "quote", "reason": "Dietary needs are missing."}
    o.update(kw)
    return o


def test_a_clean_batch_passes(tmp_path, capsys):
    root = make_project(tmp_path, booked=17, packs=[pack(4), pack(5)])
    code, out = run(root, capsys)
    assert code == 0, out


def test_one_hold_on_the_last_free_slot_is_allowed(tmp_path, capsys):
    root = make_project(tmp_path, booked=17, packs=[pack(4, "quote")])
    _, out = run(root, capsys)
    assert "exceeding the maximum of 18" not in out


def test_two_holds_on_the_last_free_slot_break_the_18_job_limit(tmp_path, capsys):
    root = make_project(tmp_path, booked=17, packs=[pack(4, "quote", "2026-10-17T15:20"),
                                                    pack(5, "quote", "2026-10-18T09:05")])
    code, out = run(root, capsys)
    assert code == 1
    line = next(l for l in out.splitlines() if "Invalid batch" in l)
    assert "19 jobs (17 booked, plus holds for enq-04 and enq-05)" in line
    assert "exceeding the maximum of 18" in line
    assert "Keep the hold for the enquiry received first" in line


def test_holds_date_counts_as_a_job_even_without_a_quote(tmp_path, capsys):
    root = make_project(tmp_path, booked=18, packs=[pack(4, "clarify", holds_date=True)])
    code, out = run(root, capsys)
    assert code == 1 and "exceeding the maximum of 18" in out


def test_an_unknown_outcome_fails(tmp_path, capsys):
    root = make_project(tmp_path, packs=[pack(4, "pending")])
    code, out = run(root, capsys)
    assert code == 1 and "Unaccounted enquiry" in out


def test_an_escalation_without_an_owner_fails(tmp_path, capsys):
    root = make_project(tmp_path, packs=[pack(4, "escalate")])
    code, out = run(root, capsys)
    assert code == 1 and "Escalation without an owner" in out


def test_a_clarification_without_a_reason_fails(tmp_path, capsys):
    root = make_project(tmp_path, packs=[pack(4, "clarify", reason="")])
    code, out = run(root, capsys)
    assert code == 1 and "Outcome without a reason" in out


def test_every_enquiry_in_the_inbox_needs_a_pack(tmp_path, capsys):
    root = make_project(tmp_path, packs=[pack(4)], inbox=["enq-04", "enq-05"])
    code, out = run(root, capsys, "--complete")
    assert code == 1 and "Missing pack: no outcome.json for enq-05" in out


def test_a_quote_without_a_pdf_fails(tmp_path, capsys):
    root = make_project(tmp_path, packs=[pack(4, "quote")])
    (root / "desk/packs/enq-04/quote.json").write_text(json.dumps({"total": "1000.00", "deposit": "300.00"}))
    code, out = run(root, capsys)
    assert code == 1 and "Missing PDF" in out


def test_a_pdf_for_an_enquiry_that_is_not_a_quote_is_flagged(tmp_path, capsys):
    root = make_project(tmp_path, packs=[pack(4, "clarify")])
    (root / "outputs/quotes/enq-04.pdf").write_bytes(b"%PDF-1.4\n")
    _, out = run(root, capsys)
    assert "must not go to the customer" in out


@pytest.mark.parametrize("wording", ["Our margin is 30%.", "Your price covers staff overtime.",
                                     "Details are in costing-and-margins.xlsx."])
def test_a_draft_with_internal_wording_fails(tmp_path, capsys, wording):
    root = make_project(tmp_path, packs=[pack(4)], drafts={"enq-04-reply.md": f"Dear Daniel,\n\n{wording}\n"})
    code, out = run(root, capsys)
    assert code == 1 and "Internal wording in a customer draft" in out
