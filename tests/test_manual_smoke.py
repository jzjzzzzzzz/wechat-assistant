from pathlib import Path

from src.manual_smoke import (
    ManualSmokeResult,
    build_manual_smoke_steps,
    log_file_has_entries,
    prompt_yes_no,
    validate_safe_manual_config,
)


def test_manual_smoke_steps_include_gui_without_launching() -> None:
    steps = build_manual_smoke_steps()

    assert steps[-1].name == "gui"
    assert "without launching" in steps[-1].description.lower()


def test_validate_safe_manual_config_accepts_safe_defaults() -> None:
    result = validate_safe_manual_config(
        {
            "dry_run": True,
            "allow_real_send": False,
            "test_contact": "文件传输助手",
        }
    )

    assert result == ManualSmokeResult("config-safety", True, "Safe manual config confirmed.")


def test_validate_safe_manual_config_rejects_real_send_flags() -> None:
    result = validate_safe_manual_config(
        {
            "dry_run": False,
            "allow_real_send": False,
            "test_contact": "文件传输助手",
        }
    )

    assert result.ok is False
    assert "dry_run" in result.message


def test_validate_safe_manual_config_rejects_non_test_target() -> None:
    result = validate_safe_manual_config(
        {
            "dry_run": True,
            "allow_real_send": False,
            "test_contact": "Normal Contact",
        }
    )

    assert result.ok is False
    assert "文件传输助手" in result.message


def test_log_file_has_entries(tmp_path: Path) -> None:
    log_path = tmp_path / "app.log"

    assert log_file_has_entries(log_path) is False
    log_path.write_text("hello\n", encoding="utf-8")
    assert log_file_has_entries(log_path) is True


def test_prompt_yes_no_defaults_to_no() -> None:
    assert prompt_yes_no("Run?", input_func=lambda prompt: "") is False
    assert prompt_yes_no("Run?", input_func=lambda prompt: "yes") is True
