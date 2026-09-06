from enum import Enum

from pydantic import BaseModel, EmailStr, field_validator


class ConsentKind(Enum):
    TERMS_OF_SERVICE = "TERMS_OF_SERVICE"
    PRIVACY_POLICY = "PRIVACY_POLICY"


class RegistrationRequest(BaseModel):
    name: str
    email: EmailStr
    password: str
    confirm_password: str
    terms_accepted: bool
    privacy_accepted: bool

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("name is required")
        if len(normalized) > 200:
            raise ValueError("name must be 200 characters or fewer")
        return normalized

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if len(value) < 12:
            raise ValueError("password must be at least 12 characters")
        if not any(character.isupper() for character in value):
            raise ValueError("password must contain an uppercase letter")
        if not any(character.islower() for character in value):
            raise ValueError("password must contain a lowercase letter")
        if not any(character.isdigit() for character in value):
            raise ValueError("password must contain a number")
        if not any(not character.isalnum() for character in value):
            raise ValueError("password must contain a symbol")
        return value

    @field_validator("confirm_password")
    @classmethod
    def validate_confirmation(cls, value: str) -> str:
        return value

    def validate_consents_and_confirmation(self) -> None:
        if self.password != self.confirm_password:
            raise ValueError("password confirmation does not match")
        if not self.terms_accepted or not self.privacy_accepted:
            raise ValueError("terms of service and privacy policy consent are required")

