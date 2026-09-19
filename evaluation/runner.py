"""Execute fixed evaluation cases through the real process_turn boundary."""
from collections.abc import Callable, Iterable
from copy import deepcopy
import re
from time import perf_counter
from typing import Any

from .cases import resolve_image_path
from .evaluators import evaluate_case
from .models import CaseResult, EvaluationCase, SuiteResult
from ..application.session import SupportSession
from ..application.turn_processor import process_turn


ProcessTurn = Callable[..., str]
SessionFactory = Callable[[], SupportSession]


def _safe_error(error: Exception) -> str:
    message = str(error)[:300] or "Evaluation case execution failed."
    message = re.sub(r"(?i)bearer\s+\S+", "Bearer [redacted]", message)
    message = re.sub(r"\bsk-[A-Za-z0-9_-]+", "[redacted]", message)
    return f"{type(error).__name__}: {message}"


def _initialize_state(session: SupportSession, values: dict[str, Any]) -> None:
    """Apply declared initial facts without replacing the session State identity."""
    for key, value in values.items():
        if not hasattr(session.state, key):
            raise ValueError(f"Unknown initial SupportState field: {key}")
        setattr(session.state, key, deepcopy(value))


class EvaluationRunner:
    """Run cases independently and compare their resulting TurnTrace records."""

    def __init__(
        self,
        process_turn_fn: ProcessTurn = process_turn,
        session_factory: SessionFactory = SupportSession,
    ) -> None:
        self.process_turn_fn = process_turn_fn
        self.session_factory = session_factory

    def run_case(self, case: EvaluationCase) -> CaseResult:
        started = perf_counter()
        session = self.session_factory()
        error: str | None = None
        try:
            _initialize_state(session, case.initial_state)
            for evaluation_turn in case.turns:
                image = resolve_image_path(evaluation_turn)
                self.process_turn_fn(
                    session=session,
                    user_input=evaluation_turn.user_input,
                    image_path=str(image) if image is not None else None,
                )
        except Exception as exc:
            error = _safe_error(exc)

        duration_ms = round((perf_counter() - started) * 1000, 3)
        return evaluate_case(
            case,
            list(session.traces),
            error=error,
            duration_ms=duration_ms,
        )

    def run(self, cases: Iterable[EvaluationCase]) -> SuiteResult:
        started = perf_counter()
        results = [self.run_case(case) for case in cases]
        return SuiteResult(
            total=len(results),
            passed=sum(result.status == "PASS" for result in results),
            failed=sum(result.status == "FAIL" for result in results),
            known_limitations=sum(result.status == "KNOWN_LIMITATION" for result in results),
            errors=sum(result.status == "ERROR" for result in results),
            case_results=results,
            duration_ms=round((perf_counter() - started) * 1000, 3),
        )
