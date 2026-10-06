import uuid
from collections.abc import Sequence

from app.ai.contracts import DocumentContext, MedicationLine
from app.models import Document, PrescriptionLine
from app.models.enums import LineStatus


def medication_from_row(row: PrescriptionLine) -> MedicationLine:
    return MedicationLine(
        position=row.position,
        page_position=row.page_position,
        status=row.status.value,
        name_read=row.name_read,
        lexicon_name=row.lexicon_name,
        lexicon_suggestion=row.lexicon_suggestion,
        strength=row.strength,
        times_per_day=row.times_per_day,
        duration_days=row.duration_days,
        timing=row.timing,
        field_statuses=dict(row.field_statuses),
        pharmacology_flags=tuple(row.pharmacology_flags),
    )


def row_from_medication(document_id: uuid.UUID, line: MedicationLine) -> PrescriptionLine:
    return PrescriptionLine(
        document_id=document_id,
        position=line.position,
        page_position=line.page_position,
        status=LineStatus(line.status),
        name_read=line.name_read,
        lexicon_name=line.lexicon_name,
        lexicon_suggestion=line.lexicon_suggestion,
        strength=line.strength,
        times_per_day=line.times_per_day,
        duration_days=line.duration_days,
        timing=line.timing,
        field_statuses=dict(line.field_statuses),
        pharmacology_flags=list(line.pharmacology_flags),
    )


def document_context(document: Document, lines: Sequence[PrescriptionLine]) -> DocumentContext:
    return DocumentContext(
        doc_type=document.doc_type,
        title=document.title,
        summary_fr=document.summary_fr or "",
        full_text=document.ocr_text or "",
        medications=tuple(medication_from_row(line) for line in lines),
    )
