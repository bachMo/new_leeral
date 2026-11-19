import base64
import hashlib
import hmac
import secrets

_ALGORITHM = "scrypt"
_N = 2**14
_R = 8
_P = 1
_KEY_LENGTH = 32
_SALT_BYTES = 16
MIN_PASSWORD_LENGTH = 12


def _derive(password: str, salt: bytes, n: int, r: int, p: int) -> bytes:
    return hashlib.scrypt(
        password.encode(), salt=salt, n=n, r=r, p=p, dklen=_KEY_LENGTH, maxmem=64 * 1024 * 1024
    )


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(_SALT_BYTES)
    key = _derive(password, salt, _N, _R, _P)
    return f"{_ALGORITHM}${_N}${_R}${_P}${_b64(salt)}${_b64(key)}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, n, r, p, salt, key = encoded.split("$")
        if algorithm != _ALGORITHM:
            return False
        derived = _derive(password, _unb64(salt), int(n), int(r), int(p))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(derived, _unb64(key))


DUMMY_HASH = hash_password(secrets.token_urlsafe(16))
