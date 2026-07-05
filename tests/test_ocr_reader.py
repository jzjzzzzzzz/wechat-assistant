import sys
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from src.ocr_reader import read_image_text


def test_read_image_text_filters_by_confidence(monkeypatch, tmp_path: Path) -> None:
    image_path = tmp_path / "screen.png"
    Image.new("RGB", (20, 20), "white").save(image_path)

    class FakeReader:
        def __init__(self, languages, gpu=False) -> None:
            self.languages = languages
            self.gpu = gpu

        def readtext(self, image_path: str):
            return [
                (None, "low", 0.2),
                (None, "high", 0.8),
            ]

    monkeypatch.setitem(sys.modules, "easyocr", SimpleNamespace(Reader=FakeReader))

    results = read_image_text(image_path, min_confidence=0.5)

    assert results == [{"text": "high", "confidence": 0.8, "source": str(image_path)}]


def test_read_image_text_missing_file_is_nonfatal(tmp_path: Path) -> None:
    assert read_image_text(tmp_path / "missing.png") == []
