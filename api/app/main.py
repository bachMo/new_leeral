from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.ai import build_ai_engine
from app.api.deps import AppContainer
from app.api.errors import register_error_handlers
from app.api.middleware import RequestContextMiddleware
from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.core.security import TokenService
from app.db.session import get_engine
from app.integrations.payments import build_payment_gateway
from app.integrations.storage import get_storage
from app.integrations.whatsapp.client import WhatsAppClient
from app.services.otp_delivery import build_otp_delivery
from app.workers.queue import ArqJobQueue


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    queue = await ArqJobQueue.connect(settings.redis_url)
    whatsapp = WhatsAppClient(settings, httpx.AsyncClient(timeout=30.0))
    ai = build_ai_engine()
    app.state.container = AppContainer(
        settings=settings,
        ai=ai,
        storage=get_storage(),
        queue=queue,
        tokens=TokenService(settings),
        whatsapp=whatsapp,
        otp_delivery=build_otp_delivery(settings, whatsapp),
        payments=build_payment_gateway(settings),
    )
    try:
        yield
    finally:
        await ai.aclose()
        await whatsapp.aclose()
        await queue.aclose()
        await get_engine().dispose()


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or get_settings()
    configure_logging(resolved.log_level, json_output=resolved.environment == "production")
    app = FastAPI(
        title=resolved.app_name,
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs" if resolved.environment != "production" else None,
        redoc_url=None,
    )
    app.state.settings = resolved
    app.add_middleware(RequestContextMiddleware)
    if resolved.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=resolved.cors_origins,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    register_error_handlers(app)
    app.include_router(api_router)
    return app


app = create_app()
