"""Fault-tolerant helpers for recording and formatting turn traces."""
from collections.abc import Callable
from dataclasses import asdict
from datetime import datetime, timezone
import re
from time import perf_counter
from typing import Any, TypeVar
from uuid import uuid4

from .models import (
    AgentStepTrace, ErrorTrace, RetrievalChunkTrace, ToolCallTrace, TurnTrace, VisionTrace,
    WorkflowTrace,
)
from schemas.state import SupportState


STATE_FIELDS = (
    "user_name", "customer_id", "identity_verified", "product", "product_id",
    "owned_products", "ownership_lookup_completed", "issue",
    "stage", "attempted_steps", "resolved",
    "diagnostic_facts",
    "warranty_status", "ticket_id", "image_received", "dock_visible",
    "indicator_on", "contacts_dirty", "robot_on_dock",
)
SENSITIVE_KEY_PARTS = ("api_key", "authorization", "token", "secret", "password")
T = TypeVar("T")


def snapshot_state(state: SupportState) -> dict[str, Any]:
    """Copy the selected business facts so later mutations cannot alter a trace."""
    snapshot: dict[str, Any] = {}
    for name in STATE_FIELDS:
        value = getattr(state, name, None)
        snapshot[name] = list(value) if isinstance(value, list) else value
    return snapshot


def _safe_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value[:240]
    return str(value)[:240]


def _safe_arguments(arguments: dict[str, Any]) -> dict[str, Any]:
    return {
        key: "[redacted]" if any(part in key.lower() for part in SENSITIVE_KEY_PARTS)
        else _safe_value(value)
        for key, value in arguments.items()
    }


def _safe_error_message(error: Exception) -> str:
    message = str(error)[:240] or "The operation failed."
    message = re.sub(r"(?i)bearer\s+\S+", "Bearer [redacted]", message)
    message = re.sub(r"\bsk-[A-Za-z0-9_-]+", "[redacted]", message)
    return message


def parse_retrieval_results(text: str) -> list[RetrievalChunkTrace]:
    """Extract bounded metadata from the existing formatted RAG output."""
    chunks: list[RetrievalChunkTrace] = []
    pattern = re.compile(
        r"\[Score: ([^\]]+)\]\n\[Source: ([^\]]+)\]\n(.*?)(?=\n\n\[Score:|\Z)",
        re.DOTALL,
    )
    for score_text, source, content in pattern.findall(text):
        try:
            score = float(score_text)
        except ValueError:
            score = None
        preview = " ".join(content.split())[:180]
        chunks.append(RetrievalChunkTrace(source=source, score=score, preview=preview))
    return chunks


class TraceRecorder:
    """Record one turn without allowing trace failures to break the turn."""

    def __init__(self, session: Any, user_input: str, has_image: bool) -> None:
        self.session = session
        self._started = perf_counter()
        self._event_start = len(session.events)
        self.trace = TurnTrace(
            trace_id=str(uuid4()),
            turn_index=session.turn_index,
            started_at=datetime.now(timezone.utc).isoformat(),
            user_input=user_input[:2000],
            has_image=has_image,
            state_before=snapshot_state(session.state),
        )
        try:
            session.traces.append(self.trace)
            session._active_trace = self.trace
        except Exception:
            pass

    def record_extraction(self, update: Any) -> None:
        try:
            data = update.model_dump() if hasattr(update, "model_dump") else asdict(update)
            self.trace.extraction_result = {key: _safe_value(value) for key, value in data.items()}
        except Exception:
            pass

    def record_vision(self, update: Any, before: dict[str, Any], after: dict[str, Any]) -> None:
        try:
            changed = [key for key in STATE_FIELDS if before.get(key) != after.get(key)]
            values = update.model_dump() if hasattr(update, "model_dump") else {}
            relevant_values = [value for key, value in values.items() if key != "observation"]
            self.trace.vision = VisionTrace(
                used=True,
                relevant=any(value is not None for value in relevant_values),
                observation=_safe_value(values.get("observation")),
                updated_fields=changed,
            )
        except Exception:
            pass

    def record_perception_state(self, state: SupportState) -> None:
        try:
            self.trace.state_after_perception = snapshot_state(state)
        except Exception:
            pass

    def record_workflow_before_agent(
        self, stage: str, next_action: str, allowed_tools: list[str]
    ) -> None:
        try:
            self.trace.workflow_before_agent = WorkflowTrace(
                stage=stage, next_action=next_action, allowed_tools=list(allowed_tools)
            )
        except Exception:
            pass

    def record_workflow_after_tools(
        self, stage: str, next_action: str, allowed_tools: list[str]
    ) -> None:
        try:
            self.trace.workflow_after_tools = WorkflowTrace(
                stage=stage, next_action=next_action, allowed_tools=list(allowed_tools)
            )
        except Exception:
            pass

    def record_retrieval(self, query: str, result: str) -> None:
        try:
            self.trace.rag_query = query[:500]
            self.trace.retrieved_chunks = parse_retrieval_results(result)
        except Exception:
            pass

    def record_context(self, sections: list[str]) -> None:
        try:
            self.trace.context_built = True
            self.trace.context_sections = list(sections)
        except Exception:
            pass

    def record_agent_called(self) -> None:
        try:
            self.trace.agent_called = True
        except Exception:
            pass

    def record_agent_step(
        self, step_index: int, stage: str, next_action: str,
        allowed_tools: list[str], state_before: dict[str, Any],
        tool_calls: list[str], state_after: dict[str, Any],
    ) -> None:
        try:
            self.trace.agent_steps.append(AgentStepTrace(
                step_index=step_index,
                workflow=WorkflowTrace(stage, next_action, list(allowed_tools)),
                state_before=state_before,
                tool_calls=list(tool_calls),
                state_after=state_after,
            ))
        except Exception:
            pass

    def record_agent_reply(self, reply: str) -> None:
        try:
            self.trace.agent_final_reply = reply[:4000]
        except Exception:
            pass

    def fail(self, failed_stage: str, error: Exception) -> None:
        try:
            self.trace.error = ErrorTrace(
                failed_stage=failed_stage,
                error_type=type(error).__name__,
                safe_error_message=_safe_error_message(error),
            )
        except Exception:
            pass

    def finish(self, state: SupportState, final_answer: str | None = None) -> None:
        try:
            self.trace.final_state = snapshot_state(state)
            self.trace.final_stage = state.stage
            if final_answer is not None:
                self.trace.final_answer = final_answer[:4000]
            self.trace.runtime_events = [
                event.event_type for event in self.session.events[self._event_start:]
            ]
            self.trace.finished_at = datetime.now(timezone.utc).isoformat()
            self.trace.duration_ms = round((perf_counter() - self._started) * 1000, 3)
        except Exception:
            pass
        finally:
            try:
                self.session._active_trace = None
            except Exception:
                pass


