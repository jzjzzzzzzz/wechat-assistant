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


def clean_contact_name(text: str) -> str | None:
    value = re.sub(r"\s+", " ", text).strip()
    if not value:
        return None
    if len(value) > 40:
        return None
    if len(value) == 1 and not re.search(r"[\u4e00-\u9fffA-Za-z0-9]", value):
        return None
    if not re.search(r"[\u4e00-\u9fffA-Za-z0-9]", value):
        return None
    if re.fullmatch(r"[\W_]+", value):
        return None
    return value


def extract_contact_candidates(ocr_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    contacts: list[dict[str, Any]] = []
    created_at = datetime.now().isoformat(timespec="seconds")

    for item in ocr_results:
        name = clean_contact_name(str(item.get("text", "")))
        if not name or name in seen:
            continue
        seen.add(name)
        contacts.append(
            {
                "contact_name": name,
                "source": item.get("source", "ocr"),
                "confidence": float(item.get("confidence", 0.0)),
                "created_at": created_at,
            }
        )
    return contacts


def save_contacts_cache(contacts: list[dict[str, Any]], path: Path = CONTACTS_CACHE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = ["contact_name", "source", "confidence", "created_at"]
    dataframe = pd.DataFrame(contacts, columns=columns)
    dataframe.to_csv(path, index=False, encoding="utf-8")
    LOGGER.info("Saved %s contact candidate(s) to %s", len(contacts), path)


def scan_contacts(config: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        ocr_results = read_latest_screenshot_text(config)
        contacts = extract_contact_candidates(ocr_results)
        save_contacts_cache(contacts)
        return contacts
    except Exception as exc:
        LOGGER.error("Contact scan failed: %s", exc)
        save_contacts_cache([])
        return []
