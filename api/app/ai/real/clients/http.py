import asyncio
import logging
from typing import Any

import httpx

from app.ai.errors import AiAuthError, AiInputError, AiUnavailableError
from app.core.logging import log_step

logger = logging.getLogger("leeral.ai.http")

USER_AGENT = "Leeral-backend/1.0 (wolof/pulaar document assistant)"

_RETRYABLE_STATUSES = frozenset({429, 500, 502, 503, 504})
_CLIENT_ERROR_STATUSES = frozenset({400, 404, 413, 415, 422})
_DEFAULT_RETRY_DELAY_S = 1.0
_MAX_RETRY_DELAY_S = 20.0


def _retry_delay(response: httpx.Response | None, attempt: int) -> float:
    if response is not None and (header := response.headers.get("Retry-After")):
        try:
            return min(max(float(str(header)), 0.0), _MAX_RETRY_DELAY_S)
        except ValueError:
            pass
    return min(_DEFAULT_RETRY_DELAY_S * 2.0**attempt, _MAX_RETRY_DELAY_S)


def _error_message(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return response.text[:200]
    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict) and isinstance(error.get("message"), str):
            return str(error["message"])[:200]
        if isinstance(body.get("detail"), str):
            return str(body["detail"])[:200]
    return str(body)[:200]


def _raise_for_status(response: httpx.Response, service: str) -> None:
    status = response.status_code
    message = _error_message(response)
    if status in {401, 403}:
        raise AiAuthError(f"{service}: credentials rejected ({status}): {message}")
    if status in _CLIENT_ERROR_STATUSES:
        raise AiInputError(f"{service}: request rejected ({status}): {message}")
    raise AiUnavailableError(f"{service}: unexpected status {status}: {message}")


async def request_with_retry(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    service: str,
    max_retries: int,
    timeout: float,
    headers: dict[str, str] | None = None,
    json: dict[str, Any] | None = None,
    data: dict[str, str] | None = None,
    files: dict[str, tuple[str, bytes, str]] | None = None,
) -> httpx.Response:
    merged_headers = {"User-Agent": USER_AGENT, **(headers or {})}
    with log_step(logger, "ai_http_request", service=service) as out:
        for attempt in range(max_retries + 1):
            response: httpx.Response | None = None
            try:
                response = await client.request(
                    method,
                    url,
                    headers=merged_headers,
                    json=json,
                    data=data,
                    files=files,
                    timeout=timeout,
                )
            except httpx.HTTPError as exc:
                if attempt >= max_retries:
                    raise AiUnavailableError(f"{service}: network error: {exc!r}") from exc
                logger.warning("ai_network_retry", extra={"service": service, "attempt": attempt})
            else:
                if response.is_success:
                    out["status"] = response.status_code
                    out["attempt"] = attempt + 1
                    return response
                if response.status_code not in _RETRYABLE_STATUSES or attempt >= max_retries:
                    _raise_for_status(response, service)
                logger.warning(
                    "ai_status_retry",
                    extra={
                        "service": service,
                        "status": response.status_code,
                        "attempt": attempt,
                    },
                )
            await asyncio.sleep(_retry_delay(response, attempt))
        raise AiUnavailableError(f"{service}: exhausted {max_retries + 1} attempts")
