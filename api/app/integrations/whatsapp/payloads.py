from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class _Model(BaseModel):
    model_config = ConfigDict(extra="ignore")


class Text(_Model):
    body: str = ""


class Media(_Model):
    id: str
    mime_type: str | None = None
    filename: str | None = None
    caption: str | None = None
    voice: bool | None = None


class Reply(_Model):
    id: str
    title: str = ""


class Interactive(_Model):
    type: str
    button_reply: Reply | None = None
    list_reply: Reply | None = None

    @property
    def reply(self) -> Reply | None:
        return self.button_reply or self.list_reply


class Button(_Model):
    payload: str = ""
    text: str = ""


class InboundMessage(_Model):
    sender: str = Field(alias="from")
    id: str
    timestamp: str
    type: str
    text: Text | None = None
    image: Media | None = None
    document: Media | None = None
    audio: Media | None = None
    interactive: Interactive | None = None
    button: Button | None = None
    errors: list[dict[str, Any]] = Field(default_factory=list)

    @property
    def media(self) -> Media | None:
        return self.image or self.document or self.audio

    @property
    def reply_id(self) -> str | None:
        if self.interactive and self.interactive.reply:
            return self.interactive.reply.id
        if self.button:
            return self.button.payload or self.button.text
        return None


class Profile(_Model):
    name: str | None = None


class Contact(_Model):
    wa_id: str
    profile: Profile | None = None


class Metadata(_Model):
    phone_number_id: str
    display_phone_number: str | None = None


class StatusUpdate(_Model):
    id: str
    status: str
    recipient_id: str | None = None
    errors: list[dict[str, Any]] = Field(default_factory=list)


class ChangeValue(_Model):
    metadata: Metadata
    contacts: list[Contact] = Field(default_factory=list)
    messages: list[InboundMessage] = Field(default_factory=list)
    statuses: list[StatusUpdate] = Field(default_factory=list)

    def contact_name(self, wa_id: str) -> str | None:
        for contact in self.contacts:
            if contact.wa_id == wa_id and contact.profile:
                return contact.profile.name
        return None


class Change(_Model):
    field: str
    value: ChangeValue


class Entry(_Model):
    id: str
    changes: list[Change] = Field(default_factory=list)


class WebhookPayload(_Model):
    object: str
    entry: list[Entry] = Field(default_factory=list)
