"""Extract this collection's text without changing its wording or spacing.

Usage: python scripts/extract_pdf.py /path/to/source.pdf
Requires pdfplumber. The original PDF is an input, not a deployed site asset.
The PDF includes explicit space glyphs, even around wrapped lines. Reading the
glyph stream therefore preserves words split across lines, unlike joining plain
text extraction lines with spaces. Font sizes identify headings, verse numbers,
and verse text in this particular source layout.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import re

import pdfplumber


REFERENCE = re.compile(r"^[가-힣]+ \d+:\d+(?:-\d+)?$")


def size(char):
    return round(char["size"], 1)


def lines_of_size(page, wanted):
    lines = defaultdict(list)
    for char in page.chars:
        if size(char) == wanted:
            lines[round(char["top"], 2)].append(char)
    return [
        "".join(c["text"] for c in sorted(chars, key=lambda c: c["x0"]))
        for _, chars in sorted(lines.items())
    ]


def chunks(page):
    """Yield typography runs, preserving PDF text drawing order and spaces."""
    current_key = None
    chars = []
    for char in page.chars:
        font_size = size(char)
        if font_size not in (11.0, 14.0, 17.0, 24.0):
            continue
        # The size-14 headings use the same font, but are distinct text rows.
        key = (font_size, round(char["top"], 2) if font_size == 14.0 else None)
        if current_key is not None and key != current_key:
            yield current_key[0], "".join(chars)
            chars = []
        current_key = key
        chars.append(char["text"])
    if current_key is not None:
        yield current_key[0], "".join(chars)


def extract(pdf_path: Path):
    root = Path(__file__).resolve().parent.parent
    temp = root / "tmp"
    temp.mkdir(exist_ok=True)
    with pdfplumber.open(pdf_path) as pdf:
        category_titles = [s.strip() for s in lines_of_size(pdf.pages[0], 13.3)]
        assert len(category_titles) == 13, category_titles
        categories = []
        category = None
        selection = None
        passage = None
        subcategory = None
        all_number_chars = []

        for page_number, page in enumerate(pdf.pages[1:], start=2):
            for font_size, value in chunks(page):
                if font_size == 24.0:
                    title = value.strip()
                    assert title in category_titles, title
                    category = {
                        "id": f"topic-{len(categories) + 1:02d}",
                        "title": title,
                        "verses": [],
                    }
                    categories.append(category)
                    selection = None
                    passage = None
                    subcategory = None
                elif font_size == 14.0:
                    value = value.strip()
                    assert category is not None
                    if value == category["title"]:
                        continue
                    if REFERENCE.fullmatch(value):
                        selection = {
                            "id": f"verse-{sum(len(c['verses']) for c in categories) + 1:03d}",
                            "reference": value,
                            "subcategory": subcategory,
                            "page": page_number,
                            "passages": [],
                        }
                        category["verses"].append(selection)
                        passage = None
                    else:
                        subcategory = value
                elif font_size == 11.0:
                    assert selection is not None and value.isdigit(), value
                    passage = {"number": int(value), "text": ""}
                    selection["passages"].append(passage)
                    all_number_chars.append(value)
                elif font_size == 17.0:
                    assert passage is not None, (page_number, value)
                    passage["text"] += value

        assert [c["title"] for c in categories] == category_titles
        selections = [v for c in categories for v in c["verses"]]
        for selection in selections:
            for passage in selection["passages"]:
                passage["text"] = passage["text"].strip()
                assert passage["text"] and "\ufffd" not in passage["text"]
            selection["text"] = "\n".join(
                f"{p['number']} {p['text']}" for p in selection["passages"]
            )
            last_part = selection["reference"].split(":")[-1]
            bounds = [int(number) for number in last_part.split("-")]
            expected = list(range(bounds[0], bounds[-1] + 1))
            assert [p["number"] for p in selection["passages"]] == expected, selection

        # Check every body glyph and every printed verse-number glyph survives.
        extracted_body = "".join(
            p["text"] for s in selections for p in s["passages"]
        )
        source_body = "".join(
            c["text"] for page in pdf.pages[1:] for c in page.chars if size(c) == 17.0
        )
        assert re.sub(r"\s", "", extracted_body) == re.sub(r"\s", "", source_body)
        assert "".join(str(p["number"]) for s in selections for p in s["passages"]) == "".join(all_number_chars)

        data = {
            "title": "주제별 말씀 모음",
            "description": "그날 마음에 와닿는 말씀을 자유롭게 골라 읽고 적어 보세요.",
            "source": pdf_path.name,
            "totalPages": len(pdf.pages),
            "totalCategories": len(categories),
            "totalSelections": len(selections),
            "totalVerses": sum(len(s["passages"]) for s in selections),
            "categories": categories,
        }
        (root / "content.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        (temp / "pdf-source.txt").write_text(
            "\n\n".join(f"PAGE {i + 1}\n{p.extract_text()}" for i, p in enumerate(pdf.pages)),
            encoding="utf-8",
        )
        report = {
            "sourcePages": len(pdf.pages),
            "categories": len(categories),
            "selections": len(selections),
            "individualVerses": data["totalVerses"],
            "sourceBodyGlyphs": len(source_body),
            "bodyGlyphsVerified": True,
            "verseNumberRangesVerified": True,
            "countsByCategory": {c["title"]: len(c["verses"]) for c in categories},
        }
        (temp / "extraction-report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    args = parser.parse_args()
    extract(args.pdf)
