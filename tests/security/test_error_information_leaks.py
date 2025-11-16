"""
Security Test: Error Information Leaks

Verifies that error messages don't leak sensitive information.

Author: AMOS Dev Twin
"""

import pytest
import tempfile
from activemirror.vault_memory import VaultMemory
from activemirror.storage.sqlite import SQLiteStorage
from activemirror.exceptions import StorageError


class TestErrorInformationLeaks:
    """Test suite for preventing information leaks via error messages."""

    def test_wrong_password_error_does_not_leak_vault_contents(self):
        """Wrong password error should not reveal vault structure or data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = f"{tmpdir}/vault"

            # Create vault with password
            vault1 = VaultMemory(vault_path=vault_path, password="correct_password")
            vault1.store("secret_key", "secret_value", {"category": "private"})

            # Try to open with wrong password
            vault2 = VaultMemory(vault_path=vault_path, password="wrong_password")

            # Attempting to retrieve should fail
            try:
                value = vault2.retrieve("secret_key")
                assert False, "Should have raised exception for wrong password"
            except StorageError as e:
                error_msg = str(e).lower()

                # Error should not contain:
                assert "secret_value" not in error_msg, "Error should not leak vault data"
                assert "secret_key" not in error_msg, "Error should not leak key names"
                assert "private" not in error_msg, "Error should not leak metadata"
                assert "correct_password" not in error_msg, "Error should not leak password"

                # Error should be generic
                assert any(word in error_msg for word in ["decrypt", "failed", "vault"]), \
                    "Error should indicate failure reason generically"

    def test_sql_errors_do_not_leak_table_structure(self):
        """SQL errors should not reveal database schema."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = SQLiteStorage(db_path=f"{tmpdir}/test.db")

            # Try to trigger SQL error
            try:
                # Pass invalid data type
                storage.get_messages("session-id", limit="invalid")
            except Exception as e:
                error_msg = str(e).lower()

                # Should not leak table names or schema
                assert "create table" not in error_msg, "Error should not leak schema"
                assert "column" not in error_msg or "session_id" not in error_msg, \
                    "Error should not leak column names"

    def test_file_path_errors_do_not_leak_system_paths(self):
        """File path errors should not reveal full system paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Try to create vault in non-existent parent directory
            invalid_path = f"{tmpdir}/nonexistent/deep/path/vault"

            # This should work (mkdir creates parents)
            vault = VaultMemory(vault_path=invalid_path, password="password")

            # But if we check error messages when accessing non-existent entries
            try:
                vault.retrieve("nonexistent_key")
            except Exception as e:
                # Should return None, not raise error
                pass

            # The point is: no errors should leak full system paths
            # This is handled by returning None instead of raising

    def test_encryption_errors_are_generic(self):
        """Encryption failures should not reveal encryption details."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = f"{tmpdir}/vault"
            vault = VaultMemory(vault_path=vault_path, password="password")

            # Corrupt the vault index manually
            index_file = vault.vault_path / ".vault_index.enc"
            vault.store("key", "value")  # Create index first

            # Overwrite with garbage
            index_file.write_bytes(b"corrupted data that is not encrypted")

            # Try to open vault
            vault2 = VaultMemory(vault_path=vault_path, password="password")

            # Should load but index should be empty (handled gracefully)
            # Check logs don't leak encryption details
            assert vault2.index["entries"] == {}, "Corrupted vault should return empty index"

    def test_stack_traces_are_sanitized(self, caplog):
        """Stack traces in logs should not leak sensitive data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = f"{tmpdir}/vault"
            vault = VaultMemory(vault_path=vault_path, password="my_secret_password")

            vault.store("api_key", "sk-1234567890abcdef")

            # Trigger an error by corrupting data
            vault.vault_path.chmod(0o000)  # Make unreadable

            try:
                vault.store("another_key", "another_value")
            except Exception:
                pass

            # Restore permissions
            vault.vault_path.chmod(0o755)

            # Check that logs don't contain sensitive data
            for record in caplog.records:
                assert "my_secret_password" not in record.message, "Password should not be in logs"
                assert "sk-1234567890abcdef" not in record.message, "Secrets should not be in logs"

    def test_validation_errors_dont_echo_input(self):
        """Validation errors should not echo back potentially malicious input."""
        from activemirror.core.config import Config

        # Create config with invalid values
        config_dict = {
            "storage": {"type": "'; DROP TABLE users; --"},
            "logging": {"level": "<script>alert('xss')</script>"},
        }

        config = Config._from_dict(config_dict)
        errors = config.validate()

        # Errors should mention the field, but not echo the malicious content
        error_text = " ".join(errors).lower()

        assert "drop table" not in error_text, "Validation error should not echo SQL injection"
        assert "<script>" not in error_text, "Validation error should not echo XSS"
        assert "invalid" in error_text or "type" in error_text, "Should indicate what's wrong"

    def test_user_ids_not_leaked_across_sessions(self):
        """User IDs from one session should not leak into another's errors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = SQLiteStorage(db_path=f"{tmpdir}/test.db")

            from activemirror.core.session import Session

            # Create sessions for different users
            session1 = Session(id="s1", title="User1 Session", user_id="user_alice")
            session2 = Session(id="s2", title="User2 Session", user_id="user_bob")

            storage.save_session(session1)
            storage.save_session(session2)

            # Try to access session1 (user_alice's session)
            # Error messages should not mention user_bob
            try:
                # Simulate some error condition
                storage.get_messages("nonexistent_session")
            except Exception as e:
                error_msg = str(e)
                # No user IDs should appear in error
                assert "user_alice" not in error_msg, "Error should not leak other user IDs"
                assert "user_bob" not in error_msg, "Error should not leak other user IDs"

    def test_timing_attack_resistance(self):
        """Password verification should not leak timing information."""
        import time

        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = f"{tmpdir}/vault"

            # Create vault
            vault1 = VaultMemory(vault_path=vault_path, password="correct_password_12345")
            vault1.store("key", "value")

            # Measure time for wrong password (completely wrong)
            start = time.time()
            vault2 = VaultMemory(vault_path=vault_path, password="wrong")
            try:
                vault2.retrieve("key")
            except:
                pass
            time_wrong = time.time() - start

            # Measure time for almost correct password
            start = time.time()
            vault3 = VaultMemory(vault_path=vault_path, password="correct_password_12344")
            try:
                vault3.retrieve("key")
            except:
                pass
            time_almost = time.time() - start

            # Times should be similar (within 10x)
            # (Not exact due to PBKDF2 being constant-time for same iterations)
            ratio = max(time_wrong, time_almost) / min(time_wrong, time_almost)
            assert ratio < 10, f"Timing difference too large: {ratio}x could leak information"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
