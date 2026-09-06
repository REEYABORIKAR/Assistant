import base64
import hashlib
import hmac
import secrets


_SCHEME = "scrypt"
_SALT_BYTES = 16
_KEY_BYTES = 32
_COST = 2**14
_BLOCK_SIZE = 8
_PARALLELISM = 1


def hash_password(password: str) -> str:
    if not password:
        raise ValueError("password must not be empty")
    salt = secrets.token_bytes(_SALT_BYTES)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_COST,
        r=_BLOCK_SIZE,
        p=_PARALLELISM,
        dklen=_KEY_BYTES,
    )
    encode = base64.urlsafe_b64encode
    return (
        f"{_SCHEME}${_COST}${_BLOCK_SIZE}${_PARALLELISM}$"
        f"{encode(salt).decode('ascii')}${encode(digest).decode('ascii')}"
    )


def verify_password(password: str, encoded_hash: str) -> bool:
    try:
        scheme, cost, block_size, parallelism, encoded_salt, encoded_digest = encoded_hash.split("$")
        if scheme != _SCHEME:
            return False
        salt = base64.urlsafe_b64decode(encoded_salt.encode("ascii"))
        expected = base64.urlsafe_b64decode(encoded_digest.encode("ascii"))
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=int(cost),
            r=int(block_size),
            p=int(parallelism),
            dklen=len(expected),
        )
    except (TypeError, ValueError, UnicodeDecodeError):
        return False
    return hmac.compare_digest(actual, expected)


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> bytes:
    if not token:
        raise ValueError("token must not be empty")
    return hashlib.sha256(token.encode("utf-8")).digest()
