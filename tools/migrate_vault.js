#!/usr/bin/env node

/**
 * Vault Migration Tool for ActiveMirrorOS (JavaScript)
 *
 * Migrates vaults from old fixed-salt format to new random-salt format.
 *
 * Usage:
 *   node tools/migrate_vault.js <vault_path> <password>
 *
 * Author: AMOS Dev Twin
 */

import fs from 'fs/promises';
import { existsSync } from 'fs';
import path from 'path';
import crypto from 'crypto';

class OldVaultMemory {
  static FIXED_SALT = 'activemirror_vault';

  constructor(vaultPath, password) {
    this.vaultPath = vaultPath;
    this.password = password;
    this.algorithm = 'aes-256-gcm';

    // Use old key derivation with fixed salt
    this.encryptionKey = crypto.pbkdf2Sync(
      password,
      OldVaultMemory.FIXED_SALT,
      100000,
      32,
      'sha256'
    );
  }

  async canDecrypt() {
    const indexPath = path.join(this.vaultPath, '.vault_index.enc');

    if (!existsSync(indexPath)) {
      return false;
    }

    try {
      const encryptedData = await fs.readFile(indexPath);

      // Old format: just encrypted data, no salt prefix
      const decrypted = this._decrypt(encryptedData);
      JSON.parse(decrypted);
      return true;
    } catch (error) {
      return false;
    }
  }

  _decrypt(buffer) {
    const iv = buffer.slice(0, 16);
    const authTag = buffer.slice(16, 32);
    const encrypted = buffer.slice(32);

    const decipher = crypto.createDecipheriv(this.algorithm, this.encryptionKey, iv);
    decipher.setAuthTag(authTag);

    let decrypted = decipher.update(encrypted);
    decrypted = Buffer.concat([decrypted, decipher.final()]);

    return decrypted.toString('utf8');
  }

  async exportAll() {
    const indexPath = path.join(this.vaultPath, '.vault_index.enc');

    if (!existsSync(indexPath)) {
      return { entries: [], metadata: {} };
    }

    // Load index
    const encryptedIndex = await fs.readFile(indexPath);
    const decryptedIndex = this._decrypt(encryptedIndex);
    const index = JSON.parse(decryptedIndex);

    // Export all entries
    const exportedEntries = [];

    for (const [key, info] of Object.entries(index.entries || {})) {
      const entryFile = info.file;

      if (existsSync(entryFile)) {
        const encryptedEntry = await fs.readFile(entryFile);
        const decryptedEntry = this._decrypt(encryptedEntry);
        const entryData = JSON.parse(decryptedEntry);

        exportedEntries.push({
          key,
          value: entryData.value,
          metadata: entryData.metadata || {},
          createdAt: entryData.createdAt,
          updatedAt: entryData.updatedAt,
        });
      }
    }

    return {
      entries: exportedEntries,
      metadata: {
        vaultCreatedAt: index.createdAt,
        exportedAt: new Date().toISOString(),
        entryCount: exportedEntries.length,
      },
    };
  }
}

