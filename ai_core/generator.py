"""Document export formatting for LegalEase.

Turns the markdown-flavoured text produced by the generator layer into the
three delivery formats required by the specification:

* ``.txt``  - returned verbatim by :func:`sanitize_text`
* ``.docx`` - logo on the first page, ``Times New Roman`` body, branded title
  and a footer on every page
* ``.pdf``  - logo header and footer repeated on every page

:func:`format_html_preview` renders the scrollable, dark-themed preview card
that the Streamlit frontend displays.
"""

from __future__ import annotations

import html as _html
import io
import re

import config
from ai_core.assets import ensure_assets, is_usable_logo
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor
from fpdf import FPDF

BODY_FONT = "Times New Roman"
ACCENT_HEX = "#4A90E2"
ACCENT_RGB = RGBColor(0x4A, 0x90, 0xE2)

# The dark "card" colours used by the Streamlit preview widget.
PREVIEW_BG = "#1b1f2a"
PREVIEW_BORDER = "#2d3444"
PREVIEW_TEXT = "#e8e8e8"
PREVIEW_MUTED = "#9aa4b2"

_HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})\s*(.*)$")
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*", re.DOTALL)
_BULLET_RE = re.compile(r"^\s*(?:[-*•]|\(?[a-zA-Z0-9]{1,3}[.)])\s+(.*)$")

# Unicode punctuation that the built-in PDF core fonts cannot encode.
_PUNCT_MAP = {
    "“": '"', "”": '"', "‘": "'", "’": "'",
    "–": "-", "—": "-", "…": "...", " ": " ",
    "•": "-", "™": "(TM)", "®": "(R)", "©": "(c)",
}


def sanitize_text(text: str) -> str:
    """Normalise smart punctuation and strip the leading/trailing whitespace.

    The generated markdown passes through here before it is previewed or
    exported, so the same characters render identically in every format.
    """
    if not text:
        return ""
    for src, dst in _PUNCT_MAP.items():
        text = text.replace(src, dst)
    # Drop any other character the core PDF fonts cannot represent.
    text = text.encode("latin-1", "ignore").decode("latin-1")
    return text.strip()



# --------------------------------------------------------------------------- #
# Markdown block parsing - shared by all three renderers
# --------------------------------------------------------------------------- #

def _strip_bold(text: str) -> str:
    return _BOLD_RE.sub(r"\1", text)


def iter_blocks(text: str):
    """Yield ``(kind, payload)`` blocks from markdown-flavoured document text.

    ``kind`` is one of ``heading``, ``bullet`` or ``paragraph``.  Inline
    ``**bold**`` markers are preserved so each renderer can honour them.
    """
    for raw_line in (text or "").split("\n"):
        stripped = raw_line.strip()
        if not stripped:
            continue

        heading = _HEADING_RE.match(stripped)
        if heading:
            title = heading.group(2).strip() or stripped.lstrip("#").strip()
            if title:
                yield "heading", (len(heading.group(1)), title)
            continue

        bullet = _BULLET_RE.match(stripped)
        if bullet and bullet.group(1).strip():
            yield "bullet", bullet.group(1).strip()
            continue

        yield "paragraph", stripped


def _split_bold(text: str):
    """Split ``text`` into ``(chunk, is_bold)`` runs for inline ``**bold**``."""
    runs, pos = [], 0
    for match in _BOLD_RE.finditer(text):
        if match.start() > pos:
            runs.append((text[pos:match.start()], False))
        runs.append((match.group(1), True))
        pos = match.end()
    if pos < len(text):
        runs.append((text[pos:], False))
    return runs or [("", False)]


def resolve_logo() -> str:
    """Return a usable dark-ink logo path, regenerating the asset if needed."""
    ensure_assets(config.IMAGE_DIR)
    path = config.LOGO_PATH
    return path if is_usable_logo(path) else ""


def display_title(doc_type: str) -> str:
    """Title-case the document type for the cover title."""
    title = sanitize_text(doc_type or "").strip()
    if not title:
        return "DOCUMENT"
    return title if title.isupper() else title.title()


# --------------------------------------------------------------------------- #
# HTML preview (Streamlit preview card)
# --------------------------------------------------------------------------- #

def _render_html_bold(text: str) -> str:
    """Escape ``text`` for HTML while honouring inline ``**bold**`` runs."""
    out = []
    for chunk, is_bold in _split_bold(text):
        safe = _html.escape(chunk)
        out.append(f"<strong>{safe}</strong>" if is_bold else safe)
    return "".join(out)


