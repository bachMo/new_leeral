import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Entity


class Repository[T: Entity]:
    model: type[T]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, entity_id: uuid.UUID) -> T | None:
        return await self.session.get(self.model, entity_id)

    def add(self, entity: T) -> T:
        self.session.add(entity)
        return entity

    def add_all(self, entities: list[T]) -> list[T]:
        self.session.add_all(entities)
        return entities

    async def delete(self, entity: T) -> None:
        await self.session.delete(entity)

    async def flush(self) -> None:
        await self.session.flush()
