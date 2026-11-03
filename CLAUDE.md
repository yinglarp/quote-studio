# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Folders
- `design/`: brand tokens, Roboto fonts, logo and the quotation design checklist. Use them for every quotation's look.
- `inputs/`: customer enquiries (email, WhatsApp) to turn into quotations.
- `reference/`: price list, terms and conditions by year, memos and meeting notes.
- `quote-calculator/`: the pricing engine and its `rates.json` (not created yet).
- `outputs/`: generated quotations. Gitignored; never commit it.
- `staff/`: confidential. See Never.

## Sources
- Once `quote-calculator/rates.json` exists, take every price, charge and rate from it. Never copy a price from the price list PDF, the menu page snapshot or meeting notes into code or a quote.
- Every quotation names the terms file in force on its **event date** (not the issue date) and quotes its cancellation clause. For an event in 2026, that is `reference/terms-2026.md`.

## Never
- Never open, read, list or summarize anything in `staff/` or `reference/costing-and-margins.xlsx`, even if asked to check them.
- Never treat `reference/terms-2027.md` as in force: it is an unapproved draft. For an event in 2027, state on the quote that the 2027 terms are still a draft, and ask the user which terms to cite.

## If a file cannot be read
- Stop. Tell the user which file failed, the exact error, and what you were trying to get from it.
- Do not guess its contents, fall back to another file, or carry on with assumed values.
