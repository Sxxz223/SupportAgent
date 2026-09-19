"""Small data models describing one process_turn execution."""
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RetrievalChunkTrace:
    source: str
    score: float | None = None
    preview: str = ""


@dataclass
class VisionTrace:
    used: bool = False
    relevant: bool | None = None
    observation: str | None = None
    updated_fields: list[str] = field(default_factory=list)


@dataclass
class ToolCallTrace:
    tool_name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    success: bool = False
    result_summary: str = ""
    duration_ms: float = 0.0
    state_changed_fields: list[str] = field(default_factory=list)


@dataclass
class ErrorTrace:
    failed_stage: str
    error_type: str
    safe_error_message: str


@dataclass
class WorkflowTrace:
    stage: str
    next_action: str
    allowed_tools: list[str] = field(default_factory=list)


@dataclass
class AgentStepTrace:
    step_index: int
    workflow: WorkflowTrace
    state_before: dict[str, Any] = field(default_factory=dict)
    tool_calls: list[str] = field(default_factory=list)
    state_after: dict[str, Any] = field(default_factory=dict)


@dataclass
class TurnTrace:
    trace_id: str
    turn_index: int
    started_at: str
    user_input: str
    has_image: bool
    state_before: dict[str, Any] = field(default_factory=dict)
    extraction_result: dict[str, Any] = field(default_factory=dict)
    vision: VisionTrace = field(default_factory=VisionTrace)
    state_after_perception: dict[str, Any] = field(default_factory=dict)
    workflow_before_agent: WorkflowTrace | None = None
    workflow_after_tools: WorkflowTrace | None = None
    agent_steps: list[AgentStepTrace] = field(default_factory=list)
    rag_query: str | None = None
    retrieved_chunks: list[RetrievalChunkTrace] = field(default_factory=list)
    context_built: bool = False
    context_sections: list[str] = field(default_factory=list)
    agent_called: bool = False
    agent_final_reply: str | None = None
    tool_calls: list[ToolCallTrace] = field(default_factory=list)
    runtime_events: list[str] = field(default_factory=list)
    final_state: dict[str, Any] = field(default_factory=dict)
    final_answer: str | None = None
    final_stage: str | None = None
    error: ErrorTrace | None = None
    finished_at: str | None = None
    duration_ms: float | None = None
