"""Quote Studio form for Priya: a small web page that runs only on this computer.

    python quote-calculator/app.py        (or double-click Start-Quote-Studio.bat)

Opens http://127.0.0.1:8765 in the browser. Listens on 127.0.0.1 only, so nothing is reachable
from the network. PDFs are saved to outputs/quotes/.
"""
from __future__ import annotations

import json
import re
import threading
import webbrowser
from datetime import date
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import engine
from pdf import render_pdf

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUTPUT = ROOT / "outputs" / "quotes"
DESIGN = ROOT / "design"
HOST, PORT = "127.0.0.1", 8765
MAX_BODY = 64 * 1024

STATIC = {
    "/": (HERE / "form.html", "text/html; charset=utf-8"),
    "/logo.png": (DESIGN / "heicoders-catering-logo.png", "image/png"),
    "/fonts/roboto-400.ttf": (DESIGN / "fonts" / "roboto-400.ttf", "font/ttf"),
    "/fonts/roboto-500.ttf": (DESIGN / "fonts" / "roboto-500.ttf", "font/ttf"),
    "/fonts/roboto-700.ttf": (DESIGN / "fonts" / "roboto-700.ttf", "font/ttf"),
}


def options() -> dict:
    rates = engine.load_rates()
    return {
        "packages": [{"key": k, "name": p["name"], "minimum": p["minimum"], "unit": p["unit"]}
                     for k, p in rates["packages"].items()],
        "zones": [{"key": k, "name": z["name"], "where": z["where"]} for k, z in rates["delivery"]["zones"].items()],
        "station_kinds": rates["add_ons"]["live_station"]["kinds"],
        "staff_min_hours": rates["add_ons"]["service_staff"]["minimum_hours"],
        "repeat_corporate_definition": rates["delivery"]["repeat_corporate"]["definition"],
    }


def summary(q: engine.Quote) -> dict:
    m = lambda v: engine.fmt_money(v, q.currency_symbol)
    return {
        "quote_number": q.quote_number,
        "event_date": engine.fmt_date(q.event_date),
        "valid_until": engine.fmt_date(q.valid_until),
        "lines": [{"description": l.description, "amount": m(l.amount)} for l in q.lines],
        "delivery": m(q.delivery_charge) if q.delivery_charge else "Free",
        "delivery_note": q.delivery_free_reason,
        "subtotal": m(q.subtotal), "gst": m(q.gst), "total": m(q.total),
        "deposit": m(q.deposit), "balance": m(q.balance),
        "terms_file": q.terms_file, "terms_note": q.terms_note,
        "confirm_items": q.confirm_items,
    }


def enquiry_from(form: dict) -> dict:
    """Turn the form's fields into an engine enquiry, with plain-English errors for missing fields."""
    missing = [label for key, label in (("customer_name", "customer name"), ("event_date", "event date"),
                                        ("headcount", "headcount"), ("package", "package"),
                                        ("delivery_zone", "delivery zone")) if not str(form.get(key, "")).strip()]
    if missing:
        raise engine.QuoteError("Please fill in: " + ", ".join(missing) + ".")
    def num(key, kind=int):
        raw = str(form.get(key) or "0").strip()
        try:
            return kind(raw)
        except Exception:
            raise engine.QuoteError(f"'{raw}' is not a valid number for {key.replace('_', ' ')}.")
    return {
        "customer_name": form["customer_name"].strip(),
        "company": str(form.get("company", "")).strip(),
        "delivery_address": str(form.get("delivery_address", "")).strip(),
        "issue_date": date.today().isoformat(),
        "event_date": form["event_date"],
        "headcount": num("headcount"),
        "package": form["package"],
        "extra_dessert": bool(form.get("extra_dessert")),
        "live_stations": num("live_stations"),
        "live_station_kind": form.get("live_station_kind", ""),
        "service_staff": num("service_staff"),
        "service_hours": num("service_hours", Decimal),
        "delivery_zone": form["delivery_zone"],
        "repeat_corporate": bool(form.get("repeat_corporate")),
        "confirm_items": [s.strip() for s in str(form.get("confirm_items", "")).splitlines() if s.strip()],
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # keep the console quiet apart from errors
        pass

    def send(self, status: int, body: bytes, ctype: str):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, status: int, data: dict):
        self.send(status, json.dumps(data).encode(), "application/json")

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path in STATIC:
            file, ctype = STATIC[path]
            return self.send(200, file.read_bytes(), ctype)
        if path == "/api/options":
            try:
                return self.send_json(200, options())
            except engine.QuoteError as e:
                return self.send_json(500, {"error": str(e)})
        m = re.fullmatch(r"/quotes/([A-Za-z0-9._-]+\.pdf)", path)
        if m and (OUTPUT / m.group(1)).is_file():
            return self.send(200, (OUTPUT / m.group(1)).read_bytes(), "application/pdf")
        self.send(404, b"Not found", "text/plain")

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            return self.send_json(413, {"error": "The form is too large."})
        try:
            form = json.loads(self.rfile.read(length) or b"{}")
            quote = engine.price_quote(enquiry_from(form))
        except engine.QuoteError as e:
            return self.send_json(400, {"error": str(e)})
        except (ValueError, KeyError) as e:
            return self.send_json(400, {"error": f"Something in the form could not be read ({e})."})

        if self.path == "/api/preview":
            return self.send_json(200, summary(quote))
        if self.path == "/api/make":
            name = re.sub(r"[^A-Za-z0-9-]+", "-", quote.quote_number) + ".pdf"
            render_pdf(quote, OUTPUT / name)
            return self.send_json(200, {**summary(quote), "pdf_url": f"/quotes/{name}",
                                        "saved_to": str(OUTPUT / name)})
        self.send_json(404, {"error": "Unknown action."})


def main(open_browser: bool = True):
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    url = f"http://{HOST}:{PORT}/"
    print(f"Quote Studio is running at {url}  (close this window to stop it)")
    if open_browser:
        threading.Timer(0.8, webbrowser.open, args=(url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    import sys
    main(open_browser="--no-browser" not in sys.argv)
