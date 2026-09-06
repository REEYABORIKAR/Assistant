from refyne.db.base import Base
import refyne.db.models  # noqa: F401


def test_auth_tables_are_declared() -> None:
    expected = {
        "tenants",
        "users",
        "tenant_members",
        "sessions",
        "refresh_tokens",
        "password_reset_tokens",
        "consents",
        "audit_events",
        "projects",
        "conversations",
        "messages",
        "files",
        "requirements",
        "requirement_links",
        "workflow_definitions",
    }

    assert expected.issubset(Base.metadata.tables)


def test_session_and_token_secrets_are_not_plaintext_columns() -> None:
    assert Base.metadata.tables["refresh_tokens"].c.token_hash.type.python_type is bytes
    assert Base.metadata.tables["password_reset_tokens"].c.token_hash.type.python_type is bytes


def test_audit_events_store_structured_metadata() -> None:
    audit_events = Base.metadata.tables["audit_events"]
    assert audit_events.c.metadata.name == "metadata"
    assert audit_events.c.tenant_id.nullable is True