async function migrateVault(vaultPath, password, backup = true) {
  console.log(`🔍 Analyzing vault at: ${vaultPath}`);

  // Check if vault exists
  if (!existsSync(vaultPath)) {
    return {
      success: false,
      error: 'Vault path does not exist',
    };
  }

  // Try old format first
  const oldVault = new OldVaultMemory(vaultPath, password);

  if (!(await oldVault.canDecrypt())) {
    // Check if it's already new format
    const indexPath = path.join(vaultPath, '.vault_index.enc');
    if (existsSync(indexPath)) {
      const rawData = await fs.readFile(indexPath);
      if (rawData.length >= 16) {
        console.log('✅ Vault is already in new format (has salt prefix)');
        return {
          success: true,
          alreadyMigrated: true,
          message: 'Vault already uses random salt format',
        };
      }
    }

    return {
      success: false,
      error: 'Cannot decrypt vault with old or new format - wrong password?',
    };
  }

  console.log('📤 Exporting data from old vault format...');
  const exportData = await oldVault.exportAll();

  const entryCount = exportData.entries.length;
  console.log(`   Found ${entryCount} entries to migrate`);

  if (entryCount === 0) {
    console.log('⚠️  Vault is empty - nothing to migrate');
    return {
      success: true,
      entriesMigrated: 0,
      message: 'Vault is empty',
    };
  }

  // Backup old vault
  let backupPath;
  if (backup) {
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
    backupPath = `${vaultPath}.backup_${timestamp}`;
    console.log(`💾 Creating backup at: ${backupPath}`);

    await fs.cp(vaultPath, backupPath, { recursive: true });
    console.log('   ✅ Backup created');
  }

  // Save export to JSON
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
  const exportFile = path.join(
    path.dirname(vaultPath),
    `${path.basename(vaultPath)}_export_${timestamp}.json`
  );
  await fs.writeFile(exportFile, JSON.stringify(exportData, null, 2));
  console.log(`💾 Export saved to: ${exportFile}`);

  // Import new VaultMemory (with random salt)
  console.log('🔄 Importing new VaultMemory...');
  const sdkPath = path.join(path.dirname(new URL(import.meta.url).pathname), '../sdk/javascript');
  const { VaultMemory } = await import(path.join(sdkPath, 'vault.js'));

  // Delete old vault files
  console.log('🗑️  Removing old vault files...');
  const files = await fs.readdir(vaultPath);
  for (const file of files) {
    await fs.unlink(path.join(vaultPath, file));
  }

  // Create new vault with random salt
  console.log('🔐 Creating new vault with random salt...');
  const newVault = new VaultMemory({ vaultPath, password });
  await newVault.initialize();

  // Import all entries
  console.log('📥 Importing entries into new vault...');
  let migratedCount = 0;
  const failedEntries = [];

  for (const entry of exportData.entries) {
    try {
      await newVault.store(entry.key, entry.value, entry.metadata || {});
      migratedCount++;
      console.log(`   ✅ Migrated: ${entry.key}`);
    } catch (error) {
      failedEntries.push({
        key: entry.key,
        error: error.message,
      });
      console.log(`   ❌ Failed: ${entry.key} - ${error.message}`);
    }
  }

  console.log(`\n✨ Migration complete!`);
  console.log(`   Migrated: ${migratedCount}/${entryCount} entries`);

  if (failedEntries.length > 0) {
    console.log(`   ⚠️  Failed: ${failedEntries.length} entries (see export file)`);
  }

  return {
    success: true,
    entriesMigrated: migratedCount,
    entriesTotal: entryCount,
    failedEntries,
    backupPath,
    exportFile,
  };
}

async function main() {
  const args = process.argv.slice(2);

  if (args.length < 2) {
    console.log('Usage: node tools/migrate_vault.js <vault_path> <password>');
    console.log('\nExample:');
    console.log('  node tools/migrate_vault.js ./my_vault my_password');
    console.log('\nOptions:');
    console.log('  --no-backup    Skip creating backup');
    process.exit(1);
  }

  const vaultPath = args[0];
  const password = args[1];
  const backup = !args.includes('--no-backup');

  console.log('='.repeat(60));
  console.log('🔧 ActiveMirrorOS Vault Migration Tool');
  console.log('='.repeat(60));
  console.log();

  const result = await migrateVault(vaultPath, password, backup);

  console.log();
  console.log('='.repeat(60));

  if (result.success) {
    console.log('✅ MIGRATION SUCCESSFUL');
    if (result.alreadyMigrated) {
      console.log('   Vault already in new format - no changes needed');
    } else {
      console.log(`   Migrated: ${result.entriesMigrated} entries`);
      if (result.backupPath) {
        console.log(`   Backup: ${result.backupPath}`);
      }
      console.log(`   Export: ${result.exportFile}`);
    }
  } else {
    console.log('❌ MIGRATION FAILED');
    console.log(`   Error: ${result.error}`);
    process.exit(1);
  }

  console.log('='.repeat(60));
}

main().catch((error) => {
  console.error('Fatal error:', error);
  process.exit(1);
});
