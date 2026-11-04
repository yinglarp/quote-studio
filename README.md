# Quote Studio

Tools and reference material for producing Heicoders Catering quotations, plus the **Enquiry Desk**: a set of Claude Code subagents that turn customer enquiries into checked draft replies for people to approve.

Heicoders Catering is a fictional company created for the GA200 course (Building Harnesses for Reliable Generative AI Systems).

## What's here

| Part | What it does |
|---|---|
| **Quote Studio** (`quote-calculator/`) | Prices an event from `rates.json` and renders a branded one-page A4 quotation PDF. It has a local form for Priya and a command-line route. |
| **Enquiry Desk** (`desk/`, `.claude/`, `design/`) | Reads each enquiry in `inbox/`, checks capacity and menu, decides quote / clarify / escalate, drafts a reply and has a Checker review it. **It never sends anything.** Priya and Jun Wei approve on the Desk board. |

## Setup

Requires Python 3 and Node.js (Node is used by the project's guard hook).

```bash
pip install -r requirements.txt
```

On Windows, use `python`, not `python3`. Here `python3` is the Microsoft Store stub. Some script docstrings still say `python3`.

## Quote Studio

**The form.** Double-click `Start-Quote-Studio.bat`, or run:

```bash
python quote-calculator/app.py
```

It opens http://127.0.0.1:8765 (local only). PDFs are saved to `outputs/quotes/`. Add `--no-browser` to start it without opening a browser.

**From a case file:**

```bash
python quote-calculator/make_quote.py quote-calculator/test_cases/harbourline-town-hall.json
```

**Checks:**

```bash
python -m pytest quote-calculator/tests
```

```bash
python scripts/quote_check.py
```

`quote_check.py` builds every test case and checks R1–R5 of `design/quotation-design-checklist.md`: figures, terms and forbidden wording, and that the PDF is one page. The J items on that checklist are checked by a person looking at the page.

## Enquiry Desk

### How an enquiry flows

```
inbox/enq-NN-*.txt
  → Reader                → event.json, contact.json
  → Capacity + Menu       → capacity.json, menu.json     (each file contract-checked)
  → Decide                → outcome.json: quote | clarify | escalate
  → Quote engine + PDF    (only for quote)
  → Drafter               → outputs/drafts/enq-NN-reply.md
  → Checker               → outputs/checks/enq-NN-check.md
  → Batch validation      → outputs/open-items.md, outputs/run-log.md
  → Priya / Jun Wei approve on the Desk board
```

Each enquiry has its own pack folder, `desk/packs/enq-NN/`. Pack files are the only handover between steps. An agent never sees another agent's reply.

### Running it

In Claude Code, from the project folder:

```
/run-desk enq-04
/run-desk all
```

The skill (`.claude/skills/run-desk/SKILL.md`) runs every step, checks each saved file with `desk/check_contract.py`, retries a failing agent once, and validates the batch at the end. A Stop hook (`.claude/hooks/desk_stop.py`) re-runs the validators before a Desk session can finish.

You can also run the checks by hand:

```bash
python desk/check_contract.py desk/packs/enq-04/event.json
```

```bash
python desk/validate_desk.py
```

```bash
python desk/check_inputs_unchanged.py
```

Add `--complete` to `validate_desk.py` to require a pack for every enquiry in `inbox/`.

### The Desk board

```bash
python desk/board_server.py --port 9000
```

Then open http://127.0.0.1:9000. The board shows each enquiry's pack, draft and PDF, and records approvals in `desk/approvals.json`. It enforces who may approve what: only **Priya** approves replies and quote PDFs, and only **Jun Wei** approves capacity exceptions and extra vans.

The board's default port is 8765, the same as the Quote Studio form. Pass `--port` if the form is running.

### Key rules

From `desk/desk-rules.md`:

- **18 jobs per date** (six vans × three jobs) is a hard limit. Booked jobs plus proposed holds count.
- **Only a `quote` holds a date**, and only until the deposit is paid. `clarify` and `escalate` hold nothing.
- **Two enquiries for the last slot:** the one received first keeps the hold. The other is escalated to Jun Wei.
- **An allergy clash** with the requested menu is escalated to Priya. No reply promises that food is allergen-free, because the kitchen is shared.
- **Agents never** change `bookings.csv`, add a van, promise a date or send a message.

## Folders

| Folder | Contents |
|---|---|
| `.claude/agents/` | The five Desk subagents: `reader`, `capacity`, `menu`, `drafter`, `checker` |
| `.claude/skills/run-desk/` | The `/run-desk` skill and `price_pack.py` (feeds a pack to the engine) |
| `.claude/hooks/` | `guard.js` (PreToolUse guard) and `desk_stop.py` (Stop-hook validation) |
| `design/` | Brand tokens, Roboto fonts, logo, the quotation design checklist, the Desk graph (`graph.md`), handover contracts (`contracts.md`) and JSON schemas |
| `desk/` | Desk rules, allowed values, menu and dietary notes, `bookings.csv`, the board, the validators, packs, and `starter-agents/` (the course's starting agent briefs) |
| `inbox/` | Customer enquiries for the Desk (enq-01 to enq-07) |
| `inputs/` | Customer enquiries used for the Quote Studio lessons |
| `quote-calculator/` | `rates.json` (every price), `engine.py`, `pdf.py`, `make_quote.py`, the form (`app.py`, `form.html`), `test_cases/`, `tests/` |
| `reference/` | Price list, terms and conditions by year, memos and meeting notes |
| `scripts/` | `quote_check.py` |
| `outputs/` | Generated quotes, drafts, Checker reports and run logs. Not tracked by Git. |

## Sources of truth

- **Prices:** every price, charge and rate comes from `quote-calculator/rates.json`. Never copy a figure from the price list PDF, the menu page snapshot or meeting notes.
- **Terms:** a quotation cites the terms in force on the **event date**, for example `reference/terms-2026.md` for a 2026 event. `reference/terms-2027.md` is an unapproved draft and is never treated as in force.

## Guardrails and what stays out of Git

- `staff/` and `reference/costing-and-margins.xlsx` are confidential. The `.gitignore` excludes them, `.claude/settings.json` denies reading them, and `guard.js` blocks any tool call that mentions them. The guard matches the word "staff" anywhere in a shell command, so write long text such as commit messages to a file and pass it with `-F`.
- Force-pushes and repository deletion are blocked. Any other push asks first.
- `outputs/`, `.env` files and the Desk's state files (`.input-snapshot.json`, `.stop-hook-state.json`) are ignored. Never force-add them.

See `CLAUDE.md` for the full instructions Claude Code follows in this project.
