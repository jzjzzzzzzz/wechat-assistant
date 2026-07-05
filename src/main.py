"""Command-line entry point for WeChat Assistant."""

from __future__ import annotations

import argparse
import sys

from src.config_loader import ConfigError, load_config
from src.logger import setup_logger
from src.mac_permissions import run_environment_checks


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="wechat-assistant")
    parser.add_argument(
        "command",
        choices=[
            "check",
            "screenshot",
            "test-send",
            "ocr",
            "scan-contacts",
            "birthday-check",
            "send-birthday",
            "gui",
            "manual-test",
        ],
        help="Command to run",
    )
    parser.add_argument("--plan-only", action="store_true", help="Only print the manual smoke-test plan.")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Run confirmation-gated manual smoke-test UI actions. Does not enable real sending.",
    )
    parser.add_argument(
        "--contact",
        default=None,
        help="Contact name to force-send birthday message to (send-birthday only).",
    )
    return parser


def run_command(command: str, *, plan_only: bool = False, assume_yes: bool = False, contact: str | None = None) -> int:
    try:
        config = load_config()
    except ConfigError as exc:
        setup_logger().error("Configuration error: %s", exc)
        return 2

    logger = setup_logger(log_file=config["log_file"])
    logger.info("Running command: %s", command)

    if command == "check":
        results = run_environment_checks()
        return 0 if all(result.ok for result in results) else 1

    if command == "screenshot":
        from src.screenshot import capture_screenshot

        path = capture_screenshot(config)
        print(path if path else "Screenshot failed. Check logs/app.log.")
        return 0 if path else 1

    if command == "test-send":
        from src.message_sender import send_test_message

        return 0 if send_test_message(config) else 1

    if command == "ocr":
        from src.ocr_reader import read_latest_screenshot_text

        results = read_latest_screenshot_text(config)
        for item in results:
            print(item)
        return 0

    if command == "scan-contacts":
        from src.contact_scanner import scan_contacts

        contacts = scan_contacts(config)
        print(f"Saved {len(contacts)} contact candidates.")
        return 0

    if command == "birthday-check":
        from src.scheduler import check_birthdays

        tasks = check_birthdays(config)
        print(f"Matched {len(tasks)} birthday task(s).")
        return 0

    if command == "send-birthday":
        from src.scheduler import run_birthday_send

        results = run_birthday_send(config, force_contact=contact)
        sent = sum(1 for r in results if r.get("sent"))
        print(f"Birthday send complete: {sent}/{len(results)} sent.")
        return 0 if results else 1

    if command == "gui":
        from src.gui.dashboard import run_dashboard

        run_dashboard(config)
        return 0

    if command == "manual-test":
        from src.manual_smoke import print_manual_smoke_plan, run_manual_smoke_test

        print_manual_smoke_plan()
        if plan_only:
            return 0
        results = run_manual_smoke_test(assume_yes=assume_yes)
        for result in results:
            status = "OK" if result.ok else "CHECK"
            print(f"[{status}] {result.name}: {result.message}")
        return 0 if all(result.ok for result in results if result.name != "permissions") else 1

    logger.error("Unknown command: %s", command)
    return 2


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return run_command(args.command, plan_only=args.plan_only, assume_yes=args.yes, contact=args.contact)


if __name__ == "__main__":
    sys.exit(main())