def format_html_preview(text: str) -> str:
    """Render the dark, scrollable preview card shown after generation."""
    parts = [
        "<div style='background-color:{bg}; border:1px solid {border}; border-radius:10px; "
        "padding:18px 22px; max-height:420px; overflow-y:auto; color:{fg}; "
        "font-family:'Source Sans', sans-serif; font-size:0.95rem; line-height:1.6;'>".format(
            bg=PREVIEW_BG,
            border=PREVIEW_BORDER,
            fg=PREVIEW_TEXT,
        )
    ]
    for kind, payload in iter_blocks(sanitize_text(text)):
        if kind == "heading":
            level, title = payload
            size = {1: "1.10rem", 2: "1.05rem"}.get(level, "1.0rem")
            parts.append(
                "<div style='color:{fg}; font-weight:700; font-size:{size}; "
                "margin:14px 0 8px 0;'>{body}</div>".format(
                    fg=PREVIEW_TEXT, size=size, body=_render_html_bold(title)
                )
            )
        elif kind == "bullet":
            parts.append(
                "<div style='display:flex; gap:9px; margin:0 0 7px 0;'>"
                "<span style='color:{fg};'>&bull;</span>"
                "<span style='flex:1;'>{body}</span></div>".format(
                    fg=PREVIEW_TEXT, body=_render_html_bold(payload)
                )
            )
        else:
            parts.append(
                "<p style='margin:0 0 10px 0;'>{body}</p>".format(body=_render_html_bold(payload))
            )
    parts.append("</div>")
    return "".join(parts)


# --------------------------------------------------------------------------- #
# DOCX export
# --------------------------------------------------------------------------- #

def _docx_add_runs(paragraph, text: str, size: int, bold: bool = False, color=None):
    """Add text to a docx paragraph, honouring inline ``**bold**`` runs."""
    for chunk, is_bold in _split_bold(text):
        if not chunk:
            continue
        run = paragraph.add_run(chunk)
        run.font.size = Pt(size)
        run.font.bold = bold or is_bold
        run.font.name = BODY_FONT
        if color is not None:
            run.font.color.rgb = color
    return paragraph


def _add_terms_table(doc, terms: str):
    """Append the auto-generated summary table of the user's term bullets."""
    from ai_core.templates import split_terms

    bullets = split_terms(terms)
    if not bullets:
        return
    heading = doc.add_paragraph()
    _docx_add_runs(heading, "Summary of Agreed Terms", 12, bold=True, color=ACCENT_RGB)
    table = doc.add_table(rows=1, cols=2)
    table.style = "Light Grid Accent 1"
    header = table.rows[0].cells
    header[0].text = "#"
    header[1].text = "Term"
    for cell in header:
        for para in cell.paragraphs:
            for run in para.runs:
                run.font.bold = True
                run.font.name = BODY_FONT
                run.font.size = Pt(10)
    for idx, bullet in enumerate(bullets, start=1):
        cells = table.add_row().cells
        cells[0].text = str(idx)
        cells[1].text = bullet
        for cell in cells:
            for para in cell.paragraphs:
                for run in para.runs:
                    run.font.name = BODY_FONT
                    run.font.size = Pt(10)


def format_docx(text: str, doc_type: str, terms: str = "") -> bytes:
    """Build the branded .docx export: logo cover block, title, body, footer."""
    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = BODY_FONT
    style.font.size = Pt(11)

    logo = resolve_logo()
    if logo:
        para = doc.add_paragraph()
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        para.add_run().add_picture(logo, width=Inches(2.2))

    title_para = doc.add_paragraph()
    title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _docx_add_runs(title_para, display_title(doc_type), 18, bold=True, color=ACCENT_RGB)

    first_block = True
    for kind, payload in iter_blocks(sanitize_text(text)):
        if kind == "heading":
            level, title = payload
            if first_block and logo:
                # The document title is already shown above the logo block.
                first_block = False
                continue
            para = doc.add_paragraph()
            para.paragraph_format.space_before = Pt(10)
            _docx_add_runs(para, title, 14 if level <= 2 else 12, bold=True, color=ACCENT_RGB)
        elif kind == "bullet":
            para = doc.add_paragraph(style="List Bullet")
            para.paragraph_format.space_after = Pt(4)
            _docx_add_runs(para, payload, 11)
        else:
            para = doc.add_paragraph()
            para.paragraph_format.line_spacing = 1.15
            para.paragraph_format.space_after = Pt(8)
            _docx_add_runs(para, payload, 11)
        first_block = False

    if terms:
        doc.add_paragraph()
        _add_terms_table(doc, terms)

    end = doc.add_paragraph()
    end.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    end_run = end.add_run(config.END_MARKER)
    end_run.font.size = Pt(8)
    end_run.font.italic = True
    end_run.font.name = BODY_FONT

    return _docx_finish(doc)


