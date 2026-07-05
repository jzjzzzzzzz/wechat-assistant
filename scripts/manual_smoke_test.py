#!/usr/bin/env python
"""Interactive manual smoke-test runner."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.logger import setup_logger  # noqa: E402
from src.manual_smoke import print_manual_smoke_plan, run_manual_smoke_test  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run WeChat Assistant manual smoke checks.")
    parser.add_argument("--plan-only", action="store_true", help="Only print the manual test plan.")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Run confirmation-gated UI actions. Still does not enable real sending.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    setup_logger()
    print_manual_smoke_plan()
    if args.plan_only:
        return 0
    results = run_manual_smoke_test(assume_yes=args.yes)
    for result in results:
        status = "OK" if result.ok else "CHECK"
        print(f"[{status}] {result.name}: {result.message}")
    return 0 if all(result.ok for result in results if result.name != "permissions") else 1


if __name__ == "__main__":
    raise SystemExit(main())
