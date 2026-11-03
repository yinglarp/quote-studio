"""Make a quotation PDF (and a page-1 PNG for the J-list) from a case file.

    python quote-calculator/make_quote.py quote-calculator/test_cases/harbourline-town-hall.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import engine
from pdf import render_pdf

OUTPUT = Path(__file__).resolve().parent.parent / "outputs" / "quotes"


def render_png(pdf_path: Path, scale: float = 110 / 72) -> Path:
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(str(pdf_path))
    png = pdf_path.with_name(pdf_path.stem + "-page1.png")
    doc[0].render(scale=scale).to_pil().save(png)
    doc.close()
    return png


def make(case_path: Path) -> tuple[engine.Quote, Path, Path]:
    case = json.loads(Path(case_path).read_text(encoding="utf-8"))
    quote = engine.price_quote(case["enquiry"])
    pdf = render_pdf(quote, OUTPUT / f"{Path(case_path).stem}.pdf")
    return quote, pdf, render_png(pdf)


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        try:
            q, pdf, png = make(Path(arg))
            print(f"{Path(arg).stem}: {engine.fmt_money(q.total)} -> {pdf} (+ {png.name})")
        except engine.QuoteError as e:
            print(f"{Path(arg).stem}: NO QUOTE - {e}")
