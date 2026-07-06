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
            "auto-reply-plan",
            "auto-reply-daemon",
            "notification-check",
            "unread-scan",
            "background-scan",
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
    parser.add_argument(
        "--force-send",
        action="store_true",
        help=(
            "Temporarily enable real sending in memory for this run only. "
            "Does NOT write to config/settings.yaml. "
            "Safe for use in cron/launchd — config file stays at dry_run: true."
        ),
    )
    parser.add_argument("--dry-run", action="store_true", help="Force dry-run behavior for auto-reply commands.")
    parser.add_argument("--once", action="store_true", help="Run one detection pass and exit.")
    return parser


def run_command(
    command: str,
    *,
    plan_only: bool = False,
    assume_yes: bool = False,
    contact: str | None = None,
    force_send: bool = False,
    dry_run: bool = False,
    once: bool = False,
) -> int:
    try:
        config = load_config()
    except ConfigError as exc:
        setup_logger().error("Configuration error: %s", exc)
        return 2

    # --force-send: override safety flags in memory only, never on disk.
    # This lets launchd/cron call send-birthday without touching settings.yaml.
    if force_send:
        config = dict(config)
        config["dry_run"] = False
        config["allow_real_send"] = True

    if dry_run:
        config = dict(config)
        config["dry_run"] = True
        config["allow_real_send"] = False
        auto_reply = dict(config.get("auto_reply", {}))
        auto_reply["dry_run"] = True
        config["auto_reply"] = auto_reply

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

    if command == "auto-reply-plan":
        from src.auto_reply_daemon import print_auto_reply_plan

        print_auto_reply_plan(config)
        return 0

    if command == "notification-check":
        from src.notification_listener import notification_check_once

        events = notification_check_once(config)
        for event in events:
            print(
                f"[{event.status}] source={event.source} sender={event.sender} "
                f"preview={event.message_preview} confidence={event.confidence:.2f}"
            )
        if not events:
            print("No WeChat notification candidates detected.")
        return 0

    if command == "unread-scan":
        from src.unread_scanner import get_last_unread_scan_report, unread_scan_once

        events = unread_scan_once(config)
        report = get_last_unread_scan_report()
        if report:
            print(f"screenshot_path: {report.screenshot_path}")
            print(f"chat_list_crop_path: {report.chat_list_crop_path}")
            print(f"red_mask_path: {report.red_mask_path}")
            print(f"contour_overlay_path: {report.contour_overlay_path}")
            print(f"row_overlay_path: {report.row_overlay_path}")
            print(f"contour_count: {report.contour_count}")
            print(f"accepted_red_badge_count: {report.accepted_badge_count}")
            print(f"rejected_red_contour_count: {report.rejected_contour_count}")
            print(f"row_count: {report.row_count}")
            print(f"association_count: {report.association_count}")
            print(f"final_auto_reply_candidate_count: {report.final_candidate_count}")
            for candidate in report.badge_candidates:
                print(f"badge_candidate: {candidate}")
            for reason in report.ignored_reasons:
                print(f"ignored_reason: {reason}")
        for event in events:
            print(
                f"[{event.status}] source={event.source} sender={event.sender} "
                f"preview={event.message_preview} confidence={event.confidence:.2f}"
            )
        if not events:
            print("No unread private chat candidates detected.")
        return 0

    if command == "background-scan":
        from src.unread_scanner import run_background_scan_once

        result = run_background_scan_once(config)
        print(f"ok: {result.ok}")
        print(f"message: {result.message}")
        if result.error:
            print(f"error: {result.error}")
        if result.window:
            print(f"window_id: {result.window.window_id}")
            print(f"owner_name: {result.window.owner_name}")
            print(f"window_title: {result.window.window_title}")
            print(
                "bounds: "
                f"{result.window.bounds.x},{result.window.bounds.y},"
                f"{result.window.bounds.width},{result.window.bounds.height}"
            )
            print(f"is_visible: {result.window.is_visible}")
            print(f"is_minimized_or_hidden: {result.window.is_minimized_or_hidden}")
        if result.capture:
            print(f"capture_success: {result.capture.success}")
            print(f"capture_method: {result.capture.capture_method}")
            print(f"image_path: {result.capture.image_path}")
            if result.capture.bounds:
                print(f"capture_bounds: {result.capture.bounds}")
            if result.capture.error:
                print(f"capture_error: {result.capture.error}")
        if result.verification:
            print(f"is_wechat: {result.verification.is_wechat}")
            print(f"verification_confidence: {result.verification.confidence:.2f}")
            print(f"verification_reasons: {', '.join(result.verification.reasons)}")
        return 0

    if command == "auto-reply-daemon":
        from src.auto_reply_daemon import AutoReplyDaemon, print_planned_actions

        if not dry_run:
            print("auto-reply-daemon is dry-run only in this milestone. Re-run with --dry-run.")
            return 2
        daemon = AutoReplyDaemon(config)
        if once:
            events = daemon.run_once()
            print_planned_actions(events, daemon.config)
            return 0
        daemon.run_forever()
        return 0

    logger.error("Unknown command: %s", command)
    return 2


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return run_command(
        args.command,
        plan_only=args.plan_only,
        assume_yes=args.yes,
        contact=args.contact,
        force_send=args.force_send,
        dry_run=args.dry_run,
        once=args.once,
    )


if __name__ == "__main__":
    sys.exit(main())
