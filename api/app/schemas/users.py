import uuid
from datetime import datetime
from typing import Annotated

from pydantic import StringConstraints

from app.core.languages import Language
from app.models.enums import PlanCode
from app.schemas.common import Schema

FirstName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]


class UserOut(Schema):
    id: uuid.UUID
    first_name: str | None
    phone_number: str | None
    language: Language
    is_guest: bool
    has_completed_profile: bool
    registered_at: datetime | None


class ProfileIn(Schema):
    first_name: FirstName | None = None
    language: Language | None = None
    accept_terms: bool | None = None


class UsageOut(Schema):
    writings_used: int
    writings_limit: int
    practice_used: int
    practice_limit: int | None


class PlanStatusOut(Schema):
    code: PlanCode
    expires_at: datetime | None
    document_words: bool


class MeOut(Schema):
    user: UserOut
    plan: PlanStatusOut
    usage: UsageOut


class LanguageOut(Schema):
    code: Language
    name: str
    available: bool
