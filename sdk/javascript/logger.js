/**
 * Structured logging infrastructure for ActiveMirrorOS (JavaScript)
 *
 * Provides consistent, configurable logging across all components with
 * support for multiple output formats, log levels, and audit trails.
 */

export const LogLevel = {
  DEBUG: 'DEBUG',
  INFO: 'INFO',
  WARNING: 'WARNING',
  ERROR: 'ERROR',
  CRITICAL: 'CRITICAL',
};

export const LogFormat = {
  JSON: 'json',
  TEXT: 'text',
  STRUCTURED: 'structured',
};

/**
 * ActiveMirrorOS structured logger
 *
 * Provides consistent logging with support for:
 * - Multiple log levels
 * - Structured data (JSON format)
 * - Audit trails
 * - Performance metrics
 * - Security events
 */
export class AMOSLogger {
  /**
   * Initialize AMOS logger
   *
   * @param {Object} options - Logger configuration
   * @param {string} options.name - Logger name (typically module or component name)
   * @param {string} options.level - Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
   * @param {string} options.format - Output format (json, text, structured)
   * @param {string} options.logFile - Optional file path for log output
   * @param {boolean} options.enableConsole - Whether to output to console
   */
  constructor(options = {}) {
    this.name = options.name || 'activemirror';
    this.level = this._parseLevelValue(options.level || 'INFO');
    this.format = options.format || 'text';
    this.logFile = options.logFile;
    this.enableConsole = options.enableConsole !== false;
    this.handlers = [];

    // Set up file handler if specified
    if (this.logFile) {
      this._setupFileHandler();
    }
  }

  _parseLevelValue(levelName) {
    const levels = {
      DEBUG: 10,
      INFO: 20,
      WARNING: 30,
      ERROR: 40,
      CRITICAL: 50,
    };
    return levels[levelName.toUpperCase()] || 20;
  }

  _getLevelName(levelValue) {
    const levels = {
      10: 'DEBUG',
      20: 'INFO',
      30: 'WARNING',
      40: 'ERROR',
      50: 'CRITICAL',
    };
    return levels[levelValue] || 'INFO';
  }

  _setupFileHandler() {
    // File handler setup (would use fs in Node.js)
    // For now, we'll handle this in the _writeToFile method
  }

  _formatMessage(level, message, context = null) {
    const timestamp = new Date().toISOString();
    const levelName = this._getLevelName(level);

    if (this.format === 'json') {
      const logData = {
        timestamp,
        level: levelName,
        logger: this.name,
        message,
      };

      if (context) {
        logData.context = context;
      }

      return JSON.stringify(logData);
    } else if (this.format === 'structured') {
      const contextStr = context ? JSON.stringify(context) : '{}';
      return `${timestamp} | ${levelName.padEnd(8)} | ${this.name} | ${message} | ${contextStr}`;
    } else {
      // text format
      return `${timestamp} - ${this.name} - ${levelName} - ${message}`;
    }
  }

  _shouldLog(level) {
    return level >= this.level;
  }

  _log(level, message, context = null, error = null) {
    if (!this._shouldLog(level)) {
      return;
    }

    const formatted = this._formatMessage(level, message, context);
    const levelName = this._getLevelName(level);

    // Console output
    if (this.enableConsole) {
      if (level >= 40) {
        // ERROR or CRITICAL
        console.error(formatted);
        if (error) {
          console.error(error);
        }
      } else if (level >= 30) {
        // WARNING
        console.warn(formatted);
      } else {
        console.log(formatted);
      }
    }

    // File output
    if (this.logFile) {
      this._writeToFile(formatted, error);
    }

    // Custom handlers
    for (const handler of this.handlers) {
      handler(levelName, message, context, error);
    }
  }

  async _writeToFile(message, error = null) {
    try {
      const fs = await import('fs/promises');
      let output = message + '\n';

      if (error) {
        output += error.stack || error.toString() + '\n';
      }

      await fs.appendFile(this.logFile, output);
    } catch (err) {
      // Fallback to console if file write fails
      console.error('Failed to write to log file:', err.message);
    }
  }

  /**
   * Add a custom log handler
   *
   * @param {Function} handler - Handler function(level, message, context, error)
   */
  addHandler(handler) {
    this.handlers.push(handler);
  }

  /**
   * Log debug message
   *
   * @param {string} message - Log message
   * @param {Object} context - Optional context data
   */
  debug(message, context = null) {
    this._log(10, message, context);
  }

