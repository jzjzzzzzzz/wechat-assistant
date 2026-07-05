from pathlib import Path

from src.database import connect_database, initialize_database
from src.gui.contacts import ContactsViewModel
from src.repositories import create_contact, get_contact_by_name


def test_contacts_view_model_lists_contacts(tmp_path: Path) -> None:
    database_path = tmp_path / "wechat_assistant.sqlite3"
    initialize_database(database_path)
    with connect_database(database_path) as connection:
        create_contact(connection, "Alice", source="ocr", confidence=0.8)

    view_model = ContactsViewModel({"database_path": str(database_path)})
    contacts = view_model.list_contacts()

    assert len(contacts) == 1
    assert contacts[0].contact_name == "Alice"
    assert contacts[0].source == "ocr"
    assert contacts[0].reviewed is False
    assert contacts[0].enabled is True


def test_contacts_view_model_review_and_disable(tmp_path: Path) -> None:
    database_path = tmp_path / "wechat_assistant.sqlite3"
    initialize_database(database_path)
    with connect_database(database_path) as connection:
        create_contact(connection, "Alice", source="ocr", confidence=0.8)

    view_model = ContactsViewModel({"database_path": str(database_path)})

    assert view_model.mark_reviewed("Alice") is True
    assert view_model.disable("Alice") is True
    with connect_database(database_path) as connection:
        contact = get_contact_by_name(connection, "Alice")

    assert contact is not None
    assert contact["reviewed"] == 1
    assert contact["enabled"] == 0


def test_contacts_view_model_exposes_no_send_action(tmp_path: Path) -> None:
    view_model = ContactsViewModel({"database_path": str(tmp_path / "wechat_assistant.sqlite3")})

    assert "send" not in view_model.exposed_actions
    assert "real_send" not in view_model.exposed_actions
