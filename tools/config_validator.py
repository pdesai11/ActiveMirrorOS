#!/usr/bin/env python3
"""
Configuration Validator & Generator for ActiveMirrorOS

Validates configuration files and generates starter templates.

Usage:
    # Validate existing config
    python tools/config_validator.py validate config.yaml

    # Generate starter config
    python tools/config_validator.py generate --template development
    python tools/config_validator.py generate --template production
    python tools/config_validator.py generate --template testing

Author: AMOS Dev Twin
"""

import sys
import argparse
from pathlib import Path
import yaml
import json


# Configuration templates
TEMPLATES = {
    "development": {
        "storage": {
            "type": "sqlite",
            "db_path": "./data/dev_memories.db",
            "enable_wal": True,
        },
        "memory": {
            "max_context_messages": 50,
            "enable_semantic_memory": True,
            "context_window_size": 4096,
            "context_strategy": "recent_and_relevant",
        },
        "identity": {
            "type": "anonymous",
            "create_if_missing": False,
        },
        "dialogue": {
            "engine": "basic",
            "mode": "conversational",
            "enable_meta_cognition": False,
        },
        "logging": {
            "level": "DEBUG",
            "format": "text",
            "log_file": "./logs/dev.log",
            "enable_console": True,
            "enable_audit": True,
            "enable_performance": True,
        },
        "debug": True,
    },

    "production": {
        "storage": {
            "type": "sqlite",
            "db_path": "/var/lib/activemirror/memories.db",
            "enable_wal": True,
        },
        "memory": {
            "max_context_messages": 100,
            "enable_semantic_memory": True,
            "context_window_size": 8192,
            "context_strategy": "recent_and_relevant",
        },
        "identity": {
            "type": "mirror_dna",
            "identity_file": "/etc/activemirror/identity.json",
            "create_if_missing": False,
        },
        "dialogue": {
            "engine": "lingos",
            "mode": "conversational",
            "enable_meta_cognition": True,
        },
        "logging": {
            "level": "INFO",
            "format": "json",
            "log_file": "/var/log/activemirror/app.log",
            "enable_console": False,
            "enable_audit": True,
            "enable_performance": False,
        },
        "debug": False,
    },

    "testing": {
        "storage": {
            "type": "memory",
        },
        "memory": {
            "max_context_messages": 10,
            "enable_semantic_memory": False,
            "context_window_size": 1024,
            "context_strategy": "recent",
        },
        "identity": {
            "type": "anonymous",
        },
        "dialogue": {
            "engine": "basic",
            "mode": "conversational",
            "enable_meta_cognition": False,
        },
        "logging": {
            "level": "WARNING",
            "format": "text",
            "enable_console": True,
            "enable_audit": False,
            "enable_performance": False,
        },
        "debug": False,
    },
}


# Security warnings
SECURITY_CHECKS = [
    {
        "path": ["debug"],
        "value": True,
        "severity": "warning",
        "message": "Debug mode is enabled - should be disabled in production",
    },
    {
        "path": ["logging", "level"],
        "value": "DEBUG",
        "severity": "warning",
        "message": "DEBUG logging level may impact performance and log sensitive data",
    },
    {
        "path": ["storage", "type"],
        "value": "memory",
        "severity": "warning",
        "message": "Memory storage is not persistent - data will be lost on restart",
    },
    {
        "path": ["logging", "enable_audit"],
        "value": False,
        "severity": "error",
        "message": "Audit logging is disabled - required for compliance and security",
    },
    {
        "path": ["logging", "enable_console"],
        "value": True,
        "severity": "info",
        "message": "Console logging enabled - consider using file logging in production",
    },
]


def get_nested_value(config: dict, path: list):
    """Get value from nested dictionary using path list."""
    value = config
    for key in path:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return None
    return value


