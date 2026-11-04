"""Unit tests: each Desk rule checked on small in-memory examples, no repo data.

Sources: desk/desk-rules.md (sections 1, 3, 4, 5) and the contracts in design/schemas/.
"""
import pytest

from desk_helpers import (date_confirmations, date_promises, holds_date, internal_references,
                          safety_claims, schema_errors, validate_desk)

pytestmark = pytest.mark.unit


def outcome(**kw):
    base = {"enquiry_id": "enq-01", "outcome": "clarify", "received": "2026-10-15T11:12",
            "date": "2026-11-20", "holds_date": False, "reason": "Dietary needs are missing."}
    base.update(kw)
    return {k: v for k, v in base.items() if v is not ...}


def capacity(**kw):
    base = {"date": "2026-11-20", "booked": 9, "held": 0, "limit": 18, "free_slots": 9, "status": "has_room",
            "alternatives": [], "date_status": "verified", "open_questions": []}
    base.update(kw)
    return base


# ---- desk-rules.md section 3: every enquiry ends in exactly one of three ways ----

@pytest.mark.parametrize("value", ["quote", "clarify", "escalate"])
def test_the_three_outcomes_are_accepted(value):
    extra = {"owner": "Priya"} if value == "escalate" else {}
    o = outcome(outcome=value, holds_date=value == "quote", **extra)
    assert schema_errors(o, "outcome") == []


@pytest.mark.parametrize("value", ["pending", "declined", "", None])
def test_any_other_outcome_is_rejected(value):
    assert any("outcome" in e for e in schema_errors(outcome(outcome=value), "outcome"))


def test_quote_must_hold_its_date():
    errors = schema_errors(outcome(outcome="quote", holds_date=False, reason=...), "outcome")
    assert any("holds_date" in e for e in errors)


@pytest.mark.parametrize("value", ["clarify", "escalate"])
def test_clarify_and_escalate_never_hold_the_date(value):
    errors = schema_errors(outcome(outcome=value, holds_date=True, owner="Jun Wei" if value == "escalate" else ...), "outcome")
    assert any("holds_date" in e for e in errors)


@pytest.mark.parametrize("value", ["clarify", "escalate"])
def test_clarify_and_escalate_need_a_reason(value):
    errors = schema_errors(outcome(outcome=value, reason=..., owner="Priya" if value == "escalate" else ...), "outcome")
    assert any("reason" in e for e in errors)


def test_escalation_must_name_its_owner():
    assert any("owner" in e for e in schema_errors(outcome(outcome="escalate"), "outcome"))


def test_escalation_owner_is_priya_or_jun_wei():
    assert any("owner" in e for e in schema_errors(outcome(outcome="escalate", owner="Hafiz"), "outcome"))


@pytest.mark.parametrize("value", ["quote", "clarify"])
def test_only_escalations_have_an_owner(value):
    o = outcome(outcome=value, holds_date=value == "quote", owner="Priya")
    assert any("owner" in e for e in schema_errors(o, "outcome"))


# ---- desk-rules.md section 1 and 4: capacity.json ----

def test_limit_is_always_18():
    assert any("limit" in e for e in schema_errors(capacity(limit=19), "capacity"))


def test_a_date_with_room_has_free_slots_and_no_alternatives():
    assert any("free_slots" in e for e in schema_errors(capacity(free_slots=0), "capacity"))
    assert any("alternatives" in e for e in schema_errors(capacity(alternatives=[{"date": "2026-11-21", "free_slots": 3}]), "capacity"))


def test_a_full_date_has_no_free_slots():
    assert any("free_slots" in e for e in schema_errors(capacity(status="full", free_slots=1), "capacity"))


def test_a_full_date_offers_at_most_two_alternatives_with_room():
    three = [{"date": f"2026-11-2{i}", "free_slots": 2} for i in range(3)]
    assert any("alternatives" in e for e in schema_errors(capacity(status="full", free_slots=0, booked=18, alternatives=three), "capacity"))
    no_room = [{"date": "2026-11-21", "free_slots": 0}]
    assert any("free_slots" in e for e in schema_errors(capacity(status="full", free_slots=0, booked=18, alternatives=no_room), "capacity"))


def test_holds_count_for_quotes_and_holds_date_only():
    assert holds_date({"outcome": "quote", "date": "2026-11-06", "holds_date": True})
    assert holds_date({"outcome": "clarify", "date": "2026-11-06", "holds_date": True})
    assert not holds_date({"outcome": "clarify", "date": "2026-11-06", "holds_date": False})
    assert not holds_date({"outcome": "quote", "date": None, "holds_date": True})


# ---- desk-rules.md section 5: what a reply may say ----

@pytest.mark.parametrize("text", [
    "Your date of 6 November is confirmed.",
    "We have reserved the date for you.",
    "Great news: your booking is held for Friday.",
    "We have secured the slot on 20 November.",
])
def test_a_date_promise_is_caught(text):
    assert date_promises(text)


@pytest.mark.parametrize("text", [
    "We have not yet confirmed or held the date.",
    "Please confirm that 88 Orchard Road, level 12 is the correct address for delivery.",
    "Could you share a contact phone number for the day?",
    "Your date is held until the deposit is paid.",
    "Once we have your answers, we will come back to you with the next steps.",
])
def test_a_safe_sentence_is_not_a_date_promise(text):
    assert date_promises(text) == []


def test_a_quote_reply_may_say_held_but_never_confirmed():
    assert date_confirmations("Your date of 6 November is held for you.") == []
    assert date_confirmations("Your booking for 6 November is confirmed.")


@pytest.mark.parametrize("text", [
    "The buffet is safe for your peanut-allergic guests.",
    "Every dish will be peanut-free.",
    "Our menu is free of nuts.",
])
def test_a_safety_claim_is_caught(text):
    assert safety_claims(text)


@pytest.mark.parametrize("text", [
    "Our food is prepared in a shared kitchen, so we cannot guarantee that any dish is free of allergens.",
    "We cannot describe any dish as safe for an allergy.",
])
def test_a_shared_kitchen_warning_is_not_a_safety_claim(text):
    assert safety_claims(text) == []


@pytest.mark.parametrize("text", [
    "See desk/packs/enq-03/outcome.json for details.",
    "Our margin on this menu is low.",
    "The figures come from rates.json.",
    "This is enquiry enq-04.",
    "Prices include overtime for the crew.",
])
def test_internal_wording_is_caught(text):
    assert internal_references(text)


def test_a_normal_reply_has_no_internal_wording():
    text = ("Thank you for your enquiry for 40 guests on 6 November 2026 at 88 Orchard Road, level 12. "
            "We have the Classic Buffet noted for your enquiry.")
    assert internal_references(text) == []


@pytest.mark.parametrize("word", ["gross margin", "food cost", "payroll", "cost price", "Northgate supplier"])
def test_validator_leak_list_still_covers_costs_margins_and_pay(word):
    assert validate_desk.leaks(f"This line mentions {word}.")
