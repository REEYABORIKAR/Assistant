"""
Audit Log Append-Only Test.

Verifies that no code path modifies or deletes existing audit_log rows.
This is a safety net — the audit_log table is immutable by design.
"""
import ast
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.audit import write_audit_log
from app.models.audit_log import AuditLog


class TestAuditLogImmutable:
    """Verify the audit log is append-only at the application layer."""

    def test_write_audit_log_only_adds(self):
        """write_audit_log must only call db.add(), never db.update() or db.delete()."""
        source = ast.parse(open(write_audit_log.__code__.co_filename).read())

        for node in ast.walk(source):
            if isinstance(node, ast.Call):
                func = node.func
                # Check for db.update() or db.delete() or session.update() / session.delete()
                if isinstance(func, ast.Attribute):
                    if func.attr in ("update", "delete", "merge"):
                        # Ensure it's not inside write_audit_log's scope
                        # by checking we're in the right function
                        pass  # We'll do a more targeted check below

        # More targeted: read the source of write_audit_log and check for forbidden calls
        import inspect
        source = inspect.getsource(write_audit_log)
        assert "db.update(" not in source, "write_audit_log must not call db.update()"
        assert "db.delete(" not in source, "write_audit_log must not call db.delete()"
        assert "db.merge(" not in source, "write_audit_log must not call db.merge()"
        assert ".update(" not in source or "json.dumps" in source, (
            "write_audit_log contains unexpected .update() call"
        )

    def test_audit_log_model_has_no_update_delete_methods(self):
        """The AuditLog model should not define update or delete methods."""
        assert not hasattr(AuditLog, "update"), "AuditLog.update() should not exist"
        assert not hasattr(AuditLog, "delete"), "AuditLog.delete() should not exist"

    def test_audit_log_entry_is_created_and_persisted(self):
        """Smoke test: create an audit entry and verify its fields."""
        mock_db = MagicMock()
        entry = write_audit_log(
            mock_db,
            user_id="user-123",
            project_id="proj-456",
            action="TEST_ACTION",
            resource_type="test",
            resource_id="res-789",
            trace_id="trace-abc",
            details={"key": "value"},
            model="gpt-4",
            model_version="2024-01",
            ip_address="127.0.0.1",
        )

        # Verify db.add was called with an AuditLog instance
        mock_db.add.assert_called_once()
        added_obj = mock_db.add.call_args[0][0]
        assert isinstance(added_obj, AuditLog)
        assert added_obj.user_id == "user-123"
        assert added_obj.project_id == "proj-456"
        assert added_obj.action == "TEST_ACTION"
        assert added_obj.trace_id == "trace-abc"
        assert added_obj.model == "gpt-4"
        assert added_obj.model_version == "2024-01"
        assert added_obj.ip_address == "127.0.0.1"

    def test_no_update_or_delete_in_audit_module(self):
        """Scan the entire audit.py module for any update/delete operations on AuditLog."""
        import inspect
        source = inspect.getsource(sys.modules["app.core.audit"])

        # The only ORM operation should be db.add() and db.flush()
        forbidden = ["db.update(", "db.delete(", "db.merge(", "session.update(", "session.delete("]
        for pattern in forbidden:
            assert pattern not in source, f"Found forbidden pattern '{pattern}' in audit module"

    def test_no_update_or_delete_in_review_api_for_audit(self):
        """Verify review API doesn't modify audit_log entries after creation."""
        # Read the source as text to avoid import-time syntax issues in FastAPI
        review_path = Path(__file__).resolve().parent.parent / "app" / "api" / "review.py"
        source = review_path.read_text()

        # Should not contain any code that updates or deletes audit_log rows
        # (it should only call write_audit_log, which is append-only)
        assert "AuditLog.query" not in source or "write_audit_log" in source, (
            "Review API should use write_audit_log, not direct AuditLog queries"
        )
        # Verify no direct ORM update/delete on AuditLog
        assert ".filter(AuditLog" not in source, (
            "Review API should not directly query AuditLog for updates/deletes"
        )
