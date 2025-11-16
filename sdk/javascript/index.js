/**
 * ActiveMirrorOS JavaScript SDK
 *
 * Main entry point for the JavaScript SDK.
 */

export { ActiveMirror, Session } from './activemirror.js';
export { MemoryStore, MemoryEntry } from './memory.js';
export { ReflectiveClient, ReflectivePattern, UncertaintyLevel } from './reflective-client.js';
export { VaultMemory } from './vault.js';
export { AMOSLogger, getLogger, configureLogging, LogLevel, LogFormat } from './logger.js';

export const VERSION = '0.2.0';
export const API_VERSION = '2.0.0';
