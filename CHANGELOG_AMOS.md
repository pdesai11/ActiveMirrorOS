# CHANGELOG_AMOS.md

This changelog documents all changes made to the ActiveMirrorOS development fork.
All modifications are designed to be merge-compatible with the canonical repository.

---

## 2025-11-16 - Structured Logging Infrastructure

**Author**: AMOS Dev Twin
**Session**: `claude/harden-amos-app-layer-01BTZvuHvTic4KMXdSVQZXnQ`

### Summary
Implemented comprehensive structured logging infrastructure across Python and JavaScript SDKs to enable production debugging, security auditing, and operational visibility.

### Files Modified

#### New Files Created
- `/sdk/python/activemirror/logging.py` - Python logging infrastructure (339 lines)
  - `AMOSLogger` class with support for multiple log levels and formats
  - `JSONFormatter` for structured JSON logging
  - `get_logger()` and `configure_logging()` helper functions
  - Audit trail support via `.audit()` method
  - Performance metrics logging via `.performance()` method
  - Security event logging via `.security()` method

- `/sdk/javascript/logger.js` - JavaScript logging infrastructure (346 lines)
  - `AMOSLogger` class matching Python functionality
  - Support for JSON, text, and structured log formats
  - File and console output handlers
  - Audit, performance, and security logging methods
  - `getLogger()` and `configureLogging()` helper functions

#### Modified Files

**Python SDK:**
- `/sdk/python/activemirror/core/config.py`
  - Added `LoggingConfig` dataclass (lines 52-61)
  - Updated `Config` class to include `logging: LoggingConfig` field
  - Updated `from_env()`, `_from_dict()`, `validate()`, and `to_dict()` methods
  - Added validation for log level and format
  - **Logging config fields**: level, format, log_file, enable_console, enable_audit, enable_performance

- `/sdk/python/activemirror/vault_memory.py`
  - Added import: `from activemirror.logging import get_logger`
  - Initialized logger in `__init__()`: `self.logger = get_logger("vault_memory")`
  - Replaced `print()` with `logger.error()` and proper exception raising
  - Added audit trail logging for all vault operations (store, retrieve, delete)
  - **Breaking Change**: Now raises `StorageError` instead of returning False/None on errors

- `/sdk/python/activemirror/__init__.py`
  - Added exports for `LoggingConfig` and all config classes
  - Added exports for `AMOSLogger`, `get_logger`, `configure_logging`, `LogLevel`, `LogFormat`
  - Updated `__all__` list to include logging components

**JavaScript SDK:**
- `/sdk/javascript/vault.js`
  - Added import: `import { getLogger } from './logger.js';`
  - Initialized logger in constructor: `this.logger = getLogger('vault_memory');`
  - Replaced `console.error()` with `logger.error()` and proper exception throwing
  - Added audit trail logging for all vault operations (store, retrieve, delete)
  - **Breaking Change**: Now throws Error instead of returning false/null on errors

- `/sdk/javascript/index.js`
  - Added exports for logger: `AMOSLogger`, `getLogger`, `configureLogging`, `LogLevel`, `LogFormat`

### What Changed and Why

**Problem**:
- No logging infrastructure across the entire codebase
- Production failures were invisible and impossible to diagnose
- No audit trail for compliance or security monitoring
- Vault operations silently swallowed errors with `print()` or `console.error()`

**Solution**:
- Created unified logging infrastructure for Python and JavaScript SDKs
- Supports multiple log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- Supports multiple output formats (JSON, text, structured)
- Added specialized logging methods for audit trails, performance metrics, and security events
- Integrated logging into vault operations with audit trails
- Changed error handling to raise exceptions instead of silent failures

**Benefits**:
1. **Production Visibility**: Can now diagnose failures in deployed systems
2. **Audit Compliance**: Complete audit trail of all vault operations
3. **Performance Monitoring**: Can track operation durations and identify bottlenecks
4. **Security Monitoring**: Can detect and log security-relevant events
5. **Debugging**: Configurable log levels for development vs. production
6. **Structured Data**: JSON format enables log aggregation and analysis

### Configuration

Users can configure logging via:

**Environment Variables:**
```bash
export ACTIVEMIRROR_LOGGING_LEVEL=DEBUG
export ACTIVEMIRROR_LOGGING_FORMAT=json
export ACTIVEMIRROR_LOGGING_LOG_FILE=/var/log/amos.log
```

**Configuration File (YAML):**
```yaml
logging:
  level: INFO
  format: text
  log_file: /var/log/amos.log
  enable_console: true
  enable_audit: true
  enable_performance: false
```

