"""Tests for src/macos_status_detector.py.

All tests are unit-level — no real screenshot, no pyautogui, no easyocr.
Inject fake capture/ocr functions to test the classification logic.
"""
from datetime import datetime
from pathlib import Path

import pytest

from src.macos_status_detector import (
    MacosStatusDetection,
    MacosStatusWatcher,
    _classify_text,
    _status_to_db_value,
    detect_macos_status,
)
from src.owner_status import OwnerStatusStore


FAKE_NOW = datetime(2026, 7, 6, 10, 0, 0)


def _make_capture(path: str | None):
    """Return a capture_func that yields *path*."""
    def capture(config):
        return path
    return capture


def _make_ocr(texts: list[str]):
    """Return an ocr_func that yields *texts* regardless of input."""
    def ocr(path, config):
        return texts
    return ocr


# ── _classify_text unit tests ─────────────────────────────────────────────────

def test_classify_ol_returns_active():
    assert _classify_text(["OL"]) == ("active", "OL")


def test_classify_wa_online_returns_active():
    assert _classify_text(["WA ONLINE"]) == ("active", "WA ONLINE")


def test_classify_off_returns_inactive():
    assert _classify_text(["OFF"]) == ("inactive", "OFF")


def test_classify_wa_offline_returns_inactive():
    assert _classify_text(["WA OFFLINE"]) == ("inactive", "WA OFFLINE")


def test_classify_online_token_case_insensitive():
    assert _classify_text(["ol"]) == ("active", "ol")


def test_classify_offline_token_case_insensitive():
    assert _classify_text(["off"]) == ("inactive", "off")


def test_classify_green_emoji_ol_returns_active():
    """🟢 OL with leading emoji should be stripped and matched."""
    status, text = _classify_text(["🟢 OL"])
    assert status == "active"


def test_classify_red_emoji_off_returns_inactive():
    status, text = _classify_text(["🔴 OFF"])
    assert status == "inactive"


def test_classify_empty_list_returns_unknown():
    assert _classify_text([]) == ("unknown", "")


def test_classify_unrelated_text_returns_unknown():
    assert _classify_text(["WeChat", "Hello", "12:34"]) == ("unknown", "")


def test_classify_conflicting_tokens_returns_unknown():
    """When both OL and OFF are present, status is ambiguous and must block."""
    status, _ = _classify_text(["OL", "OFF"])
    assert status == "unknown"


# ── _status_to_db_value mapping ───────────────────────────────────────────────

def test_active_maps_to_online():
    assert _status_to_db_value("active") == "online"


def test_inactive_maps_to_offline():
    assert _status_to_db_value("inactive") == "offline"


def test_unknown_maps_to_unknown():
    assert _status_to_db_value("unknown") == "unknown"


# ── detect_macos_status integration ───────────────────────────────────────────

def test_detect_returns_active_when_ol_found():
    config = {}
    detection = detect_macos_status(
        config,
        capture_func=_make_capture("fake/screenshot.png"),
        ocr_func=_make_ocr(["🟢 OL"]),
        now_func=lambda: FAKE_NOW,
    )
    assert detection.raw_status == "active"
    assert detection.db_status == "online"
    assert detection.is_active
    assert not detection.is_unknown
    assert detection.confidence > 0


def test_detect_returns_inactive_when_off_found():
    config = {}
    detection = detect_macos_status(
        config,
        capture_func=_make_capture("fake/screenshot.png"),
        ocr_func=_make_ocr(["🔴 OFF"]),
        now_func=lambda: FAKE_NOW,
    )
    assert detection.raw_status == "inactive"
    assert detection.db_status == "offline"
    assert not detection.is_active


def test_detect_returns_unknown_when_no_match():
    config = {}
    detection = detect_macos_status(
        config,
        capture_func=_make_capture("fake/screenshot.png"),
        ocr_func=_make_ocr(["Battery 85%", "WiFi"]),
        now_func=lambda: FAKE_NOW,
    )
    assert detection.raw_status == "unknown"
    assert detection.is_unknown
    assert detection.confidence == 0.0


def test_detect_returns_unknown_when_screenshot_fails():
    config = {}
    detection = detect_macos_status(
        config,
        capture_func=_make_capture(None),
        ocr_func=_make_ocr([]),
        now_func=lambda: FAKE_NOW,
    )
    assert detection.raw_status == "unknown"
    assert detection.screenshot_path is None


def test_detect_returns_unknown_when_capture_raises():
    def bad_capture(config):
        raise RuntimeError("capture crashed")

    detection = detect_macos_status(
        {},
        capture_func=bad_capture,
        ocr_func=_make_ocr(["OL"]),
        now_func=lambda: FAKE_NOW,
    )

    assert detection.raw_status == "unknown"
    assert detection.screenshot_path is None


