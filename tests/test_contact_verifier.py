"""Tests for src/contact_verifier.py — dual-region OCR verification."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from src.contact_verifier import (
    ContactVerifyResult,
    RegionResult,
    _get_region_boxes,
    _levenshtein,
    _name_in_texts,
    _screen_scale_factor,
    ocr_from_path,
    verify_active_contact,
)


# ── helpers ────────────────────────────────────────────────────────────────────

def _make_image(tmp_path: Path, name: str = "screen.png", size: tuple = (200, 100)) -> Path:
    p = tmp_path / name
    Image.new("RGB", size, "white").save(p)
    return p


def _ok_region(name: str, target: str) -> RegionResult:
    return RegionResult(name=name, found=True, texts=[target], crop_box=(0, 0, 50, 20), message="ok")


def _fail_region(name: str) -> RegionResult:
    return RegionResult(name=name, found=False, texts=["other"], crop_box=(0, 0, 50, 20), message="fail")


# ── _name_in_texts ─────────────────────────────────────────────────────────────

def test_name_in_texts_exact():
    assert _name_in_texts("Sample Contact", ["Sample Contact", "文件传输助手"]) is True

def test_name_in_texts_substring():
    assert _name_in_texts("File Transfer", ["File Transfer | WeChat"]) is True

def test_name_in_texts_case_insensitive():
    assert _name_in_texts("file transfer", ["File Transfer"]) is True

def test_name_in_texts_not_found():
    assert _name_in_texts("Bob", ["Alice", "Charlie"]) is False

def test_name_in_texts_empty():
    assert _name_in_texts("Sample Contact", []) is False


# ── _levenshtein ───────────────────────────────────────────────────────────────

def test_levenshtein_identical():
    assert _levenshtein("abc", "abc") == 0

def test_levenshtein_one_substitution():
    assert _levenshtein("file", "flle") == 1   # OCR misread i→l

def test_levenshtein_one_deletion():
    assert _levenshtein("file", "fil") == 1

def test_levenshtein_one_insertion():
    assert _levenshtein("fil", "file") == 1

def test_levenshtein_empty():
    assert _levenshtein("", "abc") == 3
    assert _levenshtein("abc", "") == 3


# ── _name_in_texts (fuzzy) ────────────────────────────────────────────────────

def test_name_in_texts_fuzzy_ocr_misread():
    # EasyOCR reads "Flle Transfer" instead of "File Transfer"
    assert _name_in_texts("文件传输助手", ["Flle Transfer"]) is True

def test_name_in_texts_fuzzy_does_not_match_unrelated():
    assert _name_in_texts("文件传输助手", ["Sample Contact", "USACO"]) is False


# ── _get_region_boxes ──────────────────────────────────────────────────────────

def test_get_region_boxes_scale1():
    # logical window (100,50,800,600), scale 1.0
    sidebar, title = _get_region_boxes((100, 50, 800, 600), scale=1.0)
    assert sidebar == (100, 50, 240, 600)
    # title_y = 50+22=72, h=50
    assert title == (340, 72, 560, 50)

def test_get_region_boxes_scale2():
    sidebar, title = _get_region_boxes((100, 50, 800, 600), scale=2.0)
    assert sidebar == (200, 100, 480, 1200)
    # title_y logical=72 → phys=144; h logical=50 → phys=100
    assert title == (680, 144, 1120, 100)

def test_get_region_boxes_sidebar_full_height():
    """Sidebar height must equal window height (full contact list)."""
    _, wy, _, wh = (0, 0, 1000, 700)
    sidebar, _ = _get_region_boxes((0, 0, 1000, 700), scale=1.0)
    assert sidebar[3] == wh  # height matches window height


# ── _screen_scale_factor ───────────────────────────────────────────────────────

def test_screen_scale_factor_computes_from_image(tmp_path: Path):
    img = _make_image(tmp_path, size=(3024, 1964))
    with patch("pyautogui.size", return_value=(1512, 982)):
        scale = _screen_scale_factor(str(img))
    assert scale == pytest.approx(2.0)

def test_screen_scale_factor_fallback_on_error(tmp_path: Path):
    # pyautogui not available → should return 2.0
    img = _make_image(tmp_path, size=(100, 100))
    with patch("pyautogui.size", side_effect=ImportError("no pyautogui")):
        scale = _screen_scale_factor(str(img))
    assert scale == pytest.approx(2.0)


# ── verify_active_contact — both regions pass ──────────────────────────────────

def test_verify_passes_when_both_regions_found(tmp_path: Path):
    img = _make_image(tmp_path, size=(3024, 1964))
    screenshot_func = MagicMock(return_value=str(img))

    with (
        patch("src.contact_verifier.get_wechat_window_rect", return_value=(100, 50, 800, 600)),
        patch("src.contact_verifier._screen_scale_factor", return_value=1.0),
        patch("src.contact_verifier._check_region", side_effect=[
            _ok_region("sidebar", "文件传输助手"),
            _ok_region("title_bar", "文件传输助手"),
        ]),
    ):
        result = verify_active_contact({}, "文件传输助手", screenshot_func, retries=0)

    assert result.ok is True
    assert result.sidebar is not None and result.sidebar.found
    assert result.title_bar is not None and result.title_bar.found
    assert "PASSED" in result.message


# ── verify_active_contact — one region fails ───────────────────────────────────

@pytest.mark.parametrize("sidebar_found,title_found", [(True, False), (False, True), (False, False)])
def test_verify_fails_when_any_region_missing(tmp_path: Path, sidebar_found, title_found):
    img = _make_image(tmp_path, size=(3024, 1964))
    screenshot_func = MagicMock(return_value=str(img))

    with (
        patch("src.contact_verifier.get_wechat_window_rect", return_value=(100, 50, 800, 600)),
        patch("src.contact_verifier._screen_scale_factor", return_value=1.0),
        patch("src.contact_verifier._check_region", side_effect=[
            (_ok_region("sidebar", "目标") if sidebar_found else _fail_region("sidebar")),
            (_ok_region("title_bar", "目标") if title_found else _fail_region("title_bar")),
        ]),
    ):
        result = verify_active_contact({}, "目标", screenshot_func, retries=0)

    assert result.ok is False


# ── verify_active_contact — retry behaviour ────────────────────────────────────

def test_verify_retries_then_passes(tmp_path: Path):
    img = _make_image(tmp_path, size=(3024, 1964))
    screenshot_func = MagicMock(return_value=str(img))

    # Attempt 1: sidebar fails. Attempt 2: both pass.
    check_region_side_effects = [
        _fail_region("sidebar"),
        _ok_region("title_bar", "Sample Contact"),
        _ok_region("sidebar", "Sample Contact"),
        _ok_region("title_bar", "Sample Contact"),
    ]

    with (
        patch("src.contact_verifier.get_wechat_window_rect", return_value=(0, 0, 800, 600)),
        patch("src.contact_verifier._screen_scale_factor", return_value=1.0),
        patch("src.contact_verifier._check_region", side_effect=check_region_side_effects),
        patch("time.sleep"),
    ):
        result = verify_active_contact({}, "Sample Contact", screenshot_func, retries=1, retry_delay=0.0)

    assert result.ok is True
    assert screenshot_func.call_count == 2


def test_verify_exhausts_retries(tmp_path: Path):
    img = _make_image(tmp_path, size=(3024, 1964))
    screenshot_func = MagicMock(return_value=str(img))

    # Always fail both regions
    with (
        patch("src.contact_verifier.get_wechat_window_rect", return_value=(0, 0, 800, 600)),
        patch("src.contact_verifier._screen_scale_factor", return_value=1.0),
        patch("src.contact_verifier._check_region", return_value=_fail_region("sidebar")),
        patch("time.sleep"),
    ):
        result = verify_active_contact({}, "Sample Contact", screenshot_func, retries=2, retry_delay=0.0)

    assert result.ok is False
    assert screenshot_func.call_count == 3   # retries=2 → 3 total


# ── verify_active_contact — screenshot failure ─────────────────────────────────

def test_verify_screenshot_failure():
    screenshot_func = MagicMock(return_value=None)
    result = verify_active_contact({}, "Sample Contact", screenshot_func, retries=0)
    assert result.ok is False
    assert "Screenshot capture failed" in result.message


# ── verify_active_contact — window rect unavailable (fallback) ─────────────────

def test_verify_falls_back_to_full_screenshot_when_no_window_rect(tmp_path: Path, monkeypatch):
    img = _make_image(tmp_path, size=(3024, 1964))
    screenshot_func = MagicMock(return_value=str(img))

    class FakeReader:
        def __init__(self, langs, gpu=False): ...
        def readtext(self, p):
            return [(None, "文件传输助手", 0.9)]

    monkeypatch.setitem(sys.modules, "easyocr", SimpleNamespace(Reader=FakeReader))

    with (
        patch("src.contact_verifier.get_wechat_window_rect", return_value=None),
    ):
        result = verify_active_contact({}, "文件传输助手", screenshot_func, retries=0)

    assert result.ok is True
    assert "full-screenshot" in result.message.lower()


def test_verify_uses_injected_ocr_for_regions(tmp_path: Path):
    img = _make_image(tmp_path, size=(3024, 1964))
    screenshot_func = MagicMock(return_value=str(img))
    ocr_func = MagicMock(return_value=[{"text": "目标联系人", "confidence": 0.95}])

    with (
        patch("src.contact_verifier.get_wechat_window_rect", return_value=(0, 0, 800, 600)),
        patch("src.contact_verifier._screen_scale_factor", return_value=1.0),
    ):
        result = verify_active_contact({}, "目标联系人", screenshot_func, ocr_func, retries=0)

    assert result.ok is True
    assert ocr_func.call_count == 2


# ── send_message integration ───────────────────────────────────────────────────

def test_send_message_passes_when_verify_ok(tmp_path: Path):
    from src.message_sender import send_message
    from src.screen_state import ScreenState, ScreenStateDetection

    img = _make_image(tmp_path)
    config: dict[str, Any] = {
        "dry_run": False,
        "allow_real_send": True,
        "allowed_real_contacts": ["文件传输助手"],
        "require_known_screen_state_for_real_send": False,
        "max_retry": 1,
        "send_delay_seconds": 0,
    }
    verify_func = MagicMock(
        return_value=ContactVerifyResult(
            ok=True, target="文件传输助手",
            sidebar=_ok_region("sidebar", "文件传输助手"),
            title_bar=_ok_region("title_bar", "文件传输助手"),
            message="verified",
        )
    )
    result = send_message(
        config, "文件传输助手", "hello",
        search_func=MagicMock(return_value=True),
        paste_func=MagicMock(return_value=True),
        enter_func=MagicMock(return_value=True),
        screenshot_func=MagicMock(return_value=str(img)),
        screen_state_func=MagicMock(
            return_value=ScreenStateDetection(ScreenState.INPUT_READY, 0.9, str(img), "ok")
        ),
        verify_contact_func=verify_func,
    )
    assert result is True
    verify_func.assert_called_once()


def test_send_message_blocked_when_verify_fails(tmp_path: Path):
    from src.message_sender import send_message
    from src.screen_state import ScreenState, ScreenStateDetection

    img = _make_image(tmp_path)
    config: dict[str, Any] = {
        "dry_run": False,
        "allow_real_send": True,
        "allowed_real_contacts": ["文件传输助手"],
        "require_known_screen_state_for_real_send": False,
        "max_retry": 1,
        "send_delay_seconds": 0,
    }
    paste_func = MagicMock(return_value=True)
    enter_func = MagicMock(return_value=True)
    verify_func = MagicMock(
        return_value=ContactVerifyResult(
            ok=False, target="文件传输助手",
            sidebar=_fail_region("sidebar"),
            title_bar=_ok_region("title_bar", "文件传输助手"),
            message="sidebar missing",
        )
    )
    result = send_message(
        config, "文件传输助手", "hello",
        search_func=MagicMock(return_value=True),
        paste_func=paste_func,
        enter_func=enter_func,
        screenshot_func=MagicMock(return_value=str(img)),
        screen_state_func=MagicMock(
            return_value=ScreenStateDetection(ScreenState.INPUT_READY, 0.9, str(img), "ok")
        ),
        verify_contact_func=verify_func,
    )
    assert result is False
    paste_func.assert_not_called()
    enter_func.assert_not_called()


# ── ocr_from_path shim ─────────────────────────────────────────────────────────

def test_ocr_from_path_shim(monkeypatch, tmp_path: Path):
    img = _make_image(tmp_path)

    class FakeReader:
        def __init__(self, langs, gpu=False): ...
        def readtext(self, p):
            return [(None, "Sample Contact", 0.95)]

    monkeypatch.setitem(sys.modules, "easyocr", SimpleNamespace(Reader=FakeReader))

    results = ocr_from_path(str(img), {"ocr_confidence_threshold": 0.3})
    assert len(results) == 1
    assert results[0]["text"] == "Sample Contact"
