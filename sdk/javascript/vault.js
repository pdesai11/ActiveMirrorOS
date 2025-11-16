/**
 * Vault Memory - Encrypted persistent memory storage for JavaScript
 *
 * Provides secure, long-term storage for sensitive personal data.
 */

import fs from 'fs/promises';
import path from 'path';
import crypto from 'crypto';
import { existsSync } from 'fs';
import { getLogger } from './logger.js';

export const VaultCategory = {
  GOALS: 'goals',
  REFLECTIONS: 'reflections',
  PREFERENCES: 'preferences',
  PRIVATE: 'private',
  KNOWLEDGE: 'knowledge',
  RELATIONSHIPS: 'relationships',
};

export class VaultMemory {
  /**
   * Encrypted memory vault for sensitive personal data
   *
   * @param {Object} options - Configuration options
   * @param {string} options.vaultPath - Directory for vault storage
   * @param {string} options.password - Password to derive encryption key
   * @param {string} options.encryptionKey - Pre-existing encryption key (hex)
   */
  constructor(options = {}) {
    this.vaultPath = options.vaultPath || './vault';
    this.algorithm = 'aes-256-gcm';

    // Set up logging
    this.logger = getLogger('vault_memory');

    // Derive or use encryption key
    if (options.encryptionKey) {
      this.encryptionKey = Buffer.from(options.encryptionKey, 'hex');
    } else if (options.password) {
      this.encryptionKey = this._deriveKey(options.password);
    } else {
      // Generate random key for demo/testing
      this.encryptionKey = crypto.randomBytes(32);
    }

    this.index = null;
    this.initialized = false;
  }

  async initialize() {
    if (this.initialized) return;

    // Create vault directory
    if (!existsSync(this.vaultPath)) {
      await fs.mkdir(this.vaultPath, { recursive: true });
    }

    // Load or create index
    this.index = await this._loadIndex();
    this.initialized = true;
  }

  _deriveKey(password, salt = 'activemirror_vault') {
    return crypto.pbkdf2Sync(password, salt, 100000, 32, 'sha256');
  }

  async _loadIndex() {
    const indexPath = path.join(this.vaultPath, '.vault_index.enc');

    if (!existsSync(indexPath)) {
      return {
        entries: {},
        createdAt: new Date().toISOString(),
      };
    }

    try {
      const encryptedData = await fs.readFile(indexPath);
      const decrypted = this._decrypt(encryptedData);
      return JSON.parse(decrypted);
    } catch (error) {
      // Index corrupted or wrong key
      return {
        entries: {},
        createdAt: new Date().toISOString(),
      };
    }
  }

  async _saveIndex() {
    const indexPath = path.join(this.vaultPath, '.vault_index.enc');
    const indexJson = JSON.stringify(this.index, null, 2);
    const encrypted = this._encrypt(indexJson);
    await fs.writeFile(indexPath, encrypted);
  }

