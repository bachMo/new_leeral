import uuid

from app.core.languages import Language
from app.integrations.storage import owner_prefix
from app.models import User


def _suffix() -> str:
    return uuid.uuid4().hex[:10]


def document_file(user: User, document_id: uuid.UUID, position: int, extension: str) -> str:
    prefix = owner_prefix(user.id, is_guest=user.is_guest)
    return f"{prefix}/documents/{document_id}/files/{position:02d}.{extension}"


def document_audio(user: User, document_id: uuid.UUID, name: str) -> str:
    prefix = owner_prefix(user.id, is_guest=user.is_guest)
    return f"{prefix}/documents/{document_id}/audio/{name}-{_suffix()}.mp3"


def document_image_extract(user: User, document_id: uuid.UUID, name: str) -> str:
    prefix = owner_prefix(user.id, is_guest=user.is_guest)
    return f"{prefix}/documents/{document_id}/extracts/{name}-{_suffix()}.jpg"


def message_media(user: User, conversation_id: uuid.UUID, extension: str) -> str:
    prefix = owner_prefix(user.id, is_guest=user.is_guest)
    return f"{prefix}/conversations/{conversation_id}/{_suffix()}.{extension}"


def writing_file(user: User, writing_id: uuid.UUID, name: str, extension: str) -> str:
    prefix = owner_prefix(user.id, is_guest=user.is_guest)
    return f"{prefix}/writings/{writing_id}/{name}-{_suffix()}.{extension}"


def word_audio(word_id: uuid.UUID, language: Language) -> str:
    return f"shared/words/{word_id}/{language.value}-{_suffix()}.mp3"


def prompt_audio(key: str, language: Language) -> str:
    return f"shared/prompts/{language.value}/{key}-{_suffix()}.mp3"
