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
        dci_read=row.dci_read,
        dci_lexicon=row.dci_lexicon,
        strength=row.strength,
        form=row.form,
        times_per_day=row.times_per_day,
        duration_days=row.duration_days,
        timing=row.timing,
        instructions=row.instructions,
        raw_read=row.raw_read,
        image_key=row.image_key,
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
        dci_read=line.dci_read,
        dci_lexicon=line.dci_lexicon,
        strength=line.strength,
        form=line.form,
        times_per_day=line.times_per_day,
        duration_days=line.duration_days,
        timing=line.timing,
        instructions=line.instructions,
        raw_read=line.raw_read,
        image_key=line.image_key,
        field_statuses=dict(line.field_statuses),
        pharmacology_flags=list(line.pharmacology_flags),
    )


def document_context(document: Document, lines: Sequence[PrescriptionLine]) -> DocumentContext:
    protected_terms = (document.extracted_data or {}).get("protected_terms", [])
    return DocumentContext(
        doc_type=document.doc_type,
        title=document.title,
        summary_fr=document.summary_fr or "",
        full_text=document.ocr_text or "",
        medications=tuple(medication_from_row(line) for line in lines),
        extra_protected_terms=tuple(protected_terms) if isinstance(protected_terms, list) else (),
    )
