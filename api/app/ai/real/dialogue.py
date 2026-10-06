import re
from collections.abc import Sequence

from pydantic import BaseModel, ValidationError

from app.ai.contracts import Answer, ConversationTurn, DocumentContext, QuestionContext
from app.ai.errors import AiOutputError
from app.ai.prescription_text import prescription_context
from app.ai.real import prompts
from app.ai.real.reasoning import Reasoner

MAX_CONTEXT_CHARS = 40_000
MAX_HISTORY_TURNS = 6
_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")

PRESCRIPTION_FALLBACK = (
    "Je ne suis pas sûr de cette information. Montre l'ordonnance à ton pharmacien, "
    "il pourra te répondre."
)
DOCUMENT_FALLBACK = (
    "Je ne trouve pas cette information avec certitude dans le document. "
    "Demande à l'organisme qui te l'a envoyé."
)


class _Reply(BaseModel):
    answer: str
    quote: str | None = None


def _history(turns: Sequence[ConversationTurn]) -> str:
    recent = turns[-MAX_HISTORY_TURNS:]
    if not recent:
        return "(aucun échange)"
    return "\n".join(
        f"{'Personne' if turn.role == 'user' else 'Leeral'} : {turn.text_fr}" for turn in recent
    )


def _document_text(document: DocumentContext) -> str:
    if document.is_prescription:
        return prescription_context(document.medications)
    return f"Résumé : {document.summary_fr}\n\nTexte complet :\n{document.full_text}"[
        :MAX_CONTEXT_CHARS
    ]


def _normalized_number(value: str) -> str:
    return value.replace(",", ".")


def numbers_are_grounded(answer: str, sources: Sequence[str]) -> bool:
    available = {
        _normalized_number(number) for source in sources for number in _NUMBER.findall(source)
    }
    return all(_normalized_number(number) in available for number in _NUMBER.findall(answer))


async def answer_question(reasoner: Reasoner, context: QuestionContext) -> Answer:
    history = _history(context.history)
    document = context.document
    if document is None:
        prompt = prompts.ANSWER_FREE_QUESTION.format(history=history, question=context.question_fr)
    else:
        prompt = prompts.ANSWER_QUESTION.format(
            document=_document_text(document),
            history=history,
            question=context.question_fr,
            safety_rules=prompts.PRESCRIPTION_SAFETY_RULES if document.is_prescription else "",
        )
    raw = await reasoner.complete_json(prompt, operation="answer_question", max_tokens=600)
    try:
        reply = _Reply.model_validate(raw)
    except ValidationError as exc:
        raise AiOutputError("answer output invalid") from exc

    if document is None:
        return Answer(text_fr=reply.answer.strip(), source_quote=None)

    sources = [_document_text(document), document.summary_fr]
    if not numbers_are_grounded(reply.answer, sources):
        fallback = PRESCRIPTION_FALLBACK if document.is_prescription else DOCUMENT_FALLBACK
        return Answer(text_fr=fallback, source_quote=None, grounded=False)
    quote = reply.quote.strip() if reply.quote else None
    if quote and quote not in document.full_text and quote not in _document_text(document):
        quote = None
    return Answer(text_fr=reply.answer.strip(), source_quote=quote)
