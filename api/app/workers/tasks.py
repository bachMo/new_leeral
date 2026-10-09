import uuid
from typing import Any

from app.core.languages import Language
from app.models.enums import DocumentStatus, ExplanationVariant
from app.workers.jobs import Job
from app.workers.runtime import WorkerRuntime

Context = dict[str, Any]


def _runtime(ctx: Context) -> WorkerRuntime:
    runtime: WorkerRuntime = ctx["runtime"]
    return runtime


async def process_document(ctx: Context, document_id: str) -> str | None:
    runtime = _runtime(ctx)
    identifier = uuid.UUID(document_id)
    status = await runtime.documents.process(identifier)
    if status is DocumentStatus.READY:
        await runtime.queue.enqueue(Job.EXTRACT_WORDS, document_id=document_id)
    await runtime.whatsapp.document_finished(identifier)
    return status.value if status else None


async def localize_explanation(ctx: Context, document_id: str, language: str, variant: str) -> None:
    await _runtime(ctx).documents.localize(
        uuid.UUID(document_id), Language(language), ExplanationVariant(variant)
    )


async def extract_words(ctx: Context, document_id: str) -> int:
    return await _runtime(ctx).vocabulary.extract_from_document(uuid.UUID(document_id))


async def answer_message(ctx: Context, question_id: str, answer_id: str) -> str | None:
    runtime = _runtime(ctx)
    status = await runtime.answers.answer(uuid.UUID(question_id), uuid.UUID(answer_id))
    await runtime.whatsapp.answer_finished(uuid.UUID(answer_id))
    return status.value if status else None


async def ask_writing_step(
    ctx: Context, writing_id: str, position: int, message_id: str, retry: bool = False
) -> None:
    await _runtime(ctx).writings.ask_step(
        uuid.UUID(writing_id), position, uuid.UUID(message_id), retry=retry
    )


async def analyze_writing_answer(ctx: Context, step_id: str, answer_id: str, reply_id: str) -> None:
    await _runtime(ctx).writings.analyze_answer(
        uuid.UUID(step_id), uuid.UUID(answer_id), uuid.UUID(reply_id)
    )


async def generate_writing(ctx: Context, writing_id: str, message_id: str) -> None:
    await _runtime(ctx).writings.generate(uuid.UUID(writing_id), uuid.UUID(message_id))


async def handle_whatsapp_message(
    ctx: Context, message_id: str, profile_name: str | None = None
) -> None:
    await _runtime(ctx).whatsapp.handle(uuid.UUID(message_id), profile_name)


async def collect_whatsapp_media(ctx: Context, user_id: str, message_id: str) -> None:
    await _runtime(ctx).whatsapp.collect_media(uuid.UUID(user_id), uuid.UUID(message_id))


async def reject_whatsapp_message(ctx: Context, message_id: str) -> None:
    await _runtime(ctx).whatsapp.reject_unsupported(uuid.UUID(message_id))


async def promote_guest_files(ctx: Context, user_id: str) -> int:
    return await _runtime(ctx).maintenance.promote_guest_files(uuid.UUID(user_id))


async def delete_storage_prefix(ctx: Context, prefix: str) -> None:
    await _runtime(ctx).maintenance.delete_prefix(prefix)


async def purge_guest_documents(ctx: Context) -> int:
    return await _runtime(ctx).maintenance.purge_guest_documents()


async def purge_inactive_guests(ctx: Context) -> int:
    return await _runtime(ctx).maintenance.purge_inactive_guests()


async def delete_expired_otps(ctx: Context) -> int:
    return await _runtime(ctx).maintenance.delete_expired_otps()


async def fail_stale_work(ctx: Context) -> int:
    return await _runtime(ctx).maintenance.fail_stale_work()


async def send_renewal_reminders(ctx: Context) -> int:
    return await _runtime(ctx).maintenance.send_renewal_reminders()
