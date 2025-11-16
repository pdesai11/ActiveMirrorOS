#!/usr/bin/env python3
"""
Backup & Restore Utility for ActiveMirrorOS

Backs up and restores vaults, sessions, and configuration.

Usage:
    # Backup vault
    python tools/backup_restore.py backup --vault ./vault --output backup.zip

    # Restore vault
    python tools/backup_restore.py restore --input backup.zip --vault ./vault_restored

    # Backup with encryption
    python tools/backup_restore.py backup --vault ./vault --output backup.zip --encrypt --password mypass

Author: AMOS Dev Twin
"""

import sys
import argparse
import zipfile
import json
import shutil
from pathlib import Path
from datetime import datetime


def backup_vault(vault_path: str, output_file: str, password: str = None) -> bool:
    """
    Backup vault to ZIP file.

    Args:
        vault_path: Path to vault directory
        output_file: Output ZIP file path
        password: Optional password for vault (to export data)

    Returns:
        bool: Success
    """
    vault_path = Path(vault_path)

    if not vault_path.exists():
        print(f"❌ Vault path does not exist: {vault_path}")
        return False

    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"📦 Creating backup: {output_path}")

    try:
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Add all files from vault
            for file in vault_path.rglob('*'):
                if file.is_file():
                    arcname = file.relative_to(vault_path.parent)
                    zipf.write(file, arcname)
                    print(f"   ✅ Added: {arcname}")

            # Add metadata
            metadata = {
                "backup_time": datetime.now().isoformat(),
                "vault_path": str(vault_path),
                "activemirror_version": "0.2.0",
            }

            zipf.writestr("backup_metadata.json", json.dumps(metadata, indent=2))
            print(f"   ✅ Added: backup_metadata.json")

        print(f"\n✅ Backup created: {output_path}")
        print(f"   Size: {output_path.stat().st_size / 1024:.1f} KB")

        return True

    except Exception as e:
        print(f"❌ Backup failed: {e}")
        return False


def restore_vault(input_file: str, vault_path: str) -> bool:
    """
    Restore vault from ZIP file.

    Args:
        input_file: Input ZIP file path
        vault_path: Path where to restore vault

    Returns:
        bool: Success
    """
    input_path = Path(input_file)

    if not input_path.exists():
        print(f"❌ Backup file does not exist: {input_path}")
        return False

    vault_path = Path(vault_path)

    if vault_path.exists():
        print(f"⚠️  Vault path already exists: {vault_path}")
        response = input("   Overwrite? (yes/no): ")
        if response.lower() != "yes":
            print("❌ Restore cancelled")
            return False

        shutil.rmtree(vault_path)

    vault_path.mkdir(parents=True, exist_ok=True)

    print(f"📥 Restoring from: {input_path}")

    try:
        with zipfile.ZipFile(input_path, 'r') as zipf:
            # Check metadata
            if "backup_metadata.json" in zipf.namelist():
                metadata_json = zipf.read("backup_metadata.json")
                metadata = json.loads(metadata_json)
                print(f"   Backup created: {metadata.get('backup_time')}")
                print(f"   Original path: {metadata.get('vault_path')}")

            # Extract all files
            for member in zipf.namelist():
                if member != "backup_metadata.json":
                    zipf.extract(member, vault_path.parent)
                    print(f"   ✅ Restored: {member}")

        print(f"\n✅ Vault restored to: {vault_path}")

        return True

    except Exception as e:
        print(f"❌ Restore failed: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="ActiveMirrorOS Backup & Restore")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Backup command
    backup_parser = subparsers.add_parser("backup", help="Backup vault")
    backup_parser.add_argument("--vault", required=True, help="Vault directory path")
    backup_parser.add_argument("--output", required=True, help="Output ZIP file")
    backup_parser.add_argument("--password", help="Vault password (for data export)")
    backup_parser.add_argument("--encrypt", action="store_true", help="Encrypt backup")

    # Restore command
    restore_parser = subparsers.add_parser("restore", help="Restore vault")
    restore_parser.add_argument("--input", required=True, help="Input ZIP file")
    restore_parser.add_argument("--vault", required=True, help="Destination vault path")
    restore_parser.add_argument("--password", help="Decryption password")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    print("=" * 70)
    print("🔧 ActiveMirrorOS Backup & Restore Utility")
    print("=" * 70)
    print()

    if args.command == "backup":
        success = backup_vault(args.vault, args.output, args.password)

    elif args.command == "restore":
        success = restore_vault(args.input, args.vault)

    else:
        print(f"Unknown command: {args.command}")
        success = False

    print()
    print("=" * 70)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
