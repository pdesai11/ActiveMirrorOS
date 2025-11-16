"""
Vault Memory - Encrypted persistent memory storage.

Provides secure, long-term storage for sensitive personal data,
goals, preferences, and private reflections.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from pathlib import Path
import json
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from activemirror.logging import get_logger


class VaultMemory:
    """
    Encrypted memory vault for sensitive personal data.

    Uses Fernet symmetric encryption with password-based key derivation.
    Data is stored as encrypted JSON files.
    """

    def __init__(
        self,
        vault_path: str = "./vault",
        encryption_key: Optional[str] = None,
        password: Optional[str] = None,
    ):
        """
        Initialize vault memory.

        Args:
            vault_path: Directory for vault storage
            encryption_key: Base64-encoded Fernet key (if already generated)
            password: Password to derive encryption key (if generating new)
        """
        self.vault_path = Path(vault_path)
        self.vault_path.mkdir(parents=True, exist_ok=True)

        # Set up logging
        self.logger = get_logger("vault_memory")

        # Set up encryption
        if encryption_key:
            self.encryption_key = encryption_key.encode()
        elif password:
            self.encryption_key = self._derive_key(password)
        else:
            # Generate random key for demo/testing
            self.encryption_key = Fernet.generate_key()

        self.cipher = Fernet(self.encryption_key)

        # Index file (encrypted)
        self.index_file = self.vault_path / ".vault_index.enc"
        self.index = self._load_index()

    def _derive_key(self, password: str, salt: Optional[bytes] = None) -> bytes:
        """Derive encryption key from password using PBKDF2."""
        if salt is None:
            salt = b'activemirror_vault'  # In production, use random salt

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key

    def _load_index(self) -> Dict[str, Any]:
        """Load vault index."""
        if not self.index_file.exists():
            return {"entries": {}, "created_at": datetime.now().isoformat()}

        try:
            encrypted_data = self.index_file.read_bytes()
            decrypted_data = self.cipher.decrypt(encrypted_data)
            return json.loads(decrypted_data.decode())
        except Exception:
            # Index corrupted or wrong key
            return {"entries": {}, "created_at": datetime.now().isoformat()}

    def _save_index(self):
        """Save vault index."""
        index_json = json.dumps(self.index, indent=2)
        encrypted_data = self.cipher.encrypt(index_json.encode())
        self.index_file.write_bytes(encrypted_data)

    def store(
        self,
        key: str,
        value: Any,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Store encrypted data in vault.

        Args:
            key: Unique identifier for this entry
            value: Data to store (will be JSON serialized)
            metadata: Optional metadata (tags, categories, etc.)

        Returns:
            True if stored successfully
        """
        try:
            # Create entry
            entry = {
                "key": key,
                "value": value,
                "metadata": metadata or {},
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }

            # Encrypt and save
            entry_json = json.dumps(entry, indent=2)
            encrypted_entry = self.cipher.encrypt(entry_json.encode())

            # Save to file
            entry_file = self.vault_path / f"{key}.vault"
            entry_file.write_bytes(encrypted_entry)

            # Update index
            self.index["entries"][key] = {
                "file": str(entry_file),
                "created_at": entry["created_at"],
                "updated_at": entry["updated_at"],
                "metadata": metadata or {},
            }
            self._save_index()

            self.logger.audit(
                action="vault_store",
                resource=key,
                status="success",
                details={"metadata": metadata or {}},
            )
            return True

        except Exception as e:
            self.logger.error(
                f"Failed to store vault entry: {key}",
                context={"key": key, "error": str(e)},
                exc_info=True,
            )
            self.logger.audit(
                action="vault_store",
                resource=key,
                status="failure",
                details={"error": str(e)},
            )
            # Re-raise exception instead of returning False
            from activemirror.exceptions import StorageError
            raise StorageError(f"Failed to store vault entry '{key}': {e}") from e

    def retrieve(self, key: str) -> Optional[Any]:
        """
        Retrieve and decrypt data from vault.

        Args:
            key: Entry identifier

        Returns:
            Decrypted value or None if not found
        """
        if key not in self.index["entries"]:
            return None

        try:
            entry_file = Path(self.index["entries"][key]["file"])
            encrypted_data = entry_file.read_bytes()
            decrypted_data = self.cipher.decrypt(encrypted_data)
            entry = json.loads(decrypted_data.decode())

            self.logger.audit(
                action="vault_retrieve",
                resource=key,
                status="success",
            )
            self.logger.debug(f"Retrieved vault entry: {key}")
            return entry["value"]

        except Exception as e:
            self.logger.error(
                f"Failed to retrieve vault entry: {key}",
                context={"key": key, "error": str(e)},
                exc_info=True,
            )
            self.logger.audit(
                action="vault_retrieve",
                resource=key,
                status="failure",
                details={"error": str(e)},
            )
            # Re-raise exception instead of returning None
            from activemirror.exceptions import StorageError
            raise StorageError(f"Failed to retrieve vault entry '{key}': {e}") from e

    def delete(self, key: str) -> bool:
        """Delete entry from vault."""
        if key not in self.index["entries"]:
            return False

        try:
            entry_file = Path(self.index["entries"][key]["file"])
            entry_file.unlink()
            del self.index["entries"][key]
            self._save_index()

            self.logger.audit(
                action="vault_delete",
                resource=key,
                status="success",
            )
            self.logger.info(f"Deleted vault entry: {key}")
            return True

        except Exception as e:
            self.logger.error(
                f"Failed to delete vault entry: {key}",
                context={"key": key, "error": str(e)},
                exc_info=True,
            )
            self.logger.audit(
                action="vault_delete",
                resource=key,
                status="failure",
                details={"error": str(e)},
            )
            # Re-raise exception instead of returning False
            from activemirror.exceptions import StorageError
            raise StorageError(f"Failed to delete vault entry '{key}': {e}") from e

    def list_entries(
        self,
        filter_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        List all vault entries.

        Args:
            filter_metadata: Optional metadata filter

        Returns:
            List of entry summaries
        """
        entries = []

        for key, info in self.index["entries"].items():
            # Filter by metadata if provided
            if filter_metadata:
                if not all(
                    info["metadata"].get(k) == v
                    for k, v in filter_metadata.items()
                ):
                    continue

            entries.append({
                "key": key,
                "created_at": info["created_at"],
                "updated_at": info["updated_at"],
                "metadata": info["metadata"],
            })

        return entries

    def search(self, query: str) -> List[Dict[str, Any]]:
        """
        Search vault entries by content.

        Args:
            query: Search string

        Returns:
            List of matching entries with context
        """
        results = []
        query_lower = query.lower()

        for key in self.index["entries"].keys():
            value = self.retrieve(key)
            if value is None:
                continue

            # Convert to string for searching
            value_str = json.dumps(value).lower()

            if query_lower in value_str:
                results.append({
                    "key": key,
                    "value": value,
                    "relevance": value_str.count(query_lower),
                })

        # Sort by relevance
        results.sort(key=lambda x: x["relevance"], reverse=True)
        return results

    def export_key(self) -> str:
        """
        Export encryption key for backup.

        ⚠️ Keep this key secure! Anyone with this key can decrypt your vault.

        Returns:
            Base64-encoded encryption key
        """
        return self.encryption_key.decode()

    def get_stats(self) -> Dict[str, Any]:
        """Get vault statistics."""
        total_entries = len(self.index["entries"])

        # Calculate total size
        total_size = sum(
            Path(info["file"]).stat().st_size
            for info in self.index["entries"].values()
            if Path(info["file"]).exists()
        )

        return {
            "total_entries": total_entries,
            "total_size_bytes": total_size,
            "created_at": self.index["created_at"],
            "vault_path": str(self.vault_path),
        }


class VaultCategory:
    """Predefined categories for vault organization."""

    GOALS = "goals"
    REFLECTIONS = "reflections"
    PREFERENCES = "preferences"
    PRIVATE = "private"
    KNOWLEDGE = "knowledge"
    RELATIONSHIPS = "relationships"
