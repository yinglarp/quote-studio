import copy
import json
import sys
from decimal import Decimal
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import engine  # noqa: E402

CASES = sorted((HERE.parent / "test_cases").glob("*.json"))
MONEY = ("order_value", "delivery_charge", "gst", "total", "deposit", "balance")


def load(name):
    return json.loads((HERE.parent / "test_cases" / f"{name}.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def rates():
    return engine.load_rates()


@pytest.mark.parametrize("case_file", CASES, ids=lambda p: p.stem)
def test_case_figures(case_file, rates):
    case = json.loads(case_file.read_text(encoding="utf-8"))
    exp = case["expected"]
    if "error" in exp:
        with pytest.raises(getattr(engine, exp["error"])):
            engine.price_quote(case["enquiry"], rates)
        return
    q = engine.price_quote(case["enquiry"], rates)
    for k in MONEY:
        assert getattr(q, k) == Decimal(exp[k]), k
    assert q.terms_file == exp["terms_file"]
    if "terms_note_contains" in exp:
        assert exp["terms_note_contains"] in q.terms_note
    # internal consistency: lines add up, balance + deposit = total
    assert sum(l.amount for l in q.lines) == q.order_value
    assert q.order_value + q.delivery_charge + q.gst == q.total
    assert q.deposit + q.balance == q.total


def test_classic_buffet_price_changes_on_1_october(rates):
    enq = load("harbourline-town-hall")["enquiry"]
    before = engine.price_quote({**enq, "event_date": "2026-09-30"}, rates)
    after = engine.price_quote({**enq, "event_date": "2026-10-01"}, rates)
    assert before.lines[0].unit_price == Decimal("24.80")
    assert after.lines[0].unit_price == Decimal("26.80")


def _order(value_pax, rates, **extra):
    """A Mini Buffet order with no add-ons; 18.80 x pax."""
    enq = {"customer_name": "T", "issue_date": "2026-11-03", "event_date": "2026-11-20",
           "package": "mini_buffet", "headcount": value_pax, "delivery_zone": "standard", **extra}
    return engine.price_quote(enq, rates)


def test_free_delivery_only_above_800(rates):
    # Use rates with a 1-cent price to land exactly on S$800.00.
    r = copy.deepcopy(rates)
    r["packages"]["mini_buffet"]["prices"] = [{"from": "2026-01-01", "price": "10.00"}]
    at = _order(80, r)    # S$800.00 exactly -> charged
    above = _order(81, r)  # S$810.00 -> free
    assert at.order_value == Decimal("800.00") and at.delivery_charge == Decimal("35.00")
    assert above.delivery_charge == Decimal("0.00")


def test_600_rule_from_ops_notes_is_not_used(rates):
    q = _order(33, rates)  # 33 x 18.80 = 620.40, above 600 but not 800
    assert q.delivery_charge == Decimal("35.00")


def test_repeat_corporate_free_except_sentosa(rates):
    assert _order(20, rates, repeat_corporate=True).delivery_charge == 0
    sentosa = _order(20, rates, repeat_corporate=True, delivery_zone="sentosa_jurong")
    assert sentosa.delivery_charge == Decimal("80.00")


def test_service_hours_minimum_three(rates):
    q = _order(20, rates, service_staff=2, service_hours=2)
    staff = q.lines[-1]
    assert staff.quantity == 6 and staff.amount == Decimal("210.00")
    assert any("at least 3 hours" in s for s in q.confirm_items)


def test_rounding_half_up(rates):
    # 30% of 4,192.14 = 1,257.642 -> 1,257.64 ; GST 9% of 3,846.00 = 346.14
    q = engine.price_quote(load("harbourline-town-hall")["enquiry"], rates)
    assert q.deposit == Decimal("1257.64")
    assert engine.money(Decimal("0.125")) == Decimal("0.13")


def test_valid_until_is_14_days(rates):
    q = engine.price_quote(load("harbourline-town-hall")["enquiry"], rates)
    assert (q.valid_until - q.issue_date).days == 14


def test_draft_terms_never_in_force(rates):
    q = engine.price_quote(load("event-2027")["enquiry"], rates)
    assert q.terms_file == "terms-2026.md"
    assert "draft" in q.terms_note


def test_unreadable_rates_file_stops(tmp_path):
    with pytest.raises(engine.RatesFileError, match="Could not read"):
        engine.load_rates(tmp_path / "missing.json")
    bad = tmp_path / "rates.json"
    bad.write_text("{ not json", encoding="utf-8")
    with pytest.raises(engine.RatesFileError, match="not valid JSON"):
        engine.load_rates(bad)


def test_formats():
    from datetime import date
    assert engine.fmt_date(date(2026, 12, 11)) == "Friday 11 December 2026"
    assert engine.fmt_money(Decimal("4192.14")) == "S$4,192.14"
    assert engine.fmt_qty(Decimal("120")) == "120"
