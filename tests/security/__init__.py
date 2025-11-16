"""
Security Test Suite for ActiveMirrorOS

This package contains comprehensive security tests that validate
all security fixes and prevent regressions.

Test Coverage:
- Vault salt randomness (prevents rainbow table attacks)
- SQL injection protection (parameterized queries)
- Error information leaks (prevents data exposure)
- Audit log integrity (ensures complete audit trail)

Author: AMOS Dev Twin
"""

__all__ = [
    "test_vault_salt_randomness",
    "test_sql_injection",
    "test_error_information_leaks",
    "test_audit_log_integrity",
]
