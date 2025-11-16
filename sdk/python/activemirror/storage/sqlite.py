"""
SQLite storage backend.
"""

import json
import sqlite3
from pathlib import Path
from typing import List, Optional

from activemirror.storage.base import StorageBackend
from activemirror.core.message import Message
from activemirror.exceptions import StorageError


class SQLiteStorage(StorageBackend):
    """
    SQLite storage backend.

    Stores sessions and messages in a local SQLite database.
    """

    def __init__(self, db_path: str = "./data/memories.db", enable_wal: bool = True):
        """
        Initialize SQLite storage.

        Args:
            db_path: Path to SQLite database file
            enable_wal: Enable Write-Ahead Logging for better concurrency
        """
        self.db_path = Path(db_path)

        # Create directory if needed
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize database
        self._init_db()

        # Enable WAL mode if requested
        if enable_wal:
            with self._get_connection() as conn:
                conn.execute("PRAGMA journal_mode=WAL")

    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Initialize database schema."""
        with self._get_connection() as conn:
            # Sessions table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    parent_session_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    metadata TEXT
                )
                """
            )

            # Messages table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    metadata TEXT,
                    FOREIGN KEY (session_id) REFERENCES sessions(id)
                )
                """
            )

            # Create indexes
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_messages_session_id
                ON messages(session_id)
                """
            )

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_sessions_user_id
                ON sessions(user_id)
                """
            )

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_sessions_updated_at
                ON sessions(updated_at DESC)
                """
            )

            conn.commit()

    def save_session(self, session) -> str:
        """Save a session to SQLite."""
        try:
            with self._get_connection() as conn:
                session_dict = session.to_dict()

                conn.execute(
                    """
                    INSERT OR REPLACE INTO sessions
                    (id, user_id, title, parent_session_id, created_at,
                     updated_at, status, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        session_dict["id"],
                        session_dict["user_id"],
                        session_dict["title"],
                        session_dict.get("parent_session_id"),
                        session_dict["created_at"],
                        session_dict["updated_at"],
                        session_dict["status"],
                        json.dumps(session_dict.get("metadata", {})),
                    ),
                )

                conn.commit()

            return session.id

        except sqlite3.Error as e:
            raise StorageError(f"Failed to save session: {e}")

    def load_session(self, session_id: str):
        """Load a session from SQLite."""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT id, user_id, title, parent_session_id,
                           created_at, updated_at, status, metadata
                    FROM sessions
                    WHERE id = ?
                    """,
                    (session_id,),
                )

                row = cursor.fetchone()

                if not row:
                    return None

                # Get messages for session
                messages = self.get_messages(session_id)

                # Build session data
                session_data = {
                    "id": row["id"],
                    "user_id": row["user_id"],
                    "title": row["title"],
                    "parent_session_id": row["parent_session_id"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "status": row["status"],
                    "metadata": json.loads(row["metadata"] or "{}"),
                    "messages": [msg.to_dict() for msg in messages],
                    "message_count": len(messages),
                }

                # Import here to avoid circular dependency
                from activemirror.core.session import Session

                return Session.from_dict(session_data, storage_backend=self)

        except sqlite3.Error as e:
            raise StorageError(f"Failed to load session: {e}")

    def save_message(self, message: Message) -> str:
        """Save a message to SQLite."""
        try:
            with self._get_connection() as conn:
                msg_dict = message.to_dict()

                conn.execute(
                    """
                    INSERT OR REPLACE INTO messages
                    (id, session_id, role, content, timestamp, metadata)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        msg_dict["id"],
                        msg_dict["session_id"],
                        msg_dict["role"],
                        msg_dict["content"],
                        msg_dict["timestamp"],
                        json.dumps(msg_dict.get("metadata", {})),
                    ),
                )

                conn.commit()

            return message.id

        except sqlite3.Error as e:
            raise StorageError(f"Failed to save message: {e}")

    def get_messages(
        self, session_id: str, limit: Optional[int] = None, offset: int = 0
    ) -> List[Message]:
        """Get messages for a session from SQLite."""
        try:
            with self._get_connection() as conn:
                query = """
                    SELECT id, session_id, role, content, timestamp, metadata
                    FROM messages
                    WHERE session_id = ?
                    ORDER BY timestamp ASC
                """
                params = [session_id]

                if limit:
                    query += " LIMIT ? OFFSET ?"
                    params.extend([limit, offset])

                cursor = conn.execute(query, params)

                messages = []
                for row in cursor.fetchall():
                    msg_data = {
                        "id": row["id"],
                        "session_id": row["session_id"],
                        "role": row["role"],
                        "content": row["content"],
                        "timestamp": row["timestamp"],
                        "metadata": json.loads(row["metadata"] or "{}"),
                    }
                    messages.append(Message.from_dict(msg_data))

                return messages

        except sqlite3.Error as e:
            raise StorageError(f"Failed to get messages: {e}")

    def list_sessions(
        self, user_id: Optional[str] = None, limit: int = 100, offset: int = 0
    ) -> List:
        """List sessions from SQLite."""
        try:
            from activemirror.core.mirror import SessionMetadata

            with self._get_connection() as conn:
                if user_id:
                    query = """
                        SELECT s.id, s.title, s.created_at, s.updated_at,
                               COUNT(m.id) as message_count
                        FROM sessions s
                        LEFT JOIN messages m ON s.id = m.session_id
                        WHERE s.user_id = ?
                        GROUP BY s.id
                        ORDER BY s.updated_at DESC
                        LIMIT ? OFFSET ?
                    """
                    cursor = conn.execute(query, (user_id, limit, offset))
                else:
                    query = """
                        SELECT s.id, s.title, s.created_at, s.updated_at,
                               COUNT(m.id) as message_count
                        FROM sessions s
                        LEFT JOIN messages m ON s.id = m.session_id
                        GROUP BY s.id
                        ORDER BY s.updated_at DESC
                        LIMIT ? OFFSET ?
                    """
                    cursor = conn.execute(query, (limit, offset))

                sessions = []
                for row in cursor.fetchall():
                    metadata = SessionMetadata(
                        session_id=row["id"],
                        title=row["title"],
                        created_at=row["created_at"],
                        updated_at=row["updated_at"],
                        message_count=row["message_count"],
                    )
                    sessions.append(metadata)

                return sessions

        except sqlite3.Error as e:
            raise StorageError(f"Failed to list sessions: {e}")

    def delete_session(self, session_id: str) -> bool:
        """Delete a session from SQLite."""
        try:
            with self._get_connection() as conn:
                # Delete messages first (foreign key constraint)
                conn.execute(
                    "DELETE FROM messages WHERE session_id = ?", (session_id,)
                )

                # Delete session
                conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))

                conn.commit()

            return True

        except sqlite3.Error as e:
            raise StorageError(f"Failed to delete session: {e}")
