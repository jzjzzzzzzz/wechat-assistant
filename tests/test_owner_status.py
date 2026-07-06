from datetime import datetime

from src.owner_status import OwnerStatusStore, get_owner_status, set_owner_status, toggle_owner_status


BASE_TIME = datetime(2026, 7, 5, 12, 0, 0)


def make_config(tmp_path, status_default="online"):
    return {
        "database_path": str(tmp_path / "wechat_assistant.sqlite3"),
        "owner": {
            "status_default": status_default,
            "offline_reply_immediate": True,
            "status_menu_enabled": True,
        },
    }


def test_default_owner_status_is_online(tmp_path):
    status = get_owner_status(make_config(tmp_path))

    assert status.status == "online"
    assert status.source == "config default"
    assert status.updated_at is None


def test_set_owner_status_online(tmp_path):
    config = make_config(tmp_path, status_default="offline")

    status = set_owner_status(config, "online")

    assert status.status == "online"
    assert status.source == "database"


def test_set_owner_status_offline(tmp_path):
    config = make_config(tmp_path)

    status = set_owner_status(config, "offline")

    assert status.status == "offline"
    assert status.source == "database"


def test_toggle_owner_status(tmp_path):
    config = make_config(tmp_path)

    first = toggle_owner_status(config)
    second = toggle_owner_status(config)

    assert first.status == "offline"
    assert second.status == "online"


def test_database_value_overrides_config_default(tmp_path):
    config = make_config(tmp_path, status_default="online")

    with OwnerStatusStore(config["database_path"]) as store:
        store.set_status("offline", now=BASE_TIME)

    status = get_owner_status(config)

    assert status.status == "offline"
    assert status.source == "database"
    assert status.updated_at == BASE_TIME
