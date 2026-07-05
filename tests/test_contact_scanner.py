from src.contact_scanner import clean_contact_name, extract_contact_candidates


def test_extract_contact_candidates_empty_result() -> None:
    assert extract_contact_candidates([]) == []


def test_extract_contact_candidates_removes_duplicates_and_keeps_highest_confidence() -> None:
    contacts = extract_contact_candidates(
        [
            {"text": "Alice", "confidence": 0.4, "source": "screen1.png"},
            {"text": "Alice", "confidence": 0.9, "source": "screen2.png"},
            {"text": "Bob", "confidence": 0.8, "source": "screen1.png"},
        ],
        min_confidence=0.3,
    )

    by_name = {contact["contact_name"]: contact for contact in contacts}
    assert set(by_name) == {"Alice", "Bob"}
    assert by_name["Alice"]["confidence"] == 0.9
    assert by_name["Alice"]["source"] == "screen2.png"


def test_extract_contact_candidates_filters_low_confidence() -> None:
    contacts = extract_contact_candidates(
        [
            {"text": "Low Confidence", "confidence": 0.2, "source": "screen.png"},
            {"text": "High Confidence", "confidence": 0.7, "source": "screen.png"},
        ],
        min_confidence=0.3,
    )

    assert [contact["contact_name"] for contact in contacts] == ["High Confidence"]


def test_clean_contact_name_filters_noise_and_obvious_garbage() -> None:
    assert clean_contact_name("搜索") is None
    assert clean_contact_name("!!!@@@###") is None
    assert clean_contact_name("abc!!!@@@###") is None
    assert clean_contact_name("  【文件传输助手】  ") == "文件传输助手"


def test_extract_contact_candidates_filters_obvious_garbage() -> None:
    contacts = extract_contact_candidates(
        [
            {"text": "%%%%%%", "confidence": 0.95, "source": "screen.png"},
            {"text": "正常联系人", "confidence": 0.95, "source": "screen.png"},
        ],
        min_confidence=0.3,
    )

    assert [contact["contact_name"] for contact in contacts] == ["正常联系人"]
