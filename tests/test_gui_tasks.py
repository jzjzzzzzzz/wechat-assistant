from datetime import date
from pathlib import Path

from src.gui.tasks import TasksViewModel


def test_tasks_view_model_creates_valid_task(tmp_path: Path) -> None:
    task_path = tmp_path / "birthday_tasks.csv"
    view_model = TasksViewModel({"dry_run": True, "allow_real_send": False}, task_path=task_path)

    result = view_model.create_task("文件传输助手", "07-05", "生日快乐", enabled=True)
    tasks = view_model.list_tasks()

    assert result.ok is True
    assert len(tasks) == 1
    assert tasks[0]["wechat_remark"] == "文件传输助手"


def test_tasks_view_model_rejects_invalid_date(tmp_path: Path) -> None:
    task_path = tmp_path / "birthday_tasks.csv"
    view_model = TasksViewModel({"dry_run": True, "allow_real_send": False}, task_path=task_path)

    result = view_model.create_task("文件传输助手", "02-30", "生日快乐", enabled=True)

    assert result.ok is False
    assert "birthday must be" in result.message
    assert view_model.list_tasks() == []


def test_tasks_view_model_disable_task(tmp_path: Path) -> None:
    task_path = tmp_path / "birthday_tasks.csv"
    view_model = TasksViewModel({"dry_run": True, "allow_real_send": False}, task_path=task_path)
    view_model.create_task("文件传输助手", "07-05", "生日快乐", enabled=True)

    result = view_model.disable_task(0)
    tasks = view_model.list_tasks()

    assert result.ok is True
    assert tasks[0]["enabled"] == "false"


def test_tasks_view_model_preview_is_dry_run_and_blocks_non_test_target(tmp_path: Path) -> None:
    task_path = tmp_path / "birthday_tasks.csv"
    view_model = TasksViewModel({"dry_run": False, "allow_real_send": True}, task_path=task_path)
    view_model.create_task("Normal Contact", "07-05", "生日快乐", enabled=True)

    plans = view_model.preview_today(today=date(2026, 7, 5))

    assert len(plans) == 1
    assert plans[0]["real_send_blocked"] is True
    assert "non-test target" in plans[0]["block_reason"]
