"""Integration tests: the real packs in desk/packs/, each file checked against its contract and
against the other files in the same pack and desk/bookings.csv.

Packs can be part-way through a run (enq-01 may have only event.json and contact.json), so each
test checks only the files that exist. Source: desk/desk-rules.md sections 1, 3 and 4, and design/schemas/.
"""
import pytest

from desk_helpers import LIMIT, PACK_FILES, ROOT, all_packs, booked_counts, schema_errors

pytestmark = pytest.mark.integration

PACKS = all_packs()
FILES = [(name, kind) for name, pack in PACKS.items() for kind in PACK_FILES if kind in pack and kind != "quote"]
INBOX_IDS = {f.name[:6] for f in (ROOT / "inbox").glob("enq-*.txt")}
# event.json fields that change the price, the date or the menu (desk-rules.md section 3).
PRICE_DATE_MENU = ("date", "pax", "package", "zone", "venue", "add_ons", "dietary")


def with_files(*kinds):
    names = [n for n, p in PACKS.items() if all(k in p for k in kinds)]
    return pytest.mark.parametrize("name", names or [pytest.param(None, marks=pytest.mark.skip(reason=f"no pack has {kinds} yet"))])


@pytest.mark.parametrize("name,kind", FILES, ids=[f"{n}-{k}" for n, k in FILES])
def test_each_pack_file_meets_its_contract(name, kind):
    assert schema_errors(PACKS[name][kind], kind) == []


@pytest.mark.parametrize("name", sorted(PACKS))
def test_each_pack_folder_matches_an_enquiry_in_the_inbox(name):
    assert name in INBOX_IDS, f"desk/packs/{name}/ has no matching inbox/{name}-*.txt"


@pytest.mark.parametrize("name", sorted(PACKS))
def test_enquiry_id_matches_the_folder(name):
    for kind in ("event", "outcome"):
        if kind in PACKS[name]:
            assert PACKS[name][kind]["enquiry_id"] == name, f"{kind}.json"


@with_files("capacity")
def test_capacity_booked_matches_bookings_csv(name):
    cap = PACKS[name]["capacity"]
    if cap["date"] is None:
        pytest.skip("no date yet")
    assert cap["booked"] == booked_counts()[cap["date"]], f"bookings.csv has {booked_counts()[cap['date']]} jobs on {cap['date']}"


@with_files("capacity")
def test_free_slots_are_the_limit_minus_booked_and_held(name):
    cap = PACKS[name]["capacity"]
    if cap["booked"] is None or cap["held"] is None:
        pytest.skip("capacity not worked out yet")
    assert cap["free_slots"] == max(0, LIMIT - cap["booked"] - cap["held"])
    assert (cap["status"] == "full") == (cap["free_slots"] == 0)


@with_files("event", "outcome")
def test_outcome_date_and_received_match_the_event(name):
    ev, o = PACKS[name]["event"], PACKS[name]["outcome"]
    assert o["date"] == ev["date"]
    assert o["received"] == ev["received"]


@with_files("event", "capacity")
def test_capacity_checked_the_event_date(name):
    assert PACKS[name]["capacity"]["date"] == PACKS[name]["event"]["date"]


@with_files("capacity", "outcome")
def test_a_full_date_is_escalated_to_jun_wei(name):
    cap, o = PACKS[name]["capacity"], PACKS[name]["outcome"]
    if cap["status"] != "full":
        pytest.skip("date has room")
    assert o["outcome"] == "escalate" and o["holds_date"] is False
    assert o.get("owner") == "Jun Wei"


@with_files("capacity", "menu", "outcome")
def test_an_allergy_clash_is_escalated_to_priya(name):
    p = PACKS[name]
    if not p["menu"]["clashes"]:
        pytest.skip("no allergy clash")
    assert p["outcome"]["outcome"] == "escalate"
    assert p["menu"]["verdict"] == "FLAG"
    expected = {"Priya", "Jun Wei"} if p["capacity"]["status"] == "full" else {"Priya"}
    assert p["outcome"].get("owner") in expected


@with_files("event", "outcome")
def test_a_missing_or_assumed_fact_is_never_a_quote(name):
    ev, o = PACKS[name]["event"], PACKS[name]["outcome"]
    open_facts = [k for k in PRICE_DATE_MENU if ev["field_status"].get(k) in ("missing", "assumed")]
    if not open_facts:
        pytest.skip("all facts verified")
    assert o["outcome"] != "quote", f"{', '.join(open_facts)} not verified"


@with_files("event", "capacity", "menu", "outcome")
def test_a_quote_has_complete_facts_room_and_a_suitable_menu(name):
    p = PACKS[name]
    if p["outcome"]["outcome"] != "quote":
        pytest.skip("not a quote")
    assert all(v == "verified" for k, v in p["event"]["field_status"].items() if k in PRICE_DATE_MENU)
    assert p["capacity"]["status"] == "has_room" and p["capacity"]["date_status"] == "verified"
    assert p["menu"]["verdict"] == "OK" and p["menu"]["clashes"] == []
    assert p["outcome"]["holds_date"] is True
    assert "quote" in p, "a quote needs quote.json from the Quote Studio engine"
