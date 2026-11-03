"""One-page branded A4 quotation PDF (reportlab).

Look and feel follow design/quotation-design-checklist.md (J1-J14): colours and Roboto from
design/design-tokens.json and design/fonts/, logo top left, QUOTATION as the largest header text,
lines -> delivery -> subtotal -> GST -> total -> deposit -> balance, total as the boldest figure.
"""
from __future__ import annotations

import json
from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader, simpleSplit
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas

from engine import Quote, fmt_date, fmt_money, fmt_qty

DESIGN = Path(__file__).resolve().parent.parent / "design"
W, H = A4
M = 40  # page margin, points


def _load_brand() -> dict:
    tokens = json.loads((DESIGN / "design-tokens.json").read_text(encoding="utf-8"))
    for weight, name in (("400", "Roboto"), ("500", "Roboto-Medium"), ("700", "Roboto-Bold")):
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, str(DESIGN / "fonts" / f"roboto-{weight}.ttf")))
    return {k: HexColor(v) for k, v in tokens["colours"].items()}


class QuotePDF:
    def __init__(self, quote: Quote, path: Path):
        self.q = quote
        self.c = Canvas(str(path), pagesize=A4)
        self.c.setTitle(f"Quotation {quote.quote_number}")
        self.c.setAuthor(quote.company_details["name"])
        self.col = _load_brand()
        self.y = H - M

    # -- small drawing helpers -------------------------------------------------
    def text(self, x, y, s, size=9, font="Roboto", colour="ink", align="left"):
        c = self.c
        c.setFont(font, size)
        c.setFillColor(self.col[colour])
        {"left": c.drawString, "right": c.drawRightString, "centre": c.drawCentredString}[align](x, y, s)

    def wrapped(self, x, y, s, width, size=9, font="Roboto", colour="ink", leading=None):
        leading = leading or size * 1.35
        for line in simpleSplit(s, font, size, width):
            self.text(x, y, line, size, font, colour)
            y -= leading
        return y

    def m(self, value):
        return fmt_money(value, self.q.currency_symbol)

    # -- sections --------------------------------------------------------------
    def header(self):
        q, co = self.q, self.q.company_details
        logo = ImageReader(str(DESIGN / "heicoders-catering-logo.png"))
        lw, lh = logo.getSize()
        h = 48
        w = h * lw / lh  # keep the logo's own proportions (J1)
        self.c.drawImage(logo, M, H - M - h, width=w, height=h, mask="auto")
        y = H - M - h - 14
        self.text(M, y, co["name"], 10, "Roboto-Bold", "primary")
        self.text(M, y - 12, co["address"], 8, colour="muted")
        self.text(M, y - 23, f"UEN {co['uen']}   GST Reg. No. {co['gst_reg_no']}", 8, colour="muted")
        self.text(M, y - 34, co["email"], 8, colour="muted")

        rx = W - M
        self.text(rx, H - M - 26, "QUOTATION", 26, "Roboto-Bold", "primary", "right")
        rows = [("Quote number", q.quote_number), ("Issue date", fmt_date(q.issue_date)),
                ("Valid until", fmt_date(q.valid_until))]
        yy = H - M - 46
        for label, value in rows:
            self.text(rx - 190, yy, label, 8, colour="muted")
            self.text(rx, yy, value, 8.5, "Roboto-Medium", "ink", "right")
            yy -= 12
        self.y = y - 48
        self.c.setStrokeColor(self.col["accent"])
        self.c.setLineWidth(2)
        self.c.line(M, self.y, W - M, self.y)
        self.y -= 20

    def customer(self):
        q = self.q
        top = self.y
        self.text(M, top, "PREPARED FOR", 7.5, "Roboto-Medium", "muted")
        self.text(M, top - 17, q.customer_name, 15, "Roboto-Bold", "ink")
        if q.company:
            self.text(M, top - 31, q.company, 10, "Roboto-Medium", "primary")

        x = W / 2 + 10
        self.text(x, top, "EVENT", 7.5, "Roboto-Medium", "muted")
        rows = [("Date", fmt_date(q.event_date)), ("Headcount", f"{q.headcount} pax"),
                ("Package", q.package_name), ("Delivery", q.delivery_zone_name)]
        if q.delivery_address:
            rows.append(("Address", q.delivery_address))
        yy = top - 14
        for label, value in rows:
            self.text(x, yy, label, 8.5, colour="muted")
            self.text(x + 58, yy, value, 9, "Roboto-Medium")
            yy -= 12.5
        self.y = min(top - 42, yy) - 10

    def confirm_box(self):
        items = self.q.confirm_items
        if not items:
            return
        width = W - 2 * M
        body = [simpleSplit(f"•  {s}", "Roboto", 8.5, width - 24) for s in items]
        n = sum(len(b) for b in body)
        h = 22 + n * 11.5 + 6
        c = self.c
        c.setFillColor(self.col["background"])
        c.setStrokeColor(self.col["accent"])
        c.setLineWidth(1.2)
        c.roundRect(M, self.y - h, width, h, 4, stroke=1, fill=1)
        self.text(M + 12, self.y - 15, "Please confirm before we book", 9.5, "Roboto-Bold", "warning")
        yy = self.y - 29
        for lines in body:
            for ln in lines:
                self.text(M + 12, yy, ln, 8.5)
                yy -= 11.5
        self.y -= h + 16

    def lines_table(self):
        q, c = self.q, self.c
        x_desc, x_qty, x_unit, x_amt = M + 8, W - M - 215, W - M - 110, W - M - 8
        c.setFillColor(self.col["primary"])
        c.rect(M, self.y - 6, W - 2 * M, 20, stroke=0, fill=1)
        for x, s, a in ((x_desc, "Item", "left"), (x_qty, "Qty", "right"),
                        (x_unit, "Unit price", "right"), (x_amt, "Amount", "right")):
            self.text(x, self.y, s, 8.5, "Roboto-Medium", "white", a)
        self.y -= 22

        def row(desc, qty, unit, amount, note=None, amount_colour="ink"):
            self.text(x_desc, self.y, desc, 9, "Roboto-Medium")
            self.text(x_qty, self.y, qty, 9, align="right")
            self.text(x_unit, self.y, unit, 9, align="right")
            self.text(x_amt, self.y, amount, 9, "Roboto-Medium", amount_colour, "right")
            if note:
                self.y = self.wrapped(x_desc, self.y - 11, note, x_qty - x_desc - 40, 7.5, colour="muted", leading=9.5) + 9.5
            self.y -= 8
            c.setStrokeColor(self.col["line"])
            c.setLineWidth(0.6)
            c.line(M, self.y, W - M, self.y)
            self.y -= 14

        for l in q.lines:
            if l.unit == "staff-hour":
                qty, unit = f"{fmt_qty(l.quantity)} hrs", f"{self.m(l.unit_price)} / hr"
            else:
                plural = "boxes" if l.unit == "box" else f"{l.unit}s" if l.unit == "station" else l.unit
                qty, unit = f"{fmt_qty(l.quantity)} {l.unit if l.quantity == 1 else plural}", self.m(l.unit_price)
            row(l.description, qty, unit, self.m(l.amount))
        label = f"Delivery ({q.delivery_zone_name.removesuffix(' delivery')})"
        if q.delivery_charge:
            row(label, "1", self.m(q.delivery_charge), self.m(q.delivery_charge))
        else:
            row(label, "1", "", "Free", note=q.delivery_free_reason, amount_colour="good")

    def totals(self):
        q, c = self.q, self.c
        lx, rx = W - M - 230, W - M - 8
        def pair(label, value, size=9.5, font="Roboto", colour="ink"):
            self.text(lx, self.y, label, size, font, colour)
            self.text(rx, self.y, value, size, font, colour, "right")
            self.y -= size + 6
        pair("Subtotal (before GST)", self.m(q.subtotal))
        pair(f"GST {q.gst_rate * 100:.0f}%", self.m(q.gst))
        self.y -= 16
        c.setFillColor(self.col["primary"])
        c.roundRect(lx - 10, self.y - 10, rx - lx + 18, 30, 4, stroke=0, fill=1)
        self.text(lx, self.y, "TOTAL", 12, "Roboto-Bold", "white")
        self.text(rx, self.y - 1, self.m(q.total), 17, "Roboto-Bold", "white", "right")
        self.y -= 30
        pair(f"Deposit {q.deposit_rate * 100:.0f}%, due on confirmation", self.m(q.deposit), 9.5, "Roboto-Bold", "primary")
        pair("Balance, invoiced after the event", self.m(q.balance), 9.5, colour="muted")

    def terms_and_acceptance(self):
        q = self.q
        width = W - 2 * M
        self.y -= 4
        self.text(M, self.y, "Terms", 9.5, "Roboto-Bold", "primary")
        year = q.terms_file.removeprefix("terms-").removesuffix(".md")
        self.y = self.wrapped(M, self.y - 13,
                              f"This quote follows Heicoders Catering Terms and Conditions {year} ({q.terms_file}). "
                              f"Cancellation: {q.cancellation_plain}", width, 8.2, leading=10.8)
        if q.terms_note:
            self.y = self.wrapped(M, self.y - 2, q.terms_note, width, 8.2, "Roboto-Medium", "warning", 10.8)
        self.y -= 14

        self.text(M, self.y, "Acceptance", 9.5, "Roboto-Bold", "primary")
        self.text(M, self.y - 13, "To confirm, sign below and pay the deposit. We will then confirm your 30-minute delivery window.",
                  8.2, colour="muted")
        base = self.y - 52
        c = self.c
        c.setStrokeColor(self.col["ink"])
        c.setLineWidth(0.7)
        cols = [(M, 200, "Name and signature"), (M + 220, 160, "Company stamp (if any)"), (M + 400, width - 400, "Date")]
        for x, w, label in cols:
            c.line(x, base, x + w, base)
            self.text(x, base - 11, label, 7.5, colour="muted")
        self.y = base - 20

    def footer(self):
        q = self.q
        c = self.c
        c.setStrokeColor(self.col["line"])
        c.setLineWidth(0.6)
        c.line(M, M + 20, W - M, M + 20)
        self.text(M, M + 8, f"Prices checked on {fmt_date(q.prices_checked_on)}", 7.5, colour="muted")
        self.text(W / 2, M + 8, f"Questions? {q.company_details['email']}", 7.5, colour="muted", align="centre")
        self.text(W - M, M + 8, "Fictional case data, GA200", 7.5, "Roboto-Medium", "muted", "right")

    def build(self):
        self.header()
        self.customer()
        self.confirm_box()
        self.lines_table()
        self.totals()
        self.terms_and_acceptance()
        if self.y < M + 30:
            raise RuntimeError(f"Quote {self.q.quote_number} does not fit on one A4 page (ran {M + 30 - self.y:.0f} pt over).")
        self.footer()
        self.c.showPage()
        self.c.save()


def render_pdf(quote: Quote, path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    QuotePDF(quote, path).build()
    return path
