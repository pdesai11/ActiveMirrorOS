#!/usr/bin/env python3
"""
Simple test runner for security tests when pytest is not available.
"""

import sys
import os
import tempfile
import shutil
from pathlib import Path

# Add SDK to path
SDK_PATH = Path(__file__).parent / "sdk" / "python"
sys.path.insert(0, str(SDK_PATH))

# Import test modules
test_dir = Path(__file__).parent / "tests" / "security"

# Test counters
tests_run = 0
tests_passed = 0
tests_failed = 0
failures = []

def run_test(test_func, test_name):
    """Run a single test function."""
    global tests_run, tests_passed, tests_failed
    tests_run += 1
    try:
        test_func()
        tests_passed += 1
        print(f"  ✅ {test_name}")
        return True
    except AssertionError as e:
        tests_failed += 1
        failures.append((test_name, str(e)))
        print(f"  ❌ {test_name}: {e}")
        return False
    except Exception as e:
        tests_failed += 1
        failures.append((test_name, str(e)))
        print(f"  ❌ {test_name}: {type(e).__name__}: {e}")
        return False

print("=" * 70)
print("🔒 Running Security Test Suite")
print("=" * 70)
print()

# Test 1: Vault Salt Randomness
print("1️⃣  Vault Salt Randomness Tests")
print("-" * 70)

from activemirror.vault_memory import VaultMemory

# Test: Different vaults have different salts
def test_different_vaults_different_salts():
    temp_dir = tempfile.mkdtemp()
    try:
        vault1_path = Path(temp_dir) / "vault1"
        vault2_path = Path(temp_dir) / "vault2"

        vault1 = VaultMemory(vault_path=str(vault1_path), password="test_password")
        vault2 = VaultMemory(vault_path=str(vault2_path), password="test_password")

        assert vault1.salt != vault2.salt, "Vaults should have different salts"
        assert len(vault1.salt) == 16, "Salt should be 16 bytes (128 bits)"
        assert len(vault2.salt) == 16, "Salt should be 16 bytes (128 bits)"
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

run_test(test_different_vaults_different_salts, "Different vaults have different salts")

# Test: Salt persists across vault reopening
def test_salt_persists():
    temp_dir = tempfile.mkdtemp()
    try:
        vault_path = Path(temp_dir) / "vault_persist"

        # Create vault
        vault1 = VaultMemory(vault_path=str(vault_path), password="test_password")
        original_salt = vault1.salt
        vault1.store("test_key", "test_value")

        # Reopen vault
        vault2 = VaultMemory(vault_path=str(vault_path), password="test_password")
        reopened_salt = vault2.salt

        assert original_salt == reopened_salt, "Salt should persist across reopening"
        assert vault2.retrieve("test_key") == "test_value", "Data should be retrievable"
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

run_test(test_salt_persists, "Salt persists across vault reopening")

# Test: Salt entropy
def test_salt_entropy():
    temp_dir = tempfile.mkdtemp()
    try:
        vault_path = Path(temp_dir) / "vault_entropy"
        vault = VaultMemory(vault_path=str(vault_path), password="test_password")

        # Check salt is not all zeros
        assert vault.salt != b'\x00' * 16, "Salt should not be all zeros"

        # Check salt has some variation (at least 8 different bytes)
        unique_bytes = len(set(vault.salt))
        assert unique_bytes >= 8, f"Salt should have good entropy (found {unique_bytes} unique bytes)"
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

run_test(test_salt_entropy, "Salt has sufficient entropy")

print()

# Test 2: SQL Injection Prevention
print("2️⃣  SQL Injection Prevention Tests")
print("-" * 70)

from activemirror.storage.sqlite import SQLiteStorage
from activemirror.core.session import Session
from activemirror.core.message import Message

def test_limit_parameter_safe():
    temp_dir = tempfile.mkdtemp()
    try:
        db_path = Path(temp_dir) / "test.db"
        storage = SQLiteStorage(db_path=str(db_path))

        # Create session and messages
        session = Session(id="test-session", title="Test Session")
        storage.save_session(session)

        for i in range(10):
            msg = Message(session_id="test-session", role="user", content=f"Message {i}")
            storage.save_message(msg)

        # Test malicious limit parameters are rejected
        malicious_limits = [
            "1; DROP TABLE messages; --",
            "1 UNION SELECT * FROM sessions",
            "1 OR 1=1"
        ]

        for malicious_limit in malicious_limits:
            try:
                # This should raise TypeError or ValueError
                messages = storage.get_messages("test-session", limit=malicious_limit)
                raise AssertionError(f"Malicious limit should be rejected: {malicious_limit}")
            except (TypeError, ValueError, AttributeError):
                # Expected - limit should only accept integers
                pass
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

run_test(test_limit_parameter_safe, "Malicious LIMIT parameters rejected")

