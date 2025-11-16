"""
Configuration management for ActiveMirrorOS.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
import os
import yaml


@dataclass
class StorageConfig:
    """Storage configuration."""

    type: str = "sqlite"
    db_path: str = "./data/memories.db"
    enable_wal: bool = True
    connection_string: Optional[str] = None
    pool_size: int = 20
    max_overflow: int = 10


@dataclass
class MemoryConfig:
    """Memory management configuration."""

    max_context_messages: int = 50
    enable_semantic_memory: bool = True
    context_window_size: int = 4096
    context_strategy: str = "recent_and_relevant"


@dataclass
class IdentityConfig:
    """Identity configuration."""

    type: str = "anonymous"
    identity_file: Optional[str] = None
    create_if_missing: bool = False


@dataclass
class DialogueConfig:
    """Dialogue engine configuration."""

    engine: str = "basic"
    mode: str = "conversational"
    enable_meta_cognition: bool = False


@dataclass
class LoggingConfig:
    """Logging configuration."""

    level: str = "INFO"
    format: str = "text"
    log_file: Optional[str] = None
    enable_console: bool = True
    enable_audit: bool = True
    enable_performance: bool = False


@dataclass
class Config:
    """
    Main ActiveMirror configuration.

    Can be loaded from files, environment variables, or created programmatically.
    """

    storage: StorageConfig = field(default_factory=StorageConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    identity: IdentityConfig = field(default_factory=IdentityConfig)
    dialogue: DialogueConfig = field(default_factory=DialogueConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    debug: bool = False

    @classmethod
    def from_file(cls, path: str) -> "Config":
        """
        Load configuration from a YAML or JSON file.

        Args:
            path: Path to configuration file

        Returns:
            Config object

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If config file is invalid
        """
        config_path = Path(path)
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {path}")

        with open(config_path) as f:
            if config_path.suffix in (".yaml", ".yml"):
                data = yaml.safe_load(f)
            else:
                import json
                data = json.load(f)

        return cls._from_dict(data)

    @classmethod
    def from_env(cls) -> "Config":
        """
        Load configuration from environment variables.

        Environment variables should be prefixed with ACTIVEMIRROR_
        Example: ACTIVEMIRROR_STORAGE_TYPE=sqlite

        Returns:
            Config object
        """
        config_dict: Dict[str, Any] = {
            "storage": {},
            "memory": {},
            "identity": {},
            "dialogue": {},
            "logging": {},
        }

        # Parse environment variables
        for key, value in os.environ.items():
            if not key.startswith("ACTIVEMIRROR_"):
                continue

            parts = key[len("ACTIVEMIRROR_"):].lower().split("_")
            if len(parts) < 2:
                continue

            section = parts[0]
            setting = "_".join(parts[1:])

            if section in config_dict:
                # Convert string values to appropriate types
                if value.lower() in ("true", "false"):
                    value = value.lower() == "true"
                elif value.isdigit():
                    value = int(value)

                config_dict[section][setting] = value

        return cls._from_dict(config_dict)

    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> "Config":
        """Create Config from dictionary."""
        storage_data = data.get("storage", {})
        memory_data = data.get("memory", {})
        identity_data = data.get("identity", {})
        dialogue_data = data.get("dialogue", {})
        logging_data = data.get("logging", {})

        return cls(
            storage=StorageConfig(**storage_data),
            memory=MemoryConfig(**memory_data),
            identity=IdentityConfig(**identity_data),
            dialogue=DialogueConfig(**dialogue_data),
            logging=LoggingConfig(**logging_data),
            debug=data.get("debug", False),
        )

    def validate(self) -> List[str]:
        """
        Validate configuration.

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Validate storage
        if self.storage.type not in ("sqlite", "postgresql", "filesystem", "memory"):
            errors.append(f"Invalid storage type: {self.storage.type}")

        if self.storage.type == "sqlite" and not self.storage.db_path:
            errors.append("SQLite storage requires db_path")

        if self.storage.type == "postgresql" and not self.storage.connection_string:
            errors.append("PostgreSQL storage requires connection_string")

        # Validate memory
        if self.memory.max_context_messages < 1:
            errors.append("max_context_messages must be positive")

        if self.memory.context_window_size < 1:
            errors.append("context_window_size must be positive")

        if self.memory.context_strategy not in (
            "recent",
            "relevant",
            "recent_and_relevant",
        ):
            errors.append(f"Invalid context_strategy: {self.memory.context_strategy}")

        # Validate identity
        if self.identity.type not in ("mirror_dna", "anonymous", "custom"):
            errors.append(f"Invalid identity type: {self.identity.type}")

        # Validate dialogue
        if self.dialogue.engine not in ("lingos", "basic", "custom"):
            errors.append(f"Invalid dialogue engine: {self.dialogue.engine}")

        # Validate logging
        if self.logging.level not in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
            errors.append(f"Invalid log level: {self.logging.level}")

        if self.logging.format not in ("json", "text", "structured"):
            errors.append(f"Invalid log format: {self.logging.format}")

        return errors

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "storage": {
                "type": self.storage.type,
                "db_path": self.storage.db_path,
                "enable_wal": self.storage.enable_wal,
                "connection_string": self.storage.connection_string,
                "pool_size": self.storage.pool_size,
                "max_overflow": self.storage.max_overflow,
            },
            "memory": {
                "max_context_messages": self.memory.max_context_messages,
                "enable_semantic_memory": self.memory.enable_semantic_memory,
                "context_window_size": self.memory.context_window_size,
                "context_strategy": self.memory.context_strategy,
            },
            "identity": {
                "type": self.identity.type,
                "identity_file": self.identity.identity_file,
                "create_if_missing": self.identity.create_if_missing,
            },
            "dialogue": {
                "engine": self.dialogue.engine,
                "mode": self.dialogue.mode,
                "enable_meta_cognition": self.dialogue.enable_meta_cognition,
            },
            "logging": {
                "level": self.logging.level,
                "format": self.logging.format,
                "log_file": self.logging.log_file,
                "enable_console": self.logging.enable_console,
                "enable_audit": self.logging.enable_audit,
                "enable_performance": self.logging.enable_performance,
            },
            "debug": self.debug,
        }