**Programmatic (Python):**
```python
from activemirror import configure_logging, get_logger

configure_logging(level="DEBUG", format="json", log_file="amos.log")
logger = get_logger("my_module")
logger.info("Application started")
logger.audit(action="user_login", user_id="alice", status="success")
```

**Programmatic (JavaScript):**
```javascript
import { configureLogging, getLogger } from 'activemirror';

configureLogging({ level: 'DEBUG', format: 'json', logFile: 'amos.log' });
const logger = getLogger('my_module');
logger.info('Application started');
logger.audit({ action: 'user_login', userId: 'alice', status: 'success' });
```

### Breaking Changes

⚠️ **Vault Error Handling**:
- **Python**: `VaultMemory.store()`, `.retrieve()`, and `.delete()` now raise `StorageError` on failures instead of returning `False` or `None`
- **JavaScript**: `VaultMemory.store()`, `.retrieve()`, and `.delete()` now throw `Error` on failures instead of returning `false` or `null`

**Migration Guide**:

Old code (Python):
```python
success = vault.store("key", "value")
if not success:
    print("Failed to store")
```

New code (Python):
```python
try:
    vault.store("key", "value")
except StorageError as e:
    logger.error(f"Failed to store: {e}")
```

Old code (JavaScript):
```javascript
const success = await vault.store("key", "value");
if (!success) {
    console.error("Failed to store");
}
```

New code (JavaScript):
```javascript
try {
    await vault.store("key", "value");
} catch (error) {
    logger.error("Failed to store", null, error);
}
```

### Testing Notes

- Existing tests may fail due to breaking changes in vault error handling
- Tests should be updated to expect exceptions instead of False/None return values
- New tests should be added for logging functionality

### Merge-Back Notes

**Compatibility**:
- All changes are additive except for vault error handling
- New `LoggingConfig` integrates cleanly with existing `Config` system
- No changes to database schema or file formats
- Environment variable prefix `ACTIVEMIRROR_` maintained for consistency

**Merge Strategy**:
1. Review vault error handling breaking changes with team
2. Consider gradual migration path (deprecation warnings)
3. Ensure tests are updated in canonical repo
4. Update documentation to reflect new logging capabilities
5. Consider whether to make logging opt-in or opt-out initially

**Files to Review Carefully**:
- `vault_memory.py` and `vault.js` - error handling changes
- `config.py` - new LoggingConfig dataclass
- Tests that depend on vault returning False/None

### Next Steps

Recommended follow-up tasks:
1. Add logging to other SDK components (Session, ActiveMirror, storage backends)
2. Create logging best practices documentation
3. Add integration tests for logging functionality
4. Add performance benchmarks to measure logging overhead
5. Consider adding log rotation and size limits for file handlers

---

## 2025-11-16 - Security Fix: Random Salt for Vault Encryption

**Author**: AMOS Dev Twin
**Session**: `claude/harden-amos-app-layer-01BTZvuHvTic4KMXdSVQZXnQ`

### Summary
Fixed critical security vulnerability where all vaults used the same fixed salt for PBKDF2 key derivation. Each vault now generates and stores a unique random salt, significantly improving encryption security.

### Files Modified

**Python SDK:**
- `/sdk/python/activemirror/vault_memory.py`
  - Added `import os` for random salt generation
  - Added `_extract_salt()` method to retrieve salt from existing vaults
  - Modified `__init__()` to generate random 128-bit salt for new vaults
  - Modified `_derive_key()` to require salt parameter (no default)
  - Modified `_load_index()` to skip salt prefix when decrypting
  - Modified `_save_index()` to prepend salt to encrypted data
  - Added security event logging for vault creation with random salt

**JavaScript SDK:**
- `/sdk/javascript/vault.js`
  - Modified constructor to defer key derivation until initialization
  - Added `_extractSalt()` async method to retrieve salt from existing vaults
  - Modified `initialize()` to generate random 128-bit salt for new vaults
  - Modified `_deriveKey()` to require salt parameter (no default)
  - Modified `_loadIndex()` to skip salt prefix when decrypting
  - Modified `_saveIndex()` to prepend salt to encrypted data
  - Added security event logging for vault creation with random salt

### What Changed and Why

**Problem**:
- Both Python and JavaScript vaults used a hardcoded salt: `b'activemirror_vault'` (Python) and `'activemirror_vault'` (JavaScript)
- This meant all vaults in the world used the same salt
- Attackers could precompute rainbow tables for common passwords
- Code comments acknowledged this: "In production, use random salt" but didn't implement it

