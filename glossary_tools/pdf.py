"""Render the glossary as a PDF: cover, contents by category, then one entry per term."""

from __future__ import annotations

import re
from datetime import date
from html import escape
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)
from reportlab.platypus.tableofcontents import TableOfContents

from .core import Glossary

TITLE = "Spent Fuel Dissolution Glossary"
SUBTITLE = "EURAD-2 SAREC (WP8) · Amphos 21"
ACCENT = colors.HexColor("#1F4E79")
MUTED = colors.HexColor("#555555")

_base = getSampleStyleSheet()
S = {
    "title": ParagraphStyle("title", _base["Title"], fontSize=26, leading=32, textColor=ACCENT, alignment=TA_CENTER),
    "subtitle": ParagraphStyle("subtitle", _base["Normal"], fontSize=13, textColor=MUTED, alignment=TA_CENTER),
    "h1": ParagraphStyle("h1", _base["Heading1"], textColor=ACCENT, spaceBefore=6, spaceAfter=8),
    "h2": ParagraphStyle("h2", _base["Heading2"], textColor=ACCENT, spaceBefore=10, spaceAfter=4),
    "term": ParagraphStyle("term", _base["Heading3"], fontSize=13, spaceBefore=10, spaceAfter=2),
    "body": ParagraphStyle("body", _base["BodyText"], fontSize=9.5, leading=13),
    "small": ParagraphStyle("small", _base["BodyText"], fontSize=8.5, leading=11, textColor=MUTED),
    "label": ParagraphStyle("label", _base["BodyText"], fontSize=8.5, leading=11, fontName="Helvetica-Bold"),
    "toc1": ParagraphStyle("toc1", _base["Normal"], fontSize=11, leading=16, fontName="Helvetica-Bold"),
    "toc2": ParagraphStyle("toc2", _base["Normal"], fontSize=10, leading=14, leftIndent=14),
    "toc3": ParagraphStyle("toc3", _base["Normal"], fontSize=9.5, leading=13, leftIndent=28),
}


def _md(text: str) -> str:
    """The little Markdown used in descriptions: **bold**, `code`, line breaks and '- ' bullets."""
    out = []
    for line in escape(text or "").strip().splitlines():
        line = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", line)
        line = re.sub(r"`(.+?)`", r"<font face='Courier'>\1</font>", line)
        out.append("&bull; " + line.strip()[2:] if line.strip().startswith("- ") else line)
    return "<br/>".join(out)


def _p(text, style="body"):
    return Paragraph(text, S[style])


def _rows(term: dict, names: dict[str, str]) -> list[list]:
    """Label/value rows of the details table of one term (only the fields that are filled)."""
    rows = []

    def add(label, value):
        if value:
            rows.append([_p(label, "label"), _p(value, "small")])

    add("Synonyms", "; ".join(f"{escape(s['label'])} <i>({s['type']}{', ' + s['lang'] if s.get('lang') else ''})</i>"
                              for s in term.get("synonyms") or []))
    add("Translations", "; ".join(f"<b>{k}</b>: {escape(v)}" for k, v in (term.get("translations") or {}).items() if v))
    q = term.get("quantity") or {}
    add("Unit", escape(" / ".join(filter(None, [q.get("unit"), q.get("si_unit") and f"SI: {q['si_unit']}"]))))
    add("Other units", "; ".join(f"{escape(u['unit'])} → {escape(u.get('to_db_unit') or '')}"
                                 for u in q.get("other_units") or []))
    add("Allowed values", "<br/>".join(f"<b>{escape(v['value'])}</b>: {escape(v.get('definition') or '')}"
                                       for v in q.get("allowed_values") or []))
    rng = q.get("typical_range") or {}
    if rng.get("min") is not None or rng.get("max") is not None:
        span = f"{rng.get('min')} – {rng.get('max')} {q.get('unit') or ''} {rng.get('context') or ''}"
        add("Typical range", escape(span))
    add("Formula", f"<font face='Courier'>{escape(q.get('formula') or '')}</font>" if q.get("formula") else "")

    def ref(tid):
        return f"{escape(names.get(tid, tid))}" + ("" if tid in names else " <i>(not written yet)</i>")

    add("Broader", ", ".join(ref(t) for t in term.get("broader") or []))
    add("Narrower", ", ".join(ref(t) for t in term.get("narrower") or []))
    add("Related", ", ".join(f"{ref(r['id'])} <i>({r.get('relation', 'related')})</i>"
                             for r in term.get("related") or []))
    add("Database", "<br/>".join(
        f"<font face='Courier'>{escape(m['table'])}.{escape(m['field'])}</font>"
        + (f" — “{escape(m['excel_header'])}”" if m.get("excel_header") else "")
        + (f" — {escape(m['note'])}" if m.get("note") else "") for m in term.get("db_mapping") or []))
    add("Notes", "<br/>".join("&bull; " + escape(n) for n in term.get("notes") or []))
    add("Pitfalls", "<br/>".join("&bull; " + escape(n) for n in term.get("pitfalls") or []))
    add("Examples", "<br/>".join("&bull; " + escape(e["text"]) for e in term.get("examples") or []))
    add("References", "<br/>".join(
        escape(r["citation"]) + (f" doi:{escape(r['doi'])}" if r.get("doi") else "")
        + (f" {escape(r['url'])}" if r.get("url") else "") + (f" ({escape(r['pages'])})" if r.get("pages") else "")
        for r in term.get("references") or []))
    add("Standards", "; ".join(escape(s) for s in term.get("standards") or []))
    add("Record", escape(f"status {term.get('status')} · updated {term.get('updated')} · "
                         f"authors: {', '.join(term.get('authors') or [])}"
                         + (f" · reviewers: {', '.join(term['reviewers'])}" if term.get("reviewers") else "")))
    return rows


