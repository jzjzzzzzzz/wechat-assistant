"""Verify screenshots before OCR so background scans do not OCR arbitrary apps."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass(frozen=True)
class ScreenshotMetadata:
    width: int
    height: int
    ocr_texts: list[str]
    dominant_left_panel_width_ratio: float | None = None


@dataclass(frozen=True)
class ScreenshotVerification:
    ok: bool
    confidence: float
    reason: str
    cues: list[str]


WECHAT_POSITIVE_CUES = (
    "微信",
    "WeChat",
    "通讯录",
    "聊天",
    "文件传输助手",
    "搜索",
    "订阅号",
)

NON_WECHAT_NEGATIVE_CUES = (
    "Terminal",
    "zsh",
    "pytest",
    "Visual Studio Code",
    "PyCharm",
    "Safari",
    "Chrome",
    "Finder",
)


def metadata_from_image(
    image_path: str | Path,
    *,
    ocr_func: Callable[..., list[dict[str, Any]]] | None = None,
) -> ScreenshotMetadata:
    path = Path(image_path)
    try:
        from PIL import Image  # type: ignore

        with Image.open(path) as image:
            width, height = image.size
    except Exception:
        width = 0
        height = 0

    texts: list[str] = []
    if ocr_func is not None:
        try:
            texts = [str(item.get("text", "")).strip() for item in ocr_func(path) if str(item.get("text", "")).strip()]
        except Exception:
            texts = []
    return ScreenshotMetadata(width=width, height=height, ocr_texts=texts)


class WeChatScreenshotVerifier:
    def __init__(self, *, min_confidence: float = 0.70) -> None:
        self.min_confidence = float(min_confidence)

    def verify_metadata(self, metadata: ScreenshotMetadata) -> ScreenshotVerification:
        cues: list[str] = []
        score = 0.0
        combined_text = " ".join(metadata.ocr_texts)

        if metadata.width >= 500 and metadata.height >= 400:
            score += 0.15
            cues.append("plausible_window_size")
        if metadata.width > 0 and metadata.height > 0:
            aspect = metadata.width / metadata.height
            if 0.45 <= aspect <= 2.4:
                score += 0.10
                cues.append("plausible_aspect_ratio")

        positive_hits = [cue for cue in WECHAT_POSITIVE_CUES if cue in combined_text]
        if positive_hits:
            score += min(0.60, 0.25 + 0.12 * len(positive_hits))
            cues.extend(f"wechat_text:{cue}" for cue in positive_hits)

        if metadata.dominant_left_panel_width_ratio is not None:
            ratio = metadata.dominant_left_panel_width_ratio
            if 0.18 <= ratio <= 0.42:
                score += 0.20
                cues.append("left_sidebar_structure")

        negative_hits = [cue for cue in NON_WECHAT_NEGATIVE_CUES if cue in combined_text]
        if negative_hits:
            score -= min(0.60, 0.30 + 0.10 * len(negative_hits))
            cues.extend(f"negative_text:{cue}" for cue in negative_hits)

        confidence = max(0.0, min(1.0, score))
        ok = confidence >= self.min_confidence
        reason = "likely WeChat screenshot" if ok else "screenshot verification below threshold"
        return ScreenshotVerification(ok=ok, confidence=confidence, reason=reason, cues=cues)

    def verify_image(
        self,
        image_path: str | Path,
        *,
        ocr_func: Callable[..., list[dict[str, Any]]] | None = None,
    ) -> ScreenshotVerification:
        return self.verify_metadata(metadata_from_image(image_path, ocr_func=ocr_func))


def should_skip_ocr(verification: ScreenshotVerification) -> bool:
    return not verification.ok