def validate_config(config_path: str) -> dict:
    """
    Validate configuration file.

    Returns:
        dict with validation results
    """
    config_file = Path(config_path)

    if not config_file.exists():
        return {
            "valid": False,
            "errors": [f"Configuration file not found: {config_path}"],
            "warnings": [],
            "info": [],
        }

    # Load config
    try:
        with open(config_file) as f:
            if config_file.suffix in (".yaml", ".yml"):
                config = yaml.safe_load(f)
            elif config_file.suffix == ".json":
                config = json.load(f)
            else:
                return {
                    "valid": False,
                    "errors": [f"Unsupported file format: {config_file.suffix}. Use .yaml, .yml, or .json"],
                    "warnings": [],
                    "info": [],
                }
    except Exception as e:
        return {
            "valid": False,
            "errors": [f"Failed to parse config file: {e}"],
            "warnings": [],
            "info": [],
        }

    # Import Config for validation
    sys.path.insert(0, str(Path(__file__).parent.parent / "sdk" / "python"))
    from activemirror.core.config import Config

    # Validate using Config class
    try:
        config_obj = Config._from_dict(config)
        validation_errors = config_obj.validate()
    except Exception as e:
        return {
            "valid": False,
            "errors": [f"Configuration validation failed: {e}"],
            "warnings": [],
            "info": [],
        }

    # Security checks
    warnings = []
    infos = []
    errors = list(validation_errors)  # Start with Config validation errors

    for check in SECURITY_CHECKS:
        value = get_nested_value(config, check["path"])
        if value == check["value"]:
            message = f"{' > '.join(check['path'])}: {check['message']}"

            if check["severity"] == "error":
                errors.append(message)
            elif check["severity"] == "warning":
                warnings.append(message)
            elif check["severity"] == "info":
                infos.append(message)

    # Additional checks
    if config.get("storage", {}).get("type") == "sqlite":
        db_path = config.get("storage", {}).get("db_path")
        if db_path:
            db_file = Path(db_path)
            if not db_file.parent.exists():
                warnings.append(f"Database directory does not exist: {db_file.parent}")

    # Check environment variable completeness
    missing_env_vars = []
    if config.get("logging", {}).get("log_file"):
        log_file = Path(config["logging"]["log_file"])
        if not log_file.parent.exists():
            warnings.append(f"Log directory does not exist: {log_file.parent}")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "info": infos,
    }


def generate_config(template: str, output_path: str, format: str = "yaml") -> bool:
    """
    Generate configuration from template.

    Args:
        template: Template name (development, production, testing)
        output_path: Where to save the config
        format: Output format (yaml or json)

    Returns:
        bool: Success
    """
    if template not in TEMPLATES:
        print(f"❌ Unknown template: {template}")
        print(f"   Available templates: {', '.join(TEMPLATES.keys())}")
        return False

    config = TEMPLATES[template]
    output_file = Path(output_path)

    # Ensure parent directory exists
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Write config
    try:
        with open(output_file, 'w') as f:
            if format == "yaml":
                yaml.dump(config, f, default_flow_style=False, sort_keys=False)
            elif format == "json":
                json.dump(config, f, indent=2)
            else:
                print(f"❌ Unknown format: {format}")
                return False

        print(f"✅ Generated {template} config: {output_file}")
        return True

    except Exception as e:
        print(f"❌ Failed to write config: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="ActiveMirrorOS Configuration Validator & Generator"
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Validate configuration file")
    validate_parser.add_argument("config_file", help="Path to configuration file")

    # Generate command
    generate_parser = subparsers.add_parser("generate", help="Generate configuration from template")
    generate_parser.add_argument(
        "--template",
        "-t",
        choices=["development", "production", "testing"],
        default="development",
        help="Configuration template to use"
    )
    generate_parser.add_argument(
        "--output",
        "-o",
        default="config.yaml",
        help="Output file path"
    )
    generate_parser.add_argument(
        "--format",
        "-f",
        choices=["yaml", "json"],
        default="yaml",
        help="Output format"
    )

    args = parser.parse_args()

    if args.command == "validate":
        print("=" * 60)
        print("🔍 ActiveMirrorOS Configuration Validator")
        print("=" * 60)
        print()

        result = validate_config(args.config_file)

        if result["valid"]:
            print("✅ CONFIGURATION VALID")
        else:
            print("❌ CONFIGURATION INVALID")

        if result["errors"]:
            print(f"\n🚫 Errors ({len(result['errors'])}):")
            for error in result["errors"]:
                print(f"   - {error}")

        if result["warnings"]:
            print(f"\n⚠️  Warnings ({len(result['warnings'])}):")
            for warning in result["warnings"]:
                print(f"   - {warning}")

        if result["info"]:
            print(f"\nℹ️  Info ({len(result['info'])}):")
            for info in result["info"]:
                print(f"   - {info}")

        print()
        print("=" * 60)

        sys.exit(0 if result["valid"] else 1)

    elif args.command == "generate":
        print("=" * 60)
        print("🔧 ActiveMirrorOS Configuration Generator")
        print("=" * 60)
        print()

        success = generate_config(args.template, args.output, args.format)

        if success:
            # Validate generated config
            print("\n📋 Validating generated configuration...")
            result = validate_config(args.output)

            if result["warnings"]:
                print(f"\n⚠️  Warnings in generated config:")
                for warning in result["warnings"]:
                    print(f"   - {warning}")

        print()
        print("=" * 60)

        sys.exit(0 if success else 1)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
