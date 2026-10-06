from datetime import date
from pathlib import Path

from fpdf import FPDF
from fpdf.enums import XPos, YPos

from app.ai.contracts import ComposedDocument

FONTS_DIR = Path(__file__).resolve().parents[1] / "assets" / "fonts"
FONT_FAMILY = "DejaVu"
_INK = (18, 35, 59)
_ACCENT = (23, 117, 106)


def _new_pdf() -> FPDF:
    pdf = FPDF(format="A4")
    pdf.set_margins(left=20, top=20, right=20)
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_font(FONT_FAMILY, "", str(FONTS_DIR / "DejaVuSans.ttf"))
    pdf.add_font(FONT_FAMILY, "B", str(FONTS_DIR / "DejaVuSans-Bold.ttf"))
    pdf.set_text_color(*_INK)
    pdf.set_title("Document Leeral")
    pdf.set_creator("Leeral")
    return pdf


def render_pdf(document: ComposedDocument, *, issued_on: date) -> bytes:
    pdf = _new_pdf()
    pdf.add_page()
    pdf.set_font(FONT_FAMILY, "B", 17)
    pdf.multi_cell(0, 9, document.title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    if document.kind != "cv":
        pdf.set_font(FONT_FAMILY, "", 10)
        pdf.cell(0, 6, f"Le {issued_on.strftime('%d/%m/%Y')}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)
    for section in document.sections:
        if section.heading:
            pdf.set_font(FONT_FAMILY, "B", 12)
            pdf.set_text_color(*_ACCENT)
            pdf.multi_cell(0, 7, section.heading, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_text_color(*_INK)
        pdf.set_font(FONT_FAMILY, "", 11)
        for line in section.lines:
            pdf.multi_cell(0, 6, line, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(3)
    return bytes(pdf.output())
