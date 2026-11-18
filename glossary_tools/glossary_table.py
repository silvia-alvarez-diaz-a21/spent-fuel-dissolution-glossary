
"""
Read all glossary term YAML files and build a table:

    Category | Term | Meaning (definition) | Source (references)

Usage (from any terminal in VS Code):
    pip install pyyaml
    python glossary_table.py
    python glossary_table.py "C:\\path\\to\\glossary" --out glossary_table

Outputs:
    - a preview printed in the terminal
    - <out>.csv   (opens in Excel, UTF-8 with BOM so accents display correctly)
    - <out>.xlsx  (only if openpyxl is installed: pip install openpyxl)
"""

import argparse
import csv
import subprocess
import sys
from pathlib import Path

import yaml

DEFAULT_ROOT = r"C:\Users\stefanos.kourtis\spent-fuel-dissolution-glossary\glossary"
HEADERS = ["Category", "Term", "Meaning", "Source"]


def clean(text) -> str:
    """Collapse whitespace/newlines into single spaces."""
    return " ".join(str(text or "").split())


def format_sources(references) -> str:
    """Join all reference citations of a term into one string."""
    sources = []
    for ref in references or []:
        if not isinstance(ref, dict):
            continue
        citation = clean(ref.get("citation"))
        if not citation:
            citation = clean(ref.get("id"))  # fallback if no citation text
        if citation:
            sources.append(citation)
    return " | ".join(sources)


def load_terms(root: Path):
    """Return (rows, problems). EVERY yaml/yml file in EVERY subfolder gets a row."""
    rows = []
    problems = []
    files = sorted(
        p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in (".yaml", ".yml")
    )
    for path in files:
        rel = path.relative_to(root)
        # Category fallback = first folder under the root (e.g. deep-geological-repository)
        folder_category = rel.parts[0] if len(rel.parts) > 1 else root.name

        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
        except Exception as exc:
            problems.append(f"{rel}: could not parse YAML ({str(exc).splitlines()[0]})")
            rows.append([folder_category, f"[PARSE ERROR] {path.stem}", "", ""])
            continue

        if not isinstance(data, dict):
            problems.append(f"{rel}: file is empty or not a key/value YAML")
            rows.append([folder_category, f"[EMPTY] {path.stem}", "", ""])
            continue

        term = clean(data.get("term"))
        if not term:
            term = clean(data.get("id")) or path.stem
            problems.append(f"{rel}: no 'term' field, used '{term}' instead")

        category = clean(data.get("category")) or folder_category
        rows.append(
            [
                category,
                term,
                clean(data.get("definition")),
                format_sources(data.get("references")),
            ]
        )
    rows.sort(key=lambda r: (r[0].lower(), r[1].lower()))
    return rows, problems


def print_preview(rows, width=45):
    def cut(s):
        return s if len(s) <= width else s[: width - 1] + "…"

    cols = [[cut(c) for c in row] for row in [HEADERS] + rows]
    widths = [max(len(r[i]) for r in cols) for i in range(len(HEADERS))]
    line = "-+-".join("-" * w for w in widths)
    for n, row in enumerate(cols):
        print(" | ".join(c.ljust(w) for c, w in zip(row, widths)))
        if n == 0:
            print(line)


def save_csv(rows, path: Path):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(HEADERS)
        writer.writerows(rows)


def save_xlsx(rows, path: Path):
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font
    except ImportError:
        print("[INFO] openpyxl not installed, skipping .xlsx (pip install openpyxl)")
        return False

    wb = Workbook()
    ws = wb.active
    ws.title = "Glossary"
    ws.append(HEADERS)
    for row in rows:
        ws.append(row)

    for cell in ws[1]:
        cell.font = Font(bold=True)
    for col, w in zip("ABCD", (28, 28, 80, 60)):
        ws.column_dimensions[col].width = w
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")
    ws.freeze_panes = "A2"
    wb.save(path)
    return True


def open_in_vscode(path: Path):
    """Open the file in VS Code (needs the 'Excel Viewer' extension for .xlsx)."""
    try:
        # shell=True is needed on Windows because 'code' is a .cmd launcher
        subprocess.run(f'code "{path.resolve()}"', shell=True, check=True)
    except Exception as exc:
        print(f"[INFO] Could not open VS Code automatically ({exc}). Open the file manually.")


def main():
    parser = argparse.ArgumentParser(description="Export glossary terms to a table.")
    parser.add_argument("root", nargs="?", default=DEFAULT_ROOT, help="glossary folder")
    parser.add_argument("--out", default="glossary_table", help="output file name (no extension)")
    args = parser.parse_args()

    root = Path(args.root)
    if not root.is_dir():
        sys.exit(f"Folder not found: {root}")

    rows, problems = load_terms(root)
    if not rows:
        sys.exit(f"No .yaml/.yml files found under {root}")

    print_preview(rows)

    counts = {}
    for r in rows:
        counts[r[0]] = counts.get(r[0], 0) + 1
    print("\nTerms per category:")
    for cat, n in sorted(counts.items()):
        print(f"  {cat}: {n}")
    print(f"\nTotal: {len(rows)} terms in {len(counts)} categories (searched: {root})")

    if problems:
        print("\nFiles that need attention:")
        for p in problems:
            print(f"  - {p}")

    csv_path = Path(args.out).with_suffix(".csv")
    save_csv(rows, csv_path)
    print(f"Saved: {csv_path.resolve()}")

    xlsx_path = Path(args.out).with_suffix(".xlsx")
    if save_xlsx(rows, xlsx_path):
        print(f"Saved: {xlsx_path.resolve()}")
        open_in_vscode(xlsx_path)


if __name__ == "__main__":
    main()