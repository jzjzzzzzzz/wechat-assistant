from pathlib import Path

from src.database import connect_database, initialize_database
from src.repositories import (
    create_birthday_task,
    create_contact,
    create_message_template,
    list_audit_events,
    list_birthday_tasks,
    list_contacts,
    list_message_templates,
    record_audit_event,
)


def _connection(tmp_path: Path):
    database_path = tmp_path / "wechat_assistant.sqlite3"
    initialize_database(database_path)
    return connect_database(database_path)


def test_contact_repository_insert_and_list(tmp_path: Path) -> None:
    with _connection(tmp_path) as connection:
        contact_id = create_contact(
            connection,
            "文件传输助手",
            source="manual",
            confidence=1.0,
            reviewed=True,
        )
        contacts = list_contacts(connection)

    assert contact_id > 0
    assert len(contacts) == 1
    assert contacts[0]["contact_name"] == "文件传输助手"
    assert contacts[0]["reviewed"] == 1
    assert contacts[0]["enabled"] == 1


def test_birthday_task_repository_insert_and_list(tmp_path: Path) -> None:
    with _connection(tmp_path) as connection:
        task_id = create_birthday_task(
            connection,
            "文件传输助手",
            "07-05",
            "生日快乐",
            enabled=False,
        )
        tasks = list_birthday_tasks(connection)

    assert task_id > 0
    assert tasks[0]["wechat_remark"] == "文件传输助手"
    assert tasks[0]["enabled"] == 0


def test_message_template_repository_insert_and_list(tmp_path: Path) -> None:
    with _connection(tmp_path) as connection:
        template_id = create_message_template(
            connection,
            "birthday_default",
            "birthday",
            "生日快乐，{name}",
        )
        templates = list_message_templates(connection)

    assert template_id > 0
    assert templates[0]["name"] == "birthday_default"
    assert templates[0]["body"] == "生日快乐，{name}"


def test_audit_event_repository_insert_and_list(tmp_path: Path) -> None:
    with _connection(tmp_path) as connection:
        event_id = record_audit_event(
            connection,
            "dry_run_send",
            target="文件传输助手",
            message_preview="hello",
            safety_decision="dry_run",
            metadata={"dry_run": True},
        )
        events = list_audit_events(connection)

    assert event_id > 0
    assert events[0]["event_type"] == "dry_run_send"
    assert events[0]["target"] == "文件传输助手"
    assert '"dry_run": true' in events[0]["metadata_json"]
