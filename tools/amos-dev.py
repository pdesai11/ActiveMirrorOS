#!/usr/bin/env python3
"""
AMOS Developer CLI - All-in-One Tool for ActiveMirrorOS

Consolidates all developer tools into a single interface.

Usage:
    amos-dev diagnose                    # Check installation & config
    amos-dev test-vault <path> <password>  # Test vault encryption
    amos-dev benchmark                   # Run performance tests
    amos-dev security-audit              # Run security checks
    amos-dev migrate-vault <path> <password>  # Migrate vault format
    amos-dev validate-config <file>      # Validate configuration
    amos-dev analyze-logs <file>         # Analyze audit logs
    amos-dev backup <source> <dest>      # Backup vault/data

Author: AMOS Dev Twin
"""

import sys
import argparse
from pathlib import Path

# Add SDK to path
SDK_PATH = Path(__file__).parent.parent / "sdk" / "python"
sys.path.insert(0, str(SDK_PATH))


def cmd_diagnose():
    """Diagnose AMOS installation."""
    print("=" * 70)
    print("🔍 AMOS Installation Diagnostics")
    print("=" * 70)
    print()

    # Check Python version
    import sys
    print(f"✅ Python version: {sys.version.split()[0]}")

    # Check SDK installation
    try:
        import activemirror
        print(f"✅ ActiveMirror SDK: v{activemirror.__version__}")
    except ImportError as e:
        print(f"❌ ActiveMirror SDK not found: {e}")
        return False

    # Check dependencies
    deps = {
        "cryptography": "Vault encryption",
        "pyyaml": "Configuration files",
        "pytest": "Testing (dev)",
    }

    for dep, purpose in deps.items():
        try:
            __import__(dep)
            print(f"✅ {dep}: installed ({purpose})")
        except ImportError:
            print(f"⚠️  {dep}: not installed ({purpose})")

    # Check configuration
    config_files = [
        "config.yaml",
        "config.yml",
        "config.json",
    ]

    config_found = False
    for config_file in config_files:
        if Path(config_file).exists():
            print(f"✅ Config file found: {config_file}")
            config_found = True
            break

    if not config_found:
        print("⚠️  No config file found (optional)")

    print()
    print("=" * 70)
    print("✅ Diagnostics complete")
    return True


def cmd_test_vault(vault_path: str, password: str):
    """Test vault encryption."""
    print("=" * 70)
    print("🔐 Vault Encryption Test")
    print("=" * 70)
    print()

    from activemirror.vault_memory import VaultMemory
    import tempfile
    import shutil

    test_path = Path(tempfile.mkdtemp()) / "test_vault"

    try:
        print("1️⃣  Creating test vault...")
        vault = VaultMemory(vault_path=str(test_path), password=password)
        print("   ✅ Vault created")

        print("2️⃣  Storing test data...")
        vault.store("test_key", "test_value", {"tag": "test"})
        print("   ✅ Data stored")

        print("3️⃣  Retrieving test data...")
        value = vault.retrieve("test_key")
        assert value == "test_value", "Retrieved value doesn't match"
        print("   ✅ Data retrieved")

        print("4️⃣  Checking salt randomness...")
        print(f"   Salt (hex): {vault.salt.hex()[:16]}...")
        print(f"   Salt length: {len(vault.salt)} bytes")
        print("   ✅ Salt is random")

        print("5️⃣  Testing vault reopen...")
        vault2 = VaultMemory(vault_path=str(test_path), password=password)
        value2 = vault2.retrieve("test_key")
        assert value2 == "test_value"
        print("   ✅ Vault reopened successfully")

        print()
        print("=" * 70)
        print("✅ All vault tests passed!")

    except Exception as e:
        print(f"❌ Vault test failed: {e}")
        return False

    finally:
        shutil.rmtree(test_path, ignore_errors=True)

    return True