**Solution**:
- Generate a unique random 128-bit (16-byte) salt for each vault
- Store the salt as prefix to the encrypted index file: `[salt (16 bytes)][encrypted data]`
- Extract salt when opening existing vaults
- Use extracted salt for key derivation

**Security Impact**:
- ✅ Each vault now has unique encryption parameters
- ✅ Rainbow table attacks are no longer feasible
- ✅ Password cracking difficulty increased significantly
- ✅ Meets cryptographic best practices for PBKDF2

### Storage Format Change

**Old Format** (index file):
```
[encrypted JSON data]
```

**New Format** (index file):
```
[salt (16 bytes)][encrypted JSON data]
```

**Backward Compatibility**:
- ⚠️ **BREAKING**: Old vaults encrypted with the fixed salt cannot be opened with new code
- Existing vaults will appear empty or fail to decrypt
- Users must migrate vaults manually or keep old code version

**Migration Path**:
1. Old vault with password "mypass" used salt `b'activemirror_vault'`
2. User must:
   - Export vault data with old code
   - Create new vault with new code (gets random salt)
   - Import data into new vault
3. Alternatively, keep a copy of old VaultMemory class for migration script

### Testing Notes

**Important**:
- All existing vault test fixtures are now invalid
- Tests that create vaults with passwords will get random salts
- Vault files are not portable between test runs (different salts)
- For deterministic testing, provide `encryption_key` instead of `password`

**Test Update Required**:
```python
# Old test (will fail - no longer deterministic)
vault1 = VaultMemory(vault_path="test1", password="test")
vault2 = VaultMemory(vault_path="test2", password="test")
# These vaults now have DIFFERENT encryption keys (different salts)

# New test (deterministic)
key = Fernet.generate_key().decode()
vault1 = VaultMemory(vault_path="test1", encryption_key=key)
vault2 = VaultMemory(vault_path="test2", encryption_key=key)
# These vaults have the same encryption key
```

### Configuration

No configuration required - random salt generation is automatic.

**New Vault Creation**:
```python
# Python - creates vault with random salt
vault = VaultMemory(vault_path="./my_vault", password="my_password")
# Salt is generated automatically and stored in vault index
```

```javascript
// JavaScript - creates vault with random salt
const vault = new VaultMemory({ vaultPath: './my_vault', password: 'my_password' });
await vault.initialize();
// Salt is generated automatically and stored in vault index
```

**Opening Existing Vault**:
```python
# Python - salt is extracted from vault index
vault = VaultMemory(vault_path="./my_vault", password="my_password")
# Salt is loaded from index file automatically
```

```javascript
// JavaScript - salt is extracted from vault index
const vault = new VaultMemory({ vaultPath: './my_vault', password: 'my_password' });
await vault.initialize();
// Salt is loaded from index file automatically
```

### Merge-Back Notes

**Compatibility**:
- ⚠️ **BREAKING CHANGE**: Existing vaults cannot be opened
- Consider providing migration tool or backward-compatibility mode
- Could detect old format (no salt prefix) and prompt for migration

**Merge Strategy**:
1. **Option A - Hard Break** (recommended for pre-1.0 project):
   - Merge as-is with clear upgrade notes
   - Provide migration guide in documentation
   - Accept that vaults must be recreated

2. **Option B - Backward Compatibility**:
   - Detect old format (try decrypting without salt extraction)
   - If successful, prompt user to migrate
   - Auto-migrate on first write

3. **Option C - Versioned Format**:
   - Add version byte to vault index
   - Version 1: no salt prefix (old format)
   - Version 2: salt prefix (new format)
   - Support reading both, write only v2

**Recommended Approach**: Option A for dev/preview release, Option B or C for production release.

### Security Audit Recommendations

1. **Verify salt randomness**: Ensure `os.urandom()` and `crypto.randomBytes()` use cryptographically secure RNG
2. **Salt storage security**: Index file contains salt in plaintext, which is acceptable (salt is not secret)
3. **Key derivation parameters**: Current 100,000 iterations is adequate; consider increasing to 200,000+ for future
4. **Salt length**: 128 bits (16 bytes) is adequate; 256 bits would be more future-proof
5. **Fernet limitations**: Consider migrating to AES-256-GCM with explicit nonce management for more control

### Next Steps

Recommended follow-up tasks:
1. Write migration tool for existing vaults
2. Add vault format version detection
3. Update all vault-related tests
4. Document vault security model
5. Consider adding salt to individual vault entries (currently only index has salt)
6. Increase PBKDF2 iteration count to 200,000+

---

**End of Entry**
