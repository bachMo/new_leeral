from fastapi import APIRouter

from app.api.v1 import (
    auth,
    billing,
    conversations,
    documents,
    files,
    health,
    learning,
    meta,
    speech,
    users,
    webhooks,
    writings,
)

API_PREFIX = "/v1"

api_router = APIRouter(prefix=API_PREFIX)
for module in (
    health,
    meta,
    auth,
    users,
    documents,
    conversations,
    speech,
    writings,
    learning,
    billing,
    webhooks,
    files,
):
    api_router.include_router(module.router)
