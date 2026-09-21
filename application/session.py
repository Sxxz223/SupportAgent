"""In-memory session and per-turn execution context."""
from dataclasses import asdict, dataclass, field
from typing import Any

from .events import RuntimeEvent
from ..trace.models import TurnTrace
from ..schemas.state import SupportState
from ..schemas.vision import VisionUpdate
from ..schemas.case import CaseFact

CONFLICT_SENSITIVE_FACTS = {
    "target_device", "symptom", "current_port", "power_reading",
    "product_model", "safety_signals",
}


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
    emotion_history: list[dict[str, Any]] = field(default_factory=list)
    interaction_state: dict[str, Any] = field(default_factory=dict)
    behavior_state: dict[str, Any] = field(default_factory=lambda: {
        "activityVersion": 0,
        "introductionShown": False,
        "lastActivity": "session_created",
        "lastProactiveCategory": None,
        "proactiveCount": 0,
    })
    service_tasks: dict[str, dict[str, Any]] = field(default_factory=dict)
    task_history: list[dict[str, Any]] = field(default_factory=list)
    focus_task_id: str | None = None
    focus_history: list[dict[str, Any]] = field(default_factory=list)
    path_history: list[dict[str, Any]] = field(default_factory=list)
    focus_path: dict[str, Any] = field(default_factory=dict)
    focus_plan: dict[str, Any] = field(default_factory=dict)
    pending_task_change: str | None = None
    pending_fact_conflicts: dict[str, dict[str, Any]] = field(default_factory=dict)
    vision_request: dict[str, Any] = field(default_factory=dict)
    pending_vision_fields: dict[str, dict[str, Any]] = field(default_factory=dict)
    pending_reshoot_target: str | None = None
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
        kind: str = "context", detect_conflict: bool = False,
    ) -> bool:
        if value is None:
            return False
        turn_id = f"turn_{self.turn_index:03d}"
        next_version = self.case_version + 1
        current = self.facts.get(key)
        if current is not None and current.value == value and current.confirmed and not confirmed:
            return True
        if (
            detect_conflict and key in CONFLICT_SENSITIVE_FACTS and current is not None
            and current.value != value
        ):
            self.pending_fact_conflicts[key] = {
                "key": key, "previous": current.value, "incoming": value,
                "incomingSource": source, "kind": kind,
            }
            return False
        if current is None:
            self.facts[key] = CaseFact(
                key=key, value=value, source=source, confirmed=confirmed,
                turn_id=turn_id, case_version=next_version, kind=kind,
            )
        else:
            current.replace(value, source, confirmed, turn_id, next_version, kind)
        return True

    def resolve_fact_conflict(self, user_input: str) -> tuple[str, Any] | None:
        normalized = user_input.strip().casefold()
        for key, conflict in list(self.pending_fact_conflicts.items()):
            choices = (conflict["previous"], conflict["incoming"])
            for value in choices:
                if normalized == str(value).strip().casefold():
                    self.upsert_fact(
                        key, value, "user_confirmation", confirmed=True,
                        kind=conflict.get("kind", "observation"),
                    )
                    del self.pending_fact_conflicts[key]
                    self.pending_vision_fields.pop(key, None)
                    return key, value
        return None

    def stage_vision_result(self, fields: list[Any], reshoot_target: str | None) -> None:
        for field_value in fields:
            data = field_value.model_dump(mode="json") if hasattr(field_value, "model_dump") else dict(field_value)
            self.pending_vision_fields[data["key"]] = data
            current = self.facts.get(data["key"])
            if (
                data.get("status") == "recognized" and current is not None
                and current.value != data.get("value")
            ):
                self.pending_fact_conflicts[data["key"]] = {
                    "key": data["key"], "previous": current.value,
                    "incoming": data.get("value"), "incomingSource": "image_analysis",
                    "kind": "observation",
                }
        self.pending_reshoot_target = reshoot_target

    def resolve_vision_confirmation(self, user_input: str) -> str | None:
        normalized = user_input.strip().casefold()
        if normalized in {"vision_confirm", "识别正确", "确认识别结果"}:
            for key, field_value in self.pending_vision_fields.items():
                if field_value.get("status") == "recognized":
                    self.upsert_fact(
                        key, field_value.get("value"), "image_confirmed",
                        confirmed=True, kind="observation", detect_conflict=True,
                    )
            self.pending_vision_fields = {}
            self.pending_reshoot_target = None
            return "confirmed"
        if normalized in {"vision_reject", "有错误", "识别有误"}:
            self.pending_vision_fields = {}
            self.pending_reshoot_target = None
            return "rejected"
        return None

    def case_snapshot(self) -> dict[str, Any]:
        """Return the complete JSON-safe customer-service case."""
        return {
            "turnId": f"turn_{self.turn_index:03d}",
            "caseVersion": self.case_version,
            "state": asdict(self.state),
            "history": self.history,
            "facts": {key: fact.to_dict() for key, fact in self.facts.items()},
            "tasks": list(self.service_tasks.values()),
            "taskHistory": self.task_history,
            "focusTaskId": self.focus_task_id,
            "focusHistory": self.focus_history,
            "pathHistory": self.path_history,
            "focusPath": self.focus_path,
            "plan": self.focus_plan,
            "interaction": self.presentation.get("interaction", {}),
            "emotionState": self.presentation.get("emotionState", {}),
            "agentState": self.presentation.get("agentState", {}),
            "visionRequest": self.vision_request,
            "pendingTaskChange": self.pending_task_change,
            "pendingFactConflicts": self.pending_fact_conflicts,
            "pendingVisionFields": self.pending_vision_fields,
            "pendingReshootTarget": self.pending_reshoot_target,
            "proactiveEvents": self.proactive_events,
            "emotionHistory": self.emotion_history,
            "interactionState": self.interaction_state,
            "behaviorState": self.behavior_state,
        }

    def restore_case(self, snapshot: dict[str, Any]) -> None:
        """Restore the UI/service portion of a previously serialized case."""
        self.case_version = int(snapshot.get("caseVersion", 0))
        state_data = snapshot.get("state")
        if isinstance(state_data, dict):
            self.state = SupportState(**state_data)
        self.history = list(snapshot.get("history") or [])
        turn_id = str(snapshot.get("turnId", "turn_000"))
        try:
            self.turn_index = int(turn_id.rsplit("_", 1)[1])
        except (IndexError, ValueError):
            self.turn_index = 0
        self.facts = {
            key: CaseFact.from_dict(value)
            for key, value in snapshot.get("facts", {}).items()
        }
        self.service_tasks = {
            task["taskId"]: dict(task)
            for task in snapshot.get("tasks", []) if task.get("taskId")
        }
        self.task_history = list(snapshot.get("taskHistory") or [])
        self.focus_task_id = snapshot.get("focusTaskId")
        self.focus_history = list(snapshot.get("focusHistory") or [])
        self.path_history = list(snapshot.get("pathHistory") or [])
        self.focus_path = dict(snapshot.get("focusPath") or {})
        self.focus_plan = dict(snapshot.get("plan") or {})
        self.vision_request = dict(snapshot.get("visionRequest") or {})
        self.pending_task_change = snapshot.get("pendingTaskChange")
        self.pending_fact_conflicts = dict(snapshot.get("pendingFactConflicts") or {})
        self.pending_vision_fields = dict(snapshot.get("pendingVisionFields") or {})
        self.pending_reshoot_target = snapshot.get("pendingReshootTarget")
        self.proactive_events = list(snapshot.get("proactiveEvents") or [])
        self.emotion_history = list(snapshot.get("emotionHistory") or [])
        self.interaction_state = dict(snapshot.get("interactionState") or {})
        self.behavior_state = dict(snapshot.get("behaviorState") or {
            "activityVersion": 0, "introductionShown": False,
            "lastActivity": "session_created", "lastProactiveCategory": None,
            "proactiveCount": 0,
        })
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
