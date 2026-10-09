from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.workers.jobs import Job
from app.workers.queue import JobQueue


@dataclass(frozen=True, slots=True)
class _DeferredJob:
    job: Job
    key: str | None
    defer_by: float | None
    kwargs: dict[str, Any]


class UnitOfWork:
    def __init__(self, session: AsyncSession, queue: JobQueue) -> None:
        self.session = session
        self._queue = queue
        self._jobs: list[_DeferredJob] = []

    def defer(
        self, job: Job, *, key: str | None = None, defer_by: float | None = None, **kwargs: Any
    ) -> None:
        self._jobs.append(_DeferredJob(job, key, defer_by, kwargs))

    async def commit(self) -> None:
        await self.session.commit()
        jobs, self._jobs = self._jobs, []
        for deferred in jobs:
            await self._queue.enqueue(
                deferred.job, key=deferred.key, defer_by=deferred.defer_by, **deferred.kwargs
            )

    async def rollback(self) -> None:
        self._jobs.clear()
        await self.session.rollback()
