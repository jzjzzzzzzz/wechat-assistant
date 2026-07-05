"""Contact candidate extraction from OCR results."""

from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from src.ocr_reader import read_latest_screenshot_text


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOGGER = logging.getLogger(__name__)


CONTACTS_CACHE = PROJECT_ROOT / "data" / "contacts_cache.csv"
DEFAULT_NOISE_TERMS = {
    "微信",
    "通讯录",
    "发现",
    "我",
    "搜索",
    "聊天",
    "朋友圈",
    "视频号",
    "看一看",
    "搜一搜",
}


def clean_contact_name(text: str, noise_terms: set[str] | None = None) -> str | None:
    noise_terms = noise_terms or DEFAULT_NOISE_TERMS
    value = re.sub(r"\s+", " ", text).strip()
    value = value.strip("｜|[]【】()（）{}<>《》:：;；,.，。")
    if not value:
        return None
    if value in noise_terms:
        return None
    if len(value) > 40:
        return None
    if re.search(r"[\x00-\x08\x0b-\x1f\x7f]", value):
        return None
    if len(value) == 1 and not re.search(r"[\u4e00-\u9fffA-Za-z0-9]", value):
        return None
    if not re.search(r"[\u4e00-\u9fffA-Za-z0-9]", value):
        return None
    if re.fullmatch(r"[\W_]+", value):
        return None
    useful_chars = re.findall(r"[\u4e00-\u9fffA-Za-z0-9]", value)
    if len(useful_chars) / max(len(value), 1) < 0.45:
        return None
    if re.search(r"([^\w\s\u4e00-\u9fff])\1{2,}", value):
        return None
    return value


def extract_contact_candidates(
    ocr_results: list[dict[str, Any]],
    *,
    min_confidence: float = 0.3,
    noise_terms: set[str] | None = None,
) -> list[dict[str, Any]]:
    by_name: dict[str, dict[str, Any]] = {}
    created_at = datetime.now().isoformat(timespec="seconds")

    for item in ocr_results:
        confidence = float(item.get("confidence", 0.0))
        if confidence < min_confidence:
            continue
        name = clean_contact_name(str(item.get("text", "")), noise_terms=noise_terms)
        if not name:
            continue
        existing = by_name.get(name)
        if existing is None or confidence > float(existing["confidence"]):
            by_name[name] = {
                "contact_name": name,
                "source": item.get("source", "ocr"),
                "confidence": confidence,
                "created_at": created_at,
            }
    return list(by_name.values())


def save_contacts_cache(contacts: list[dict[str, Any]], path: Path = CONTACTS_CACHE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = ["contact_name", "source", "confidence", "created_at"]
    dataframe = pd.DataFrame(contacts, columns=columns)
    dataframe.to_csv(path, index=False, encoding="utf-8")
    LOGGER.info("Saved %s contact candidate(s) to %s", len(contacts), path)


def scan_contacts(config: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        ocr_results = read_latest_screenshot_text(config)
        contacts = extract_contact_candidates(
            ocr_results,
            min_confidence=float(config.get("ocr_confidence_threshold", 0.3)),
        )
        save_contacts_cache(contacts)
        return contacts
    except Exception as exc:
        LOGGER.error("Contact scan failed: %s", exc)
        save_contacts_cache([])
        return []
