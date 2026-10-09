import logging
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import Settings

logger = logging.getLogger("leeral.whatsapp")

MAX_BUTTONS = 3
MAX_BUTTON_TITLE = 20
MAX_TEXT_LENGTH = 4096


class WhatsAppError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        self.status_code = status_code
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class DownloadedMedia:
    content: bytes
    mime_type: str


@dataclass(frozen=True, slots=True)
class ReplyButton:
    id: str
    title: str


class WhatsAppClient:
    def __init__(self, settings: Settings, http: httpx.AsyncClient | None = None) -> None:
        self._base_url = settings.graph_api_url
        self._token = settings.whatsapp_access_token.get_secret_value()
        self._http = http or httpx.AsyncClient(timeout=30.0)

    @property
    def configured(self) -> bool:
        return bool(self._token)

    async def aclose(self) -> None:
        await self._http.aclose()

    async def send_text(self, phone_number_id: str, to: str, body: str) -> str:
        return await self._send(
            phone_number_id,
            to,
            {"type": "text", "text": {"body": body[:MAX_TEXT_LENGTH], "preview_url": False}},
        )

    async def send_buttons(
        self, phone_number_id: str, to: str, body: str, buttons: list[ReplyButton]
    ) -> str:
        return await self._send(
            phone_number_id,
            to,
            {
                "type": "interactive",
                "interactive": {
                    "type": "button",
                    "body": {"text": body[:1024]},
                    "action": {
                        "buttons": [
                            {
                                "type": "reply",
                                "reply": {
                                    "id": button.id,
                                    "title": button.title[:MAX_BUTTON_TITLE],
                                },
                            }
                            for button in buttons[:MAX_BUTTONS]
                        ]
                    },
                },
            },
        )

    async def send_audio(
        self,
        phone_number_id: str,
        to: str,
        content: bytes,
        mime_type: str,
        filename: str,
        *,
        voice: bool = False,
    ) -> str:
        media_id = await self.upload_media(phone_number_id, content, mime_type, filename)
        audio: dict[str, Any] = {"id": media_id}
        if voice:
            audio["voice"] = True
        return await self._send(phone_number_id, to, {"type": "audio", "audio": audio})

    async def send_document(
        self,
        phone_number_id: str,
        to: str,
        content: bytes,
        mime_type: str,
        filename: str,
        caption: str | None = None,
    ) -> str:
        media_id = await self.upload_media(phone_number_id, content, mime_type, filename)
        document: dict[str, Any] = {"id": media_id, "filename": filename}
        if caption:
            document["caption"] = caption[:1024]
        return await self._send(phone_number_id, to, {"type": "document", "document": document})

    async def send_template(
        self,
        phone_number_id: str,
        to: str,
        name: str,
        language: str,
        components: list[dict[str, Any]] | None = None,
    ) -> str:
        template: dict[str, Any] = {"name": name, "language": {"code": language}}
        if components:
            template["components"] = components
        return await self._send(phone_number_id, to, {"type": "template", "template": template})

    async def send_otp_template(
        self, phone_number_id: str, to: str, name: str, language: str, code: str
    ) -> str:
        return await self.send_template(
            phone_number_id,
            to,
            name,
            language,
            [
                {"type": "body", "parameters": [{"type": "text", "text": code}]},
                {
                    "type": "button",
                    "sub_type": "url",
                    "index": "0",
                    "parameters": [{"type": "text", "text": code}],
                },
            ],
        )

    async def mark_as_read(self, phone_number_id: str, message_id: str) -> None:
        await self._post(
            f"/{phone_number_id}/messages",
            json={"messaging_product": "whatsapp", "status": "read", "message_id": message_id},
        )

    async def upload_media(
        self, phone_number_id: str, content: bytes, mime_type: str, filename: str
    ) -> str:
        body = await self._post(
            f"/{phone_number_id}/media",
            data={"messaging_product": "whatsapp", "type": mime_type},
            files={"file": (filename, content, mime_type)},
        )
        media_id = body.get("id")
        if not isinstance(media_id, str):
            raise WhatsAppError("media upload returned no id")
        return media_id

    async def download_media(self, media_id: str) -> DownloadedMedia:
        metadata = await self._request("GET", f"/{media_id}")
        url = metadata.get("url")
        if not isinstance(url, str):
            raise WhatsAppError("media metadata without url")
        response = await self._http.get(url, headers=self._headers())
        if not response.is_success:
            raise WhatsAppError("media download failed", status_code=response.status_code)
        mime_type = str(metadata.get("mime_type") or response.headers.get("content-type", ""))
        return DownloadedMedia(
            content=response.content, mime_type=mime_type.split(";", maxsplit=1)[0]
        )

    async def _send(self, phone_number_id: str, to: str, message: dict[str, Any]) -> str:
        body = await self._post(
            f"/{phone_number_id}/messages",
            json={"messaging_product": "whatsapp", "recipient_type": "individual", "to": to}
            | message,
        )
        try:
            return str(body["messages"][0]["id"])
        except (KeyError, IndexError, TypeError) as exc:
            raise WhatsAppError("send response without message id") from exc

    async def _post(
        self,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        data: dict[str, str] | None = None,
        files: dict[str, tuple[str, bytes, str]] | None = None,
    ) -> dict[str, Any]:
        return await self._request("POST", path, json=json, data=data, files=files)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        data: dict[str, str] | None = None,
        files: dict[str, tuple[str, bytes, str]] | None = None,
    ) -> dict[str, Any]:
        if not self.configured:
            raise WhatsAppError("WHATSAPP_ACCESS_TOKEN is not configured")
        try:
            response = await self._http.request(
                method,
                f"{self._base_url}{path}",
                headers=self._headers(),
                json=json,
                data=data,
                files=files,
            )
        except httpx.HTTPError as exc:
            raise WhatsAppError(f"graph api unreachable: {exc!r}") from exc
        if not response.is_success:
            logger.warning(
                "whatsapp_api_error",
                extra={"status": response.status_code, "body": response.text[:300]},
            )
            raise WhatsAppError("graph api error", status_code=response.status_code)
        payload = response.json()
        return payload if isinstance(payload, dict) else {}

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}
