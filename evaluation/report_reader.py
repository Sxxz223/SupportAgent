"""Read an existing Evaluation JSON report without running evaluations."""
import json
from pathlib import Path
from typing import Any, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT_PATH = PROJECT_ROOT / "evaluation_results.json"
SUMMARY_FIELDS = (
    "total",
    "passed",
    "failed",
    "known_limitations",
    "errors",
    "duration_ms",
)


class EvaluationReportNotFoundError(FileNotFoundError):
    """Raised when no generated Evaluation report is available."""


class InvalidEvaluationReportError(ValueError):
    """Raised when a report cannot be read as the expected JSON object."""


def load_latest_report(path: str | Path = DEFAULT_REPORT_PATH) -> dict[str, Any]:
    """Load the generated report from disk without executing Evaluation Runner."""
    report_path = Path(path)
    try:
        content = report_path.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        raise EvaluationReportNotFoundError(report_path) from error
    except (OSError, UnicodeError) as error:
        raise InvalidEvaluationReportError("Evaluation report is unreadable") from error

    try:
        report = json.loads(content)
    except json.JSONDecodeError as error:
        raise InvalidEvaluationReportError("Evaluation report is invalid") from error

    if not isinstance(report, dict):
        raise InvalidEvaluationReportError("Evaluation report must be a JSON object")
    return report


def get_report_summary(report: Mapping[str, Any]) -> dict[str, Any]:
    """Select the report's existing aggregate fields without recalculating them."""
    missing = [field for field in SUMMARY_FIELDS if field not in report]
    if missing:
        raise InvalidEvaluationReportError("Evaluation report is missing summary fields")
    return {field: report[field] for field in SUMMARY_FIELDS}
