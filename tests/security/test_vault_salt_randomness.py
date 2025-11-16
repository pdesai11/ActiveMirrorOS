"""
Security Test: Vault Salt Randomness

Verifies that each vault generates a unique random salt,
preventing rainbow table attacks.

Author: AMOS Dev Twin
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from activemirror.vault_memory import VaultMemory


class TestVaultSaltRandomness:
    """Test suite for vault salt randomness."""

    def test_different_vaults_have_different_salts(self):
        """Each new vault should have a unique random salt."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create two vaults with same password
            vault1_path = Path(tmpdir) / "vault1"
            vault2_path = Path(tmpdir) / "vault2"

            vault1 = VaultMemory(vault_path=str(vault1_path), password="test_password")
            vault2 = VaultMemory(vault_path=str(vault2_path), password="test_password")

            # Salts should be different
            assert vault1.salt != vault2.salt, "Vaults with same password should have different salts"

            # Salts should be 16 bytes
            assert len(vault1.salt) == 16, "Salt should be 16 bytes (128 bits)"
            assert len(vault2.salt) == 16, "Salt should be 16 bytes (128 bits)"

    def test_salt_is_random_not_predictable(self):
        """Generated salts should not be predictable."""
        with tempfile.TemporaryDirectory() as tmpdir:
            salts = []

            # Create 10 vaults
            for i in range(10):
                vault_path = Path(tmpdir) / f"vault{i}"
                vault = VaultMemory(vault_path=str(vault_path), password="password")
                salts.append(vault.salt)

            # All salts should be unique
            unique_salts = set(salts)
            assert len(unique_salts) == 10, "All salts should be unique"

            # Check that salts are not sequential or patterned
            for i in range(len(salts) - 1):
                # XOR two consecutive salts - should not be 0 or predictable
                xor_result = bytes(a ^ b for a, b in zip(salts[i], salts[i + 1]))
                # At least half the bits should differ
                bit_differences = bin(int.from_bytes(xor_result, 'big')).count('1')
                assert bit_differences > 32, f"Salts {i} and {i+1} are too similar"

    def test_salt_persisted_in_index(self):
        """Salt should be stored in vault index file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = Path(tmpdir) / "vault"
            vault = VaultMemory(vault_path=str(vault_path), password="test_password")

            # Store something to ensure index is saved
            vault.store("test_key", "test_value")

            # Read raw index file
            index_file = vault_path / ".vault_index.enc"
            raw_data = index_file.read_bytes()

            # First 16 bytes should be the salt
            stored_salt = raw_data[:16]
            assert stored_salt == vault.salt, "Salt should be stored as first 16 bytes"

    def test_salt_loaded_on_vault_reopen(self):
        """Salt should be loaded when reopening existing vault."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = Path(tmpdir) / "vault"

            # Create vault and store data
            vault1 = VaultMemory(vault_path=str(vault_path), password="test_password")
            original_salt = vault1.salt
            vault1.store("test_key", "test_value")

            # Reopen vault
            vault2 = VaultMemory(vault_path=str(vault_path), password="test_password")

            # Salt should be same
            assert vault2.salt == original_salt, "Reopened vault should use same salt"

            # Should be able to retrieve data
            value = vault2.retrieve("test_key")
            assert value == "test_value", "Should decrypt data with loaded salt"

    def test_different_passwords_same_vault_use_same_salt(self):
        """
        Wrong password should fail to decrypt, but detect the salt.
        (This tests that salt is not password-dependent)
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = Path(tmpdir) / "vault"

            # Create vault with password1
            vault1 = VaultMemory(vault_path=str(vault_path), password="password1")
            original_salt = vault1.salt
            vault1.store("key", "value")

            # Try to open with wrong password
            vault2 = VaultMemory(vault_path=str(vault_path), password="wrong_password")

            # Salt should still be extracted (salt is not secret)
            assert vault2.salt == original_salt, "Salt should be extracted regardless of password"

            # But decryption should fail
            with pytest.raises(Exception):
                vault2.retrieve("key")

    def test_salt_entropy_is_high(self):
        """Salts should have high entropy (be truly random)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = Path(tmpdir) / "vault"
            vault = VaultMemory(vault_path=str(vault_path), password="password")

            # Convert salt to binary string
            salt_bits = ''.join(format(byte, '08b') for byte in vault.salt)

            # Count 0s and 1s
            ones = salt_bits.count('1')
            zeros = salt_bits.count('0')

            # Should be roughly balanced (not all 0s or all 1s)
            # Allow some deviation but expect >30% and <70% for each
            total_bits = len(salt_bits)
            assert 0.3 < ones / total_bits < 0.7, f"Salt should have balanced bits, got {ones}/{total_bits} ones"
            assert 0.3 < zeros / total_bits < 0.7, f"Salt should have balanced bits, got {zeros}/{total_bits} zeros"

    def test_salt_not_leaked_in_logs(self, caplog):
        """Salt should not appear in plaintext in logs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = Path(tmpdir) / "vault"
            vault = VaultMemory(vault_path=str(vault_path), password="password")
            vault.store("key", "value")

            # Check that salt bytes are not in any log message
            for record in caplog.records:
                assert vault.salt.hex() not in record.message, "Salt should not be logged in hex"
                # Salt itself would be binary, but check it's not accidentally converted to str
                assert str(vault.salt) not in record.message, "Salt should not be logged"

    def test_encryption_key_differs_with_different_salts(self):
        """
        Same password with different salts should produce different encryption keys.
        (This validates PBKDF2 is working correctly)
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            vault1_path = Path(tmpdir) / "vault1"
            vault2_path = Path(tmpdir) / "vault2"

            # Same password, but vaults will have different salts
            vault1 = VaultMemory(vault_path=str(vault1_path), password="same_password")
            vault2 = VaultMemory(vault_path=str(vault2_path), password="same_password")

            # Encryption keys should be different
            assert vault1.encryption_key != vault2.encryption_key, \
                "Different salts with same password should produce different keys"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
