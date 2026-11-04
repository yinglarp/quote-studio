#!/usr/bin/env python3
"""Run the Quote Studio engine on one Desk pack (graph nodes N7 and N9).

Run from the project folder:

    python .claude/skills/run-desk/price_pack.py enq-04          N7: write desk/packs/enq-04/quote.json
    python .claude/skills/run-desk/price_pack.py enq-04 --pdf    N9: write outputs/quotes/enq-04.pdf

N7 maps event.json (and the name/company from contact.json) onto the engine's input keys and saves the
engine's result unchanged: {"status": "ok", ...} or {"status": "refused", "reason": ...}.
N9 re-prices with the saved quote number and issue date, refuses if total or deposit differ from
quote.json, and renders the PDF with quote-calculator/pdf.py.

This file only adapts field names. Every price comes from engine.py and rates.json.
Exit code 0 = done, 1 = the engine refused or the reprice did not match, 2 = a file could not be read.
"""
import json
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "quote-calculator"))

import engine  # noqa: E402


def read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"CANNOT READ {path.relative_to(ROOT)}: {e}", file=sys.stderr)
        sys.exit(2)


def engine_input(event: dict, contact: dict) -> dict:
    add = event.get("add_ons") or {}
    return {
        "customer_name": contact.get("name") or event["client"],
        "company": contact.get("company") or "",
        "event_date": event["date"],
        "headcount": event["pax"],
        "package": event["package"],
        "delivery_zone": event["zone"],
        "delivery_address": event.get("venue") or "",
        "extra_dessert": bool(add.get("extra_dessert")),
        "live_stations": add.get("live_stations") or 0,
        "service_staff": add.get("staff") or 0,
        "service_hours": add.get("staff_hours") or 0,
        "repeat_corporate": bool(event.get("repeat_client")),
    }


def plain(v):
    if isinstance(v, Decimal):
        return str(v)
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return v


def to_json(q: engine.Quote) -> dict:
    money = lambda d: f"{d:.2f}"
    return {
        "status": "ok",
        "quote_number": q.quote_number,
        "issue_date": q.issue_date.isoformat(),
        "valid_until": q.valid_until.isoformat(),
        "customer_name": q.customer_name,
        "company": q.company,
        "event_date": q.event_date.isoformat(),
        "headcount": q.headcount,
        "package_name": q.package_name,
        "delivery_zone_name": q.delivery_zone_name,
        "delivery_address": q.delivery_address,
        "lines": [{"description": l.description, "quantity": plain(l.quantity), "unit": l.unit,
                   "unit_price": money(l.unit_price), "amount": money(l.amount)} for l in q.lines],
        "order_value": money(q.order_value),
        "delivery_charge": money(q.delivery_charge),
        "delivery_free_reason": q.delivery_free_reason,
        "subtotal": money(q.subtotal),
        "gst_rate": str(q.gst_rate),
        "gst": money(q.gst),
        "total": money(q.total),
        "deposit_rate": str(q.deposit_rate),
        "deposit": money(q.deposit),
        "balance": money(q.balance),
        "terms_file": q.terms_file,
        "terms_note": q.terms_note,
        "cancellation_plain": q.cancellation_plain,
        "confirm_items": q.confirm_items,
        "prices_checked_on": q.prices_checked_on.isoformat(),
    }


def main(argv):
    if not argv or not argv[0].startswith("enq-"):
        print(__doc__, file=sys.stderr)
        return 2
    name, want_pdf = argv[0], "--pdf" in argv
    pack = ROOT / "desk" / "packs" / name
    enquiry = engine_input(read_json(pack / "event.json"), read_json(pack / "contact.json"))

    if not want_pdf:
        try:
            result = to_json(engine.price_quote(enquiry))
        except engine.QuoteError as e:
            result = {"status": "refused", "reason": str(e)[:200]}
        (pack / "quote.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"{name}: quote.json {result['status']}"
              + (f", total {result['total']}, deposit {result['deposit']}, terms {result['terms_file']}"
                 if result["status"] == "ok" else f" - {result['reason']}"))
        return 0 if result["status"] == "ok" else 1

    saved = read_json(pack / "quote.json")
    if saved.get("status") != "ok":
        print(f"{name}: quote.json is not 'ok', so no PDF is made.", file=sys.stderr)
        return 1
    enquiry.update(issue_date=saved["issue_date"], quote_number=saved["quote_number"])
    q = engine.price_quote(enquiry)
    if (f"{q.total:.2f}", f"{q.deposit:.2f}") != (saved["total"], saved["deposit"]):
        print(f"{name}: reprice gives total {q.total:.2f} / deposit {q.deposit:.2f}, but quote.json has "
              f"{saved['total']} / {saved['deposit']}. No PDF made. Re-run N7.", file=sys.stderr)
        return 1
    from pdf import render_pdf
    out = render_pdf(q, ROOT / "outputs" / "quotes" / f"{name}.pdf")
    print(f"{name}: PDF -> {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
