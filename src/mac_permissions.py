"""macOS environment and permission checks for WeChat Assistant."""

from __future__ import annotations

import logging
import platform
import sys
from dataclasses import dataclass


LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class PermissionCheckResult:
    name: str
    ok: bool
    message: str


def _import_pyautogui():
    try:
        import pyautogui  # type: ignore

        return pyautogui, None
    except Exception as exc:  # pragma: no cover - depends on local install
        return None, exc


def check_platform() -> PermissionCheckResult:
    system = platform.system()
    ok = system == "Darwin"
    message = f"Current platform: {system}. Python: {sys.version.split()[0]}"
    if not ok:
        message += ". This project is designed for macOS."
    LOGGER.info(message)
    return PermissionCheckResult("platform", ok, message)


def check_screenshot() -> PermissionCheckResult:
    pyautogui, import_error = _import_pyautogui()
    if import_error:
        message = f"pyautogui import failed: {import_error}"
        LOGGER.error(message)
        return PermissionCheckResult("screenshot", False, message)

    try:
        image = pyautogui.screenshot()
        size = getattr(image, "size", None)
        message = f"Screenshot check passed. Captured size: {size}"
        LOGGER.info(message)
        return PermissionCheckResult("screenshot", True, message)
    except Exception as exc:  # pragma: no cover - permission dependent
        message = (
            "Screenshot check failed. Enable System Settings > Privacy & "
            f"Security > Screen Recording for your terminal. Error: {exc}"
        )
        LOGGER.error(message)
        return PermissionCheckResult("screenshot", False, message)


def check_mouse_control() -> PermissionCheckResult:
    pyautogui, import_error = _import_pyautogui()
    if import_error:
        message = f"pyautogui import failed: {import_error}"
        LOGGER.error(message)
        return PermissionCheckResult("mouse_control", False, message)

    try:
        x, y = pyautogui.position()
        pyautogui.moveTo(x, y, duration=0)
        message = "Mouse control check passed."
        LOGGER.info(message)
        return PermissionCheckResult("mouse_control", True, message)
    except Exception as exc:  # pragma: no cover - permission dependent
        message = (
            "Mouse control check failed. Enable System Settings > Privacy & "
            f"Security > Accessibility for your terminal. Error: {exc}"
        )
        LOGGER.error(message)
        return PermissionCheckResult("mouse_control", False, message)


def run_environment_checks() -> list[PermissionCheckResult]:
    """Run all macOS checks and return structured results."""
    results = [check_platform(), check_screenshot(), check_mouse_control()]
    reminder = (
        "Required macOS permissions: System Settings > Privacy & Security > "
        "Accessibility, and System Settings > Privacy & Security > Screen Recording."
    )
    LOGGER.info(reminder)
    print(reminder)
    for result in results:
        status = "OK" if result.ok else "FAILED"
        print(f"[{status}] {result.name}: {result.message}")
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_environment_checks()
