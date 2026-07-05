from src.packaging_support import pyinstaller_command, should_exclude_from_package


def test_should_exclude_private_runtime_artifacts() -> None:
    assert should_exclude_from_package(".venv/bin/python") is True
    assert should_exclude_from_package("logs/app.log") is True
    assert should_exclude_from_package("screenshots/screen.png") is True
    assert should_exclude_from_package("data/wechat_assistant.sqlite3") is True


def test_should_not_exclude_safe_project_inputs() -> None:
    assert should_exclude_from_package("config/settings.yaml") is False
    assert should_exclude_from_package("data/birthday_tasks.csv") is False


def test_pyinstaller_command_uses_gui_entry_and_safe_data_files() -> None:
    command = pyinstaller_command()
    command_text = " ".join(command)

    assert command[0] == "pyinstaller"
    assert "packaging/pyinstaller_entry.py" in command
    assert "config/settings.yaml:config" in command_text
    assert "data/birthday_tasks.csv:data" in command_text