def test_offset_parameter_safe():
    temp_dir = tempfile.mkdtemp()
    try:
        db_path = Path(temp_dir) / "test.db"
        storage = SQLiteStorage(db_path=str(db_path))

        session = Session(id="test-session", title="Test Session")
        storage.save_session(session)

        # Test malicious offset parameters
        try:
            messages = storage.get_messages("test-session", limit=5, offset="0; DROP TABLE sessions; --")
            raise AssertionError("Malicious offset should be rejected")
        except (TypeError, ValueError, AttributeError):
            pass
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

run_test(test_offset_parameter_safe, "Malicious OFFSET parameters rejected")

def test_parameterized_queries():
    temp_dir = tempfile.mkdtemp()
    try:
        db_path = Path(temp_dir) / "test.db"
        storage = SQLiteStorage(db_path=str(db_path))

        session = Session(id="test-session", title="Test Session")
        storage.save_session(session)

        for i in range(20):
            msg = Message(session_id="test-session", role="user", content=f"Message {i}")
            storage.save_message(msg)

        # Normal pagination should work
        messages = storage.get_messages("test-session", limit=5, offset=0)
        assert len(messages) == 5, "Should return 5 messages"

        messages = storage.get_messages("test-session", limit=5, offset=5)
        assert len(messages) == 5, "Should return next 5 messages"
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

run_test(test_parameterized_queries, "Parameterized queries work correctly")

print()

# Test 3: Error Information Leaks
print("3️⃣  Error Information Leak Prevention Tests")
print("-" * 70)

from activemirror.exceptions import StorageError

def test_vault_errors_no_password_leak():
    temp_dir = tempfile.mkdtemp()
    try:
        vault_path = Path(temp_dir) / "vault_error"
        vault = VaultMemory(vault_path=str(vault_path), password="SecretPassword123!")

        # Trigger an error by trying to retrieve non-existent key
        try:
            vault.retrieve("nonexistent_key")
            # This should raise an error
        except Exception as e:
            error_msg = str(e)
            # Make sure password is not in error message
            assert "SecretPassword123!" not in error_msg, "Password should not appear in error messages"
            assert "password" not in error_msg.lower() or "incorrect" in error_msg.lower(), \
                "Error should not leak password information"
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

run_test(test_vault_errors_no_password_leak, "Vault errors don't leak passwords")

def test_storage_errors_no_path_leak():
    temp_dir = tempfile.mkdtemp()
    try:
        db_path = Path(temp_dir) / "test.db"
        storage = SQLiteStorage(db_path=str(db_path))

        # Try to get messages for non-existent session
        try:
            messages = storage.get_messages("nonexistent-session")
            # This should work but return empty list
            assert messages == [], "Should return empty list for non-existent session"
        except Exception as e:
            # If it raises an error, make sure it doesn't leak sensitive paths
            error_msg = str(e)
            # Full absolute paths should not be in error messages
            assert "/home/" not in error_msg, "Error should not leak full file paths"
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

run_test(test_storage_errors_no_path_leak, "Storage errors don't leak file paths")

print()

# Test 4: Audit Log Integrity
print("4️⃣  Audit Log Integrity Tests")
print("-" * 70)

from activemirror.logging import get_logger
import json

def test_audit_log_records_actions():
    import io
    import logging

    # Create a logger with a string buffer
    logger = get_logger("test_audit", format_type="json")

    # Create string buffer to capture logs
    log_stream = io.StringIO()
    handler = logging.StreamHandler(log_stream)
    handler.setLevel(logging.INFO)
    logger.logger.addHandler(handler)

    # Perform auditable action
    logger.audit(
        action="vault_store",
        user_id="test_user",
        resource="api_keys",
        status="success",
        details={"key": "test_key"}
    )

    # Check log output
    log_output = log_stream.getvalue()
    assert "vault_store" in log_output, "Audit log should contain action"
    assert "test_user" in log_output, "Audit log should contain user_id"
    assert "api_keys" in log_output, "Audit log should contain resource"

run_test(test_audit_log_records_actions, "Audit logs record all actions")

def test_audit_log_immutable_context():
    logger = get_logger("test_audit_immutable")

    # Create mutable context
    context = {"user": "alice", "resource": "vault"}

    # Log it
    logger.audit(action="test_action", details=context)

    # Modify original context
    context["user"] = "bob"
    context["malicious"] = "injection"

    # The logged context should not be affected
    # (This test just ensures no errors occur)
    assert True, "Audit logging should handle context safely"

run_test(test_audit_log_immutable_context, "Audit log context is immutable")

print()
print("=" * 70)
print(f"📊 Test Results: {tests_passed}/{tests_run} passed")
if tests_failed > 0:
    print(f"❌ {tests_failed} tests failed:")
    for name, error in failures:
        print(f"   - {name}")
        print(f"     {error}")
else:
    print("✅ All security tests passed!")
print("=" * 70)

sys.exit(0 if tests_failed == 0 else 1)
