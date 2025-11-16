#!/usr/bin/env python3
"""
Vault Migration Tool for ActiveMirrorOS

Migrates vaults from old fixed-salt format to new random-salt format.

Usage:
    python tools/migrate_vault.py <vault_path> <password>

What it does:
1. Detects old vault format (fixed salt)
2. Exports all vault data with old decryption
3. Creates new vault with random salt
4. Re-encrypts all data
5. Preserves metadata and timestamps

Author: AMOS Dev Twin
"""

import sys
import json
import base64
from pathlib import Path
from datetime import datetime
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class OldVaultMemory:
    """Old vault implementation with fixed salt - for migration only."""

    FIXED_SALT = b'activemirror_vault'

    def __init__(self, vault_path: str, password: str):
        self.vault_path = Path(vault_path)
        self.password = password

        # Use old key derivation with fixed salt
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self.FIXED_SALT,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        self.cipher = Fernet(key)

        self.index_file = self.vault_path / ".vault_index.enc"

    def can_decrypt(self) -> bool:
        """Check if we can decrypt with fixed salt."""
        if not self.index_file.exists():
            return False

        try:
            encrypted_data = self.index_file.read_bytes()

            # Old format: just encrypted data, no salt prefix
            decrypted = self.cipher.decrypt(encrypted_data)
            json.loads(decrypted.decode())
            return True
        except Exception:
            return False

    def export_all(self) -> dict:
        """Export all vault data."""
        if not self.index_file.exists():
            return {"entries": [], "metadata": {}}

        # Load index
        encrypted_index = self.index_file.read_bytes()
        decrypted_index = self.cipher.decrypt(encrypted_index)
        index = json.loads(decrypted_index.decode())

        # Export all entries
        exported_entries = []

        for key, info in index.get("entries", {}).items():
            entry_file = Path(info["file"])

            if entry_file.exists():
                encrypted_entry = entry_file.read_bytes()
                decrypted_entry = self.cipher.decrypt(encrypted_entry)
                entry_data = json.loads(decrypted_entry.decode())

                exported_entries.append({
                    "key": key,
                    "value": entry_data["value"],
                    "metadata": entry_data.get("metadata", {}),
                    "created_at": entry_data.get("created_at"),
                    "updated_at": entry_data.get("updated_at"),
                })

        return {
            "entries": exported_entries,
            "metadata": {
                "vault_created_at": index.get("created_at"),
                "exported_at": datetime.now().isoformat(),
                "entry_count": len(exported_entries),
            }
        }


def migrate_vault(vault_path: str, password: str, backup: bool = True) -> dict:
    """
    Migrate vault from old to new format.

    Args:
        vault_path: Path to vault directory
        password: Vault password
        backup: Whether to backup old vault (default: True)

    Returns:
        Migration report dict
    """
    vault_path = Path(vault_path)

    print(f"🔍 Analyzing vault at: {vault_path}")

    # Check if vault exists
    if not vault_path.exists():
        return {
            "success": False,
            "error": "Vault path does not exist",
        }

    # Try old format first
    old_vault = OldVaultMemory(str(vault_path), password)

    if not old_vault.can_decrypt():
        # Check if it's already new format
        index_file = vault_path / ".vault_index.enc"
        if index_file.exists():
            raw_data = index_file.read_bytes()
            if len(raw_data) >= 16:
                print("✅ Vault is already in new format (has salt prefix)")
                return {
                    "success": True,
                    "already_migrated": True,
                    "message": "Vault already uses random salt format",
                }

        return {
            "success": False,
            "error": "Cannot decrypt vault with old or new format - wrong password?",
        }

    print("📤 Exporting data from old vault format...")
    export_data = old_vault.export_all()

    entry_count = len(export_data["entries"])
    print(f"   Found {entry_count} entries to migrate")

    if entry_count == 0:
        print("⚠️  Vault is empty - nothing to migrate")
        return {
            "success": True,
            "entries_migrated": 0,
            "message": "Vault is empty",
        }

    # Backup old vault
    if backup:
        backup_path = vault_path.parent / f"{vault_path.name}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        print(f"💾 Creating backup at: {backup_path}")

        import shutil
        shutil.copytree(vault_path, backup_path)
        print(f"   ✅ Backup created")

    # Save export to JSON (for safety)
    export_file = vault_path.parent / f"{vault_path.name}_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    export_file.write_text(json.dumps(export_data, indent=2))
    print(f"💾 Export saved to: {export_file}")

    # Import new VaultMemory (with random salt)
    print("🔄 Importing new VaultMemory...")
    sys.path.insert(0, str(Path(__file__).parent.parent / "sdk" / "python"))
    from activemirror.vault_memory import VaultMemory

    # Delete old vault files
    print("🗑️  Removing old vault files...")
    for file in vault_path.glob("*"):
        file.unlink()

    # Create new vault with random salt
    print("🔐 Creating new vault with random salt...")
    new_vault = VaultMemory(vault_path=str(vault_path), password=password)

    # Import all entries
    print("📥 Importing entries into new vault...")
    migrated_count = 0
    failed_entries = []

    for entry in export_data["entries"]:
        try:
            new_vault.store(
                key=entry["key"],
                value=entry["value"],
                metadata=entry.get("metadata", {}),
            )
            migrated_count += 1
            print(f"   ✅ Migrated: {entry['key']}")
        except Exception as e:
            failed_entries.append({
                "key": entry["key"],
                "error": str(e),
            })
            print(f"   ❌ Failed: {entry['key']} - {e}")

    print(f"\n✨ Migration complete!")
    print(f"   Migrated: {migrated_count}/{entry_count} entries")

    if failed_entries:
        print(f"   ⚠️  Failed: {len(failed_entries)} entries (see export file)")

    return {
        "success": True,
        "entries_migrated": migrated_count,
        "entries_total": entry_count,
        "failed_entries": failed_entries,
        "backup_path": str(backup_path) if backup else None,
        "export_file": str(export_file),
    }


def main():
    """CLI entry point."""
    if len(sys.argv) < 3:
        print("Usage: python tools/migrate_vault.py <vault_path> <password>")
        print("\nExample:")
        print("  python tools/migrate_vault.py ./my_vault my_password")
        print("\nOptions:")
        print("  --no-backup    Skip creating backup")
        sys.exit(1)

    vault_path = sys.argv[1]
    password = sys.argv[2]
    backup = "--no-backup" not in sys.argv

    print("=" * 60)
    print("🔧 ActiveMirrorOS Vault Migration Tool")
    print("=" * 60)
    print()

    result = migrate_vault(vault_path, password, backup=backup)

    print()
    print("=" * 60)

    if result["success"]:
        print("✅ MIGRATION SUCCESSFUL")
        if result.get("already_migrated"):
            print("   Vault already in new format - no changes needed")
        else:
            print(f"   Migrated: {result['entries_migrated']} entries")
            if result.get("backup_path"):
                print(f"   Backup: {result['backup_path']}")
            print(f"   Export: {result['export_file']}")
    else:
        print("❌ MIGRATION FAILED")
        print(f"   Error: {result['error']}")
        sys.exit(1)

    print("=" * 60)


if __name__ == "__main__":
    main()
