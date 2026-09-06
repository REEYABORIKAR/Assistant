from refyne.auth.credentials import generate_token, hash_password, hash_token, verify_password


def test_password_hash_is_not_plaintext_and_verifies() -> None:
    password = "SecurePassword1!"
    encoded = hash_password(password)

    assert password not in encoded
    assert verify_password(password, encoded)
    assert not verify_password("WrongPassword1!", encoded)


def test_password_hashes_use_unique_salts() -> None:
    password = "SecurePassword1!"

    assert hash_password(password) != hash_password(password)


def test_malformed_password_hash_fails_closed() -> None:
    assert not verify_password("SecurePassword1!", "not-a-password-hash")


def test_tokens_are_random_and_only_hashes_are_persistable() -> None:
    first = generate_token()
    second = generate_token()

    assert first != second
    assert hash_token(first) != hash_token(second)
    assert len(hash_token(first)) == 32
