"""In-memory session and per-turn execution context."""
from dataclasses import dataclass, field
from typing import Any

from .events import RuntimeEvent
from ..trace.models import TurnTrace
from ..schemas.state import SupportState
from ..schemas.vision import VisionUpdate


@dataclass
class SupportSession:
    """Own the persistent business state and basic conversation history."""

    state: SupportState = field(default_factory=SupportState)
    history: list[dict[str, Any]] = field(default_factory=list)
    events: list[RuntimeEvent] = field(default_factory=list)
    traces: list[TurnTrace] = field(default_factory=list)
    turn_index: int = 0
    presentation: dict[str, Any] = field(default_factory=dict)
    proactive_events: list[dict[str, Any]] = field(default_factory=list)
    service_tasks: dict[str, dict[str, Any]] = field(default_factory=dict)
    focus_task_id: str | None = None
    focus_path: dict[str, Any] = field(default_factory=dict)
    vision_request: dict[str, Any] = field(default_factory=dict)
    _active_trace: TurnTrace | None = field(default=None, repr=False)

    def record_event(self, event_type: str, **data: Any) -> RuntimeEvent:
        """Append one important runtime event for the current turn."""
        event = RuntimeEvent(
            event_type=event_type,
            turn_index=self.turn_index,
            data=data,
        )
        self.events.append(event)
        return event


@dataclass
class TurnContext:
    """Hold transient values that belong only to one process_turn call."""

    user_input: str
    image_path: str | None = None
    vision_update: VisionUpdate | None = None
    retrieved_knowledge: str = ""
    next_action: str = ""
    allowed_tools: list[Any] = field(default_factory=list)
    allowed_tool_names: list[str] = field(default_factory=list)
    model_context: str = ""
