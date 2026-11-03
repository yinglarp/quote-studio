"""Quote Studio pricing engine.

Turns an enquiry (a dict) into a priced Quote. Every price, charge and rate comes from
rates.json; nothing is hard-coded here. Money is Decimal, rounded half up to the cent.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

HERE = Path(__file__).resolve().parent
RATES_PATH = HERE / "rates.json"
CENT = Decimal("0.01")


class QuoteError(Exception):
    """A quote cannot be produced. The message is written for Priya, not for a developer."""


class BelowMinimum(QuoteError):
    pass


class RatesFileError(QuoteError):
    pass


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def load_rates(path: Path = RATES_PATH) -> dict:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        raise RatesFileError(f"Could not read the rates file {path.name}: {e.strerror or e}. No quote was made.") from e
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise RatesFileError(
            f"The rates file {path.name} is not valid JSON (line {e.lineno}, column {e.colno}: {e.msg}). No quote was made."
        ) from e


@dataclass
class Line:
    description: str
    quantity: Decimal
    unit: str
    unit_price: Decimal
    amount: Decimal


@dataclass
class Quote:
    quote_number: str
    issue_date: date
    valid_until: date
    customer_name: str
    company: str
    event_date: date
    headcount: int
    package_name: str
    delivery_zone_name: str
    delivery_address: str
    lines: list[Line]
    order_value: Decimal
    delivery_charge: Decimal
    delivery_free_reason: str
    subtotal: Decimal
    gst_rate: Decimal
    gst: Decimal
    total: Decimal
    deposit_rate: Decimal
    deposit: Decimal
    balance: Decimal
    terms_file: str
    terms_note: str
    cancellation_plain: str
    confirm_items: list[str]
    prices_checked_on: date
    company_details: dict = field(default_factory=dict)
    currency_symbol: str = "S$"


def _as_date(value) -> date:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError as e:
        raise QuoteError(f"'{value}' is not a valid date. Use the format YYYY-MM-DD.") from e


def _price_on(package: dict, event_date: date) -> Decimal:
    """The package price in force on the event date (latest 'from' that is not after it)."""
    in_force = [p for p in package["prices"] if date.fromisoformat(p["from"]) <= event_date]
    if not in_force:
        raise QuoteError(f"There is no {package['name']} price in force on {event_date:%d %b %Y}.")
    return Decimal(max(in_force, key=lambda p: p["from"])["price"])


def _terms_for(rates: dict, event_date: date) -> tuple[dict, str]:
    """(in-force terms entry, extra note) for the event year. Draft terms are never treated as in force."""
    terms = rates["terms"]
    year = str(event_date.year)
    entry = terms.get(year)
    if entry and entry["status"] == "in_force":
        return entry, ""
    in_force = [(y, t) for y, t in terms.items() if isinstance(t, dict) and t.get("status") == "in_force"]
    if not in_force:
        raise QuoteError("No terms and conditions are marked as in force in rates.json.")
    latest_year, latest = max(in_force, key=lambda yt: yt[0])
    if entry and entry["status"] == "draft" and int(year) > int(latest_year):
        return latest, (f"Your event is in {year}. The {year} terms and conditions are still a draft; "
                        f"this quote follows the {latest_year} terms until they are approved.")
    raise QuoteError(f"There are no terms and conditions in force for an event in {year}.")


def _slug(text: str) -> str:
    """First word of the company or customer name, e.g. 'Harbourline Insurance' -> 'HARBOURLINE'."""
    words = re.findall(r"[A-Z0-9]+", text.upper())
    return words[0][:12] if words else "QUOTE"


def price_quote(enquiry: dict, rates: dict | None = None) -> Quote:
    rates = rates if rates is not None else load_rates()
    sym = rates.get("currency_symbol", "S$")

    event_date = _as_date(enquiry["event_date"])
    issue_date = _as_date(enquiry.get("issue_date") or date.today())
    headcount = int(enquiry["headcount"])
    if headcount <= 0:
        raise QuoteError("The headcount must be at least 1.")

    pkg_key = enquiry["package"]
    if pkg_key not in rates["packages"]:
        raise QuoteError(f"Unknown package '{pkg_key}'.")
    pkg = rates["packages"][pkg_key]
    if headcount < pkg["minimum"]:
        raise BelowMinimum(
            f"{pkg['name']} needs at least {pkg['minimum']} {pkg['unit']}"
            f"{'es' if pkg['unit'] == 'box' else ''}; this enquiry has {headcount}. No quote was made."
        )

    lines: list[Line] = []
    unit_price = _price_on(pkg, event_date)
    lines.append(Line(pkg["name"], Decimal(headcount), pkg["unit"], unit_price, money(unit_price * headcount)))

    add = rates["add_ons"]
    if enquiry.get("extra_dessert"):
        a = add["extra_dessert"]
        p = Decimal(a["price"])
        lines.append(Line(a["name"], Decimal(headcount), "pax", p, money(p * headcount)))

    stations = int(enquiry.get("live_stations") or 0)
    if stations:
        a = add["live_station"]
        kind = (enquiry.get("live_station_kind") or "").strip().lower()
        if kind and kind not in a["kinds"]:
            raise QuoteError(f"Live stations can be {' or '.join(a['kinds'])}, not '{kind}'.")
        p = Decimal(a["price"])
        desc = f"{a['name']} ({kind})" if kind else a["name"]
        lines.append(Line(desc, Decimal(stations), "station", p, money(p * stations)))

    confirm_items = list(enquiry.get("confirm_items") or [])
    crew = int(enquiry.get("service_staff") or 0)
    if crew:
        a = add["service_staff"]
        asked = Decimal(str(enquiry.get("service_hours") or 0))
        minimum = Decimal(a["minimum_hours"])
        hours = max(asked, minimum)
        if asked < minimum:
            confirm_items.append(f"Service staff are booked for at least {a['minimum_hours']} hours each, "
                                 f"so {fmt_qty(hours)} hours are quoted instead of {fmt_qty(asked)}.")
        p = Decimal(a["price"])
        lines.append(Line(f"{a['name']}, {crew} x {fmt_qty(hours)} hours", Decimal(crew) * hours,
                          "staff-hour", p, money(p * crew * hours)))

    order_value = sum((l.amount for l in lines), Decimal("0"))

    deliv = rates["delivery"]
    zone_key = enquiry["delivery_zone"]
    if zone_key not in deliv["zones"]:
        raise QuoteError(f"Unknown delivery zone '{zone_key}'.")
    zone = deliv["zones"][zone_key]
    threshold = Decimal(deliv["free_above_order_value"])
    rc = deliv["repeat_corporate"]
    if order_value > threshold:
        delivery_charge = Decimal("0.00")
        free_reason = f"Free: orders above {sym}{threshold:,.2f} before GST get free delivery."
    elif enquiry.get("repeat_corporate") and rc["free_delivery"] and zone_key not in rc["excluded_zones"]:
        delivery_charge = Decimal("0.00")
        free_reason = "Free: thank you for being a repeat corporate client."
    else:
        delivery_charge = money(Decimal(zone["charge"]))
        free_reason = ""

    subtotal = order_value + delivery_charge
    gst_rate = Decimal(rates["gst_rate"])
    gst = money(subtotal * gst_rate)
    total = subtotal + gst
    deposit_rate = Decimal(rates["deposit_rate"])
    deposit = money(total * deposit_rate)

    terms, terms_note = _terms_for(rates, event_date)

    # Issue date + customer + event date, so two quotes for one customer on one day stay distinct.
    number = enquiry.get("quote_number") or (
        f"Q-{issue_date:%Y%m%d}-{_slug(enquiry.get('company') or enquiry['customer_name'])}-{event_date:%m%d}")

    return Quote(
        quote_number=number,
        issue_date=issue_date,
        valid_until=issue_date + timedelta(days=int(rates["quote_valid_days"])),
        customer_name=enquiry["customer_name"],
        company=enquiry.get("company", ""),
        event_date=event_date,
        headcount=headcount,
        package_name=pkg["name"],
        delivery_zone_name=zone["name"],
        delivery_address=enquiry.get("delivery_address", ""),
        lines=lines,
        order_value=order_value,
        delivery_charge=delivery_charge,
        delivery_free_reason=free_reason,
        subtotal=subtotal,
        gst_rate=gst_rate,
        gst=gst,
        total=total,
        deposit_rate=deposit_rate,
        deposit=deposit,
        balance=total - deposit,
        terms_file=terms["file"],
        terms_note=terms_note,
        cancellation_plain=terms["cancellation_plain"],
        confirm_items=confirm_items,
        prices_checked_on=date.fromisoformat(rates["prices_checked_on"]),
        company_details=rates["company"],
        currency_symbol=sym,
    )


def fmt_money(value: Decimal, sym: str = "S$") -> str:
    return f"{sym}{value:,.2f}"


def fmt_qty(value: Decimal) -> str:
    """120 -> '120', 3.5 -> '3.5' (Decimal.normalize alone would give '1.2E+2')."""
    return f"{value.normalize():f}"


def fmt_date(d: date) -> str:
    """Friday 11 December 2026 — never 11/12."""
    return f"{d:%A} {d.day} {d:%B %Y}"
