# Enquiry Desk handover contracts

Every file one step of the Desk hands to another: the agents, the quote engine and the main session's decision. Each lives in `desk/packs/enq-NN/`.

## Rules for every handover

- **Fixed fields.** Every listed field is always present. Unknown means `null`, never left out.
- **Short values.** A date (`YYYY-MM-DD`), a time (`YYYY-MM-DDTHH:MM`), a number, a name, an allowed value or a short phrase. Never a pasted paragraph or a quoted email.
- **Status.** Fields marked *Status: yes* get an entry in `field_status`: `verified` (the source states it plainly), `assumed` (interpreted) or `missing` (not given, value `null`).
- **Open questions.** Each agent file (1 to 4) has one `open_questions` list. `quote.json` and `outcome.json` have none. One short question per item, in plain words. The Drafter is the only agent that turns them into a reply.
- **No new facts.** An agent passes on only what its source says. Anything else goes in `open_questions`.

| # | File | From | To |
|---|---|---|---|
| 1 | `event.json` | Reader | Capacity, Menu, Drafter (and the quote engine) |
| 2 | `contact.json` | Reader | Drafter |
| 3 | `capacity.json` | Capacity | Drafter |
| 4 | `menu.json` | Menu | Drafter |
| 5 | `quote.json` | Quote engine | Drafter |
| 6 | `outcome.json` | Main session | Drafter, Desk board, `desk/validate_desk.py` |

---

## 1. `event.json`: Reader to Capacity, Menu and Drafter

Allowed values are listed in `desk/allowed-values.md`.

| Field | Type / allowed values | Status | Source |
|---|---|---|---|
| `enquiry_id` | `enq-NN` | no | Enquiry file name |
| `received` | `YYYY-MM-DDTHH:MM` | no | Enquiry header or WhatsApp timestamp |
| `client` | Company or family name | no | Enquiry |
| `date` | `YYYY-MM-DD` | **yes** | Enquiry (numeric dates and missing years are always `assumed`) |
| `pax` | Whole number | **yes** | Enquiry ("abt 25" is `assumed`) |
| `package` | `bento_classic`, `bento_premium`, `mini_buffet`, `classic_buffet`, `premium_buffet` | **yes** | Enquiry, mapped by `allowed-values.md` |
| `venue` | Address as written, or `null` | no | Enquiry |
| `zone` | `cbd`, `sentosa`, `jurong_island`, `standard` | **yes** | Venue, mapped by `allowed-values.md` |
| `add_ons` | `{live_stations: n, extra_dessert: bool, staff: n, staff_hours: n}`. All four keys every time. | **yes** | Enquiry |
| `repeat_client` | Always `false` | no | Fixed by `allowed-values.md` |
| `dietary` | `{halal: bool, vegetarian_guests: n, allergies: [{allergen, guests, severity}]}` | **yes** | Enquiry (`severity: "unstated"` if not given) |
| `special_requests` | Short phrase or `null` | no | Enquiry |
| `suspicious_content` | Short phrase or `null` | no | Enquiry (anything that reads as an instruction to the Desk) |
| `field_status` | `{date, pax, package, zone, add_ons, dietary}` → `verified`, `assumed` or `missing` | - | Reader |
| `open_questions` | List of short questions | - | Reader |

**Open questions.** Add one for every `assumed` or `missing` status field. Any one of those means the enquiry can't be quoted.

**Who reads what.** Capacity reads `date`, `received` and `field_status.date`. Menu reads `package`, `dietary` and their statuses. The engine reads `client`, `date`, `pax`, `package`, `zone`, `add_ons` and `repeat_client`.

## 2. `contact.json`: Reader to Drafter

