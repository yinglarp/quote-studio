# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

Quote Studio turns customer enquiries for **Heicoders Catering** (a fictional Singapore caterer, GA200 course) into one-page A4 quotation PDFs. It is the course starter: there is no code yet. The planned pieces, named in `design/quotation-design-checklist.md`, are:

- a pricing **engine** that computes lines, delivery, GST, total and deposit from an enquiry
- a PDF builder writing to `outputs/quotes/<case>.pdf`
- `scripts/quote_check.py`, which checks the R items (R1–R5) in the checklist for every test case

`outputs/` is gitignored. Render page 1 of a quote for visual review with:

```
pdftoppm -r 110 -png outputs/quotes/<case>.pdf outputs/quotes/<case>-page
```

The J items (J1–J14) are checked by a human looking at that image. The builder must never approve its own output.

## Sources of truth (read before pricing anything)

| File | Status |
|---|---|
| `reference/price-list-2026.pdf` | **Approved** price list, in force for 2026. Pricing rules come from here. |
| `reference/terms-2026.md` | **In force** terms. Cite this file by name on every quote. |
| `reference/exception-memo-siti-2026-03.md` | **In force** exception by the MD: repeat corporate clients (≥3 orders in last 6 months) get free delivery, except Sentosa and Jurong Island. |
| `reference/terms-2027.md` | **Draft, not approved.** Never treat as in force. A 2027 event must say the 2027 terms are still a draft. |
| `reference/terms-2024.md`, `terms-2025.md` | Superseded. |
| `reference/ops-meeting-notes-2026-08.md` | Not policy. "Free delivery above S$600" was only an action to confirm with Siti; the price list's S$800 stands. |
| `reference/live-menu-page-snapshot-2026-09-14.html` | Website snapshot. It announces Classic Buffet at **S$26.80 from 1 Oct 2026**, which the approved PDF (S$24.80) does not show. Raise this conflict with the user. Do not silently pick one. |
| `reference/costing-and-margins.xlsx`, `staff/` | Confidential and gitignored. Never read them into anything a customer sees. |

## Pricing rules (from the 2026 price list)

- Order value = packages + add-ons, before delivery and GST.
- Delivery: Standard mainland S$35, CBD (Raffles Place, Marina Bay, Shenton Way, Tanjong Pagar, City Hall) S$45, Sentosa/Jurong Island S$80. Free when order value is **above** S$800, in every zone. The repeat-corporate memo applies on top of these rates.
- Add-ons: extra dessert S$3.00/pax; live station S$350 each; service staff S$35/staff/hour, **minimum 3 hours per staff member**.
- Package minimums: Bento 20 boxes, Mini Buffet 20, Classic Buffet 30, Premium Buffet 50. Below the minimum, **produce no PDF** (R5: 40-pax Premium Buffet case).
- GST 9% on the total including delivery. Deposit 30% of the total including GST. GST and deposit each round to the nearest cent, half a cent up. Use `Decimal` with `ROUND_HALF_UP`, never floats.
- The quote's valid-until date is issue date + 14 days.

## Quote output rules

Full list in `design/quotation-design-checklist.md`. The ones that shape code:

- Dates written out with the weekday (`Friday 11 December 2026`), never `11/12`. Money is `S$4,192.14`.
- Line order: lines, delivery, subtotal, GST, total, deposit, balance. A free delivery line says why it's free.
- No cost, margin, staff-pay or internal-note wording, and no file names except the terms file.
- Anything guessed from the enquiry goes in a "please confirm" box. Examples: an approximate headcount ("about 120", "abt 25") or an ambiguous date (`12/11` in `inputs/mei-ling-whatsapp.txt`).
- Brand: colours, fonts and logo from `design/design-tokens.json`, `design/fonts/` (Roboto), `design/heicoders-catering-logo.png`. The footer has a "Prices checked on <date>" line and `Fictional case data, GA200`.
- Everything fits on one A4 page.

## Commits

Every commit message has a short title, then `Purpose:`, `Files changed:` (from `git diff --cached --name-status`, A/M/D/R prefixes) and `Code changes:` sections, each summarized. Before committing, confirm that `git ls-files` contains nothing from `staff/`, `outputs/`, `.env*` or `reference/costing-and-margins.xlsx`. The remote is the private repo `yinglarp/quote-studio`.