  _encrypt(text) {
    const iv = crypto.randomBytes(16);
    const cipher = crypto.createCipheriv(this.algorithm, this.encryptionKey, iv);

    let encrypted = cipher.update(text, 'utf8');
    encrypted = Buffer.concat([encrypted, cipher.final()]);

    const authTag = cipher.getAuthTag();

    // Combine iv + authTag + encrypted
    return Buffer.concat([iv, authTag, encrypted]);
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

  /**
   * Store encrypted data in vault
   *
   * @param {string} key - Unique identifier for this entry
   * @param {*} value - Data to store (will be JSON serialized)
   * @param {Object} metadata - Optional metadata (tags, categories, etc.)
   * @returns {Promise<boolean>} True if stored successfully
   */
  async store(key, value, metadata = {}) {
    await this.initialize();

    try {
      const entry = {
        key,
        value,
        metadata,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      };

      // Encrypt and save
      const entryJson = JSON.stringify(entry, null, 2);
      const encrypted = this._encrypt(entryJson);

      const entryFile = path.join(this.vaultPath, `${key}.vault`);
      await fs.writeFile(entryFile, encrypted);

      // Update index
      this.index.entries[key] = {
        file: entryFile,
        createdAt: entry.createdAt,
        updatedAt: entry.updatedAt,
        metadata,
      };

      await this._saveIndex();

      this.logger.audit({
        action: 'vault_store',
        resource: key,
        status: 'success',
        details: { metadata },
      });

      return true;
    } catch (error) {
      this.logger.error(
        `Failed to store vault entry: ${key}`,
        { key, error: error.message },
        error
      );
      this.logger.audit({
        action: 'vault_store',
        resource: key,
        status: 'failure',
        details: { error: error.message },
      });

      // Re-raise exception instead of returning false
      throw new Error(`Failed to store vault entry '${key}': ${error.message}`);
    }
  }

  /**
   * Retrieve and decrypt data from vault
   *
   * @param {string} key - Entry identifier
   * @returns {Promise<*>} Decrypted value or null if not found
   */
  async retrieve(key) {
    await this.initialize();

    if (!this.index.entries[key]) {
      return null;
    }

    try {
      const entryFile = this.index.entries[key].file;
      const encrypted = await fs.readFile(entryFile);
      const decrypted = this._decrypt(encrypted);
      const entry = JSON.parse(decrypted);

      this.logger.audit({
        action: 'vault_retrieve',
        resource: key,
        status: 'success',
      });
      this.logger.debug(`Retrieved vault entry: ${key}`);

      return entry.value;
    } catch (error) {
      this.logger.error(
        `Failed to retrieve vault entry: ${key}`,
        { key, error: error.message },
        error
      );
      this.logger.audit({
        action: 'vault_retrieve',
        resource: key,
        status: 'failure',
        details: { error: error.message },
      });

      // Re-raise exception instead of returning null
      throw new Error(`Failed to retrieve vault entry '${key}': ${error.message}`);
    }
  }

  /**
   * Delete entry from vault
   */
  async delete(key) {
    await this.initialize();

    if (!this.index.entries[key]) {
      return false;
    }

    try {
      const entryFile = this.index.entries[key].file;
      await fs.unlink(entryFile);
      delete this.index.entries[key];
      await this._saveIndex();

      this.logger.audit({
        action: 'vault_delete',
        resource: key,
        status: 'success',
      });
      this.logger.info(`Deleted vault entry: ${key}`);

      return true;
    } catch (error) {
      this.logger.error(
        `Failed to delete vault entry: ${key}`,
        { key, error: error.message },
        error
      );
      this.logger.audit({
        action: 'vault_delete',
        resource: key,
        status: 'failure',
        details: { error: error.message },
      });

      // Re-raise exception instead of returning false
      throw new Error(`Failed to delete vault entry '${key}': ${error.message}`);
    }
  }

  /**
   * List all vault entries
   *
   * @param {Object} filterMetadata - Optional metadata filter
   * @returns {Promise<Array>} List of entry summaries
   */
  async listEntries(filterMetadata = null) {
    await this.initialize();

    const entries = [];

    for (const [key, info] of Object.entries(this.index.entries)) {
      // Filter by metadata if provided
      if (filterMetadata) {
        const matches = Object.entries(filterMetadata).every(
          ([k, v]) => info.metadata[k] === v
        );
        if (!matches) continue;
      }

      entries.push({
        key,
        createdAt: info.createdAt,
        updatedAt: info.updatedAt,
        metadata: info.metadata,
      });
    }

    return entries;
  }

  /**
   * Search vault entries by content
   *
   * @param {string} query - Search string
   * @returns {Promise<Array>} List of matching entries with context
   */
  async search(query) {
    await this.initialize();

    const results = [];
    const queryLower = query.toLowerCase();

    for (const key of Object.keys(this.index.entries)) {
      const value = await this.retrieve(key);
      if (value === null) continue;

      // Convert to string for searching
      const valueStr = JSON.stringify(value).toLowerCase();

      if (valueStr.includes(queryLower)) {
        const count = (valueStr.match(new RegExp(queryLower, 'g')) || []).length;
        results.push({
          key,
          value,
          relevance: count,
        });
      }
    }

    // Sort by relevance
    results.sort((a, b) => b.relevance - a.relevance);
    return results;
  }

  /**
   * Export encryption key for backup
   *
   * ⚠️ Keep this key secure! Anyone with this key can decrypt your vault.
   *
   * @returns {string} Hex-encoded encryption key
   */
  exportKey() {
    return this.encryptionKey.toString('hex');
  }

  /**
   * Get vault statistics
   */
  async getStats() {
    await this.initialize();

    const totalEntries = Object.keys(this.index.entries).length;

    // Calculate total size
    let totalSize = 0;
    for (const info of Object.values(this.index.entries)) {
      if (existsSync(info.file)) {
        const stats = await fs.stat(info.file);
        totalSize += stats.size;
      }
    }

    return {
      totalEntries,
      totalSizeBytes: totalSize,
      createdAt: this.index.createdAt,
      vaultPath: this.vaultPath,
    };
  }
}
