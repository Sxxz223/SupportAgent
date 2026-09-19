"""Human- and machine-readable Evaluation reports."""
from dataclasses import asdict
import json
from pathlib import Path
from typing import Any

from .models import CaseResult, SuiteResult


def _compact(value: Any, limit: int = 500) -> str:
    rendered = repr(value)
    return rendered if len(rendered) <= limit else f"{rendered[:limit]}..."


def format_case_result(result: CaseResult) -> str:
    lines = [
        "-" * 60,
        f"{result.case_id}  {result.case_name}",
        result.status,
        "",
    ]
    for check in result.checks:
        lines.append(f"{check.layer.title():<16} {check.status}")
        if check.passed is False:
            lines.extend([
                f"  {check.message}",
                f"  Expected: {_compact(check.expected)}",
                f"  Actual:   {_compact(check.actual)}",
            ])
    if result.first_failed_layer:
        lines.extend(["", f"First observed failed layer: {result.first_failed_layer}"])
    if result.error:
        lines.append(f"Execution error: {result.error}")
    lines.append(f"Turns traced: {result.turn_count}  Duration: {result.duration_ms:.3f}ms")
    return "\n".join(lines)


def format_suite_report(result: SuiteResult) -> str:
    header = [
        "=" * 60,
        "Agent Evaluation",
        "=" * 60,
        f"Total: {result.total}",
        f"Pass: {result.passed}",
        f"Fail: {result.failed}",
        f"Known Limitations: {result.known_limitations}",
        f"Errors: {result.errors}",
        f"Duration: {result.duration_ms:.3f}ms",
        "",
    ]
    return "\n".join(header + [format_case_result(item) for item in result.case_results])


def suite_to_dict(result: SuiteResult) -> dict[str, Any]:
    """Serialize only evaluation results and Trace IDs, never full Trace payloads."""
    return asdict(result)


def suite_to_json(result: SuiteResult, *, indent: int = 2) -> str:
    return json.dumps(suite_to_dict(result), indent=indent, ensure_ascii=False, default=str)


def write_json_report(result: SuiteResult, destination: str | Path) -> Path:
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(suite_to_json(result) + "\n", encoding="utf-8")
    return path
