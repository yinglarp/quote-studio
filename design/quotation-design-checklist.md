# Quotation design checklist (the J list)

This is the look Heicoders Catering wants on every quotation PDF. Siti Rahman approved it. The colours, fonts and logo are in this folder (`design-tokens.json`, `fonts/`, `heicoders-catering-logo.png`).

A quote is a promise in writing, so check it twice: a script checks the figures (the R items), and you check the look (the J items).

## How to use it

1. Ask Claude Code to render page 1 of a quotation to an image. For example: `pdftoppm -r 110 -png outputs/quotes/<case>.pdf outputs/quotes/<case>-page` (Claude Code can run this for you). Or open the PDF in any PDF viewer.
2. Put the image beside this file and tick each line by eye. A line you cannot tick is a defect: write down what you see.
3. Never let the thing that made the PDF be the thing that approves it. You tick the J list, not the builder.

## R items: a script can check them

The quote checker you build later (`scripts/quote_check.py`) checks these for every test case:

- [ ] R1. The total and the deposit on the PDF equal the engine's.
- [ ] R2. The lines add up: every line is on the PDF, and lines + delivery + GST = the total shown.
- [ ] R3. The PDF names the terms file in force (`terms-2026.md`), and never treats another year as in force.
- [ ] R4. No cost, margin or staff-pay wording appears. (A priced line called "Service staff" is fine.)
- [ ] R5. The 40-person Premium Buffet case (below the 50-pax minimum) produces no PDF at all.

## J items: your eyes must check them

**Letterhead and header**
- [ ] J1. The logo sits top left and is sharp (not stretched or fuzzy). The company name, address, UEN and GST number sit under it.
- [ ] J2. The word QUOTATION is the largest text in the header. It has a quote number, an issue date and a valid-until date that is 14 days after the issue date.

**Customer and event**
- [ ] J3. The customer's name stands out. The event date is written out in full with the weekday (for example, Friday 11 December 2026), never 11/12. The headcount, the package and the delivery zone are shown.

**Lines and money**
- [ ] J4. Each line says what it is, how many, and the price per unit where it helps. Amounts line up on the right with two decimals, an S$ sign and a thousands separator (S$4,192.14).
- [ ] J5. Delivery has its own line. When it is free, the line says so and says why.
- [ ] J6. The order reads top to bottom: lines, delivery, subtotal, GST, total, deposit, balance.
- [ ] J7. The total is the most noticeable figure on the page, and the same figure appears nowhere else with a different value.

**Terms and acceptance**
- [ ] J8. The terms line names the terms file in force and quotes the cancellation clause in words a customer can follow. An event in 2027 also says that the 2027 terms are still a draft.
- [ ] J9. The acceptance block has room to sign: name and signature, company stamp if any, and a date. The lines are long enough to write on.
- [ ] J10. When the enquiry needed a guess (an approximate headcount, a date without a year), a box lists each item for the customer to confirm, in plain words.

**Page and brand**
- [ ] J11. Everything fits on one A4 page. Nothing is cut off, overlaps or sits outside the margins, and the white space is even.
- [ ] J12. The colours and fonts come from `design-tokens.json`: teal `#0F4C5C`, amber `#E09F3E`, cream `#FFF8EC`, Roboto. Body text is at least 8 pt and easy to read.
- [ ] J13. The footer carries a "Prices checked on" line with the date, and the label "Fictional case data, GA200".
- [ ] J14. A customer reading it sees no costs, no margins, no staff pay and no internal notes, and no file names other than the terms file.

## Signing off

A quotation passes when all five R items pass for the case and you have ticked J1 to J14 on the page image. Record which case and which date you ticked, and what you changed afterwards.
