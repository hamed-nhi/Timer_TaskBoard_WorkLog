"""Password hashing and random session token digests."""
import hashlib
import secrets
import string

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from .errors import ApiError

COOKIE_NAME = "tl_session"
MIN_PASSWORD_LEN = 8
_hasher = PasswordHasher()
# verifying against this keeps the response time of "no such user" equal to "wrong password"
_DUMMY_HASH = _hasher.hash("timelog-dummy-password")


def validate_password(password: str):
    if not isinstance(password, str) or not 8 <= len(password) <= 1024 or not all([
            any(c in string.ascii_uppercase for c in password), any(c in string.ascii_lowercase for c in password),
            any(c in string.digits for c in password), any(c in string.punctuation for c in password)]):
        raise ApiError("رمز باید حداقل ۸ کاراکتر و شامل حرف بزرگ، حرف کوچک، عدد و نماد باشد")


def generate_password(length=16):
    groups = [string.ascii_uppercase, string.ascii_lowercase, string.digits, "!@#$%^&*"]
    chars = [secrets.choice(group) for group in groups]
    chars += [secrets.choice("".join(groups)) for _ in range(max(8, length) - 4)]
    secrets.SystemRandom().shuffle(chars)
    return "".join(chars)


def hash_password(password: str) -> str:
    if len(password) < MIN_PASSWORD_LEN:
        raise ApiError(f"رمز باید حداقل {MIN_PASSWORD_LEN} کاراکتر باشد")
    return _hasher.hash(password)


def verify_password(stored_hash: str | None, password: str) -> bool:
    try:
        return _hasher.verify(stored_hash or _DUMMY_HASH, password) and stored_hash is not None
    except (VerifyMismatchError, InvalidHashError):
        return False


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
