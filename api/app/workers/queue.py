import logging
from typing import Any, Protocol

from arq.connections import ArqRedis, RedisSettings, create_pool

from app.workers.jobs import Job

logger = logging.getLogger("leeral.queue")


class JobQueue(Protocol):
    async def enqueue(
        self, job: Job, *, key: str | None = None, defer_by: float | None = None, **kwargs: Any
    ) -> None: ...


class ArqJobQueue:
    def __init__(self, pool: ArqRedis) -> None:
        self._pool = pool

    @classmethod
    async def connect(cls, redis_url: str) -> "ArqJobQueue":
        return cls(await create_pool(RedisSettings.from_dsn(redis_url)))

    async def enqueue(
        self, job: Job, *, key: str | None = None, defer_by: float | None = None, **kwargs: Any
    ) -> None:
        enqueued = await self._pool.enqueue_job(
            job.value, _job_id=key, _defer_by=defer_by, **kwargs
        )
        if enqueued is None:
            logger.info("job_already_queued", extra={"job": job.value, "key": key})

    async def aclose(self) -> None:
        await self._pool.aclose()
