"""
Security Test: SQL Injection Protection

Verifies that SQL injection attempts are blocked by parameterized queries.

Author: AMOS Dev Twin
"""

import pytest
import tempfile
from activemirror.storage.sqlite import SQLiteStorage
from activemirror.core.session import Session
from activemirror.core.message import Message


class TestSQLInjectionProtection:
    """Test suite for SQL injection protection."""

    def test_limit_parameter_sql_injection(self):
        """LIMIT parameter should not allow SQL injection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = SQLiteStorage(db_path=f"{tmpdir}/test.db")

            # Create a session
            session = Session(id="test-session", title="Test")
            storage.save_session(session)

            # Add some messages
            for i in range(5):
                msg = Message(
                    session_id="test-session",
                    role="user",
                    content=f"Message {i}"
                )
                storage.save_message(msg)

            # Malicious limit values (SQL injection attempts)
            malicious_limits = [
                "1; DROP TABLE messages; --",
                "1 UNION SELECT * FROM sessions",
                "1 OR 1=1",
                "1; DELETE FROM messages WHERE 1=1; --",
                "1/**/UNION/**/SELECT/**/*",
            ]

            for malicious_limit in malicious_limits:
                # Should raise TypeError or ValueError, not execute injection
                with pytest.raises((TypeError, ValueError, AttributeError)):
                    storage.get_messages("test-session", limit=malicious_limit)

                # Verify messages table still exists and has data
                messages = storage.get_messages("test-session")
                assert len(messages) == 5, f"Messages should not be deleted by injection attempt: {malicious_limit}"

    def test_offset_parameter_sql_injection(self):
        """OFFSET parameter should not allow SQL injection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = SQLiteStorage(db_path=f"{tmpdir}/test.db")

            session = Session(id="test-session", title="Test")
            storage.save_session(session)

            for i in range(5):
                msg = Message(
                    session_id="test-session",
                    role="user",
                    content=f"Message {i}"
                )
                storage.save_message(msg)

            # Malicious offset values
            malicious_offsets = [
                "0; DROP TABLE sessions; --",
                "0 UNION SELECT * FROM messages",
                "0 OR 1=1",
            ]

            for malicious_offset in malicious_offsets:
                with pytest.raises((TypeError, ValueError, AttributeError)):
                    storage.get_messages("test-session", limit=2, offset=malicious_offset)

                # Verify data integrity
                messages = storage.get_messages("test-session")
                assert len(messages) == 5

    def test_session_id_parameter_sql_injection(self):
        """Session ID parameter should be safe from SQL injection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = SQLiteStorage(db_path=f"{tmpdir}/test.db")

            # Create legitimate session
            session = Session(id="legitimate-session", title="Legitimate")
            storage.save_session(session)

            msg = Message(
                session_id="legitimate-session",
                role="user",
                content="Test message"
            )
            storage.save_message(msg)

            # Try SQL injection via session_id
            malicious_ids = [
                "' OR '1'='1",
                "'; DROP TABLE messages; --",
                "\" OR \"1\"=\"1",
                "1' UNION SELECT * FROM sqlite_master WHERE '1'='1",
            ]

            for malicious_id in malicious_ids:
                # Should return empty list (no match) or raise error, not execute injection
                try:
                    messages = storage.get_messages(malicious_id)
                    assert len(messages) == 0, "Should not return messages for malicious session ID"
                except Exception:
                    # Some databases might raise errors for invalid IDs, that's fine
                    pass

                # Verify legitimate data still exists
                legit_messages = storage.get_messages("legitimate-session")
                assert len(legit_messages) == 1, "Legitimate messages should not be affected"

    def test_no_string_formatting_in_queries(self):
        """Verify no f-strings or .format() in SQL queries."""
        import inspect
        from activemirror.storage import sqlite

        # Get source code of SQLiteStorage
        source = inspect.getsource(sqlite.SQLiteStorage)

        # Check for dangerous patterns
        dangerous_patterns = [
            'f".*LIMIT',  # f-string with LIMIT
            'f".*OFFSET',  # f-string with OFFSET
            'f".*WHERE',  # f-string with WHERE
            '".format(.*LIMIT',  # .format() with LIMIT
            '".format(.*OFFSET',  # .format() with OFFSET
        ]

        import re
        for pattern in dangerous_patterns:
            matches = re.findall(pattern, source, re.IGNORECASE)
            assert not matches, f"Found dangerous SQL pattern: {pattern} in {matches}"

    def test_parameterized_queries_used(self):
        """Verify that all queries use parameterized placeholders (?)."""
        import inspect
        from activemirror.storage import sqlite

        source = inspect.getsource(sqlite.SQLiteStorage)

        # Find all execute() calls
        execute_pattern = r'execute\([^)]+\)'
        executes = re.findall(execute_pattern, source)

        # Each execute should have either:
        # 1. A query with ? placeholders followed by parameters
        # 2. Or be a simple DDL query with no parameters
        for execute_call in executes:
            # If it contains LIMIT or WHERE, it should use ?
            if 'LIMIT' in execute_call or 'WHERE' in execute_call:
                assert '?' in execute_call or 'params' in execute_call, \
                    f"Query with LIMIT/WHERE should use parameterized queries: {execute_call}"

    def test_table_drop_prevention(self):
        """Verify that malicious DROP TABLE attempts are blocked."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = SQLiteStorage(db_path=f"{tmpdir}/test.db")

            session = Session(id="test", title="Test")
            storage.save_session(session)

            # Try various DROP TABLE injections
            drop_attempts = [
                "'; DROP TABLE sessions; --",
                "\"; DROP TABLE messages; --",
                "1; DROP TABLE sessions; DROP TABLE messages; --",
            ]

            for drop_attempt in drop_attempts:
                # Try to inject via various parameters
                try:
                    storage.get_messages(drop_attempt)
                except Exception:
                    pass

                try:
                    storage.get_messages("test", limit=drop_attempt)
                except Exception:
                    pass

                # Verify tables still exist by querying them
                sessions = storage.list_sessions()
                assert sessions is not None, "Sessions table should still exist"

                messages = storage.get_messages("test")
                assert messages is not None, "Messages table should still exist"

    def test_union_injection_prevention(self):
        """Verify UNION-based SQL injection is prevented."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = SQLiteStorage(db_path=f"{tmpdir}/test.db")

            # Create test data
            session = Session(id="session1", title="Session 1")
            storage.save_session(session)

            msg = Message(
                session_id="session1",
                role="user",
                content="Secret data"
            )
            storage.save_message(msg)

            # UNION injection attempts
            union_attempts = [
                "session1' UNION SELECT * FROM sessions WHERE '1'='1",
                "session1\" UNION SELECT id, password, secret FROM users WHERE \"1\"=\"1",
                "1' UNION SELECT sqlite_version(), 1, 1, 1, 1, 1 --",
            ]

            for union_attempt in union_attempts:
                messages = storage.get_messages(union_attempt)

                # Should return 0 messages (no match for malformed ID)
                # Should NOT return data from other tables
                assert len(messages) == 0, f"UNION injection should not work: {union_attempt}"

    def test_boolean_injection_prevention(self):
        """Verify boolean-based SQL injection is prevented."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = SQLiteStorage(db_path=f"{tmpdir}/test.db")

            # Create specific sessions
            session1 = Session(id="authorized", title="Authorized Session")
            session2 = Session(id="unauthorized", title="Unauthorized Session")
            storage.save_session(session1)
            storage.save_session(session2)

            # Add message only to authorized session
            msg = Message(
                session_id="authorized",
                role="user",
                content="Secret message"
            )
            storage.save_message(msg)

            # Boolean injection attempts (try to get all messages)
            boolean_attempts = [
                "' OR '1'='1",
                "' OR 1=1 --",
                "\" OR \"\"=\"",
                "' OR 'x'='x",
            ]

            for boolean_attempt in boolean_attempts:
                messages = storage.get_messages(boolean_attempt)

                # Should return 0 messages (no match)
                # Should NOT return all messages
                assert len(messages) == 0, f"Boolean injection should not bypass auth: {boolean_attempt}"

                # Verify we can still get authorized messages
                auth_messages = storage.get_messages("authorized")
                assert len(auth_messages) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
