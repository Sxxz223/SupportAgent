"""Minimal runtime events for important support workflow changes."""
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RuntimeEvent:
    """Describe an important fact-producing action that occurred in a turn."""

    event_type: str
    turn_index: int
    data: dict[str, Any] = field(default_factory=dict)
