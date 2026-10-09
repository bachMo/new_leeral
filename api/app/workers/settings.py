from typing import Any, ClassVar

from arq import cron
from arq.connections import RedisSettings
from arq.cron import CronJob
from arq.typing import WorkerCoroutine

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.workers import tasks
from app.workers.runtime import WorkerRuntime

_settings = get_settings()


async def startup(ctx: dict[str, Any]) -> None:
    configure_logging(_settings.log_level, json_output=_settings.environment == "production")
    ctx["runtime"] = WorkerRuntime.build(ctx["redis"])


async def shutdown(ctx: dict[str, Any]) -> None:
    runtime: WorkerRuntime | None = ctx.get("runtime")
    if runtime is not None:
        await runtime.close()


class WorkerSettings:
    redis_settings = RedisSettings.from_dsn(_settings.redis_url)
    functions: ClassVar[list[WorkerCoroutine]] = [
        tasks.process_document,
        tasks.localize_explanation,
        tasks.extract_words,
        tasks.answer_message,
        tasks.ask_writing_step,
        tasks.analyze_writing_answer,
        tasks.generate_writing,
        tasks.handle_whatsapp_message,
        tasks.collect_whatsapp_media,
        tasks.reject_whatsapp_message,
        tasks.promote_guest_files,
        tasks.delete_storage_prefix,
    ]
    cron_jobs: ClassVar[list[CronJob]] = [
        cron(tasks.purge_guest_documents, minute={5, 35}),
        cron(tasks.delete_expired_otps, minute=15),
        cron(tasks.fail_stale_work, minute={0, 10, 20, 30, 40, 50}),
        cron(tasks.purge_inactive_guests, hour=3, minute=20),
        cron(tasks.send_renewal_reminders, hour=9, minute=10),
    ]
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = 8
    job_timeout = 600
    keep_result = 60
