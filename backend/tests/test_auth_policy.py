import pytest
from pydantic import ValidationError

from refyne.auth.policy import RegistrationRequest


def valid_registration(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "name": "Ada Lovelace",
        "email": "ada@example.com",
        "password": "SecurePassword1!",
        "confirm_password": "SecurePassword1!",
        "terms_accepted": True,
        "privacy_accepted": True,
    }
    values.update(overrides)
    return values


def test_registration_accepts_configured_password_policy() -> None:
    request = RegistrationRequest.model_validate(valid_registration())

    request.validate_consents_and_confirmation()
    assert request.email == "ada@example.com"


@pytest.mark.parametrize(
    "password",
    ["short1!", "alllowercase123!", "ALLUPPERCASE123!", "NoNumberHere!!", "NoSymbol12345"],
)
def test_registration_rejects_invalid_passwords(password: str) -> None:
    with pytest.raises(ValidationError):
        RegistrationRequest.model_validate(valid_registration(password=password, confirm_password=password))


def test_registration_requires_both_consents() -> None:
    request = RegistrationRequest.model_validate(valid_registration(privacy_accepted=False))

    with pytest.raises(ValueError, match="consent"):
        request.validate_consents_and_confirmation()


def test_registration_requires_matching_password_confirmation() -> None:
    request = RegistrationRequest.model_validate(valid_registration(confirm_password="DifferentPassword1!"))

    with pytest.raises(ValueError, match="confirmation"):
        request.validate_consents_and_confirmation()
