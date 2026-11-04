"""End-to-end tests: the finished output of a Desk run, read the way Priya and a customer would see it.

Checks packs, draft replies (outputs/drafts/), quote PDFs (outputs/quotes/) and desk/bookings.csv
together. outputs/ is gitignored, so on a fresh clone the draft tests are skipped, not failed.
Source: desk/desk-rules.md sections 1, 3, 4 and 5.
"""
import re
import subprocess
import sys

import pytest

from desk_helpers import (ROOT, all_packs, booking_customers, date_confirmations, date_promises, holds_date,
                          internal_references, mentions, safety_claims)

pytestmark = pytest.mark.e2e

PACKS = all_packs()
DRAFTS = {f.name[:6]: f for f in sorted((ROOT / "outputs" / "drafts").glob("enq-*-reply.md"))}
DECIDED = sorted(n for n, p in PACKS.items() if "outcome" in p)


def drafts_where(pred=lambda name: True):
    names = [n for n in sorted(DRAFTS) if pred(n)]
    return pytest.mark.parametrize("name", names or [pytest.param(None, marks=pytest.mark.skip(reason="no matching drafts"))])


def outcome_of(name):
    return PACKS.get(name, {}).get("outcome", {}).get("outcome")


def reply(name):
    return DRAFTS[name].read_text(encoding="utf-8")


def test_the_desk_validator_passes_on_the_real_project():
    r = subprocess.run([sys.executable, str(ROOT / "desk/validate_desk.py"), "--root", str(ROOT)],
                       cwd=str(ROOT), capture_output=True, text=True, timeout=150)
    assert r.returncode == 0, r.stderr + r.stdout


@pytest.mark.parametrize("name", DECIDED or [pytest.param(None, marks=pytest.mark.skip(reason="no decided packs"))])
def test_every_decided_enquiry_has_a_draft_reply(name):
    assert name in DRAFTS, f"{name} has an outcome but no outputs/drafts/{name}-reply.md"


@drafts_where()
def test_every_draft_belongs_to_a_decided_pack(name):
    assert outcome_of(name) in ("quote", "clarify", "escalate"), f"{name}-reply.md has no outcome.json behind it"


@drafts_where(lambda n: outcome_of(n) != "quote")
def test_a_reply_never_promises_a_date_without_a_quote(name):
    assert date_promises(reply(name)) == []


@drafts_where(lambda n: outcome_of(n) == "quote")
def test_a_quote_reply_says_held_until_the_deposit_never_confirmed(name):
    text = reply(name)
    assert date_confirmations(text) == []
    assert re.search(r"\bheld\b", text, re.I) and re.search(r"\bdeposit\b", text, re.I)


@drafts_where()
def test_a_reply_has_no_internal_costs_pay_or_file_names(name):
    assert internal_references(reply(name)) == []


@drafts_where()
def test_a_reply_never_names_another_customer(name):
    own = {v for kind in ("event", "contact") for k, v in PACKS.get(name, {}).get(kind, {}).items()
           if k in ("client", "company", "name") and v}
    others = booking_customers()
    for other, pack in PACKS.items():
        if other != name:
            others |= {v for kind in ("event", "contact") for k, v in pack.get(kind, {}).items()
                       if k in ("client", "company", "name") and v}
    leaked = sorted(o for o in others - own if mentions(reply(name), o))
    assert leaked == []


@drafts_where(lambda n: bool(PACKS.get(n, {}).get("menu", {}).get("clashes")))
def test_a_reply_with_an_allergy_clash_never_says_the_food_is_safe(name):
    assert safety_claims(reply(name)) == []


@pytest.mark.parametrize("name", DECIDED or [pytest.param(None, marks=pytest.mark.skip(reason="no decided packs"))])
def test_only_quotes_have_a_quote_pdf(name):
    pdfs = list((ROOT / "outputs" / "quotes").glob(f"{name}*.pdf"))
    if outcome_of(name) == "quote":
        assert pdfs, f"{name} is a quote but outputs/quotes/{name}.pdf is missing"
    else:
        assert pdfs == [], f"{name} is '{outcome_of(name)}' but has {[p.name for p in pdfs]}"


def test_the_first_received_enquiry_keeps_the_last_slot():
    """Anyone escalated to Jun Wei on a date someone else holds must have been received after the holder."""
    for name, p in PACKS.items():
        o = p.get("outcome", {})
        if o.get("outcome") != "escalate" or o.get("owner") != "Jun Wei":
            continue
        for other, q in PACKS.items():
            h = q.get("outcome", {})
            if other != name and holds_date(h) and h["date"] == o["date"]:
                assert h["received"] <= o["received"], f"{other} holds {o['date']} but {name} was received first"


def test_bookings_csv_is_unchanged_from_git():
    """Agents never change bookings.csv (desk-rules.md section 1). Line endings are ignored."""
    r = subprocess.run(["git", "show", "HEAD:desk/bookings.csv"], cwd=str(ROOT), capture_output=True, text=True)
    if r.returncode != 0:
        pytest.skip("git history not available")
    committed = r.stdout.replace("\r\n", "\n").strip()
    current = (ROOT / "desk/bookings.csv").read_text(encoding="utf-8").replace("\r\n", "\n").strip()
    assert current == committed
