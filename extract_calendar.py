from pathlib import Path

import requests
from bs4 import BeautifulSoup


URL = "https://donga.ac.kr/community/academic-calendar"
OUT_FILE = Path("md/2026_donga_academic_calendar.md")


def expand_html_table(table) -> list[list[str]]:
    """
    Convert an HTML table into a normal rectangular grid.

    Handles rowspan and colspan so merged cells from the
    Dong-A academic calendar do not shift Markdown columns.
    """

    rows = []
    active_rowspans = {}

    for tr in table.find_all("tr"):
        cells = tr.find_all(["th", "td"], recursive=False)

        row = []
        col = 0

        def add_active_cells():
            nonlocal col

            while col in active_rowspans:
                value, remaining = active_rowspans[col]

                row.append(value)

                if remaining <= 1:
                    del active_rowspans[col]
                else:
                    active_rowspans[col] = (value, remaining - 1)

                col += 1

        add_active_cells()

        for cell in cells:
            add_active_cells()

            value = " ".join(cell.stripped_strings)
            value = value.replace("|", "/")

            rowspan = int(cell.get("rowspan", 1))
            colspan = int(cell.get("colspan", 1))

            for offset in range(colspan):
                row.append(value)

                if rowspan > 1:
                    active_rowspans[col + offset] = (
                        value,
                        rowspan - 1,
                    )

            col += colspan

        add_active_cells()

        if row:
            rows.append(row)

    if not rows:
        return []

    width = max(len(row) for row in rows)

    for row in rows:
        row.extend([""] * (width - len(row)))

    return rows


def table_to_markdown(table) -> str:
    rows = expand_html_table(table)

    if not rows:
        return ""

    header = rows[0]
    body = rows[1:]

    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(["---"] * len(header)) + " |",
    ]

    for row in body:
        lines.append(
            "| " + " | ".join(row) + " |"
        )

    return "\n".join(lines)


def main():
    response = requests.get(
        URL,
        timeout=30,
        headers={
            "User-Agent": "Mozilla/5.0"
        },
    )
    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser",
    )

    wanted_sections = {
        "2026학년도 학사일정",
        "2026학년도 지정보강일",
    }

    parts = [
        "# Dong-A University 2026 Academic Calendar",
        "",
        f"Source: {URL}",
        "",
    ]

    found_sections = []

    for heading in soup.find_all(
        ["h1", "h2", "h3", "h4", "h5"]
    ):
        title = " ".join(heading.stripped_strings)

        if title not in wanted_sections:
            continue

        table = heading.find_next("table")

        if table is None:
            print(
                f"! Table not found for section: {title}"
            )
            continue

        found_sections.append(title)

        parts.append(f"## {title}")
        parts.append("")
        parts.append(table_to_markdown(table))
        parts.append("")

    missing = wanted_sections - set(found_sections)

    if missing:
        raise RuntimeError(
            "Could not find these calendar sections: "
            + ", ".join(sorted(missing))
        )

    OUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUT_FILE.write_text(
        "\n".join(parts),
        encoding="utf-8",
    )

    print(f"Saved: {OUT_FILE}")

    for section in found_sections:
        print(f"  OK: {section}")


if __name__ == "__main__":
    main()