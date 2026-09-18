import pdfplumber
from collections import defaultdict
import re

def is_probably_garbled(text):
    """
    Heuristic: flags strings with unusually high density of
    non-ASCII 'accented' characters, which is what we're seeing
    as garbage (Ä, Å, etc.) instead of normal table content.
    """
    if not text:
        return False
    non_ascii = sum(1 for ch in text if ord(ch) > 127)
    return non_ascii > 0 and (non_ascii / max(len(text), 1)) > 0.15


def scan_pdf_for_garbled_tables(filepath):
    pdf = pdfplumber.open(filepath)
    flagged_pages = []

    for i, page in enumerate(pdf.pages):
        tables = page.extract_tables()
        if not tables:
            continue

        page_has_garbage = False
        for t_idx, table in enumerate(tables):
            for row in table:
                for cell in row:
                    if cell and is_probably_garbled(cell):
                        print(f"[Page {i}] [Table {t_idx}] Garbled cell: {cell!r}")
                        page_has_garbage = True

        if page_has_garbage:
            flagged_pages.append(i)

    pdf.close()
    return flagged_pages


def font_breakdown_for_page(filepath, page_index):
    pdf = pdfplumber.open(filepath)
    page = pdf.pages[page_index]

    fonts = defaultdict(list)
    for c in page.chars:
        fonts[c["fontname"]].append(c["text"])

    print(f"\n--- Font breakdown for page {page_index} ---")
    for fontname, chars in fonts.items():
        print(f"FONT: {fontname}  |  char count: {len(chars)}  |  sample: {''.join(chars[:60])!r}")

    pdf.close()
    return fonts


if __name__ == "__main__":
    filepath = "./2025GraduationRates.pdf"



    print("Scanning all pages for garbled table cells...\n")
    flagged = scan_pdf_for_garbled_tables(filepath)

    print(f"\nDEBUG type: {type(flagged)}")
    print(f"DEBUG repr: {flagged!r}")
    print(f"\n=== Pages with likely garbled table output: {flagged} ===")

    with open("debug_output.txt", "w", encoding="utf-8") as f:
        f.write(f"type: {type(flagged)}\n")
        f.write(f"repr: {flagged!r}\n")

    for page_index in flagged:
        font_breakdown_for_page(filepath, page_index)