def test_detect_does_not_raise_on_ocr_failure():
    def bad_ocr(path, config):
        raise RuntimeError("OCR crashed")

    config = {}
    detection = detect_macos_status(
        config,
        capture_func=_make_capture("fake.png"),
        ocr_func=bad_ocr,
        now_func=lambda: FAKE_NOW,
    )
    assert detection.raw_status == "unknown"


# ── MacosStatusWatcher DB update tests ────────────────────────────────────────

def test_watcher_updates_db_on_status_change(tmp_path: Path):
    db_path = tmp_path / "test.sqlite3"
    config = {"database_path": str(db_path), "screenshot_dir": str(tmp_path)}

    with OwnerStatusStore(db_path) as store:
        watcher = MacosStatusWatcher(
            config,
            store=store,
            capture_func=_make_capture("fake/path.png"),
            ocr_func=_make_ocr(["OL"]),
            now_func=lambda: FAKE_NOW,
        )
        detection = watcher.poll()

        assert detection.raw_status == "active"
        # DB should now show "online"
        record = store.get_database_status()
        assert record is not None
        assert record.status == "online"
        assert record.updated_by == "macos_status_detector"


def test_watcher_updates_db_to_offline_when_off(tmp_path: Path):
    db_path = tmp_path / "test.sqlite3"
    config = {"database_path": str(db_path), "screenshot_dir": str(tmp_path)}

    with OwnerStatusStore(db_path) as store:
        watcher = MacosStatusWatcher(
            config,
            store=store,
            capture_func=_make_capture("fake/path.png"),
            ocr_func=_make_ocr(["OFF"]),
            now_func=lambda: FAKE_NOW,
        )
        watcher.poll()
        record = store.get_database_status()
        assert record is not None
        assert record.status == "offline"


def test_watcher_does_not_write_db_when_unknown(tmp_path: Path):
    db_path = tmp_path / "test.sqlite3"
    config = {"database_path": str(db_path), "screenshot_dir": str(tmp_path)}

    with OwnerStatusStore(db_path) as store:
        watcher = MacosStatusWatcher(
            config,
            store=store,
            capture_func=_make_capture("fake/path.png"),
            ocr_func=_make_ocr(["Battery", "Clock"]),
            now_func=lambda: FAKE_NOW,
        )
        watcher.poll()
        # DB should have no rows — unknown status never writes
        record = store.get_database_status()
        assert record is None


def test_watcher_logs_transition_from_active_to_inactive(tmp_path: Path, caplog):
    import logging
    db_path = tmp_path / "test.sqlite3"
    config = {"database_path": str(db_path), "screenshot_dir": str(tmp_path)}

    with OwnerStatusStore(db_path) as store:
        # First poll: OL
        watcher = MacosStatusWatcher(
            config,
            store=store,
            capture_func=_make_capture("fake/path.png"),
            ocr_func=_make_ocr(["OL"]),
            now_func=lambda: FAKE_NOW,
        )
        with caplog.at_level(logging.INFO, logger="src.macos_status_detector"):
            watcher.poll()

        # Second poll: OFF
        watcher.ocr_func = _make_ocr(["OFF"])
        with caplog.at_level(logging.INFO, logger="src.macos_status_detector"):
            watcher.poll()

    assert any("STATUS CHANGED" in r.message for r in caplog.records), \
        "Expected a STATUS CHANGED log entry"


def test_watcher_logs_transition_to_unknown(tmp_path: Path, caplog):
    import logging
    db_path = tmp_path / "test.sqlite3"
    config = {"database_path": str(db_path), "screenshot_dir": str(tmp_path)}

    with OwnerStatusStore(db_path) as store:
        watcher = MacosStatusWatcher(
            config,
            store=store,
            capture_func=_make_capture("fake/path.png"),
            ocr_func=_make_ocr(["OL"]),
            now_func=lambda: FAKE_NOW,
        )
        watcher.poll()
        watcher.ocr_func = _make_ocr(["Battery", "Clock"])
        with caplog.at_level(logging.WARNING, logger="src.macos_status_detector"):
            watcher.poll()

    assert any("STATUS CHANGED active → unknown" in r.message for r in caplog.records)


def test_watcher_no_duplicate_db_write_when_status_unchanged(tmp_path: Path):
    db_path = tmp_path / "test.sqlite3"
    config = {"database_path": str(db_path), "screenshot_dir": str(tmp_path)}

    with OwnerStatusStore(db_path) as store:
        watcher = MacosStatusWatcher(
            config,
            store=store,
            capture_func=_make_capture("fake/path.png"),
            ocr_func=_make_ocr(["OL"]),
            now_func=lambda: FAKE_NOW,
        )
        watcher.poll()
        watcher.poll()  # same status, should not write again

        # Only one row written
        from src.database import connect_database, initialize_database
        initialize_database(db_path)
        with connect_database(db_path) as conn:
            count = conn.execute("SELECT COUNT(*) FROM owner_status").fetchone()[0]
        assert count == 1
