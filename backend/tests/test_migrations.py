from pathlib import Path


def test_initial_auth_migration_exists() -> None:
    migration = Path(__file__).parents[1] / "migrations" / "versions" / "0001_auth_foundation.py"

    assert migration.exists()
    assert "refresh_tokens" in migration.read_text(encoding="utf-8")
    assert "password_reset_tokens" in migration.read_text(encoding="utf-8")
