"""Password hashing and random session token digests."""
import hashlib

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from .errors import ApiError

COOKIE_NAME = "tl_session"
MIN_PASSWORD_LEN = 8
_hasher = PasswordHasher()
# verifying against this keeps the response time of "no such user" equal to "wrong password"
_DUMMY_HASH = _hasher.hash("timelog-dummy-password")


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