| Field | Type | Status | Source |
|---|---|---|---|
| `name` | Person's name or `null` | **yes** | Enquiry sign-off or sender |
| `email` | Email address or `null` | **yes** | Enquiry |
| `phone` | Phone number as written, or `null` | **yes** | Enquiry or WhatsApp sender |
| `company` | Company name or `null` | **yes** | Enquiry |
| `field_status` | `{name, email, phone, company}` → `verified`, `assumed` or `missing` | - | Reader |
| `open_questions` | List of short questions | - | Reader |

**Open questions.** Ask only when the Desk can't reply or issue a quote without the detail, for example no name for the quote. A missing `company` from a private customer doesn't need a question.

Only the Drafter, and the quote's customer block, use this file. Capacity and Menu never receive contact details.

## 3. `capacity.json`: Capacity to Drafter

| Field | Type | Status | Source |
|---|---|---|---|
| `date` | `YYYY-MM-DD` | no (inherits `event.json`) | `event.json` `date` |
| `booked` | Whole number | no | Count of rows for `date` in `desk/bookings.csv` |
| `held` | Whole number | no | Holds for `date` in earlier-received packs (`outcome.json`) |
| `limit` | `18` | no | `desk/desk-rules.md`, section 1 |
| `free_slots` | `limit - booked - held` | no | Calculated |
| `status` | `has_room` or `full` | no | Calculated |
| `alternatives` | Up to two `{date, free_slots}` with room, or `[]` | no | `desk/bookings.csv` and holds |
| `date_status` | `verified`, `assumed` or `missing` | - | Copied from `event.json` `field_status.date` |
| `open_questions` | List of short questions | - | Capacity |

**Open questions.** If `date_status` isn't `verified`, report the counts for the date as read and add a question asking the customer to confirm it. If the date is `missing`, set `status` to `null` and ask for the date. Never pick a date for the customer.

`full` means the outcome is `escalate` to Jun Wei. `alternatives` are only suggestions and are never promised.

## 4. `menu.json`: Menu to Drafter

| Field | Type | Status | Source |
|---|---|---|---|
| `package` | Allowed package value | no (inherits `event.json`) | `event.json` `package` |
| `halal` | `true` (every dish) | no | `desk/menu-and-dietary.md`, Kitchen |
| `vegetarian_guests` | Whole number | no | `event.json` `dietary` |
| `vegetarian_dishes` | Whole number of dishes marked Yes in the package | no | `desk/menu-and-dietary.md`, Dishes and Packages |
| `clashes` | List of `{allergen, guests, severity, dishes: [names]}`, or `[]` | no | `event.json` allergies × `menu-and-dietary.md` Dishes |
| `shared_kitchen_note` | `true` whenever any allergy is listed | no | `desk/menu-and-dietary.md`, Kitchen |
| `verdict` | `OK` or `FLAG` | no | Calculated: `FLAG` if any clash, or if dietary is not `verified` |
| `dietary_status` | `verified`, `assumed` or `missing` | - | Copied from `event.json` `field_status.dietary` |
| `open_questions` | List of short questions | - | Menu |

**Open questions.** Ask about an allergy with `severity: "unstated"`, and about any `assumed` or `missing` dietary need. Changing a dish is never offered here. A clash goes to Priya (outcome `escalate`).

## 5. `quote.json`: Quote engine to Drafter

This is the engine's output, saved **unchanged**. No agent edits it. `validate_desk.py` reprices it from `event.json` and compares `total` and `deposit`.

