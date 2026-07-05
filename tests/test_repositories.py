from pathlib import Path

from src.database import connect_database, initialize_database
from src.repositories import (
    create_birthday_task,
    create_contact,
    create_message_template,
    get_contact_by_name,
    list_audit_events,
    list_birthday_tasks,
    list_contacts,
    list_enabled_reviewed_contacts,
    list_message_templates,
    record_audit_event,
    set_contact_enabled,
    set_contact_reviewed,
    upsert_contact_candidate,
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


def test_contact_repository_upsert_review_disable_and_available_list(tmp_path: Path) -> None:
    with _connection(tmp_path) as connection:
        contact_id, created = upsert_contact_candidate(
            connection,
            "Alice",
            source="ocr-low.png",
            confidence=0.4,
        )
        same_id, created_again = upsert_contact_candidate(
            connection,
            "Alice",
            source="ocr-high.png",
            confidence=0.9,
        )
        set_contact_reviewed(connection, "Alice", True)
        available_before_disable = list_enabled_reviewed_contacts(connection)
        set_contact_enabled(connection, "Alice", False)
        available_after_disable = list_enabled_reviewed_contacts(connection)
        contact = get_contact_by_name(connection, "Alice")

    assert created is True
    assert created_again is False
    assert same_id == contact_id
    assert contact is not None
    assert contact["confidence"] == 0.9
    assert contact["source"] == "ocr-high.png"
    assert [item["contact_name"] for item in available_before_disable] == ["Alice"]
    assert available_after_disable == []


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
