import re
import sys
from pathlib import Path

import pymupdf

PRINTED_PAGE_RE = re.compile(r"^\s*[-–]\s*(\d{1,3})\s*[-–]\s*$")


def inside(block_bbox, table_bboxes) -> bool:
    """True if the centre of a text block lies inside any table bbox."""
    x0, y0, x1, y1 = block_bbox
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    return any(t[0] <= cx <= t[2] and t[1] <= cy <= t[3] for t in table_bboxes)


def clean_cell(value) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip().replace("|", "/")


def table_to_markdown(rows: list[list]) -> str:
    rows = [[clean_cell(c) for c in r] for r in rows]
    rows = [r for r in rows if any(r)]          # drop fully empty rows
    if len(rows) < 2:
        return ""
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    header, body = rows[0], rows[1:]
    lines = ["| " + " | ".join(header) + " |",
             "| " + " | ".join(["---"] * width) + " |"]
    lines += ["| " + " | ".join(r) + " |" for r in body]
    return "\n".join(lines)


def extract_page(page: pymupdf.Page):
    """Return (markdown_text, printed_page_number_or_None, n_tables)."""
    items = []  # (y_position, markdown_chunk)
    table_bboxes = []

    # --- tables ---
    try:
        found = page.find_tables()
        for t in found.tables:
            md = table_to_markdown(t.extract())
            if md:
                table_bboxes.append(t.bbox)
                items.append((t.bbox[1], md))
    except Exception as e:  # table detection can fail on odd pages
        print(f"  ! table detection failed on page {page.number + 1}: {e}")

    # --- text blocks outside tables ---
    printed = None
    for x0, y0, x1, y1, text, *_ in page.get_text("blocks", sort=True):
        if inside((x0, y0, x1, y1), table_bboxes):
            continue
        text = text.strip()
        if not text:
            continue
        m = PRINTED_PAGE_RE.match(text)
        if m:                       # "- 5 -" footer: remember, don't keep in text
            printed = int(m.group(1))
            continue
        # join hard line-wraps inside a block, keep list items / headings apart
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        merged = []
        for ln in lines:
            starts_new = re.match(r"^([A-Z]\.|\d{1,2}\.|[-•∙⁻₋※①②③ⅰⅱ]|\d\))\s*", ln)
            if merged and not starts_new:
                merged[-1] += " " + ln
            else:
                merged.append(ln)
        items.append((y0, "\n".join(merged)))

    items.sort(key=lambda it: it[0])
    return "\n\n".join(chunk for _, chunk in items), printed, len(table_bboxes)


def main(pdf_path: str, out_dir: str = "md"):
    pdf = Path(pdf_path)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    doc = pymupdf.open(pdf)
    parts, report = [], []

    for i, page in enumerate(doc, start=1):
        text, printed, n_tables = extract_page(page)
        marker = f"<!-- page: {i} | printed: {printed if printed else '-'} -->"
        parts.append(f"{marker}\n\n{text}\n")
        report.append((i, printed, len(text), n_tables, len(page.get_images())))

    md_path = out / (pdf.stem + ".md")
    md_path.write_text("\n".join(parts), encoding="utf-8")

    print(f"\nSaved: {md_path}")
    print(f"{'pdf':>4} {'printed':>8} {'chars':>7} {'tables':>7} {'images':>7}  note")
    for i, printed, chars, tables, imgs in report:
        note = ""
        if chars < 200:
            note = "<- little text (cover / image page?)"
        print(f"{i:>4} {str(printed or '-'):>8} {chars:>7} {tables:>7} {imgs:>7}  {note}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(*sys.argv[1:3])