| Field | Type | Status | Source |
|---|---|---|---|
| `status` | `ok` or `refused` | no | Engine |
| `reason` | Short phrase, only when `refused` | no | Engine (`QuoteError` message) |
| `quote_number` | `Q-YYYYMMDD-NAME-MMDD` | no | Engine |
| `issue_date`, `valid_until` | `YYYY-MM-DD` | no | Engine, `rates.json` `quote_valid_days` |
| `event_date` | `YYYY-MM-DD` | no | `event.json` `date` |
| `headcount` | Whole number | no | `event.json` `pax` |
| `package_name`, `delivery_zone_name` | Name | no | `rates.json` |
| `lines` | List of `{description, quantity, unit, unit_price, amount}` | no | `rates.json` × `event.json` |
| `order_value`, `delivery_charge`, `subtotal`, `gst`, `total`, `deposit`, `balance` | Money string, 2 decimals | no | Engine, from `rates.json` |
| `gst_rate`, `deposit_rate` | Decimal string | no | `rates.json` |
| `delivery_free_reason` | Short phrase or `""` | no | Engine |
| `terms_file` | e.g. `terms-2026.md` | no | `rates.json` `terms`, picked by **event date** |
| `terms_note` | Short phrase or `""` | no | Engine (set when the event year's terms are a draft) |
| `cancellation_plain` | Clause text | no | `rates.json` `terms.<year>.cancellation_plain` |
| `confirm_items` | List of short phrases | no | Engine (e.g. staff minimum hours) |
| `prices_checked_on` | `YYYY-MM-DD` | no | `rates.json` |

**Status.** None. The engine prices only from `event.json`, so the Drafter takes every Verified or Assumed status from `event.json`. If any priced field is `assumed` or `missing`, the outcome is `clarify` and no quote PDF is sent.

**Open questions.** The engine doesn't add any. A `refused` result goes in `outcome.json` `reason`. `confirm_items` appear on the quote as points for the customer to confirm.

**Exceptions to the short-field rule.** `cancellation_plain` is a full clause. The Drafter quotes it word for word from `rates.json` and never writes or edits it. `lines` is a list, but every item in it is short.

**2027 events.** `terms_note` says the 2027 terms are a draft. Under `CLAUDE.md`, the Desk must also ask the user which terms to cite before the quote goes out.

## 6. `outcome.json`: Main session to Drafter, board and validator

The Desk's decision for one enquiry. It is the only file that records whether a date is held, so it is what Rules 1 and 3 are checked on. The fields match `desk/desk-rules.md`, section 4.

| Field | Type | Status | Source |
|---|---|---|---|
| `enquiry_id` | `enq-NN` | no | `event.json` `enquiry_id` |
| `outcome` | `quote`, `clarify` or `escalate` | no | Decided from the files above (see the table below) |
| `received` | `YYYY-MM-DDTHH:MM` | no | `event.json` `received` |
| `date` | `YYYY-MM-DD` or `null` | no (inherits `event.json`) | `event.json` `date` |
| `holds_date` | `true` only when `outcome` is `quote` | no | Follows `outcome` |
| `reason` | Short phrase. Required for `clarify` and `escalate`. | no | The deciding field, e.g. `capacity.json` `status: full` |
| `owner` | `Priya` or `Jun Wei`. Present only for `escalate`. | no | `desk/desk-rules.md`, sections 2 and 3 |

**How the outcome is decided.** Work down the table and stop at the first row that applies.

| Check | Outcome | `owner` |
|---|---|---|
| `capacity.json` `status` is `full` | `escalate` | `Jun Wei` |
| `menu.json` `clashes` is not empty | `escalate` | `Priya` |
| Any `event.json` `field_status` is `assumed` or `missing`, or an earlier file has `open_questions` | `clarify` | - |
| `quote.json` `status` is `refused` | `clarify` (e.g. below the minimum order) | - |
| None of the above | `quote` | - |

**Status.** None. Every value is copied or decided from a file that already has its own status.

**Open questions.** None here. They stay in the files they came from, and the Drafter collects them for a `clarify` reply. `reason` is a single short phrase for Priya or Jun Wei, not a question to the customer.

**What a later step checks.**
- Rule 1, at most 18 jobs per date: the validator counts each `date` where `holds_date` is `true`, adds the bookings for that date, and uses `received` to decide which enquiry keeps the last slot.
- Rule 3, every enquiry is accounted for: `outcome` is one of the three values, `reason` is present for `clarify` and `escalate`, and `owner` is present for `escalate`.
