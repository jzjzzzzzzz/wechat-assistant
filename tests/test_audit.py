from pathlib import Path

from src.audit import AuditEventType, message_preview, write_audit_event
from src.database import connect_database
from src.repositories import list_audit_events


def test_message_preview_truncates_long_messages() -> None:
    preview = message_preview("x" * 200)

    assert preview is not None
    assert len(preview) == 123
    assert preview.endswith("...")


def test_write_audit_event_creates_structured_record(tmp_path: Path) -> None:
    database_path = tmp_path / "wechat_assistant.sqlite3"
    config = {"audit_enabled": True, "database_path": str(database_path)}

    event_id = write_audit_event(
        config,
        AuditEventType.DRY_RUN_SEND,
        target="文件传输助手",
        message="hello",
        safety_decision="dry_run",
        metadata={"reason": "dry_run is true"},
    )

    assert event_id is not None
    with connect_database(database_path) as connection:
        events = list_audit_events(connection)

    assert len(events) == 1
    assert events[0]["event_type"] == "dry_run_send"
    assert events[0]["target"] == "文件传输助手"
    assert events[0]["message_preview"] == "hello"
    assert events[0]["safety_decision"] == "dry_run"


def test_write_audit_event_respects_disabled_flag(tmp_path: Path) -> None:
    database_path = tmp_path / "wechat_assistant.sqlite3"
    config = {"audit_enabled": False, "database_path": str(database_path)}

    event_id = write_audit_event(
        config,
        AuditEventType.DRY_RUN_SEND,
        target="文件传输助手",
        message="hello",
        safety_decision="dry_run",
    )

    assert event_id is None
    assert not database_path.exists()
