from pathlib import Path

from src.database import connect_database, initialize_database, table_names


def test_initialize_database_creates_project_tables(tmp_path: Path) -> None:
    database_path = tmp_path / "wechat_assistant.sqlite3"

    initialized_path = initialize_database(database_path)

    assert initialized_path == database_path
    with connect_database(database_path) as connection:
        assert table_names(connection) == {
            "contacts",
            "birthday_tasks",
            "message_templates",
            "audit_events",
        }


def test_connect_database_uses_row_factory(tmp_path: Path) -> None:
    database_path = tmp_path / "wechat_assistant.sqlite3"
    initialize_database(database_path)

    with connect_database(database_path) as connection:
        row = connection.execute("SELECT 'ok' AS status").fetchone()

    assert row["status"] == "ok"