# --------------------------------------------------------------------------- #
# PDF export
# --------------------------------------------------------------------------- #

class PDFGenerator(FPDF):
    """FPDF document that repeats the LegalEase logo header and footer."""

    LOGO_WIDTH_MM = 52
    LOGO_HEIGHT_MM = 22

    def header(self):
        logo = resolve_logo()
        if logo:
            x = max(self.l_margin, (self.w - self.LOGO_WIDTH_MM) / 2)
            try:
                self.image(logo, x=x, y=8, w=self.LOGO_WIDTH_MM)
            except Exception:
                self.set_font("Helvetica", "B", 14)
                self.cell(0, 8, "LegalEase", new_x="LMARGIN", new_y="NEXT", align="C")
        else:
            self.set_font("Helvetica", "B", 14)
            self.cell(0, 8, "LegalEase", new_x="LMARGIN", new_y="NEXT", align="C")
        self.ln(6)
        self.y = max(self.y, 34)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.cell(
            0, 10,
            sanitize_text(config.FOOTER_TEXT),
            new_x="LMARGIN", new_y="TOP", align="C",
        )


def _pdf_write_runs(pdf: FPDF, text: str, size: int, base_font: str = "Helvetica", lead: float = 5.0):
    """Write ``text`` honouring inline ``**bold**`` runs, wrapping on page width.

    Words are buffered into a line, then each line is emitted run-by-run so the
    PDF cursor and the measured x position never drift apart.
    """
    words = []
    for chunk, is_bold in _split_bold(text):
        for token in chunk.split(" "):
            if token:
                words.append((token, is_bold))
    if not words:
        return

    right = pdf.w - pdf.r_margin
    line = []
    line_w = 0.0

    def flush():
        nonlocal line, line_w
        if not line:
            return
        pdf.set_x(pdf.l_margin)
        for token, is_bold in line:
            pdf.set_font(base_font, "B" if is_bold else "", size)
            pdf.cell(pdf.get_string_width(token) + 0.6, lead, token,
                     border=0, new_x="RIGHT", new_y="TOP")
        pdf.ln(lead)
        line, line_w = [], 0.0

    for token, is_bold in words:
        pdf.set_font(base_font, "B" if is_bold else "", size)
        token_w = pdf.get_string_width(token) + 0.6
        if line and line_w + token_w > right - pdf.l_margin:
            flush()
        line.append((token, is_bold))
        line_w += token_w
    flush()
    pdf.set_font(base_font, "", size)


def format_pdf(text: str, doc_type: str) -> bytes:
    """Build the .pdf export: logo + title up front, footer on every page."""
    pdf = PDFGenerator()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.set_margins(18, 18, 18)
    pdf.add_page()

    title = display_title(doc_type)
    pdf.set_font("Helvetica", "B", 15)
    pdf.multi_cell(0, 9, title, align="C")
    pdf.ln(4)

    seen_first_heading = False
    for kind, payload in iter_blocks(sanitize_text(text)):
        if kind == "heading":
            level, heading = payload
            if not seen_first_heading:
                seen_first_heading = True
                # The cover title already shows the document type.
                if heading.strip().casefold() == title.strip().casefold():
                    continue
            _pdf_write_runs(pdf, f"**{heading}**", 12 if level <= 2 else 11, lead=6.0)
            pdf.ln(1)
        elif kind == "bullet":
            saved_x = pdf.get_x()
            pdf.set_x(pdf.l_margin + 4)
            _pdf_write_runs(pdf, f"-  {payload}", 10, lead=5.0)
            pdf.set_x(saved_x)
        else:
            _pdf_write_runs(pdf, payload, 10)

    pdf.ln(8)
    pdf.set_font("Helvetica", "I", 8)
    pdf.cell(0, 6, config.END_MARKER, new_x="LMARGIN", new_y="NEXT", align="R")

    return bytes(pdf.output())


def _docx_finish(doc):
    """Attach the branded footer and serialise the document to bytes."""
    footer = doc.sections[0].footer
    footer_para = footer.paragraphs[0]
    footer_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = footer_para.add_run(config.FOOTER_TEXT)
    run.font.size = Pt(9)
    run.font.name = BODY_FONT

    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()
