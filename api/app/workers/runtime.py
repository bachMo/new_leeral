from dataclasses import dataclass

import httpx
from arq.connections import ArqRedis

from app.ai import AiEngine, build_ai_engine
from app.channels.whatsapp.assistant import WhatsAppAssistant
from app.core.config import Settings, get_settings
from app.db.session import get_engine, get_session_factory
from app.integrations.storage import get_storage
from app.integrations.whatsapp.client import WhatsAppClient
from app.services.ai_jobs import AiJobTracker
from app.services.document_processor import DocumentProcessor
from app.services.maintenance_service import MaintenanceService
from app.services.question_answerer import QuestionAnswerer
from app.services.vocabulary_builder import VocabularyBuilder
from app.services.writing_assistant import WritingAssistant
from app.workers.queue import ArqJobQueue


@dataclass(frozen=True, slots=True)
class WorkerRuntime:
    settings: Settings
    ai: AiEngine
    queue: ArqJobQueue
    whatsapp_client: WhatsAppClient
    documents: DocumentProcessor
    answers: QuestionAnswerer
    writings: WritingAssistant
    vocabulary: VocabularyBuilder
    whatsapp: WhatsAppAssistant
    maintenance: MaintenanceService

    @classmethod
    def build(cls, redis: ArqRedis) -> "WorkerRuntime":
        settings = get_settings()
        ai = build_ai_engine()
        storage = get_storage()
        sessions = get_session_factory()
        queue = ArqJobQueue(redis)
        tracker = AiJobTracker(sessions, ai.name)
        whatsapp_client = WhatsAppClient(settings, httpx.AsyncClient(timeout=60.0))
        return cls(
            settings=settings,
            ai=ai,
            queue=queue,
            whatsapp_client=whatsapp_client,
            documents=DocumentProcessor(sessions, ai, storage, tracker, settings),
            answers=QuestionAnswerer(sessions, ai, storage, tracker),
            writings=WritingAssistant(sessions, ai, storage, tracker),
            vocabulary=VocabularyBuilder(sessions, ai, storage, tracker),
            whatsapp=WhatsAppAssistant(sessions, ai, storage, whatsapp_client, queue, settings),
            maintenance=MaintenanceService(sessions, storage, settings, whatsapp_client),
        )

    async def close(self) -> None:
        await self.ai.aclose()
        await self.whatsapp_client.aclose()
        await get_engine().dispose()
