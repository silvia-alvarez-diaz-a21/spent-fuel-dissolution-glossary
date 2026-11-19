"""
Read all glossary term YAML files and show them in Excel:

    Category | Term | Meaning (definition) | Source (references)

Nothing is saved in your project folders: the spreadsheet is created in the
system temp folder and opened straight away in your default spreadsheet app.

Usage (Git Bash, PowerShell, or any terminal):
    pip install pyyaml openpyxl
    python glossary_tools/glossary_table.py
    python glossary_tools/glossary_table.py "C:/path/to/glossary"
"""

import argparse
import os
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import yaml

try:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font
except ImportError:
    sys.exit("openpyxl is missing. Run:  python -m pip install openpyxl")

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
        citation = clean(ref.get("citation")) or clean(ref.get("id"))
        if citation:
            sources.append(citation)
    return " | ".join(sources)


def load_terms(root: Path):
    """Return (rows, problems). Every yaml/yml file in every subfolder gets a row."""
    rows = []
    problems = []
    files = sorted(
        p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in (".yaml", ".yml")
    )
    for path in files:
        rel = path.relative_to(root)
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


def build_workbook(rows, path: Path):
    wb = Workbook()
    ws = wb.active
    ws.title = "Glossary"
    ws.append(HEADERS)
    for row in rows:
        ws.append(row)

    for cell in ws[1]:
        cell.font = Font(bold=True)
    for col, width in zip("ABCD", (28, 28, 80, 60)):
        ws.column_dimensions[col].width = width
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    wb.save(path)


def open_file(path: Path):
    """Open the file with the default app (Excel)."""
    try:
        if sys.platform.startswith("win"):
            os.startfile(str(path))  # noqa: S606
        elif sys.platform == "darwin":
            subprocess.run(["open", str(path)], check=True)
        else:
            subprocess.run(["xdg-open", str(path)], check=True)
    except Exception as exc:
        print(f"[WARN] Could not open the file automatically: {exc}")
        print(f"       It is here: {path}")


def main():
    parser = argparse.ArgumentParser(description="Show glossary terms in Excel.")
    parser.add_argument("root", nargs="?", default=DEFAULT_ROOT, help="glossary folder")
    args = parser.parse_args()

    root = Path(args.root)
    if not root.is_dir():
        sys.exit(f"Folder not found: {root}")

    rows, problems = load_terms(root)
    if not rows:
        sys.exit(f"No .yaml/.yml files found under {root}")

    counts = {}
    for r in rows:
        counts[r[0]] = counts.get(r[0], 0) + 1
    print("Terms per category:")
    for cat, n in sorted(counts.items()):
        print(f"  {cat}: {n}")
    print(f"\nTotal: {len(rows)} terms in {len(counts)} categories")

    if problems:
        print("\nFiles that need attention:")
        for p in problems:
            print(f"  - {p}")

    # Temp file with a unique name, so a previous copy still open in Excel never blocks it
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    tmp_path = Path(tempfile.gettempdir()) / f"glossary_table_{stamp}.xlsx"
    build_workbook(rows, tmp_path)
    print("\nOpening in Excel...")
    open_file(tmp_path)


if __name__ == "__main__":
    main()
