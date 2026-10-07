from typing import Annotated

from pydantic import Field, StringConstraints

from app.core.languages import Language
from app.models.enums import Platform
from app.schemas.common import Schema
from app.schemas.users import UserOut

DeviceId = Annotated[str, StringConstraints(strip_whitespace=True, min_length=8, max_length=128)]
PhoneNumber = Annotated[str, StringConstraints(strip_whitespace=True, min_length=6, max_length=20)]
OtpCodeValue = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^\d{4,8}$")]


class DeviceIn(Schema):
    platform: Platform
    device_name: str | None = Field(default=None, max_length=120)
    push_token: str | None = Field(default=None, max_length=300)


class GuestIn(DeviceIn):
    device_id: DeviceId
    language: Language


class OtpRequestIn(Schema):
    phone_number: PhoneNumber


class OtpChallengeOut(Schema):
    phone_number: str
    expires_in: int
    resend_in: int
    code_length: int


class OtpVerifyIn(DeviceIn):
    phone_number: PhoneNumber
    code: OtpCodeValue
    language: Language


class RefreshIn(Schema):
    refresh_token: Annotated[str, StringConstraints(min_length=20, max_length=200)]


class TokenOut(Schema):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    is_new_account: bool = False
    user: UserOut
