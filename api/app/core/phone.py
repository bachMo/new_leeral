import re

import phonenumbers

from app.core.errors import AppError, ErrorCode

_NOT_DIALABLE = re.compile(r"[^\d+]")
_LOCAL_NUMBER_LENGTH = 9


def normalize_phone_number(raw: str, default_region: str) -> str:
    candidate = _NOT_DIALABLE.sub("", raw)
    if candidate.startswith("00"):
        candidate = f"+{candidate[2:]}"
    elif candidate and not candidate.startswith("+") and len(candidate) > _LOCAL_NUMBER_LENGTH:
        candidate = f"+{candidate}"
    try:
        parsed = phonenumbers.parse(candidate, default_region)
    except phonenumbers.NumberParseException as exc:
        raise AppError(ErrorCode.INVALID_PHONE_NUMBER) from exc
    if not phonenumbers.is_valid_number(parsed):
        raise AppError(ErrorCode.INVALID_PHONE_NUMBER)
    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)


def to_whatsapp_id(e164_number: str) -> str:
    return e164_number.removeprefix("+")
