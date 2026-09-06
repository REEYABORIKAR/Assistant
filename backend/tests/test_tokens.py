import pytest

from refyne.auth.tokens import create_access_token, decode_access_token


def test_access_token_round_trip() -> None:
    token = create_access_token("user", "session", "test-secret", 60)

    assert decode_access_token(token, "test-secret")["sub"] == "user"


def test_access_token_rejects_wrong_secret() -> None:
    token = create_access_token("user", "session", "test-secret", 60)

    with pytest.raises(ValueError, match="invalid access token"):
        decode_access_token(token, "wrong-secret")
