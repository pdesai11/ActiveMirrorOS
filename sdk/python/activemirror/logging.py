"""
Structured logging infrastructure for ActiveMirrorOS.

Provides consistent, configurable logging across all components with
support for multiple output formats, log levels, and audit trails.
"""

import logging
import sys
import json
from typing import Any, Dict, Optional
from datetime import datetime
from pathlib import Path
from enum import Enum


class LogLevel(Enum):
    """Log level enumeration."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogFormat(Enum):
    """Log output format."""
    JSON = "json"
    TEXT = "text"
    STRUCTURED = "structured"


class AMOSLogger:
    """
    ActiveMirrorOS structured logger.

    Provides consistent logging with support for:
    - Multiple log levels
    - Structured data (JSON format)
    - Audit trails
    - Performance metrics
    - Security events
    """

    def __init__(
        self,
        name: str,
        level: str = "INFO",
        format_type: str = "text",
        log_file: Optional[str] = None,
        enable_console: bool = True,
    ):
        """
        Initialize AMOS logger.

        Args:
            name: Logger name (typically module or component name)
            level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            format_type: Output format (json, text, structured)
            log_file: Optional file path for log output
            enable_console: Whether to output to console
        """
        self.name = name
        self.logger = logging.getLogger(f"activemirror.{name}")
        self.logger.setLevel(getattr(logging, level.upper()))
        self.logger.propagate = False

        # Clear existing handlers
        self.logger.handlers = []

        # Set up formatters
        if format_type == "json":
            formatter = self._get_json_formatter()
        elif format_type == "structured":
            formatter = self._get_structured_formatter()
        else:
            formatter = self._get_text_formatter()

        # Console handler
        if enable_console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)

        # File handler
        if log_file:
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)

    def _get_text_formatter(self) -> logging.Formatter:
        """Get text log formatter."""
        return logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

    def _get_structured_formatter(self) -> logging.Formatter:
        """Get structured log formatter with extra context."""
        return logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s | %(context)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

    def _get_json_formatter(self) -> 'JSONFormatter':
        """Get JSON log formatter."""
        return JSONFormatter()

    def _log_with_context(
        self,
        level: int,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        exc_info: bool = False,
    ):
        """Internal logging with context."""
        extra = {'context': json.dumps(context or {})}
        self.logger.log(level, message, extra=extra, exc_info=exc_info)

    def debug(self, message: str, context: Optional[Dict[str, Any]] = None):
        """Log debug message."""
        self._log_with_context(logging.DEBUG, message, context)

    def info(self, message: str, context: Optional[Dict[str, Any]] = None):
        """Log info message."""
        self._log_with_context(logging.INFO, message, context)

    def warning(self, message: str, context: Optional[Dict[str, Any]] = None):
        """Log warning message."""
        self._log_with_context(logging.WARNING, message, context)

    def error(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        exc_info: bool = False,
    ):
        """Log error message."""
        self._log_with_context(logging.ERROR, message, context, exc_info=exc_info)

    def critical(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        exc_info: bool = False,
    ):
        """Log critical message."""
        self._log_with_context(logging.CRITICAL, message, context, exc_info=exc_info)

    def audit(
        self,
        action: str,
        user_id: Optional[str] = None,
        resource: Optional[str] = None,
        status: str = "success",
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Log audit trail event.

        Args:
            action: Action performed (e.g., "session_created", "vault_accessed")
            user_id: User who performed the action
            resource: Resource affected (e.g., session ID, vault key)
            status: Action status (success, failure, denied)
            details: Additional audit details
        """
        audit_data = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "user_id": user_id or "anonymous",
            "resource": resource,
            "status": status,
            "details": details or {},
        }
        self.info(f"AUDIT: {action}", context=audit_data)

    def performance(
        self,
        operation: str,
        duration_ms: float,
        context: Optional[Dict[str, Any]] = None,
    ):
        """
        Log performance metric.

        Args:
            operation: Operation name
            duration_ms: Duration in milliseconds
            context: Additional performance context
        """
        perf_data = {
            "operation": operation,
            "duration_ms": duration_ms,
            **(context or {}),
        }
        self.debug(f"PERF: {operation} took {duration_ms:.2f}ms", context=perf_data)

    def security(
        self,
        event: str,
        severity: str = "info",
        context: Optional[Dict[str, Any]] = None,
    ):
        """
        Log security event.

        Args:
            event: Security event description
            severity: Severity level (info, warning, critical)
            context: Security event context
        """
        security_data = {
            "timestamp": datetime.now().isoformat(),
            "event_type": "security",
            "event": event,
            "severity": severity,
            **(context or {}),
        }

        if severity == "critical":
            self.critical(f"SECURITY: {event}", context=security_data)
        elif severity == "warning":
            self.warning(f"SECURITY: {event}", context=security_data)
        else:
            self.info(f"SECURITY: {event}", context=security_data)


class JSONFormatter(logging.Formatter):
    """JSON log formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add context if available
        if hasattr(record, 'context'):
            try:
                context = json.loads(record.context)
                log_data["context"] = context
            except (json.JSONDecodeError, TypeError):
                log_data["context"] = record.context

        # Add exception info if available
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


# Global logger registry
_loggers: Dict[str, AMOSLogger] = {}


def get_logger(
    name: str,
    level: Optional[str] = None,
    format_type: Optional[str] = None,
    log_file: Optional[str] = None,
    enable_console: Optional[bool] = None,
) -> AMOSLogger:
    """
    Get or create a logger instance.

    Args:
        name: Logger name
        level: Log level (overrides config default)
        format_type: Format type (overrides config default)
        log_file: Log file path (overrides config default)
        enable_console: Enable console output (overrides config default)

    Returns:
        AMOSLogger instance
    """
    # Use defaults from environment or config
    if level is None:
        import os
        level = os.getenv('ACTIVEMIRROR_LOG_LEVEL', 'INFO')

    if format_type is None:
        import os
        format_type = os.getenv('ACTIVEMIRROR_LOG_FORMAT', 'text')

    if enable_console is None:
        enable_console = True

    # Check if logger already exists
    logger_key = f"{name}:{level}:{format_type}:{log_file}:{enable_console}"

    if logger_key not in _loggers:
        _loggers[logger_key] = AMOSLogger(
            name=name,
            level=level,
            format_type=format_type,
            log_file=log_file,
            enable_console=enable_console,
        )

    return _loggers[logger_key]


def configure_logging(
    level: str = "INFO",
    format_type: str = "text",
    log_file: Optional[str] = None,
    enable_console: bool = True,
):
    """
    Configure global logging defaults.

    Args:
        level: Default log level
        format_type: Default format type
        log_file: Default log file
        enable_console: Default console output
    """
    import os
    os.environ['ACTIVEMIRROR_LOG_LEVEL'] = level
    os.environ['ACTIVEMIRROR_LOG_FORMAT'] = format_type

    # Clear existing loggers to apply new config
    _loggers.clear()
