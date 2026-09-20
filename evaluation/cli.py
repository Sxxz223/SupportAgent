"""Command-line entry point for live Agent evaluation."""
import argparse

from .cases import EVALUATION_CASES
from .models import VALID_CATEGORIES
from .report import format_suite_report, write_json_report
from .runner import EvaluationRunner


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run fixed support Agent evaluations.")
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--case", help="Run one case by ID, for example case_08.")
    selection.add_argument("--category", choices=sorted(VALID_CATEGORIES))
    selection.add_argument("--all", action="store_true", help="Run all fixed cases.")
    parser.add_argument("--json", metavar="PATH", help="Also write a machine-readable report.")
    return parser


def select_cases(args: argparse.Namespace):
    if args.case:
        selected = [case for case in EVALUATION_CASES if case.id == args.case]
        if not selected:
            raise ValueError(f"Unknown evaluation case: {args.case}")
        return selected
    if args.category:
        return [case for case in EVALUATION_CASES if case.category == args.category]
    return list(EVALUATION_CASES)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        cases = select_cases(args)
    except ValueError as error:
        parser.error(str(error))

    result = EvaluationRunner().run(cases)
    print(format_suite_report(result))
    if args.json:
        path = write_json_report(result, args.json)
        print(f"\nJSON report: {path}")
    return 1 if result.failed or result.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
