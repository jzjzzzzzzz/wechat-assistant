from pathlib import Path

from PIL import Image

from src.screen_state import (
    ScreenState,
    ScreenStateDetection,
    detect_screen_state,
    infer_state_from_text,
    real_send_allowed_by_screen_state,
)


def test_screen_state_detection_dataclass() -> None:
    detection = ScreenStateDetection(
        state=ScreenState.UNKNOWN,
        confidence=0.0,
        source=None,
        message="unknown",
    )

    assert detection.state == ScreenState.UNKNOWN
    assert detection.ok_for_real_send is False


def test_detect_screen_state_unknown_without_path() -> None:
    detection = detect_screen_state(None)

    assert detection.state == ScreenState.UNKNOWN
    assert detection.ok_for_real_send is False


def test_detect_screen_state_wechat_active_for_existing_image_without_ocr(tmp_path: Path) -> None:
    # When a screenshot loads successfully but no OCR data is supplied,
    # the detector infers WECHAT_ACTIVE (minimum state) instead of UNKNOWN
    # so that real-send is not unconditionally blocked when templates/OCR
    # are not yet available.
    image_path = tmp_path / "screen.png"
    Image.new("RGB", (100, 100), "white").save(image_path)

    detection = detect_screen_state(image_path)

    assert detection.state == ScreenState.WECHAT_ACTIVE
    assert detection.ok_for_real_send is True
    assert detection.source == str(image_path)


def test_infer_state_from_text_detects_input_ready() -> None:
    detection = infer_state_from_text(["聊天", "发送"], source="ocr")

    assert detection.state == ScreenState.INPUT_READY
    assert detection.ok_for_real_send is True


def test_real_send_allowed_by_screen_state_blocks_unknown() -> None:
    allowed, reason = real_send_allowed_by_screen_state(
        ScreenStateDetection(ScreenState.UNKNOWN, 0.0, None, "not sure")
    )

    assert allowed is False
    assert "blocks real send" in reason
