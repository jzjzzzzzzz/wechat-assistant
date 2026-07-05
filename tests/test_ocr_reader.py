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

    assert len(results) == 1
    assert results[0]["text"] == "high"
    assert results[0]["confidence"] == 0.8
    assert results[0]["source"] == str(image_path)


def test_read_image_text_missing_file_is_nonfatal(tmp_path: Path) -> None:
    assert read_image_text(tmp_path / "missing.png") == []


def test_read_image_text_dedupes_preprocessed_variants(monkeypatch, tmp_path: Path) -> None:
    image_path = tmp_path / "screen.png"
    Image.new("RGB", (20, 20), "white").save(image_path)

    class FakeReader:
        def __init__(self, languages, gpu=False) -> None:
            self.languages = languages
            self.gpu = gpu

        def readtext(self, image_path: str):
            confidence = 0.7
            if "gray_enhanced" in image_path:
                confidence = 0.91
            if "binary" in image_path:
                confidence = 0.82
            return [([[0, 0], [10, 0], [10, 10], [0, 10]], "文件传输助手", confidence)]

    monkeypatch.setitem(sys.modules, "easyocr", SimpleNamespace(Reader=FakeReader))

    results = read_image_text(image_path, min_confidence=0.5)

    assert len(results) == 1
    assert results[0]["text"] == "文件传输助手"
    assert results[0]["confidence"] == 0.91
    assert results[0]["variant"] == "gray_enhanced"
    assert results[0]["bbox"] == [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]]
