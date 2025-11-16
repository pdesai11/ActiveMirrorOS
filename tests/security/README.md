# Security Test Suite

Comprehensive security testing for ActiveMirrorOS that validates all security fixes and prevents regressions.

## Test Coverage

### 1. Vault Salt Randomness (`test_vault_salt_randomness.py`)

**What it tests:**
- Each vault generates a unique random salt
- Salts are not predictable or sequential
- Salts are persisted and loaded correctly
- High entropy in salt generation

**Why it matters:**
- Prevents rainbow table attacks
- Ensures PBKDF2 produces unique keys per vault
- Validates the security fix for fixed-salt vulnerability

**Tests included:** 8 tests

---

### 2. SQL Injection Protection (`test_sql_injection.py`)

**What it tests:**
- LIMIT parameter SQL injection prevention
- OFFSET parameter SQL injection prevention
- Session ID parameter safety
- No string formatting in SQL queries
- Parameterized queries used throughout
- DROP TABLE prevention
- UNION injection prevention
- Boolean injection prevention

**Why it matters:**
- Prevents data loss from DROP statements
- Prevents unauthorized data access
- Validates parameterized query implementation

**Tests included:** 8 tests

---

### 3. Error Information Leaks (`test_error_information_leaks.py`)

**What it tests:**
- Wrong password errors don't leak vault contents
- SQL errors don't leak schema
- File path errors don't leak system paths
- Encryption errors are generic
- Stack traces don't contain sensitive data
- Validation errors don't echo malicious input
- User IDs not leaked across sessions
- Timing attack resistance

**Why it matters:**
- Prevents information disclosure
- Protects against reconnaissance attacks
- Validates error handling security

**Tests included:** 8 tests

---

### 4. Audit Log Integrity (`test_audit_log_integrity.py`)

**What it tests:**
- All vault operations are logged
- Failed operations are logged
- Audit logs have immutable context
- Timestamps are accurate
- Audit logging cannot be bypassed
- User ID tracking in audit
- Logs are parseable (JSON format)
- Sequential audit trail
- Operation status included
- Sensitive operations logged

**Why it matters:**
- Ensures compliance with audit requirements
- Enables forensic analysis
- Validates logging infrastructure

**Tests included:** 10 tests

---

## Running the Tests

### Run All Security Tests

```bash
pytest tests/security/ -v
```

### Run Specific Test Suite

```bash
# Vault salt randomness
pytest tests/security/test_vault_salt_randomness.py -v

# SQL injection protection
pytest tests/security/test_sql_injection.py -v

# Error information leaks
pytest tests/security/test_error_information_leaks.py -v

# Audit log integrity
pytest tests/security/test_audit_log_integrity.py -v
```

### Run with Coverage

```bash
pytest tests/security/ --cov=activemirror --cov-report=html
```

### Run in CI/CD

```bash
# Fail fast on first error
pytest tests/security/ -x

# Generate JSON report
pytest tests/security/ --json-report --json-report-file=security-results.json
```

---

## Test Statistics

| Test Suite | Tests | Coverage Area |
|------------|-------|---------------|
| Vault Salt Randomness | 8 | Encryption Security |
| SQL Injection Protection | 8 | Database Security |
| Error Information Leaks | 8 | Information Disclosure |
| Audit Log Integrity | 10 | Compliance & Forensics |
| **TOTAL** | **34** | **All Security Domains** |

---

## Security Testing Best Practices

### When to Run

1. **Before every commit** - Quick smoke test
2. **Before every PR** - Full suite
3. **After dependency updates** - Regression check
4. **Scheduled (daily)** - Continuous validation

### Adding New Tests

When adding security features, add corresponding tests:

```python
# tests/security/test_new_feature.py

import pytest
from activemirror.new_feature import NewFeature

class TestNewFeatureSecurity:
    """Security tests for new feature."""

    def test_feature_prevents_attack(self):
        """Describe the attack being prevented."""
        # Arrange: Set up attack scenario
        # Act: Attempt attack
        # Assert: Verify attack is blocked
        pass
```

### Test Naming Convention

- `test_<feature>_<security_property>`
- Examples:
  - `test_vault_salt_is_random`
  - `test_sql_injection_prevention`
  - `test_password_not_leaked_in_logs`

---

## Common Attack Vectors Tested

### ✅ Cryptographic Attacks
- Rainbow table attacks (via fixed salts)
- Weak key derivation
- Timing attacks

### ✅ Injection Attacks
- SQL injection (LIMIT, OFFSET, WHERE clauses)
- NoSQL injection (if applicable)
- Command injection (file paths)

### ✅ Information Disclosure
- Error message leakage
- Stack trace exposure
- Log file exposure
- Timing information

### ✅ Authentication/Authorization
- Password bypass attempts
- Privilege escalation
- Session hijacking

### ✅ Audit/Compliance
- Incomplete audit trails
- Log tampering
- Missing timestamps

---

## Integration with CI/CD

### GitHub Actions Example

```yaml
name: Security Tests

on: [push, pull_request]

jobs:
  security:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v2
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.10'

    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install pytest pytest-cov

    - name: Run security tests
      run: |
        pytest tests/security/ -v --cov=activemirror

    - name: Fail on coverage <80%
      run: |
        pytest tests/security/ --cov=activemirror --cov-fail-under=80
```

---

## Security Test Maintenance

### Regular Updates

- **Monthly**: Review for new attack vectors
- **After incidents**: Add regression tests
- **New features**: Add corresponding security tests

### Deprecation

Mark tests as `@pytest.mark.skip` with reason:

```python
@pytest.mark.skip(reason="Feature removed in v2.0")
def test_old_feature():
    pass
```

---

## Reporting Security Issues

If tests reveal new vulnerabilities:

1. **Do NOT** commit the test publicly
2. Report to security team privately
3. Add test only after fix is deployed
4. Document in CHANGELOG_AMOS.md

---

## Author

**AMOS Dev Twin**
Session: `claude/harden-amos-app-layer-01BTZvuHvTic4KMXdSVQZXnQ`

## License

MIT License - Same as ActiveMirrorOS

---

**Last Updated:** 2025-11-16
