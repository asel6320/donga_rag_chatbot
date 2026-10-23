import json
import re
import sys
from pathlib import Path

MAX_CHARS = 2500
OVERLAP_CHARS = 350

DOCS = {
    "2027_spring_international_student_undergraduate_admission.md": {
        "source": "Dong-A Spring 2027 Undergraduate Admission (International, English Track)",
        "file": "2027_spring_international_student_undergraduate_admission.pdf",
        "category": "applicant",
        "level": "undergraduate",
        "student_type": "international",
        "track": "english",
        "intake": "2027-spring",
        "year": 2027,

        # Covers, photos, table of contents, back cover
        "skip_pages": {1, 2, 3, 21, 22},
    },

    "2026_donga_academics.md": {
        "source": "Dong-A University Academic Affairs FAQ 2026",
        "file": "2026_donga_academics.pdf",
        "category": "academic_policy",
        "level": "all",
        "student_type": "all",
        "track": "all",
        "intake": "all",
        "year": 2026,

        # Cover + table of contents
        "skip_pages": {1, 2, 3},
    },

    "2026_donga_academic_calendar.md": {
        "source": "Dong-A University 2026 Academic Calendar",
        "file": "2026_donga_academic_calendar.md",
        "category": "academic_calendar",
        "level": "all",
        "student_type": "all",
        "track": "all",
        "intake": "all",
        "year": 2026,
        "skip_pages": set(),
    },
}

PAGE_RE = re.compile(r"<!-- page: (\d+) \| printed: (\S+) -->")
HEADING_RE = re.compile(r"^(\d{1,2})\.\s+([^:]{1,80})$")
# ------------------------------------------------------------------


def split_pages(md: str):
    """
    Yield (page_number, printed_page, text).

    PDF-extracted Markdown has page markers.
    Web-extracted Markdown does not, so treat the whole file as one page.
    """
    marks = list(PAGE_RE.finditer(md))

    # Web page / Markdown without PDF page markers
    if not marks:
        yield 1, None, md.strip()
        return

    # PDF-generated Markdown
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(md)
        printed = m.group(2)

        yield (
            int(m.group(1)),
            int(printed) if printed.isdigit() else None,
            md[m.end():end].strip(),
        )


def split_table(table: str, max_chars: int) -> list[str]:
    """Split a Markdown table by rows, repeating the header in every part."""
    if len(table) <= max_chars:
        return [table]
    lines = table.splitlines()
    header, rows = lines[:2], lines[2:]
    parts, cur = [], []
    for row in rows:
        if cur and len("\n".join(header + cur + [row])) > max_chars:
            parts.append("\n".join(header + cur))
            cur = []
        cur.append(row)
    if cur:
        parts.append("\n".join(header + cur))
    return parts


def make_header(meta: dict, section: str) -> str:
    return (f"[{meta['source']} | {meta['level']} | {meta['student_type']} | "
            f"{meta['intake']} | Section: {section}]")


def chunk_document(md_path: Path, meta: dict) -> list[dict]:
    md = md_path.read_text(encoding="utf-8")
    skip = meta.get("skip_pages", set())
    doc_meta = {k: v for k, v in meta.items() if k != "skip_pages"}
    chunks = []
    section = "Front matter"

    for page_no, printed, text in split_pages(md):
        if page_no in skip:
            continue

        # (kind, section, text) pieces for this page, in order
        pieces, buf = [], []

        def flush_text():
            if buf:
                pieces.append(("text", section, "\n\n".join(buf)))
                buf.clear()

        for block in re.split(r"\n\s*\n", text):
            block = block.strip()
            if not block:
                continue
            if HEADING_RE.match(block):          # new section starts here
                flush_text()
                section = block
                buf.append(block)                # keep heading inside the text
            elif block.startswith("|"):          # table
                flush_text()
                pieces.append(("table", section, block))
            else:
                buf.append(block)
        flush_text()

        # turn pieces into size-limited chunks
        for kind, sec, body in pieces:
            if kind == "table":
                parts = split_table(body, MAX_CHARS)
            else:
                parts, cur, prev_tail = [], "", ""
                for para in body.split("\n\n"):
                    if cur and len(cur) + len(para) > MAX_CHARS:
                        parts.append(cur.strip())
                        # overlap: carry the tail of the previous chunk
                        prev_tail = cur[-OVERLAP_CHARS:].split(" ", 1)[-1]
                        cur = prev_tail + "\n\n"
                    cur += para + "\n\n"
                if cur.strip():
                    parts.append(cur.strip())

            for part in parts:
                chunks.append({
                    "text": make_header(doc_meta, sec) + "\n" + part,
                    "metadata": {
                        **doc_meta,
                        "section": sec,
                        "page_number": page_no,       # PDF index (for links)
                        "printed_page": printed,      # number shown on the page
                        "content_type": kind,         # text | table
                    },
                })
    return chunks


def main(md_dir: str = "md", out_file: str = "chunks.json"):
    all_chunks = []
    for name, meta in DOCS.items():
        path = Path(md_dir) / name
        if not path.exists():
            print(f"! missing: {path}")
            continue
        c = chunk_document(path, meta)
        print(f"{name}: {len(c)} chunks")
        all_chunks += c

    for i, c in enumerate(all_chunks):
        c["id"] = f"chunk_{i:04d}"
    Path(out_file).write_text(json.dumps(all_chunks, ensure_ascii=False, indent=2),
                              encoding="utf-8")

    sizes = [len(c["text"]) for c in all_chunks]
    print(f"\nSaved {len(all_chunks)} chunks -> {out_file}")
    print(f"chars: min {min(sizes)}, avg {sum(sizes)//len(sizes)}, max {max(sizes)}")
    print(f"tables: {sum(c['metadata']['content_type'] == 'table' for c in all_chunks)}")


if __name__ == "__main__":
    main(*sys.argv[1:3])