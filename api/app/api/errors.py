import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.errors import ERROR_CATALOG, AppError, ErrorCode
from app.core.logging import request_id_var

logger = logging.getLogger("leeral.errors")

_HTTP_STATUS_CODES = {
    401: ErrorCode.UNAUTHENTICATED,
    403: ErrorCode.FORBIDDEN,
    404: ErrorCode.NOT_FOUND,
    405: ErrorCode.NOT_FOUND,
    413: ErrorCode.FILE_TOO_LARGE,
    429: ErrorCode.RATE_LIMITED,
}


def error_response(
    code: ErrorCode, *, status_code: int | None = None, fields: dict[str, Any] | None = None
) -> JSONResponse:
    spec = ERROR_CATALOG[code]
    lowered = code.value.lower()
    return JSONResponse(
        status_code=status_code or spec.status_code,
        content={
            "error": {
                "code": code.value,
                "message": spec.message,
                "message_key": f"errors.{lowered}",
                "audio_key": f"error.{lowered}",
                "retryable": spec.retryable,
                "request_id": request_id_var.get(),
                "fields": fields or {},
            }
        },
    )


async def _app_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)
    if exc.status_code >= 500:
        logger.warning("app_error", extra={"code": exc.code.value, "detail": exc.detail})
    return error_response(exc.code, fields=exc.fields)


async def _validation_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    fields = {
        ".".join(str(part) for part in error["loc"] if part != "body"): error["msg"]
        for error in exc.errors()
    }
    return error_response(ErrorCode.VALIDATION_FAILED, fields=fields)


async def _http_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    code = _HTTP_STATUS_CODES.get(exc.status_code, ErrorCode.INTERNAL_ERROR)
    return error_response(code, status_code=exc.status_code)


async def _unhandled_error(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled_error", extra={"path": request.url.path})
    return error_response(ErrorCode.INTERNAL_ERROR)


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _app_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(Exception, _unhandled_error)