def _term_flowables(term: dict, names: dict[str, str]) -> list:
    head = escape(term["term"]) + (f"  <font color='#555555'>({escape(term['abbreviation'])})</font>"
                                   if term.get("abbreviation") else "")
    if term.get("status") == "deprecated":
        head += "  <font color='#B00020'>[deprecated"
        head += f", see {escape(names.get(term.get('replaced_by'), term.get('replaced_by') or ''))}]</font>"
    out = [_p(f"<a name='{term['id']}'/>{head}", "term"),
           _p(f"<i>{escape(term['definition'])}</i>"), Spacer(1, 4)]
    if term.get("description"):
        out += [_p(_md(term["description"])), Spacer(1, 4)]
    rows = _rows(term, names)
    if rows:
        table = Table(rows, colWidths=[3.2 * cm, 13.3 * cm])
        table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LINEBELOW", (0, 0), (-1, -2), 0.25, colors.HexColor("#DDDDDD")),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3), ("TOPPADDING", (0, 0), (-1, -1), 3),
        ]))
        out.append(table)
    return [KeepTogether(out[:3]), *out[3:], Spacer(1, 8)]


class _Doc(SimpleDocTemplate):
    def afterFlowable(self, flowable):
        """Feed the table of contents with the category headings."""
        if isinstance(flowable, Paragraph) and flowable.style.name in ("h1", "h2"):
            level = 0 if flowable.style.name == "h1" else 1
            self.notify("TOCEntry", (level, flowable.getPlainText(), self.page))


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(2 * cm, 1.2 * cm, TITLE)
    canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"{doc.page}")
    canvas.restoreState()


def build_pdf(g: Glossary, out: Path, include_drafts: bool = True) -> Path:
    """Write the glossary to out (PDF). Categories in tree order, terms alphabetically inside each one."""
    terms = {tid: t for tid, t in g.terms.items() if include_drafts or t.get("status") == "approved"}
    names = {tid: t["term"] for tid, t in terms.items()}
    story = [Spacer(1, 7 * cm), _p(TITLE, "title"), Spacer(1, 10), _p(SUBTITLE, "subtitle"), Spacer(1, 6),
             _p(f"{len(terms)} terms · {len(g.categories)} categories · {date.today().isoformat()}", "subtitle"),
             PageBreak(), Paragraph("Contents", ParagraphStyle("contents", S["h1"]))]   # not listed in itself
    toc = TableOfContents()
    toc.levelStyles = [S["toc1"], S["toc2"], S["toc3"]]
    story += [toc, PageBreak()]

    def walk(path: str, depth: int):
        cat = g.categories[path]
        story.append(_p(escape(cat["name"]), "h1" if depth == 0 else "h2"))
        story.append(_p(escape(cat.get("description", "")), "small"))
        inside = sorted((t for t in terms.values() if t.get("category") == path), key=lambda t: t["term"].lower())
        if not inside and not any(p.rsplit("/", 1)[0] == path for p in g.categories if "/" in p):
            story.append(_p("<i>No terms yet.</i>", "small"))
        for t in inside:
            story.extend(_term_flowables(t, names))
        children = sorted((p for p in g.categories if "/" in p and p.rsplit("/", 1)[0] == path),
                          key=lambda p: (g.categories[p].get("order", 0), p))
        for child in children:
            walk(child, depth + 1)

    tops = sorted((p for p in g.categories if "/" not in p), key=lambda p: (g.categories[p].get("order", 0), p))
    for i, top in enumerate(tops):
        if i:
            story.append(PageBreak())
        walk(top, 0)

    out.parent.mkdir(parents=True, exist_ok=True)
    doc = _Doc(str(out), pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm,
               bottomMargin=2 * cm, title=TITLE, author="Amphos 21", subject=SUBTITLE)
    doc.multiBuild(story, onFirstPage=lambda c, d: None, onLaterPages=_footer)
    return out
