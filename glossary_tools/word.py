"""Render the glossary as a Word document (.docx): cover, contents, categories, one entry per term.

Same content and order as the PDF (glossary_tools/pdf.py), but editable: it can be shared, commented and
merged into reports. The table of contents is a Word field; Word asks to update it when the file is opened.
"""

from __future__ import annotations

import itertools
import re
from datetime import date
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

from .core import Glossary

TITLE = "Spent Fuel Dissolution Glossary"
SUBTITLE = "EURAD-2 SAREC (WP8) · Amphos 21"
ACCENT = RGBColor(0x1F, 0x4E, 0x79)
MUTED = RGBColor(0x55, 0x55, 0x55)
_IDS = itertools.count(1)


# --- low-level helpers -----------------------------------------------------------------------------------
def _field(paragraph, instruction: str, placeholder: str = "") -> None:
    """Insert a Word field (TOC, PAGE...) in a paragraph."""
    run = paragraph.add_run()
    for kind, text in (("begin", None), ("instr", instruction), ("separate", None), ("text", placeholder),
                       ("end", None)):
        if kind == "instr":
            el = OxmlElement("w:instrText")
            el.set(qn("xml:space"), "preserve")
            el.text = text
        elif kind == "text":
            el = OxmlElement("w:t")
            el.text = text
        else:
            el = OxmlElement("w:fldChar")
            el.set(qn("w:fldCharType"), kind)
        run._r.append(el)


def _bookmark(paragraph, name: str) -> None:
    start, end = OxmlElement("w:bookmarkStart"), OxmlElement("w:bookmarkEnd")
    start.set(qn("w:id"), str(next(_IDS)))
    start.set(qn("w:name"), name[:40])
    end.set(qn("w:id"), start.get(qn("w:id")))
    paragraph._p.insert(0, start)
    paragraph._p.append(end)


def _shade(cell, hex_fill: str) -> None:
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_fill)
    cell._tc.get_or_add_tcPr().append(shd)


def _inline(paragraph, text: str, size: float | None = None, italic: bool = False, color=None) -> None:
    """Add text with the little Markdown used in descriptions: **bold** and `code`."""
    for part in re.split(r"(\*\*.+?\*\*|`.+?`)", text or ""):
        if not part:
            continue
        if part.startswith("**") and part.endswith("**"):
            run = paragraph.add_run(part[2:-2])
            run.bold = True
        elif part.startswith("`") and part.endswith("`"):
            run = paragraph.add_run(part[1:-1])
            run.font.name = "Consolas"
        else:
            run = paragraph.add_run(part)
        run.italic = italic or None
        if size:
            run.font.size = Pt(size)
        if color is not None:
            run.font.color.rgb = color


def _text_block(doc, text: str) -> None:
    """Paragraphs and '- ' bullets of a description."""
    for block in (text or "").strip().split("\n\n"):
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        if lines and all(ln.startswith("- ") for ln in lines[:1]):
            items, current = [], ""
            for ln in lines:
                if ln.startswith("- "):
                    if current:
                        items.append(current)
                    current = ln[2:]
                else:
                    current += " " + ln
            items.append(current)
            for item in items:
                _inline(doc.add_paragraph(style="List Bullet"), item)
        elif lines:
            _inline(doc.add_paragraph(), " ".join(lines))


# --- term content ---------------------------------------------------------------------------------------
def _rows(term: dict, names: dict[str, str]) -> list[tuple[str, list[str]]]:
    """Label and lines of the details table of one term (only the fields that are filled)."""
    rows: list[tuple[str, list[str]]] = []

    def add(label, lines):
        lines = [x for x in lines if x]
        if lines:
            rows.append((label, lines))

    def ref(tid):
        return names.get(tid, tid) + ("" if tid in names else " (not written yet)")

    add("Synonyms", ["; ".join(f"{s['label']} ({s['type']}{', ' + s['lang'] if s.get('lang') else ''})"
                               for s in term.get("synonyms") or [])])
    add("Translations", ["; ".join(f"{k}: {v}" for k, v in (term.get("translations") or {}).items() if v)])
    u = term.get("units") or {}
    add("Unit", [" / ".join(filter(None, [u.get("si") and f"SI: {u['si']}", u.get("db") and f"DB: {u['db']}"]))])
    add("Other units", ["; ".join(o if isinstance(o, str) else f"{o['unit']} → {o.get('to_db_unit') or ''}"
                                  for o in u.get("other") or [])])
    add("Allowed values", [f"{v['value']}: {v.get('definition') or ''}" for v in term.get("allowed_values") or []])
    rng = term.get("typical_range") or {}
    if rng.get("min") is not None or rng.get("max") is not None:
        add("Typical range", [f"{rng.get('min')} – {rng.get('max')} {u.get('db') or u.get('si') or ''} "
                              f"{rng.get('context') or ''}".strip()])
    add("Formula", [term.get("formula") or ""])
    add("Variables", [f"{v['symbol']}: {v['meaning']}" + (f" [{v['unit']}]" if v.get("unit") else "")
                      for v in term.get("formula_variables") or []])
    add("Related terms", [f"{r['relation']}: {ref(r['id'])}" for r in term.get("related_terms") or []])
    add("Database", [f"{m['table']}.{m['field']}" + (f" — “{m['excel_header']}”" if m.get("excel_header") else "")
                     + (f" — {m['note']}" if m.get("note") else "") for m in term.get("db_mapping") or []])
    add("Notes", ["• " + n for n in term.get("notes") or []])
    add("Pitfalls", ["• " + n for n in term.get("pitfalls") or []])
    add("Examples", ["• " + e["text"] for e in term.get("examples") or []])
    add("References", [r["citation"] + (f" doi:{r['doi']}" if r.get("doi") else "")
                       + (f" {r['url']}" if r.get("url") else "") + (f" ({r['pages']})" if r.get("pages") else "")
                       for r in term.get("references") or []])
    add("Standards", ["; ".join(term.get("standards") or [])])
    add("Record", [f"status {term.get('status') or 'draft'} · updated {term.get('updated') or '-'} · "
                   f"authors: {', '.join(term.get('authors') or [])}"
                   + (f" · reviewers: {', '.join(term['reviewers'])}" if term.get("reviewers") else "")])
    return rows


