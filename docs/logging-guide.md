# Logging Best Practices Guide

Comprehensive guide for using ActiveMirrorOS logging infrastructure effectively.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Log Levels](#log-levels)
3. [Structured Logging](#structured-logging)
4. [Audit Trails](#audit-trails)
5. [Performance Logging](#performance-logging)
6. [Security Logging](#security-logging)
7. [Configuration](#configuration)
8. [Best Practices](#best-practices)
9. [Privacy & Compliance](#privacy--compliance)
10. [Troubleshooting](#troubleshooting)

---

## Quick Start

### Python

```python
from activemirror.logging import get_logger

# Get a logger for your module
logger = get_logger("my_module")

# Basic logging
logger.info("Application started")
logger.debug("Processing request", context={"user_id": "user123"})
logger.error("Failed to connect", context={"host": "db.example.com"}, exc_info=True)

# Audit logging
logger.audit(
    action="user_login",
    user_id="alice",
    resource="session_123",
    status="success"
)

# Performance logging
logger.performance(
    operation="database_query",
    duration_ms=45.2,
    context={"query_type": "SELECT"}
)

# Security logging
logger.security(
    event="failed_authentication",
    severity="warning",
    context={"ip": "192.168.1.1", "attempts": 3}
)
```

### JavaScript

```javascript
import { getLogger } from 'activemirror';

const logger = getLogger('my_module');

// Basic logging
logger.info('Application started');
logger.debug('Processing request', { userId: 'user123' });
logger.error('Failed to connect', { host: 'db.example.com' }, error);

// Audit logging
logger.audit({
  action: 'user_login',
  userId: 'alice',
  resource: 'session_123',
  status: 'success'
});

// Performance logging
logger.performance('database_query', 45.2, { queryType: 'SELECT' });

// Security logging
logger.security({
  event: 'failed_authentication',
  severity: 'warning',
  context: { ip: '192.168.1.1', attempts: 3 }
});
```

---

## Log Levels

### When to Use Each Level

| Level | When to Use | Examples |
|-------|-------------|----------|
| **DEBUG** | Development debugging, verbose details | Variable values, function entry/exit |
| **INFO** | Normal operations, significant events | Application started, config loaded |
| **WARNING** | Potential issues, degraded service | Slow query, retry attempt, deprecated API |
| **ERROR** | Failures that don't crash the app | Failed API call, validation error |
| **CRITICAL** | Severe failures requiring immediate attention | Database unavailable, out of memory |

### Examples

```python
# DEBUG - Development details
logger.debug("Cache hit", context={"key": "user:123", "ttl": 300})

# INFO - Normal operations
logger.info("User session created", context={"session_id": "abc123"})

# WARNING - Potential issues
logger.warning("API rate limit approaching", context={"usage": "90%"})

# ERROR - Recoverable failures
logger.error("Failed to send email", context={"recipient": "user@example.com"}, exc_info=True)

# CRITICAL - System-wide failures
logger.critical("Database connection pool exhausted", context={"active": 100, "max": 100})
```

---

## Structured Logging

### Why Structured Logging?

- **Searchable**: Query logs by specific fields
- **Parseable**: Machine-readable for analysis
- **Contextual**: Rich metadata for debugging

### Adding Context

**Always** include context for better debugging:

```python
# ❌ BAD - Unstructured
logger.info("User logged in")

# ✅ GOOD - Structured
logger.info("User logged in", context={
    "user_id": "alice",
    "ip": "192.168.1.1",
    "session_id": "abc123",
    "login_method": "password"
})
```

### Context Best Practices

```python
context = {
    # IDs - for correlation
    "user_id": "alice",
    "session_id": "session_123",
    "request_id": "req_xyz",

    # Metadata - for analysis
    "action": "create_resource",
    "resource_type": "vault_entry",
    "resource_id": "entry_456",

    # Performance - for optimization
    "duration_ms": 45.2,
    "cache_hit": True,

    # Environment - for context
    "environment": "production",
    "version": "0.2.0",
}

logger.info("Resource created", context=context)
```

---

## Audit Trails

### What to Audit

**Always audit:**
- Authentication/authorization events
- Data access (create, read, update, delete)
- Configuration changes
- Administrative actions

**Example:**

```python
# Vault access
logger.audit(
    action="vault_store",
    user_id="alice",
    resource="api_keys",
    status="success",
    details={"metadata": {"category": "credentials"}}
)

# Configuration change
logger.audit(
    action="config_updated",
    user_id="admin",
    resource="logging.level",
    status="success",
    details={"old_value": "INFO", "new_value": "DEBUG"}
)

# Failed access attempt
logger.audit(
    action="vault_retrieve",
    user_id="bob",
    resource="api_keys",
    status="failure",
    details={"error": "permission_denied"}
)
```

### Audit Log Requirements

1. **Timestamp**: Accurate, timezone-aware
2. **Actor**: Who performed the action
3. **Action**: What was done
4. **Resource**: What was affected
5. **Status**: Success or failure
6. **Details**: Additional context

---

## Performance Logging

### When to Log Performance

- Database queries
- External API calls
- File I/O operations
- Encryption/decryption
- Any operation >100ms

### Using Performance Logging

```python
import time

# Manual timing
start = time.time()
result = expensive_operation()
duration_ms = (time.time() - start) * 1000

logger.performance(
    operation="expensive_operation",
    duration_ms=duration_ms,
    context={"items_processed": len(result)}
)

# Using decorator
from activemirror.resilience import profile_performance

@profile_performance
def database_query(user_id):
    # Automatically logged with timing
    return db.query(user_id)

# Using context manager
from activemirror.resilience import PerformanceContext

with PerformanceContext("vault_encryption"):
    vault.store("key", "value")
# Automatically logged
```

### Performance Thresholds

Set thresholds to only log slow operations:

```python
@profile_performance(log_threshold_ms=100)
def potentially_slow_operation():
    # Only logged if takes >100ms
    pass
```

---

## Security Logging

### Security Events to Log

- Failed authentication attempts
- Authorization failures
- Unusual access patterns
- Configuration changes
- Vault creation/access
- Encryption key operations

### Security Logging Examples

```python
# Failed login
logger.security(
    event="failed_login",
    severity="warning",
    context={
        "username": "alice",
        "ip": "192.168.1.1",
        "attempts": 3,
        "lockout_triggered": False
    }
)

# Unusual access pattern
logger.security(
    event="unusual_vault_access",
    severity="info",
    context={
        "user_id": "bob",
        "vault_accesses": 50,
        "time_window": "1 minute",
        "avg_accesses": 5
    }
)

# Vault created with random salt
logger.security(
    event="vault_created_with_random_salt",
    severity="info",
    context={"vault_path": "./my_vault"}
)
```

---

## Configuration

### Environment Variables

```bash
export ACTIVEMIRROR_LOG_LEVEL=INFO
export ACTIVEMIRROR_LOG_FORMAT=json
export ACTIVEMIRROR_LOG_FILE=/var/log/amos.log
```

### Configuration File (YAML)

```yaml
logging:
  level: INFO
  format: json
  log_file: /var/log/activemirror/app.log
  enable_console: false
  enable_audit: true
  enable_performance: true
```

### Programmatic Configuration

```python
from activemirror.logging import configure_logging

configure_logging(
    level="INFO",
    format="json",
    log_file="/var/log/amos.log",
    enable_console=False
)
```

### Log Formats

**Text (Development)**:
```
2025-01-16 10:30:45 - activemirror.vault - INFO - Vault created
```

**JSON (Production)**:
```json
{
  "timestamp": "2025-01-16T10:30:45.123Z",
  "level": "INFO",
  "logger": "activemirror.vault",
  "message": "Vault created",
  "context": {"vault_path": "./vault"}
}
```

**Structured (Hybrid)**:
```
2025-01-16 10:30:45 | INFO     | activemirror.vault | Vault created | {"vault_path": "./vault"}
```

---

## Best Practices

### ✅ DO

1. **Use appropriate log levels**
   ```python
   logger.debug("User preferences loaded")  # Not logger.info()
   ```

2. **Include context**
   ```python
   logger.error("Payment failed", context={"order_id": "123", "amount": 99.99})
   ```

3. **Log exceptions with stack traces**
   ```python
   logger.error("Database error", exc_info=True)
   ```

4. **Use structured data**
   ```python
   logger.info("Order placed", context={"order": {...}})
   ```

5. **Log at boundaries** (entry/exit of major functions)
   ```python
   logger.info("Processing order", context={"order_id": "123"})
   # ... process ...
   logger.info("Order processed", context={"order_id": "123", "status": "success"})
   ```

### ❌ DON'T

1. **Don't log sensitive data**
   ```python
   logger.info(f"Password: {password}")  # ❌ NEVER
   ```

2. **Don't log in tight loops**
   ```python
   for item in million_items:
       logger.debug(f"Processing {item}")  # ❌ Too verbose
   ```

3. **Don't use string concatenation**
   ```python
   logger.info("User " + user_id + " logged in")  # ❌ Use context
   ```

4. **Don't ignore exceptions**
   ```python
   try:
       risky_operation()
   except:
       pass  # ❌ At least log it!
   ```

5. **Don't log what you don't need**
   ```python
   logger.debug("Entering function")  # ❌ Unless debugging
   ```

---

## Privacy & Compliance

### What NOT to Log

**Never log:**
- Passwords (plaintext or hashed)
- Encryption keys
- API tokens/secrets
- Credit card numbers
- Social security numbers
- Personal health information

### Sanitize Before Logging

```python
def sanitize_user_data(data):
    """Remove sensitive fields."""
    return {
        k: v for k, v in data.items()
        if k not in ("password", "ssn", "credit_card")
    }

logger.info("User data", context=sanitize_user_data(user))
```

### GDPR Compliance

- **Right to erasure**: Implement log rotation and deletion
- **Data minimization**: Only log necessary data
- **Purpose limitation**: Use logs only for stated purposes
- **Anonymization**: Hash user IDs if possible

---

## Troubleshooting

### Logs Not Appearing

1. **Check log level**
   ```python
   # DEBUG logs won't appear if level is INFO
   configure_logging(level="DEBUG")
   ```

2. **Check file permissions**
   ```bash
   ls -la /var/log/activemirror/
   ```

3. **Check log file path**
   ```python
   logger = get_logger("test")
   logger.info("Test message")  # Should appear in console
   ```

### Performance Impact

**If logging is too slow:**

1. **Use async logging** (file I/O is slow)
2. **Reduce log level** in production
3. **Disable performance logging** if not needed
4. **Use log sampling** (log 1 in 100 requests)

### Log Analysis

**Use the audit log analyzer:**

```bash
python tools/analyze_audit_logs.py analyze logs/app.log
python tools/analyze_audit_logs.py report logs/app.log --format html
```

---

## Examples

### Complete Application Example

```python
from activemirror import ActiveMirror, get_logger, configure_logging

# Configure logging
configure_logging(
    level="INFO",
    format="json",
    log_file="./logs/app.log"
)

logger = get_logger("app")

# Application start
logger.info("Application starting", context={"version": "0.2.0"})

# Create mirror
mirror = ActiveMirror(storage_type="sqlite", db_path="./data/memories.db")
logger.info("ActiveMirror initialized", context={"storage": "sqlite"})

# Create session
session = mirror.create_session(title="My Session")
logger.audit(
    action="session_created",
    resource=session.id,
    status="success"
)

# Send message (with performance tracking)
from activemirror.resilience import PerformanceContext

with PerformanceContext("send_message"):
    session.send("Hello, AMOS!")

logger.info("Message sent", context={"session_id": session.id})
```

---

**Author**: AMOS Dev Twin
**Version**: 1.0
**Last Updated**: 2025-11-16
