"""Validated model-to-application presentation contract."""
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class TaskDecision(ContractModel):
    type: Literal["single", "clarify", "propose_split", "confirmed"]
    candidateTasks: list[dict[str, str]] = Field(default_factory=list)


class TaskUpdate(ContractModel):
    taskId: str = Field(min_length=1)
    name: str = Field(min_length=1)
    stage: Literal[
        "confirmed", "collecting", "information_ready", "judgement_formed",
        "solution_provided", "waiting_confirmation", "completed", "cancelled",
    ]
    statusText: str = Field(min_length=1)
    revisionReason: str | None = None


class TaskCandidate(ContractModel):
    taskId: str = Field(min_length=1)
    name: str = Field(min_length=1)
    stage: Literal[
        "confirmed", "collecting", "information_ready", "judgement_formed",
        "solution_provided", "waiting_confirmation",
    ] = "confirmed"
    statusText: str = "已根据现有信息建立"


class TaskChange(ContractModel):
    changeId: str = Field(min_length=1)
    action: Literal["add", "split", "merge", "rename", "cancel"]
    status: Literal["proposed", "confirmed"]
    sourceTaskIds: list[str] = Field(default_factory=list)
    candidateTasks: list[TaskCandidate] = Field(default_factory=list)
    reason: str = Field(min_length=1)


class FocusPath(ContractModel):
    currentState: str = ""
    knownFacts: list[str] = Field(default_factory=list)
    currentJudgement: str = ""
    nextDirection: str = ""


class PlanStep(ContractModel):
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    status: Literal["done", "current", "pending"]


class SolutionPlan(ContractModel):
    steps: list[PlanStep] = Field(min_length=1, max_length=7)
    revision_note: str | None = None


class InteractionOption(ContractModel):
    id: str | None = None
    label: str = Field(min_length=1)
    value: str | None = None
    detail: str | None = None


class ImageRequest(ContractModel):
    enabled: bool
    label: str = "拍给 AI 看"
    target: str = ""
    fields: list[str] = Field(default_factory=list)
    guidance: list[str] = Field(default_factory=list, max_length=3)


class Interaction(ContractModel):
    type: Literal[
        "choice", "choice_image", "image", "text", "confirm", "split_confirm",
        "completion_confirm", "image_confirm", "partial_reshoot", "none",
    ]
    question: str | None = None
    options: list[InteractionOption] = Field(default_factory=list)
    image: ImageRequest | None = None
    image_prompt: str | None = None


class VisionField(ContractModel):
    key: str = Field(min_length=1)
    label: str = Field(min_length=1)
    value: Any = None
    status: Literal["recognized", "unclear", "failed"]
    source: str = "image"


class VisionResult(ContractModel):
    fields: list[VisionField] = Field(default_factory=list)
    followUp: dict[str, Any] | None = None
    conflicts: list[dict[str, Any]] = Field(default_factory=list)


class AgentStateView(ContractModel):
    emoji: str = Field(min_length=1, max_length=8)
    label: str = Field(min_length=1, max_length=24)


class EmotionState(ContractModel):
    state: Literal["calm", "neutral", "confused", "anxious", "frustrated"]
    trend: Literal["improving", "stable", "worsening"]


class ProactiveMessage(ContractModel):
    id: str = Field(min_length=1)
    content: str = Field(min_length=1)
    category: Literal[
        "supplement", "explanation", "reassurance", "encouragement",
        "followup", "reminder", "offer_help", "small_talk", "light_extension",
    ]
    priority: int = Field(default=0, ge=0, le=3)
    expiresInSeconds: int = Field(default=10, ge=1, le=300)
    delaySeconds: int = Field(default=3, ge=1, le=30)
    interaction: Interaction | None = None


FIELD_ADAPTERS = {
    "taskDecision": TypeAdapter(TaskDecision),
    "taskUpdates": TypeAdapter(list[TaskUpdate]),
    "taskChange": TypeAdapter(TaskChange),
    "focusPath": TypeAdapter(FocusPath),
    "plan": TypeAdapter(SolutionPlan),
    "interaction": TypeAdapter(Interaction),
    "visionResult": TypeAdapter(VisionResult),
    "agentState": TypeAdapter(AgentStateView),
    "emotionState": TypeAdapter(EmotionState),
    "proactiveMessages": TypeAdapter(list[ProactiveMessage]),
}


def validate_presentation(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate fields independently so one malformed optional view cannot poison a turn."""
    clean: dict[str, Any] = {}
    for key, adapter in FIELD_ADAPTERS.items():
        if key not in payload:
            continue
        try:
            value = adapter.validate_python(payload[key])
        except ValidationError:
            continue
        clean[key] = adapter.dump_python(value, mode="json", exclude_none=True)
        if key == "proactiveMessages":
            # One model call may plan a short, paced sequence. Keep it bounded,
            # ordered, and far enough apart to feel conversational.
            sequence = sorted(clean[key][:4], key=lambda item: item["delaySeconds"])
            previous_delay: int | None = None
            for item in sequence:
                if previous_delay is not None:
                    item["delaySeconds"] = max(item["delaySeconds"], previous_delay + 4)
                previous_delay = item["delaySeconds"]
            clean[key] = sequence
    if isinstance(payload.get("focusTaskId"), str):
        clean["focusTaskId"] = payload["focusTaskId"]
    if isinstance(payload.get("focusChanged"), bool):
        clean["focusChanged"] = payload["focusChanged"]
    if isinstance(payload.get("focusChangeReason"), str):
        clean["focusChangeReason"] = payload["focusChangeReason"]
    if isinstance(payload.get("factsUpdate"), dict):
        clean["factsUpdate"] = payload["factsUpdate"]
    return clean