def _term(doc, term: dict, names: dict[str, str]) -> None:
    head = doc.add_heading(level=3)
    head.add_run(term["term"])
    if term.get("abbreviation"):
        run = head.add_run(f"  ({term['abbreviation']})")
        run.font.color.rgb = MUTED
    if term.get("status") == "deprecated":
        run = head.add_run(f"  [deprecated, see {names.get(term.get('replaced_by'), term.get('replaced_by') or '')}]")
        run.font.color.rgb = RGBColor(0xB0, 0x00, 0x20)
    _bookmark(head, term["id"])
    head.paragraph_format.keep_with_next = True
    definition = doc.add_paragraph()
    _inline(definition, term["definition"], italic=True)
    definition.paragraph_format.keep_with_next = True
    if term.get("description"):
        _text_block(doc, term["description"])
    rows = _rows(term, names)
    if rows:
        table = doc.add_table(rows=0, cols=2)
        table.style = "Table Grid"
        table.alignment = WD_TABLE_ALIGNMENT.LEFT
        for label, lines in rows:
            cells = table.add_row().cells
            cells[0].width, cells[1].width = Cm(3.2), Cm(13.3)
            _shade(cells[0], "EAF0F6")
            p = cells[0].paragraphs[0]
            run = p.add_run(label)
            run.bold, run.font.size = True, Pt(8.5)
            for i, line in enumerate(lines):
                p = cells[1].paragraphs[0] if i == 0 else cells[1].add_paragraph()
                _inline(p, line, size=8.5)
    doc.add_paragraph()


# --- document -------------------------------------------------------------------------------------------
def _styles(doc) -> None:
    normal = doc.styles["Normal"]
    normal.font.name, normal.font.size = "Calibri", Pt(10)
    for name, size in (("Title", 26), ("Heading 1", 16), ("Heading 2", 13), ("Heading 3", 12)):
        style = doc.styles[name]
        style.font.size = Pt(size)
        style.font.color.rgb = ACCENT if name != "Heading 3" else RGBColor(0, 0, 0)


def _update_fields_on_open(doc) -> None:
    el = OxmlElement("w:updateFields")
    el.set(qn("w:val"), "true")
    doc.settings.element.append(el)


def build_word(g: Glossary, out: Path, include_drafts: bool = True) -> Path:
    """Write the glossary to out (.docx). Categories in tree order, terms alphabetically inside each one."""
    terms = {tid: t for tid, t in g.terms.items() if include_drafts or t.get("status") == "approved"}
    names = {tid: t["term"] for tid, t in terms.items()}
    doc = Document()
    _styles(doc)
    section = doc.sections[0]
    for side in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(section, side, Cm(2))
    doc.core_properties.title, doc.core_properties.author, doc.core_properties.subject = TITLE, "Amphos 21", SUBTITLE

    for _ in range(8):
        doc.add_paragraph()
    title = doc.add_paragraph(TITLE, style="Title")
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for text in (SUBTITLE, f"{len(terms)} terms · {len(g.categories)} categories · {date.today().isoformat()}"):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _inline(p, text, size=13, color=MUTED)
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

    contents = doc.add_paragraph()
    run = contents.add_run("Contents")
    run.bold, run.font.size, run.font.color.rgb = True, Pt(16), ACCENT
    _field(doc.add_paragraph(), 'TOC \\o "1-3" \\h \\z \\u',
           "Right-click and choose Update Field to build the contents.")

    body = doc.add_section(WD_SECTION.NEW_PAGE)
    footer = body.footer
    footer.is_linked_to_previous = False
    fp = footer.paragraphs[0]
    _inline(fp, TITLE + "    ", size=8, color=MUTED)
    _field(fp, "PAGE", "1")

    def children(path):
        return sorted((p for p in g.categories if "/" in p and p.rsplit("/", 1)[0] == path),
                      key=lambda p: (g.categories[p].get("order", 0), p))

    def walk(path: str, depth: int, first: bool):
        cat = g.categories[path]
        if depth == 0 and not first:
            doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
        doc.add_heading(cat["name"], level=1 if depth == 0 else 2)
        p = doc.add_paragraph()
        _inline(p, " ".join((cat.get("description") or "").split()), size=9, color=MUTED)
        inside = sorted((t for t in terms.values() if t.get("category") == path), key=lambda t: t["term"].lower())
        if not inside and not children(path):
            _inline(doc.add_paragraph(), "No terms yet.", size=9, italic=True, color=MUTED)
        for t in inside:
            _term(doc, t, names)
        for child in children(path):
            walk(child, depth + 1, False)

    tops = sorted((p for p in g.categories if "/" not in p), key=lambda p: (g.categories[p].get("order", 0), p))
    for i, top in enumerate(tops):
        walk(top, 0, i == 0)

    _update_fields_on_open(doc)
    out.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out))
    return out