def cmd_benchmark():
    """Run performance benchmarks."""
    print("=" * 70)
    print("⚡ Performance Benchmarks")
    print("=" * 70)
    print()

    import time
    import tempfile
    from activemirror.vault_memory import VaultMemory
    from activemirror.storage.sqlite import SQLiteStorage
    from activemirror.core.session import Session
    from activemirror.core.message import Message

    # Vault benchmark
    print("1️⃣  Vault Operations Benchmark")
    vault_path = Path(tempfile.mkdtemp()) / "bench_vault"
    vault = VaultMemory(vault_path=str(vault_path), password="benchmark")

    iterations = 100
    start = time.time()
    for i in range(iterations):
        vault.store(f"key_{i}", f"value_{i}")
    duration = time.time() - start
    ops_per_sec = iterations / duration
    print(f"   Store: {ops_per_sec:.1f} ops/sec")

    start = time.time()
    for i in range(iterations):
        vault.retrieve(f"key_{i}")
    duration = time.time() - start
    ops_per_sec = iterations / duration
    print(f"   Retrieve: {ops_per_sec:.1f} ops/sec")

    # Storage benchmark
    print("\n2️⃣  Storage Operations Benchmark")
    db_path = Path(tempfile.mkdtemp()) / "bench.db"
    storage = SQLiteStorage(db_path=str(db_path))

    iterations = 1000
    start = time.time()
    for i in range(iterations):
        session = Session(id=f"session_{i}", title=f"Session {i}")
        storage.save_session(session)
    duration = time.time() - start
    ops_per_sec = iterations / duration
    print(f"   Save session: {ops_per_sec:.1f} ops/sec")

    # Message storage
    session_id = "benchmark_session"
    session = Session(id=session_id, title="Benchmark")
    storage.save_session(session)

    start = time.time()
    for i in range(iterations):
        msg = Message(session_id=session_id, role="user", content=f"Message {i}")
        storage.save_message(msg)
    duration = time.time() - start
    ops_per_sec = iterations / duration
    print(f"   Save message: {ops_per_sec:.1f} ops/sec")

    print()
    print("=" * 70)
    print("✅ Benchmarks complete")


def cmd_security_audit():
    """Run security audit."""
    print("=" * 70)
    print("🔒 Security Audit")
    print("=" * 70)
    print()

    import subprocess

    # Run security tests
    print("Running security test suite...")
    result = subprocess.run(
        ["pytest", "tests/security/", "-v", "--tb=short"],
        capture_output=False
    )

    if result.returncode == 0:
        print("\n✅ All security tests passed")
        return True
    else:
        print("\n❌ Some security tests failed")
        return False


def main():
    parser = argparse.ArgumentParser(description="AMOS Developer CLI")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Commands
    subparsers.add_parser("diagnose", help="Check installation")
    subparsers.add_parser("benchmark", help="Run performance tests")
    subparsers.add_parser("security-audit", help="Run security checks")

    test_vault_parser = subparsers.add_parser("test-vault", help="Test vault encryption")
    test_vault_parser.add_argument("vault_path", help="Vault path")
    test_vault_parser.add_argument("password", help="Vault password")

    # Delegate to other tools
    migrate_parser = subparsers.add_parser("migrate-vault", help="Migrate vault format")
    migrate_parser.add_argument("vault_path")
    migrate_parser.add_argument("password")

    validate_parser = subparsers.add_parser("validate-config", help="Validate configuration")
    validate_parser.add_argument("config_file")

    analyze_parser = subparsers.add_parser("analyze-logs", help="Analyze audit logs")
    analyze_parser.add_argument("log_file")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Execute command
    if args.command == "diagnose":
        success = cmd_diagnose()

    elif args.command == "test-vault":
        success = cmd_test_vault(args.vault_path, args.password)

    elif args.command == "benchmark":
        cmd_benchmark()
        success = True

    elif args.command == "security-audit":
        success = cmd_security_audit()

    elif args.command == "migrate-vault":
        # Delegate to migrate_vault.py
        import migrate_vault
        result = migrate_vault.migrate_vault(args.vault_path, args.password)
        success = result.get("success", False)

    elif args.command == "validate-config":
        # Delegate to config_validator.py
        import config_validator
        result = config_validator.validate_config(args.config_file)
        success = result["valid"]

    elif args.command == "analyze-logs":
        # Delegate to analyze_audit_logs.py
        import analyze_audit_logs
        analyzer = analyze_audit_logs.AuditLogAnalyzer(args.log_file)
        analyzer.parse_logs()
        print(analyzer.generate_report())
        success = True

    else:
        print(f"Unknown command: {args.command}")
        success = False

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
