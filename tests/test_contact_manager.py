from pathlib import Path

from src.contact_manager import (
    disable_contact,
    import_ocr_candidates,
    list_all_local_contacts,
    list_contacts_available_for_future_tasks,
    mark_contact_reviewed,
)
from src.database import connect_database, initialize_database


def _connection(tmp_path: Path):
    database_path = tmp_path / "wechat_assistant.sqlite3"
    initialize_database(database_path)
    return connect_database(database_path)


def test_import_ocr_candidates_as_unreviewed_contacts(tmp_path: Path) -> None:
    with _connection(tmp_path) as connection:
        result = import_ocr_candidates(
            connection,
            [
                {"contact_name": "Alice", "source": "screen.png", "confidence": 0.8},
                {"contact_name": "", "source": "screen.png", "confidence": 0.8},
            ],
        )
        contacts = list_all_local_contacts(connection)

    assert result.imported == 1
    assert result.skipped == 1
    assert contacts[0]["contact_name"] == "Alice"
    assert contacts[0]["reviewed"] == 0
    assert contacts[0]["enabled"] == 1


def test_import_ocr_candidates_dedupes_and_keeps_higher_confidence(tmp_path: Path) -> None:
    with _connection(tmp_path) as connection:
        first = import_ocr_candidates(
            connection,
            [{"contact_name": "Alice", "source": "low.png", "confidence": 0.4}],
        )
        second = import_ocr_candidates(
            connection,
            [{"contact_name": "Alice", "source": "high.png", "confidence": 0.9}],
        )
        contacts = list_all_local_contacts(connection)

    assert first.imported == 1
    assert second.imported == 0
    assert second.updated_or_existing == 1
    assert len(contacts) == 1
    assert contacts[0]["confidence"] == 0.9
    assert contacts[0]["source"] == "high.png"


def test_reviewed_enabled_contacts_available_for_future_tasks(tmp_path: Path) -> None:
    with _connection(tmp_path) as connection:
        import_ocr_candidates(
            connection,
            [
                {"contact_name": "Alice", "source": "screen.png", "confidence": 0.8},
                {"contact_name": "Bob", "source": "screen.png", "confidence": 0.8},
            ],
        )
        mark_contact_reviewed(connection, "Alice", reviewed=True)
        mark_contact_reviewed(connection, "Bob", reviewed=True)
        disable_contact(connection, "Bob")
        available = list_contacts_available_for_future_tasks(connection)

    assert [contact["contact_name"] for contact in available] == ["Alice"]


def test_mark_contact_reviewed_returns_false_for_missing_contact(tmp_path: Path) -> None:
    with _connection(tmp_path) as connection:
        result = mark_contact_reviewed(connection, "Missing", reviewed=True)

    assert result is False
