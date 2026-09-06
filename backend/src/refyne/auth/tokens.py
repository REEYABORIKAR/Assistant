import base64
import hashlib
import hmac
import json
import time
from typing import Any


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_access_token(subject: str, session_id: str, secret: str, expires_in: int) -> str:
    if not secret:
        raise ValueError("AUTH_SIGNING_SECRET must be configured")
    payload = {"sub": subject, "sid": session_id, "exp": int(time.time()) + expires_in}
    encoded = _encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = _encode(hmac.new(secret.encode("utf-8"), encoded.encode("ascii"), hashlib.sha256).digest())
    return f"{encoded}.{signature}"


def decode_access_token(token: str, secret: str) -> dict[str, Any]:
    try:
        encoded, supplied_signature = token.split(".", 1)
        expected_signature = _encode(
            hmac.new(secret.encode("utf-8"), encoded.encode("ascii"), hashlib.sha256).digest()
        )
        if not hmac.compare_digest(supplied_signature, expected_signature):
            raise ValueError("invalid token signature")
        payload = json.loads(_decode(encoded))
        if not isinstance(payload, dict) or int(payload["exp"]) <= int(time.time()):
            raise ValueError("expired token")
        return payload
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("invalid access token") from exc