  /**
   * Log info message
   *
   * @param {string} message - Log message
   * @param {Object} context - Optional context data
   */
  info(message, context = null) {
    this._log(20, message, context);
  }

  /**
   * Log warning message
   *
   * @param {string} message - Log message
   * @param {Object} context - Optional context data
   */
  warning(message, context = null) {
    this._log(30, message, context);
  }

  /**
   * Log error message
   *
   * @param {string} message - Log message
   * @param {Object} context - Optional context data
   * @param {Error} error - Optional error object
   */
  error(message, context = null, error = null) {
    this._log(40, message, context, error);
  }

  /**
   * Log critical message
   *
   * @param {string} message - Log message
   * @param {Object} context - Optional context data
   * @param {Error} error - Optional error object
   */
  critical(message, context = null, error = null) {
    this._log(50, message, context, error);
  }

  /**
   * Log audit trail event
   *
   * @param {Object} options - Audit event options
   * @param {string} options.action - Action performed
   * @param {string} options.userId - User who performed the action
   * @param {string} options.resource - Resource affected
   * @param {string} options.status - Action status (success, failure, denied)
   * @param {Object} options.details - Additional audit details
   */
  audit(options) {
    const {
      action,
      userId = 'anonymous',
      resource = null,
      status = 'success',
      details = {},
    } = options;

    const auditData = {
      timestamp: new Date().toISOString(),
      action,
      userId,
      resource,
      status,
      details,
    };

    this.info(`AUDIT: ${action}`, auditData);
  }

  /**
   * Log performance metric
   *
   * @param {string} operation - Operation name
   * @param {number} durationMs - Duration in milliseconds
   * @param {Object} context - Additional performance context
   */
  performance(operation, durationMs, context = null) {
    const perfData = {
      operation,
      durationMs,
      ...(context || {}),
    };

    this.debug(`PERF: ${operation} took ${durationMs.toFixed(2)}ms`, perfData);
  }

  /**
   * Log security event
   *
   * @param {Object} options - Security event options
   * @param {string} options.event - Security event description
   * @param {string} options.severity - Severity level (info, warning, critical)
   * @param {Object} options.context - Security event context
   */
  security(options) {
    const { event, severity = 'info', context = null } = options;

    const securityData = {
      timestamp: new Date().toISOString(),
      eventType: 'security',
      event,
      severity,
      ...(context || {}),
    };

    if (severity === 'critical') {
      this.critical(`SECURITY: ${event}`, securityData);
    } else if (severity === 'warning') {
      this.warning(`SECURITY: ${event}`, securityData);
    } else {
      this.info(`SECURITY: ${event}`, securityData);
    }
  }
}

// Global logger registry
const _loggers = new Map();

/**
 * Get or create a logger instance
 *
 * @param {string} name - Logger name
 * @param {Object} options - Logger options (overrides defaults)
 * @returns {AMOSLogger} Logger instance
 */
export function getLogger(name, options = {}) {
  // Use defaults from environment or config
  const level = options.level || process.env.ACTIVEMIRROR_LOG_LEVEL || 'INFO';
  const format = options.format || process.env.ACTIVEMIRROR_LOG_FORMAT || 'text';
  const logFile = options.logFile || process.env.ACTIVEMIRROR_LOG_FILE;
  const enableConsole = options.enableConsole !== false;

  const loggerKey = `${name}:${level}:${format}:${logFile}:${enableConsole}`;

  if (!_loggers.has(loggerKey)) {
    _loggers.set(
      loggerKey,
      new AMOSLogger({
        name,
        level,
        format,
        logFile,
        enableConsole,
      })
    );
  }

  return _loggers.get(loggerKey);
}

/**
 * Configure global logging defaults
 *
 * @param {Object} options - Configuration options
 * @param {string} options.level - Default log level
 * @param {string} options.format - Default format type
 * @param {string} options.logFile - Default log file
 * @param {boolean} options.enableConsole - Default console output
 */
export function configureLogging(options = {}) {
  const { level = 'INFO', format = 'text', logFile, enableConsole = true } = options;

  if (level) process.env.ACTIVEMIRROR_LOG_LEVEL = level;
  if (format) process.env.ACTIVEMIRROR_LOG_FORMAT = format;
  if (logFile) process.env.ACTIVEMIRROR_LOG_FILE = logFile;

  // Clear existing loggers to apply new config
  _loggers.clear();
}
