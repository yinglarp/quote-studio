"""Shared helpers for the Enquiry Desk rule tests (desk/tests/).

Every rule tested here comes from desk/desk-rules.md or the contract schemas in design/schemas/.
The reply checks (date promises, safety claims, internal references) are deliberately simple:
they look at one sentence at a time and ignore sentences that are negated, conditional or a
question, so "We have not yet confirmed or held the date." is not mistaken for a promise.
"""
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desk"
SCHEMAS = ROOT / "design" / "schemas"
sys.path.insert(0, str(DESK))

import check_contract  # noqa: E402
import validate_desk  # noqa: E402

LIMIT = 18
PACK_FILES = ("event", "contact", "capacity", "menu", "quote", "outcome")


# ---------- packs and bookings ----------

def pack_dirs(root=ROOT):
    return sorted(p for p in (root / "desk" / "packs").glob("enq-*") if p.is_dir())


def load_pack(folder):
    """{'event': {...}, 'outcome': {...}, ...} for the files that exist in one pack folder."""
    pack = {}
    for name in PACK_FILES:
        f = folder / f"{name}.json"
        if f.exists():
            pack[name] = json.loads(f.read_text(encoding="utf-8"))
    return pack


def all_packs(root=ROOT):
    return {d.name: load_pack(d) for d in pack_dirs(root)}


def booked_counts(root=ROOT):
    with open(root / "desk" / "bookings.csv", newline="", encoding="utf-8") as f:
        return Counter(r["date"] for r in csv.DictReader(f))


def booking_customers(root=ROOT):
    with open(root / "desk" / "bookings.csv", newline="", encoding="utf-8") as f:
        return {r["customer"].strip() for r in csv.DictReader(f) if r.get("customer")}


def schema_errors(data, kind):
    schema = json.loads((SCHEMAS / f"{kind}.schema.json").read_text(encoding="utf-8"))
    errors = []
    check_contract.check(data, schema, "", errors)
    return errors


def holds_date(outcome):
    """A pack holds its date when it is a quote or says holds_date (desk-rules.md section 1)."""
    return bool(outcome.get("date")) and (outcome.get("outcome") == "quote" or outcome.get("holds_date") is True)


# ---------- reply text ----------

_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")
# A sentence with any of these is negated, conditional, a request or about a future step: not a promise.
_HEDGE = re.compile(r"\b(not|no|never|cannot|can't|won't|unless|until|once|before|after|if|please|could you|can you|would you)\b|n't\b", re.I)
_DATE_WORD = re.compile(r"\b(date|booking|slot|day|event)\b", re.I)
_HOLD_WORD = re.compile(r"\b(confirm(?:s|ed)?|held|hold(?:ing)?|reserv(?:e|ed|ing)|secur(?:e|ed)|lock(?:ed)? in|guarantee[sd]?)\b", re.I)
_CONFIRM_WORD = re.compile(r"\b(confirm(?:s|ed)?|guarantee[sd]?|lock(?:ed)? in)\b", re.I)
_SAFE = re.compile(
    r"\b(safe|allergen[- ]free|(?:peanut|nut|gluten|dairy|egg|shellfish|seafood)[- ]free"
    r"|free (?:of|from) (?:all )?(?:peanuts?|nuts?|allergens?)|risk[- ]free)\b", re.I)
_INTERNAL = [
    re.compile(r"\b[\w./-]+\.(?:json|csv|md|xlsx|py|html)\b", re.I),  # file names
    re.compile(r"\b(?:desk|packs|outputs|reference|design|quote-calculator)/", re.I),  # folders
    re.compile(r"\benq-\d\d\b", re.I),  # internal enquiry IDs
]


def sentences(text):
    return [s.strip() for s in _SPLIT.split(text) if s.strip()]


def _affirmative(s):
    return not _HEDGE.search(s) and not s.endswith("?")


def date_promises(text):
    """Sentences that say the date is confirmed, held, reserved or secured."""
    return [s for s in sentences(text) if _affirmative(s) and _DATE_WORD.search(s) and _HOLD_WORD.search(s)]


def date_confirmations(text):
    """Sentences that say the date is confirmed (stronger than 'held'): never allowed, even for a quote."""
    return [s for s in sentences(text) if _affirmative(s) and _DATE_WORD.search(s) and _CONFIRM_WORD.search(s)]


def safety_claims(text):
    """Sentences that say food is safe or free of an allergen."""
    return [s for s in sentences(text) if _affirmative(s) and _SAFE.search(s)]


def internal_references(text):
    """File names, internal folders, enquiry IDs and cost/margin/pay wording (validate_desk.LEAK)."""
    found = {m.group(0) for p in _INTERNAL for m in p.finditer(text)}
    return sorted(found | set(validate_desk.leaks(text)))


def mentions(text, name):
    return re.search(r"(?<!\w)" + re.escape(name) + r"(?!\w)", text, re.I) is not None
