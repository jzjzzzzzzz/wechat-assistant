"""Manual smoke-test workflow helpers.

The workflow is intentionally interactive for UI actions. It never changes
`dry_run` or `allow_real_send`, and the default test-send remains dry-run only.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from src.config_loader import PROJECT_ROOT, load_config
from src.database import initialize_database
from src.mac_permissions import run_environment_checks
from src.message_sender import SAFE_TEST_CONTACT, send_test_message
from src.screenshot import capture_screenshot
from src.wechat_window import activate_wechat, is_wechat_running, search_contact


LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class ManualSmokeStep:
    name: str
    description: str
    requires_confirmation: bool = False


@dataclass(frozen=True)
class ManualSmokeResult:
    name: str
    ok: bool
    message: str


def build_manual_smoke_steps() -> list[ManualSmokeStep]:
    return [
        ManualSmokeStep("config-safety", "Confirm dry_run is true and allow_real_send is false."),
        ManualSmokeStep("permissions", "Check macOS Accessibility and Screen Recording permissions."),
        ManualSmokeStep("wechat-open", "Confirm WeChat for Mac is already open."),
        ManualSmokeStep("activate-wechat", "Activate the WeChat window.", requires_confirmation=True),
        ManualSmokeStep("screenshot", "Take and save a screenshot."),
        ManualSmokeStep("search-file-transfer", "Search for 文件传输助手.", requires_confirmation=True),
        ManualSmokeStep("dry-run-test-send", "Run dry-run test-send; do not send a real message."),
        ManualSmokeStep("logs", "Confirm logs/app.log has entries."),
        ManualSmokeStep("database", "Confirm the local project database initializes."),
        ManualSmokeStep("gui", "Print the GUI command without launching a blocking window."),
    ]


def validate_safe_manual_config(config: dict[str, Any]) -> ManualSmokeResult:
    if config.get("dry_run") is not True:
        return ManualSmokeResult("config-safety", False, "dry_run must remain true for manual smoke tests.")
    if config.get("allow_real_send") is not False:
        return ManualSmokeResult("config-safety", False, "allow_real_send must remain false for manual smoke tests.")
    if config.get("test_contact") != SAFE_TEST_CONTACT:
        return ManualSmokeResult("config-safety", False, f"test_contact must be {SAFE_TEST_CONTACT}.")
    return ManualSmokeResult("config-safety", True, "Safe manual config confirmed.")


def resolve_project_path(path: str | Path) -> Path:
    resolved = Path(path)
    if not resolved.is_absolute():
        resolved = PROJECT_ROOT / resolved
    return resolved


def log_file_has_entries(log_file: str | Path) -> bool:
    path = resolve_project_path(log_file)
    return path.exists() and path.stat().st_size > 0


def initialize_manual_database(config: dict[str, Any]) -> ManualSmokeResult:
    database_path = initialize_database(config.get("database_path", "data/wechat_assistant.sqlite3"))
    return ManualSmokeResult("database", database_path.exists(), f"Database initialized: {database_path}")


def prompt_yes_no(prompt: str, input_func: Callable[[str], str] = input) -> bool:
    return input_func(f"{prompt} [y/N] ").strip().lower() in {"y", "yes"}


def run_manual_smoke_test(
    *,
    assume_yes: bool = False,
    input_func: Callable[[str], str] = input,
) -> list[ManualSmokeResult]:
    config = load_config()
    results: list[ManualSmokeResult] = []

    safety = validate_safe_manual_config(config)
    results.append(safety)
    if not safety.ok:
        return results

    permission_results = run_environment_checks()
    results.append(
        ManualSmokeResult(
            "permissions",
            all(result.ok for result in permission_results),
            "Permission checks completed; review failed items above.",
        )
    )

    app_name = str(config.get("wechat_app_name", "WeChat"))
    running = is_wechat_running(app_name)
    results.append(ManualSmokeResult("wechat-open", running, f"WeChat running: {running}"))

    if assume_yes or prompt_yes_no("Activate WeChat window now?", input_func):
        activated = activate_wechat(app_name)
        results.append(ManualSmokeResult("activate-wechat", activated, f"WeChat activated: {activated}"))
    else:
        results.append(ManualSmokeResult("activate-wechat", False, "Skipped by user."))

    screenshot_path = capture_screenshot(config)
    results.append(
        ManualSmokeResult(
            "screenshot",
            screenshot_path is not None,
            f"Screenshot saved: {screenshot_path}" if screenshot_path else "Screenshot failed.",
        )
    )

    if assume_yes or prompt_yes_no(f"Search for {SAFE_TEST_CONTACT} now?", input_func):
        searched = search_contact(SAFE_TEST_CONTACT, config)
        results.append(ManualSmokeResult("search-file-transfer", searched, f"Search completed: {searched}"))
    else:
        results.append(ManualSmokeResult("search-file-transfer", False, "Skipped by user."))

    sent = send_test_message(config)
    results.append(ManualSmokeResult("dry-run-test-send", sent, "Dry-run test-send completed."))

    logs_ok = log_file_has_entries(config.get("log_file", "logs/app.log"))
    results.append(ManualSmokeResult("logs", logs_ok, f"Log file has entries: {logs_ok}"))
    results.append(initialize_manual_database(config))
    results.append(ManualSmokeResult("gui", True, "Start GUI manually with: python -m src.main gui"))

    for result in results:
        LOGGER.info("Manual smoke result: %s ok=%s message=%s", result.name, result.ok, result.message)
    return results


def print_manual_smoke_plan() -> None:
    print("Manual smoke test plan:")
    for index, step in enumerate(build_manual_smoke_steps(), start=1):
        marker = " (asks confirmation)" if step.requires_confirmation else ""
        print(f"{index}. {step.name}: {step.description}{marker}")
