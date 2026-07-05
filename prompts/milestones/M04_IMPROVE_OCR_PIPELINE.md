# M04 Improve OCR Pipeline

## 1. Goal

Improve OCR cleanup, confidence handling, and contact candidate extraction.

## 2. Context

OCR currently reads screenshots and extracts rough contact candidates. It needs better filtering and tests.

## 3. Current Repository Assumptions

- `src/ocr_reader.py` exists.
- `src/contact_scanner.py` exists.
- `data/contacts_cache.csv` is the cache output.

## 4. Files Likely To Modify

- `src/ocr_reader.py`
- `src/contact_scanner.py`
- `config/settings.yaml`
- `tests/`

## 5. Detailed Implementation Steps

1. Add configurable confidence threshold.
2. Add OCR cleanup rules for common UI noise.
3. Add optional crop-region support if simple.
4. Keep OCR failure non-fatal.
5. Save source screenshot path and confidence.
6. Add tests for cleanup and deduplication.
7. Run `pytest`.

## 6. Safety Requirements

- OCR candidates are not approved send targets.
- Do not use hidden WeChat data.
- Do not commit private screenshots.

## 7. Testing Requirements

- Test empty OCR result.
- Test duplicate removal.
- Test low-confidence filtering.
- Test obvious乱码 filtering.
- Run `pytest`.

## 8. Git Branch Name

`feature/improve-ocr-pipeline`

## 9. Commit Message

`Improve OCR contact pipeline`

## 10. Acceptance Criteria

- OCR cleanup is deterministic.
- Contact cache schema remains documented.
- OCR failures are logged and do not crash CLI.

## 11. What Not To Do

- Do not auto-send to OCR results.
- Do not scrape hidden data.
- Do not store sensitive conversations.

## 12. Final Report Format

Report cleanup rules, changed config, tests, remaining OCR weaknesses, and next step.
