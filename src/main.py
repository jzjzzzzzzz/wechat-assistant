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
            "auto-reply-drain",
            "notification-check",
            "unread-scan",
            "background-scan",
            "owner-status",
            "status-menu",
            "status-window",
            "macos-status-check",
            "dock-unread-check",
            "auto-reply-state",
            "auto-reply-monitor",
            "monitor-report",
            "runtime-status",
            "runtime-stop-all",
            "private-whitelist",
            "sender-classify",
        ],
        help="Command to run",
    )
    parser.add_argument("command_args", nargs="*", help="Command-specific arguments.")
    parser.add_argument("--plan-only", action="store_true", help="Only print the manual smoke-test plan.")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Run confirmation-gated manual smoke-test UI actions. Does not enable real sending.",
    )
    parser.add_argument(
        "--contact",
        default=None,
        help="Contact name for test-send or forced birthday send.",
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
    parser.add_argument("--scroll", action="store_true", help="Enable explicit unread chat-list scroll scan for this run.")
    parser.add_argument("--check", action="store_true", help="Run a command-specific check and exit.")
    parser.add_argument("--test", action="store_true", help="Run a command-specific test mode.")
    parser.add_argument(
        "--interval-seconds",
        type=float,
        default=None,
        help="Polling interval for limited-duration monitor commands.",
    )
    parser.add_argument(
        "--minutes",
        type=float,
        default=60.0,
        help="Runtime duration for limited-duration monitor commands.",
    )
    parser.add_argument(
        "--delay-minutes",
        type=float,
        default=None,
        help="Override auto-reply delay minutes for this run only.",
    )
    parser.add_argument(
        "--max-passes",
        type=int,
        default=None,
        help="Maximum detection/send passes for auto-reply-drain.",
    )
    return parser


def run_command(
    command: str,
    *,
    command_args: list[str] | None = None,
    plan_only: bool = False,
    assume_yes: bool = False,
    contact: str | None = None,
    force_send: bool = False,
    dry_run: bool = False,
    once: bool = False,
    scroll: bool = False,
    check: bool = False,
    test: bool = False,
    interval_seconds: float | None = None,
    minutes: float = 60.0,
    delay_minutes: float | None = None,
    max_passes: int | None = None,
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
        auto_reply = dict(config.get("auto_reply", {}))
        auto_reply["dry_run"] = False
        config["auto_reply"] = auto_reply

    if dry_run:
        config = dict(config)
        config["dry_run"] = True
        config["allow_real_send"] = False
        auto_reply = dict(config.get("auto_reply", {}))
        auto_reply["dry_run"] = True
        config["auto_reply"] = auto_reply
    if delay_minutes is not None:
        config = dict(config)
        auto_reply = dict(config.get("auto_reply", {}))
        auto_reply["delay_minutes"] = float(delay_minutes)
        config["auto_reply"] = auto_reply
    if scroll:
        config = dict(config)
        unread_scan = dict(config.get("unread_scan", {}))
        unread_scan["enable_scroll_scan"] = True
        config["unread_scan"] = unread_scan

    logger = setup_logger(log_file=config["log_file"])
    logger.info("Running command: %s", command)
    command_args = command_args or []

    if command == "check":
        results = run_environment_checks()
        return 0 if all(result.ok for result in results) else 1

    if command == "screenshot":
        from src.screenshot import capture_screenshot

        path = capture_screenshot(config)
        print(path if path else "Screenshot failed. Check logs/app.log.")
        return 0 if path else 1

    if command == "test-send":
        from src.message_sender import send_message, send_test_message

        if contact:
            message = str(config.get("test_message", "WeChat Assistant test message"))
            return 0 if send_message(config, contact, message) else 1
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

    if command == "private-whitelist":
        from src.auto_reply_policy import auto_reply_config
        from src.private_whitelist import add_private_whitelist_sender, remove_private_whitelist_sender

        ar = auto_reply_config(config)
        if command_args and command_args[0] in {"add", "remove"}:
            if len(command_args) != 2:
                print("Usage: private-whitelist [list|add <sender>|remove <sender>]")
                return 2
            try:
                if command_args[0] == "add":
                    result = add_private_whitelist_sender(command_args[1])
                else:
                    result = remove_private_whitelist_sender(command_args[1])
            except ValueError as exc:
                print(f"Invalid private whitelist update: {exc}")
                return 2
            print(f"action: {result.action}")
            print(f"sender: {result.sender}")
            print(f"path: {result.path}")
            print(f"count: {len(result.entries)}")
            return 0

        if command_args and command_args != ["list"]:
            print("Usage: private-whitelist [list|add <sender>|remove <sender>]")
            return 2
        whitelist = list(ar.get("private_chat_whitelist", []))
        print(f"require_private_chat_whitelist: {ar.get('require_private_chat_whitelist', True)}")
        print(f"count: {len(whitelist)}")
        if not whitelist:
            print("No private chat whitelist entries configured.")
            return 0
        for sender in whitelist:
            print(f"- {sender}")
        return 0

    if command == "sender-classify":
        from src.auto_reply_policy import auto_reply_config, classify_chat_sender

        if not command_args:
            print("Usage: sender-classify <sender name> [sender name ...]")
            return 2
        ar = auto_reply_config(config)
        for sender in command_args:
            classification = classify_chat_sender(sender, ar)
            print(f"sender: {classification.sender}")
            print(f"normalized_sender: {classification.normalized_sender}")
            print(f"is_private: {classification.is_private}")
            print(f"category: {classification.category}")
            print(f"reason: {classification.reason or 'none'}")
            if classification.matched_whitelist:
                print(f"matched_whitelist: {classification.matched_whitelist}")
            if classification.matched_blocklist_keyword:
                print(f"matched_blocklist_keyword: {classification.matched_blocklist_keyword}")
            if classification.matched_non_private_keyword:
                print(f"matched_non_private_keyword: {classification.matched_non_private_keyword}")
        return 0

    if command == "owner-status":
        from src.owner_status import get_owner_status, set_owner_status, toggle_owner_status

        try:
            if not command_args:
                status = get_owner_status(config)
            elif command_args[0] == "set" and len(command_args) == 2:
                status = set_owner_status(config, command_args[1], updated_by="cli")
            elif command_args[0] == "toggle" and len(command_args) == 1:
                status = toggle_owner_status(config, updated_by="cli")
            else:
                print("Usage: owner-status [set online|set offline|toggle]")
                return 2
        except ValueError as exc:
            print(f"Invalid owner status command: {exc}")
            return 2

        print(f"status: {status.status}")
        print(f"updated_at: {status.updated_at.isoformat(timespec='seconds') if status.updated_at else 'none'}")
        print(f"source: {status.source}")
        return 0

    if command == "status-menu":
        from src.status_menu import run_status_menu, run_status_menu_test, status_menu_check

        if check:
            return status_menu_check(config)
        if test:
            return run_status_menu_test()
        return run_status_menu(config)

    if command == "status-window":
        from src.status_window import run_status_window, run_status_window_test, status_window_check

        if check:
            return status_window_check(config)
        if test:
            return run_status_window_test(config)
        return run_status_window(config)

    if command == "macos-status-check":
        from src.macos_status_detector import detect_macos_status

        detection = detect_macos_status(config)
        print(f"raw_status: {detection.raw_status}")
        print(f"db_status: {detection.db_status}")
        print(f"detected_text: {detection.detected_text or 'none'}")
        print(f"screenshot_path: {detection.screenshot_path or 'none'}")
        print(f"confidence: {detection.confidence:.2f}")
        print(f"safe_to_auto_reply: {detection.raw_status == 'inactive'}")
        if detection.raw_status == "unknown":
            print("safe_default: no send")
        return 0

    if command == "dock-unread-check":
        from src.dock_unread_detector import detect_dock_wechat_unread, dock_unread_config

        dock = dock_unread_config(config)
        detection = detect_dock_wechat_unread(config)
        print(f"enabled: {dock.get('enabled', False)}")
        print(f"require_for_auto_reply: {dock.get('require_for_auto_reply', False)}")
        print(f"ok: {detection.ok}")
        print(f"has_unread: {detection.has_unread}")
        print(f"message: {detection.message}")
        print(f"confidence: {detection.confidence:.2f}")
        print(f"screenshot_path: {detection.screenshot_path or 'none'}")
        print(f"green_mask_path: {detection.green_mask_path or 'none'}")
        print(f"red_mask_path: {detection.red_mask_path or 'none'}")
        print(f"overlay_path: {detection.overlay_path or 'none'}")
        print(f"wechat_icon_candidate_count: {len(detection.wechat_icon_candidates)}")
        print(f"red_badge_candidate_count: {len(detection.red_badge_candidates)}")
        for item in detection.associated_badges:
            print(f"associated_badge: {item}")
        for reason in detection.rejected_reasons[:20]:
            print(f"rejected_reason: {reason}")
        if detection.has_unread is not True:
            print("safe_default: no send")
        return 0

    if command == "auto-reply-state":
        from src.auto_reply_state import AutoReplyStateStore

        if command_args and command_args != ["list"]:
            print("Usage: auto-reply-state list")
            return 2
        with AutoReplyStateStore(config.get("database_path")) as store:
            records = store.summarize()
            print(f"database_path: {store.database_path}")
            print(f"row_count: {len(records)}")
            if not records:
                print("No auto-reply state rows.")
                return 0
            for record in records:
                print(
                    "state: "
                    f"sender={record.sender} source={record.source} status={record.last_status} "
                    f"reason={record.last_reason or ''} confidence={record.confidence:.2f} "
                    f"first_seen_at={record.first_seen_at.isoformat(timespec='seconds')} "
                    f"last_seen_at={record.last_seen_at.isoformat(timespec='seconds')} "
                    f"replied_dry_run={record.replied_dry_run} real_sent={record.real_sent}"
                )
        return 0

    if command == "monitor-report":
        from src.auto_reply_monitor import print_monitor_report

        return print_monitor_report(config)

    if command == "runtime-status":
        from src.runtime_manager import print_runtime_status

        print_runtime_status(config)
        return 0

    if command == "runtime-stop-all":
        from src.runtime_manager import print_stop_all_results

        return print_stop_all_results()

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
        unread_scan = config.get("unread_scan", {}) if isinstance(config.get("unread_scan"), dict) else {}
        print(f"scroll_scan_enabled: {unread_scan.get('enable_scroll_scan', False)}")
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

        # dry_run_mode=True unless caller passes --force-send (which sets allow_real_send=True)
        # Normally run with --dry-run for safe monitoring, or let config drive it.
        auto_reply_runtime = config.get("auto_reply", {}) if isinstance(config.get("auto_reply"), dict) else {}
        daemon_dry_run = (
            dry_run
            or bool(config.get("dry_run", True))
            or bool(auto_reply_runtime.get("dry_run", True))
        )
        if not daemon_dry_run and not config.get("allow_real_send", False):
            logger.warning(
                "auto-reply-daemon: dry_run=false but allow_real_send=false "
                "— falling back to dry-run mode for safety."
            )
            daemon_dry_run = True
        daemon = AutoReplyDaemon(config, dry_run_mode=daemon_dry_run)
        if once:
            try:
                events = daemon.run_once()
                print_planned_actions(events, daemon.config)
            finally:
                state_store = getattr(daemon, "state_store", None)
                if state_store is not None:
                    state_store.close()
                status_watcher = getattr(daemon, "_status_watcher", None)
                if status_watcher is not None:
                    status_watcher.close()
            return 0
        daemon.run_forever()
        return 0

    if command == "auto-reply-drain":
        from src.auto_reply_drain import print_drain_summary, run_auto_reply_drain

        try:
            summary = run_auto_reply_drain(
                config,
                max_passes=max_passes or 10,
                interval_seconds=interval_seconds if interval_seconds is not None else 2.0,
            )
        except ValueError as exc:
            print(f"auto-reply-drain blocked: {exc}")
            return 2
        print_drain_summary(summary)
        return 0

    if command == "auto-reply-monitor":
        from src.auto_reply_monitor import print_monitor_summary, run_auto_reply_monitor

        if not dry_run:
            print("auto-reply-monitor is dry-run only. Re-run with --dry-run.")
            return 2
        summary = run_auto_reply_monitor(config, interval_seconds=interval_seconds, minutes=minutes)
        print_monitor_summary(summary)
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
        scroll=args.scroll,
        check=args.check,
        test=args.test,
        interval_seconds=args.interval_seconds,
        minutes=args.minutes,
        delay_minutes=args.delay_minutes,
        max_passes=args.max_passes,
        command_args=args.command_args,
    )


if __name__ == "__main__":
    sys.exit(main())
