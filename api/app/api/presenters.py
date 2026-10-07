from collections.abc import Sequence

from app.core.languages import Language
from app.integrations.storage import FileStorage
from app.models import (
    Document,
    DocumentExplanation,
    Message,
    Payment,
    PrescriptionLine,
    UiPrompt,
    User,
    UserWord,
    Word,
    WordTranslation,
    Writing,
    WritingOutput,
)
from app.models.enums import ExplanationVariant
from app.schemas.billing import PaymentOut
from app.schemas.conversations import MessageOut
from app.schemas.documents import (
    DocumentOut,
    DocumentSummaryOut,
    ExplanationOut,
    KeyPointOut,
    LibraryItemOut,
    PageOut,
    PrescriptionLineOut,
    SuggestedQuestionOut,
)
from app.schemas.learning import ChoiceOut, ExerciseOut, PracticeRoundOut, WordOut
from app.schemas.prompts import PromptOut
from app.schemas.users import UserOut
from app.schemas.writings import WritingOut, WritingOutputOut, WritingStepOut
from app.services.learning_service import PracticeRound
from app.services.writing_catalog import template_for


class Presenter:
    def __init__(self, storage: FileStorage) -> None:
        self._storage = storage

    def url(self, key: str | None, filename: str | None = None) -> str | None:
        return self._storage.signed_url(key, filename=filename) if key else None

    def _url(self, key: str, filename: str | None = None) -> str:
        return self._storage.signed_url(key, filename=filename)

    @staticmethod
    def user(user: User) -> UserOut:
        return UserOut.model_validate(user)

    @staticmethod
    def document_summary(document: Document) -> DocumentSummaryOut:
        return DocumentSummaryOut.model_validate(document)

    def explanation(self, explanation: DocumentExplanation | None) -> ExplanationOut | None:
        if explanation is None:
            return None
        return ExplanationOut(
            id=explanation.id,
            language=explanation.language,
            variant=explanation.variant,
            text=explanation.text,
            text_fr=explanation.text_fr,
            audio_url=self._url(explanation.audio_key),
            audio_duration_s=explanation.audio_duration_s,
        )

    def document(self, document: Document, language: Language) -> DocumentOut:
        explanations = {
            item.variant: item for item in document.explanations if item.language == language
        }
        summary = self.document_summary(document)
        return DocumentOut(
            **summary.model_dump(),
            issuer=document.issuer,
            document_date=document.document_date,
            pages=[
                PageOut(
                    position=file.position, mime_type=file.mime_type, url=self._url(file.file_key)
                )
                for file in document.files
            ],
            explanation=self.explanation(explanations.get(ExplanationVariant.STANDARD)),
            simple_explanation=self.explanation(explanations.get(ExplanationVariant.SIMPLE)),
            key_points=[
                KeyPointOut(
                    position=point.position,
                    kind=point.kind,
                    tag=point.tag,
                    title_fr=point.title_fr,
                    detail_fr=point.detail_fr,
                    due_date=point.due_date,
                    amount_xof=point.amount_xof,
                    audio_url=self._url(point.audio_key),
                )
                for point in document.key_points
                if point.language == language
            ],
            suggested_questions=[
                SuggestedQuestionOut(
                    id=question.id,
                    position=question.position,
                    text_fr=question.text_fr,
                    audio_url=self._url(question.audio_key),
                )
                for question in document.suggested_questions
                if question.language == language
            ],
            prescription_lines=[
                self.prescription_line(line) for line in document.prescription_lines
            ],
        )

    def prescription_line(self, line: PrescriptionLine) -> PrescriptionLineOut:
        return PrescriptionLineOut(
            position=line.position,
            status=line.status,
            name=line.lexicon_name or line.name_read,
            name_read=line.name_read,
            suggestion=line.lexicon_suggestion,
            dci=line.dci_lexicon or line.dci_read,
            strength=line.strength,
            form=line.form,
            times_per_day=line.times_per_day,
            duration_days=line.duration_days,
            timing=line.timing,
            instructions=line.instructions,
            raw=line.raw_read,
            image_url=self.url(line.image_key),
        )

    def message(self, message: Message) -> MessageOut:
        return MessageOut(
            id=message.id,
            role=message.role,
            content_type=message.content_type,
            language=message.language,
            status=message.status,
            text=message.text,
            text_fr=message.text_fr,
            audio_url=self.url(message.audio_key),
            audio_duration_s=message.audio_duration_s,
            source_quote=message.source_quote,
            suggested_question_id=message.suggested_question_id,
            created_at=message.created_at,
        )

    def writing(self, writing: Writing) -> WritingOut:
        template = template_for(writing.type)
        return WritingOut(
            id=writing.id,
            type=writing.type,
            title_fr=template.title_fr,
            status=writing.status,
            conversation_id=writing.conversation_id,
            current_step=writing.current_step,
            total_steps=writing.total_steps,
            steps=[
                WritingStepOut(
                    position=step.position,
                    field_key=step.field_key,
                    question_fr=template.steps[step.position].question_fr,
                    required=template.steps[step.position].required,
                    question_message_id=step.question_message_id,
                    understood_value=step.understood_value,
                    confirmed=step.confirmed_at is not None,
                )
                for step in writing.steps
            ],
            outputs=[self.writing_output(output) for output in writing.outputs],
            created_at=writing.created_at,
        )

    def writing_output(self, output: WritingOutput) -> WritingOutputOut:
        return WritingOutputOut(
            id=output.id,
            version=output.version,
            kind=output.kind,
            pdf_url=self._url(output.pdf_key, f"leeral-{output.kind.value}-v{output.version}.pdf"),
            readback_audio_url=self.url(output.readback_audio_key),
            created_at=output.created_at,
        )

    @staticmethod
    def library(documents: Sequence[Document], writings: Sequence[Writing]) -> list[LibraryItemOut]:
        items = [
            LibraryItemOut(
                kind="document",
                id=document.id,
                title=document.title or "Document",
                category=document.category.value,
                status=document.status.value,
                created_at=document.created_at,
            )
            for document in documents
        ] + [
            LibraryItemOut(
                kind="writing",
                id=writing.id,
                title=template_for(writing.type).title_fr,
                category="writing",
                status=writing.status.value,
                created_at=writing.created_at,
            )
            for writing in writings
        ]
        return sorted(items, key=lambda item: item.created_at, reverse=True)

    @staticmethod
    def payment(payment: Payment) -> PaymentOut:
        return PaymentOut(
            public_token=payment.public_token,
            status=payment.status,
            provider=payment.provider,
            method=payment.method,
            amount_xof=payment.amount_xof,
            checkout_url=(payment.raw_payload or {}).get("checkout_url"),
            paid_at=payment.paid_at,
            created_at=payment.created_at,
        )

    def practice_round(self, practice: PracticeRound) -> PracticeRoundOut:
        return PracticeRoundOut(
            session_id=practice.session.id,
            exercises=[
                ExerciseOut(
                    word_id=exercise.word.id,
                    word_fr=exercise.word.word_fr,
                    example_fr=exercise.word.example_fr,
                    meaning=exercise.translation.meaning,
                    meaning_audio_url=self._url(exercise.translation.audio_key),
                    choices=[
                        ChoiceOut(word_id=choice.id, word_fr=choice.word_fr)
                        for choice in exercise.choices
                    ],
                )
                for exercise in practice.exercises
            ],
        )

    def word(self, user_word: UserWord, word: Word, translation: WordTranslation | None) -> WordOut:
        return WordOut(
            word_id=word.id,
            word_fr=word.word_fr,
            category=word.category,
            example_fr=word.example_fr,
            meaning=translation.meaning if translation else None,
            meaning_audio_url=self.url(translation.audio_key) if translation else None,
            box=user_word.box,
            mastered=user_word.mastered,
            next_review_at=user_word.next_review_at,
        )

    def prompt(self, prompt: UiPrompt) -> PromptOut:
        return PromptOut(
            key=prompt.key, text_fr=prompt.text_fr, audio_url=self._url(prompt.audio_key)
        )
