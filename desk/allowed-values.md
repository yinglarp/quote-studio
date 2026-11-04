# Allowed values for `event.json`

The Reader fills in `event.json` from one customer enquiry, using only the values below.

## Fields

```json
{
  "enquiry_id": "enq-01",
  "received": "2026-10-03T16:40",
  "client": "Harbourline Insurance",
  "date": "2026-12-11",
  "pax": 120,
  "package": "classic_buffet",
  "zone": "cbd",
  "add_ons": {"live_stations": 1, "extra_dessert": false, "staff": 2, "staff_hours": 4},
  "repeat_client": false,
  "dietary": {"halal": true, "vegetarian_guests": 0, "allergies": []},
  "special_requests": null,
  "suspicious_content": null,
  "field_status": {"date": "verified", "pax": "verified", "package": "verified", "zone": "verified", "add_ons": "verified", "dietary": "verified"},
  "open_questions": []
}
```

- `received` is the date and time on the enquiry, written as `YYYY-MM-DDTHH:MM`. A WhatsApp message gives the timestamp in its brackets.
- `client` is the company or family name.
- `add_ons` always has all four keys. Use `0` or `false` when an add-on wasn't asked for.
- `dietary.allergies` is a list. Each item is `{"allergen": "peanut", "guests": 2, "severity": "severe"}`. Write `"severity": "unstated"` when the customer didn't say.
- `special_requests` is a short quotation of anything else the customer asked for, or `null`.
- `suspicious_content` is `null` unless the Reader brief tells the Reader to put something there.
- `open_questions` lists, in plain words, what the Desk must ask the customer.

## `field_status`

Every field gets one of three statuses.

- `verified`: the customer wrote it plainly.
- `assumed`: the Reader had to interpret it, for example "abt 25", "half day" or "12/11".
- `missing`: the customer didn't say. Use `null` for the value.

An `assumed` or `missing` value in `date`, `pax`, `package`, `zone`, `add_ons` or `dietary` means the enquiry can't be quoted yet. Add a question to `open_questions`.

## Dates

- Write dates as `YYYY-MM-DD`.
- A numeric date such as 12/11 is read day first, as is usual in Singapore, but it is always `assumed`, because it can also be read month first.
- If the customer gives no year, the year is `assumed`.

## Packages

| Value | Customer might write |
|---|---|
| `bento_classic` | Bento Classic |
| `bento_premium` | Bento Premium |
| `mini_buffet` | Mini Buffet |
| `classic_buffet` | Classic Buffet |
| `premium_buffet` | Premium Buffet |

If the customer says only "bento" or "buffet", the package is `missing`.

## Delivery zones

| Value | Where |
|---|---|
| `cbd` | Raffles Place, Marina Bay, Shenton Way, Tanjong Pagar, City Hall |
| `sentosa` | Sentosa, including Sentosa Cove |
| `jurong_island` | Jurong Island |
| `standard` | Every other mainland address |

If the address could fall in two zones, or the customer gave none, the zone is `missing`.

## Repeat clients

`repeat_client` is always `false`. Whether a client has ordered three or more times in six months is a fact from Heicoders Catering's records, not from the enquiry.
