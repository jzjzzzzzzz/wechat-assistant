from src.mac_permissions import PermissionCheckResult, run_environment_checks


def test_run_environment_checks_skips_mouse_when_screenshot_fails(monkeypatch) -> None:
    calls: list[str] = []

    monkeypatch.setattr(
        "src.mac_permissions.check_platform",
        lambda: PermissionCheckResult("platform", True, "platform ok"),
    )
    monkeypatch.setattr(
        "src.mac_permissions.check_screenshot",
        lambda: PermissionCheckResult("screenshot", False, "screen recording missing"),
    )
    monkeypatch.setattr(
        "src.mac_permissions.check_mouse_control",
        lambda: calls.append("mouse") or PermissionCheckResult("mouse_control", True, "mouse ok"),
    )

    results = run_environment_checks()

    assert [result.name for result in results] == ["platform", "screenshot", "mouse_control"]
    assert results[2].ok is False
    assert "skipped" in results[2].message
    assert calls == []


def test_run_environment_checks_runs_mouse_when_screenshot_passes(monkeypatch) -> None:
    calls: list[str] = []

    monkeypatch.setattr(
        "src.mac_permissions.check_platform",
        lambda: PermissionCheckResult("platform", True, "platform ok"),
    )
    monkeypatch.setattr(
        "src.mac_permissions.check_screenshot",
        lambda: PermissionCheckResult("screenshot", True, "screenshot ok"),
    )
    monkeypatch.setattr(
        "src.mac_permissions.check_mouse_control",
        lambda: calls.append("mouse") or PermissionCheckResult("mouse_control", True, "mouse ok"),
    )

    results = run_environment_checks()

    assert results[2].ok is True
    assert calls == ["mouse"]
