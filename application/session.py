"""In-memory session and per-turn execution context."""
from dataclasses import dataclass, field
from typing import Any

from .events import RuntimeEvent
from ..trace.models import TurnTrace
from ..schemas.state import SupportState
from ..schemas.vision import VisionUpdate
from ..schemas.case import CaseFact


@dataclass
class SupportSession:
    """Own the persistent business state and basic conversation history."""

    state: SupportState = field(default_factory=SupportState)
    history: list[dict[str, Any]] = field(default_factory=list)
    events: list[RuntimeEvent] = field(default_factory=list)
    traces: list[TurnTrace] = field(default_factory=list)
    turn_index: int = 0
    case_version: int = 0
    facts: dict[str, CaseFact] = field(default_factory=dict)
    presentation: dict[str, Any] = field(default_factory=dict)
    proactive_events: list[dict[str, Any]] = field(default_factory=list)
    service_tasks: dict[str, dict[str, Any]] = field(default_factory=dict)
    focus_task_id: str | None = None
    focus_path: dict[str, Any] = field(default_factory=dict)
    focus_plan: dict[str, Any] = field(default_factory=dict)
    pending_task_change: str | None = None
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

    def upsert_fact(
        self, key: str, value: Any, source: str, confirmed: bool = False,
        kind: str = "context",
    ) -> None:
        if value is None:
            return
        turn_id = f"turn_{self.turn_index:03d}"
        next_version = self.case_version + 1
        current = self.facts.get(key)
        if current is None:
            self.facts[key] = CaseFact(
                key=key, value=value, source=source, confirmed=confirmed,
                turn_id=turn_id, case_version=next_version, kind=kind,
            )
        else:
            current.replace(value, source, confirmed, turn_id, next_version, kind)

    def case_snapshot(self) -> dict[str, Any]:
        """Return the complete JSON-safe customer-service case."""
        return {
            "turnId": f"turn_{self.turn_index:03d}",
            "caseVersion": self.case_version,
            "facts": {key: fact.to_dict() for key, fact in self.facts.items()},
            "tasks": list(self.service_tasks.values()),
            "focusTaskId": self.focus_task_id,
            "focusPath": self.focus_path,
            "plan": self.focus_plan,
            "interaction": self.presentation.get("interaction", {}),
            "emotionState": self.presentation.get("emotionState", {}),
            "agentState": self.presentation.get("agentState", {}),
            "visionRequest": self.vision_request,
            "pendingTaskChange": self.pending_task_change,
        }

    def restore_case(self, snapshot: dict[str, Any]) -> None:
        """Restore the UI/service portion of a previously serialized case."""
        self.case_version = int(snapshot.get("caseVersion", 0))
        self.facts = {
            key: CaseFact.from_dict(value)
            for key, value in snapshot.get("facts", {}).items()
        }
        self.service_tasks = {
            task["taskId"]: dict(task)
            for task in snapshot.get("tasks", []) if task.get("taskId")
        }
        self.focus_task_id = snapshot.get("focusTaskId")
        self.focus_path = dict(snapshot.get("focusPath") or {})
        self.focus_plan = dict(snapshot.get("plan") or {})
        self.vision_request = dict(snapshot.get("visionRequest") or {})
        self.pending_task_change = snapshot.get("pendingTaskChange")
        self.presentation = {
            key: snapshot[key] for key in ("interaction", "emotionState", "agentState")
            if snapshot.get(key)
        }


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
