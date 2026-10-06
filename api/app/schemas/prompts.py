from app.schemas.common import Schema


class PromptOut(Schema):
    key: str
    text_fr: str
    audio_url: str
