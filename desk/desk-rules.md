# Enquiry Desk rules

Heicoders Catering is a fictional company created for the GA200 course.

## 1. The fleet and the calendar

- The company has six vans, based at the central kitchen in Senoko.
- Each van can take three jobs a day. That makes **18 jobs per date**, and 18 is a hard limit.
- A job is one delivery. `desk/bookings.csv` lists the jobs already booked, one row per job.
- When the Desk offers a customer a quote that holds a date, that hold counts as a job too. The limit applies to booked jobs plus proposed holds.
- A date that is not in `bookings.csv` has no jobs booked yet.
- When two enquiries want the last free slot, the enquiry received first keeps the hold. The other is escalated to Jun Wei Tan, the Logistics Coordinator, for a business decision.
- Agents never change `bookings.csv`, never add a van and never promise a date. Only people confirm a booking.

## 2. People

- **Priya Menon**, Sales and Events Lead. Approves every customer-facing reply and every quote PDF.
- **Jun Wei Tan**, Logistics Coordinator. Approves every capacity exception, and any spending, such as an extra van.
- **Chef Hafiz Osman** runs the kitchen. Priya checks with him before a menu is changed.

## 3. How an enquiry ends

Every enquiry ends in exactly one of three ways:

| Outcome | When | Holds the date? |
|---|---|---|
| `quote` | The facts are complete, the date has room and the menu is suitable. | Yes |
| `clarify` | Something that affects the price, the date or the menu is missing or was assumed. The reply asks the customer. | No |
| `escalate` | A person has to decide. A full date goes to Jun Wei. A menu that clashes with a guest's allergy goes to Priya. | No |

A full date never gets a quote PDF. A menu clash with an allergy never gets a quote that promises the food is safe.

## 4. What is saved where

Each enquiry has its own folder, `desk/packs/enq-NN/`, where NN is the enquiry number in the file name.

| File | Written by | Contents |
|---|---|---|
| `event.json` | Reader (saved by the main session) | The event facts, as described in `desk/allowed-values.md` |
| `contact.json` | Reader (saved by the main session) | `name`, `email`, `phone`, `company` (`null` when the customer didn't give one), `field_status`, `open_questions` |
| `capacity.json` | Capacity | `date`, `booked`, `held`, `limit` (18), `free_slots`, `status` (`has_room` or `full`), `alternatives` (when full: up to two nearby dates with room, each with its `free_slots`; otherwise `[]`), `date_status`, `open_questions` |
| `menu.json` | Menu | `package`, `halal`, `vegetarian_guests`, `vegetarian_dishes`, `clashes`, `shared_kitchen_note`, `verdict` (`OK` or `FLAG`), `dietary_status`, `open_questions` |
| `quote.json` | Quote Studio engine | The engine's JSON output, unchanged |
| `outcome.json` | Main session | `enquiry_id`, `outcome`, `received`, `date`, `holds_date`, `reason`, and `owner` when escalating |

The full field list for each handover, with each field's source and status, is in `design/contracts.md`.

`outcome.json` example for an escalation:

```json
{"enquiry_id": "enq-05", "outcome": "escalate", "received": "2026-10-18T09:05",
 "date": "2026-11-06", "holds_date": false, "owner": "Jun Wei",
 "reason": "Friday 6 November has one free slot and it is held for enq-04, received first."}
```

Other files the Desk produces:

- Draft replies: `outputs/drafts/enq-NN-reply.md`
- Quote PDFs: `outputs/quotes/enq-NN.pdf`
- The open-items summary: `outputs/open-items.md`
- The run log: `outputs/run-log.md`
- Approvals: `desk/approvals.json`, written by the Desk board and nothing else

## 5. Replies to customers

- A reply says only what the pack supports.
- A reply never contains internal costs, margins, staff pay, other customers' details or the names of internal files.
- A reply never confirms a date unless the pack says `quote`. Even then it says the date is held, not confirmed, until the deposit is paid.
- Every reply is a draft until Priya approves it.
