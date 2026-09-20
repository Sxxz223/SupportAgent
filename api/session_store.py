"""Thread-safe in-memory mapping from public IDs to support sessions."""
from threading import RLock
from uuid import uuid4

from application.session import SupportSession


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