def trace_tool_call(
    session: Any,
    tool_name: str,
    arguments: dict[str, Any],
    operation: Callable[[], T],
) -> T:
    """Run a tool operation once and append a safe summary to the active trace."""
    trace = getattr(session, "_active_trace", None)
    started = perf_counter()
    try:
        before = snapshot_state(session.state)
    except Exception:
        before = {}

    try:
        result = operation()
    except Exception as error:
        if trace is not None:
            try:
                trace.tool_calls.append(ToolCallTrace(
                    tool_name=tool_name,
                    arguments=_safe_arguments(arguments),
                    success=False,
                    result_summary=_safe_error_message(error),
                    duration_ms=round((perf_counter() - started) * 1000, 3),
                ))
            except Exception:
                pass
        raise

    if trace is not None:
        try:
            after = snapshot_state(session.state)
            trace.tool_calls.append(ToolCallTrace(
                tool_name=tool_name,
                arguments=_safe_arguments(arguments),
                success=True,
                result_summary=str(result)[:240],
                duration_ms=round((perf_counter() - started) * 1000, 3),
                state_changed_fields=[
                    key for key in STATE_FIELDS if before.get(key) != after.get(key)
                ],
            ))
        except Exception:
            pass
    return result


def format_trace(trace: TurnTrace) -> str:
    """Render one trace as a compact developer-readable report."""
    def state_lines(snapshot: dict[str, Any]) -> list[str]:
        return [f"{key}: {value}" for key, value in snapshot.items() if value not in (None, [], False)] or ["no known facts"]

    extraction = [
        f"{key}: {value}" for key, value in trace.extraction_result.items() if value is not None
    ] or ["no new fields"]
    vision = (
        [f"observation: {trace.vision.observation or 'none'}",
         f"updated_fields: {', '.join(trace.vision.updated_fields) or 'none'}"]
        if trace.vision.used else ["not used"]
    )
    retrieval = [
        f"{index}. {chunk.source} score={chunk.score if chunk.score is not None else 'unknown'}"
        for index, chunk in enumerate(trace.retrieved_chunks, 1)
    ] or ["not used or no parsed results"]
    tools = [
        f"{tool.tool_name}({tool.arguments}) -> {'ok' if tool.success else 'failed'}: {tool.result_summary}"
        for tool in trace.tool_calls
    ] or ["none"]
    steps = []
    for step in trace.agent_steps:
        steps.extend([
            f"STEP {step.step_index}",
            f"stage: {step.workflow.stage}",
            f"next_action: {step.workflow.next_action}",
            f"allowed_tools: {', '.join(step.workflow.allowed_tools) or 'none'}",
            f"tool_calls: {', '.join(step.tool_calls) or 'none'}",
            f"state_after: {step.state_after}",
        ])
    if not steps:
        steps = ["none"]
    before = trace.workflow_before_agent
    after = trace.workflow_after_tools
    before_lines = [
        f"stage: {before.stage if before else 'not recorded'}",
        f"next_action: {before.next_action if before else 'not recorded'}",
        f"allowed_tools: {', '.join(before.allowed_tools) if before and before.allowed_tools else 'none'}",
    ]
    after_lines = [
        f"stage: {after.stage if after else 'not recorded'}",
        f"next_action: {after.next_action if after else 'not recorded'}",
        f"allowed_tools: {', '.join(after.allowed_tools) if after and after.allowed_tools else 'none'}",
    ]
    error = [] if trace.error is None else [
        "", "ERROR", f"{trace.error.failed_stage}: {trace.error.error_type}: {trace.error.safe_error_message}"
    ]
    lines = [
        f"TURN {trace.turn_index}  trace_id={trace.trace_id}", "-" * 48,
        "", "INPUT", repr(trace.user_input),
        "", "STATE BEFORE", *state_lines(trace.state_before),
        "", "EXTRACTION", *extraction,
        "", "VISION", *vision,
        "", "WORKFLOW BEFORE AGENT", *before_lines,
        "", "RAG", f"query: {trace.rag_query or 'not used'}", *retrieval,
        "", "TOOL CALLS", *tools,
        "", "AGENT STEPS", *steps,
        "", "WORKFLOW AFTER TOOLS", *after_lines,
        "", "FINAL STATE", *state_lines(trace.final_state),
        "", "FINAL ANSWER", trace.final_answer or "none",
        "", "DURATION", f"{trace.duration_ms if trace.duration_ms is not None else 'unknown'}ms",
        *error,
    ]
    return "\n".join(lines)
