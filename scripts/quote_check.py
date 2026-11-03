"""R-list checker (design/quotation-design-checklist.md, R1-R5).

Builds every test case into a fresh PDF, reads the text back out of the PDF, and checks it
against the engine. The J items are for a human looking at the page image.

    python scripts/quote_check.py
"""
from __future__ import annotations

import json
import re
import sys
import tempfile
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "quote-calculator"))
import engine  # noqa: E402
from pdf import render_pdf  # noqa: E402
from pypdf import PdfReader  # noqa: E402

CASES = sorted((ROOT / "quote-calculator" / "test_cases").glob("*.json"))
# R4: wording that must never reach a customer. "Service staff" as a priced line is allowed.
FORBIDDEN = [r"\bcost(s|ing)?\b", r"\bmargins?\b", r"staff[\s-]*pay", r"\bwages?\b", r"\bsalar(y|ies)\b",
             r"\bovertime\b", r"\binternal\b", r"\bprofit\b"]
IN_FORCE = "terms-2026.md"


def amounts(text: str) -> list[Decimal]:
    return [Decimal(m.replace(",", "")) for m in re.findall(r"S\$([\d,]+\.\d{2})", text)]


def check_case(case_file: Path, out_dir: Path) -> list[tuple[str, bool, str]]:
    case = json.loads(case_file.read_text(encoding="utf-8"))
    pdf_path = out_dir / f"{case_file.stem}.pdf"
    results = []
    try:
        q = engine.price_quote(case["enquiry"])
    except engine.BelowMinimum as e:
        made = pdf_path.exists()
        return [("R5 below minimum -> no PDF", not made and case["expected"].get("error") == "BelowMinimum", str(e))]
    if case["expected"].get("error"):
        return [("R5 below minimum -> no PDF", False, "engine produced a quote")]
    render_pdf(q, pdf_path)
    reader = PdfReader(str(pdf_path))
    text = "\n".join(p.extract_text() for p in reader.pages)
    nums = amounts(text)

    total_s, dep_s = engine.fmt_money(q.total), engine.fmt_money(q.deposit)
    results.append(("R1 total and deposit match engine", total_s in text and dep_s in text, f"{total_s}, {dep_s}"))

    lines_ok = all(engine.fmt_money(l.amount) in text for l in q.lines)
    parts = sum((l.amount for l in q.lines), Decimal("0")) + q.delivery_charge + q.gst
    results.append(("R2 every line on PDF, lines + delivery + GST = total", lines_ok and parts == q.total and q.total in nums,
                    f"{len(q.lines)} lines, sum {engine.fmt_money(parts)}"))

    other_years = [y for y in re.findall(r"terms-(\d{4})\.md", text) if f"terms-{y}.md" != IN_FORCE]
    results.append(("R3 names the in-force terms file only", IN_FORCE in text and not other_years,
                    IN_FORCE + (f"; also mentions {other_years}" if other_years else "")))

    hits = [p for p in FORBIDDEN if re.search(p, text, re.I)]
    results.append(("R4 no cost / margin / staff-pay wording", not hits, ", ".join(hits) or "clean"))

    results.append(("One A4 page", len(reader.pages) == 1, f"{len(reader.pages)} page(s)"))
    return results


def main() -> int:
    failed = 0
    with tempfile.TemporaryDirectory() as tmp:
        for case_file in CASES:
            print(case_file.stem)
            for name, ok, detail in check_case(case_file, Path(tmp)):
                failed += not ok
                print(f"  {'PASS' if ok else 'FAIL'}  {name}  ({detail})")
    print("\nAll R items pass." if not failed else f"\n{failed} check(s) failed.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
