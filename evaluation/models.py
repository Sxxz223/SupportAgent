"""Lightweight schemas for fixed Agent evaluation cases."""
from dataclasses import dataclass, field
from typing import Any


VALID_CATEGORIES = frozenset({
    "extraction",
    "workflow",
    "multi_turn",
    "retrieval",
    "vision",
    "tool",
    "boundary",
})


@dataclass(frozen=True)
class EvaluationTurn:
    """One user turn and its optional project-relative image fixture."""

    user_input: str
    image_path: str | None = None

    def __post_init__(self) -> None:
        if not self.user_input and self.image_path is None:
            raise ValueError("An evaluation turn needs text or an image")


@dataclass(frozen=True)
class FieldExpectation:
    """Describe a stable field requirement without forcing exact free text."""

    equals: Any = None
    contains_any: tuple[str, ...] = ()
    must_be_present: bool = False
    must_be_absent: bool = False

    def __post_init__(self) -> None:
        if (
            self.equals is None
            and not self.contains_any
            and not self.must_be_present
            and not self.must_be_absent
        ):
            raise ValueError("A field expectation must define at least one requirement")
        if self.must_be_present and self.must_be_absent:
            raise ValueError("A field cannot be both present and absent")


@dataclass(frozen=True)
class AnswerRequirements:
    """Minimal semantic cues for later answer evaluation; never an exact answer."""

    must_mention: tuple[str, ...] = ()
    must_not_mention: tuple[str, ...] = ()
    must_not_claim: tuple[str, ...] = ()


@dataclass(frozen=True)
class EvaluationExpectations:
    """Optional structured expectations consumed by the future T7.3 runner."""

    expected_state: dict[str, Any] = field(default_factory=dict)
    expected_state_fields: dict[str, FieldExpectation] = field(default_factory=dict)
    expected_extraction: dict[str, Any] = field(default_factory=dict)
    expected_extraction_fields: dict[str, FieldExpectation] = field(default_factory=dict)
    expected_stage: str | None = None
    expected_next_action_before_agent: str | None = None
    expected_allowed_tools_before_agent: tuple[str, ...] | None = None
    expected_tool_calls: tuple[str, ...] = ()
    forbidden_tools: tuple[str, ...] = ()
    expected_rag_sources: tuple[str, ...] = ()
    vision_used: bool | None = None
    expected_vision_fields: tuple[str, ...] = ()
    answer_requirements: AnswerRequirements = field(default_factory=AnswerRequirements)


@dataclass(frozen=True)
class EvaluationCase:
    """A stable scenario and its behavior-level expectations."""

    id: str
    name: str
    category: str
    description: str
    turns: tuple[EvaluationTurn, ...]
    expectations: EvaluationExpectations
    initial_state: dict[str, Any] = field(default_factory=dict)
    expected_pass: bool = True
    known_limitation: bool = False
    notes: str | None = None

    def __post_init__(self) -> None:
        if not self.id or not self.name or not self.description:
            raise ValueError("Evaluation cases require id, name, and description")
        if self.category not in VALID_CATEGORIES:
            raise ValueError(f"Unknown evaluation category: {self.category}")
        if not self.turns:
            raise ValueError("Evaluation cases require at least one turn")
        if self.known_limitation and self.expected_pass:
            raise ValueError("Known limitations must be marked expected_pass=False")


EVALUATION_LAYERS = (
    "extraction",
    "state",
    "workflow",
    "retrieval",
    "vision",
    "tool",
    "answer",
)


@dataclass
class CheckResult:
    name: str
    layer: str
    passed: bool | None
    status: str
    expected: Any = None
    actual: Any = None
    message: str = ""


@dataclass
class CaseResult:
    case_id: str
    case_name: str
    category: str
    passed: bool
    expected_pass: bool
    known_limitation: bool
    status: str
    checks: list[CheckResult] = field(default_factory=list)
    turn_count: int = 0
    first_failed_layer: str | None = None
    error: str | None = None
    trace_ids: list[str] = field(default_factory=list)
    duration_ms: float = 0.0


@dataclass
class SuiteResult:
    total: int
    passed: int
    failed: int
    known_limitations: int
    errors: int
    case_results: list[CaseResult] = field(default_factory=list)
    duration_ms: float = 0.0
