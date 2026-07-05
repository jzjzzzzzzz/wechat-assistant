from pathlib import Path

from src.gui.log_viewer import resolve_log_path, tail_log_lines


def test_tail_log_lines_returns_recent_lines(tmp_path: Path) -> None:
    log_path = tmp_path / "app.log"
    log_path.write_text("\n".join(f"line {index}" for index in range(5)), encoding="utf-8")

    lines = tail_log_lines(log_path, max_lines=2)

    assert lines == ["line 3", "line 4"]


def test_tail_log_lines_missing_file_is_empty(tmp_path: Path) -> None:
    assert tail_log_lines(tmp_path / "missing.log") == []


def test_tail_log_lines_filters_by_level(tmp_path: Path) -> None:
    log_path = tmp_path / "app.log"
    log_path.write_text(
        "2026-07-05 01:00:00 INFO [x] ok\n"
        "2026-07-05 01:00:01 ERROR [x] bad\n"
        "2026-07-05 01:00:02 WARNING [x] warn\n",
        encoding="utf-8",
    )

    lines = tail_log_lines(log_path, level="ERROR")

    assert lines == ["2026-07-05 01:00:01 ERROR [x] bad"]


def test_resolve_log_path_uses_project_root_for_relative_path() -> None:
    path = resolve_log_path({"log_file": "logs/app.log"})

    assert path.is_absolute()
    assert str(path).endswith("logs/app.log")
