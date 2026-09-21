"""Thread-safe memory and SQLite stores for customer support cases."""
import json
import sqlite3
from contextlib import closing
from pathlib import Path
from threading import RLock
from uuid import uuid4

from ..application.session import SupportSession


class InMemorySessionStore:
    """Keep independent SupportSession objects for the life of one process."""

    def __init__(self) -> None:
        self._sessions: dict[str, SupportSession] = {}
        self._lock = RLock()

    def create_session(self) -> str:
        session_id = str(uuid4())
        with self._lock:
            self._sessions[session_id] = SupportSession()
        return session_id

    def get_session(self, session_id: str) -> SupportSession | None:
        with self._lock:
            return self._sessions.get(session_id)

    def save_session(self, session_id: str, session: SupportSession) -> None:
        with self._lock:
            self._sessions[session_id] = session


class SQLiteSessionStore(InMemorySessionStore):
    """Persist JSON-safe case snapshots while retaining active objects in memory."""

    def __init__(self, database_path: str | Path) -> None:
        super().__init__()
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS support_sessions (
                    session_id TEXT PRIMARY KEY,
                    snapshot_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            connection.commit()

    def _connect(self):
        connection = sqlite3.connect(self.database_path)
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    def create_session(self) -> str:
        session_id = str(uuid4())
        session = SupportSession()
        self.save_session(session_id, session)
        return session_id

    def get_session(self, session_id: str) -> SupportSession | None:
        with self._lock:
            cached = self._sessions.get(session_id)
            if cached is not None:
                return cached
            with closing(self._connect()) as connection:
                row = connection.execute(
                    "SELECT snapshot_json FROM support_sessions WHERE session_id = ?",
                    (session_id,),
                ).fetchone()
            if row is None:
                return None
            session = SupportSession()
            session.restore_case(json.loads(row[0]))
            self._sessions[session_id] = session
            return session

    def save_session(self, session_id: str, session: SupportSession) -> None:
        snapshot = json.dumps(session.case_snapshot(), ensure_ascii=False)
        with self._lock:
            self._sessions[session_id] = session
            with closing(self._connect()) as connection:
                connection.execute("""
                    INSERT INTO support_sessions(session_id, snapshot_json, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(session_id) DO UPDATE SET
                        snapshot_json = excluded.snapshot_json,
                        updated_at = CURRENT_TIMESTAMP
                """, (session_id, snapshot))
                connection.commit()
