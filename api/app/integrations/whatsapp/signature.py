import hashlib
import hmac

SIGNATURE_PREFIX = "sha256="


def is_valid_signature(app_secret: str, payload: bytes, header: str | None) -> bool:
    if not app_secret or not header or not header.startswith(SIGNATURE_PREFIX):
        return False
    expected = hmac.new(app_secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header.removeprefix(SIGNATURE_PREFIX))
