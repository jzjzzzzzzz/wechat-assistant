# OCR Contact Recognition Prompt

## Goal

Improve contact candidate extraction from screenshots while respecting privacy and safety boundaries.

## Allowed Inputs

- User-triggered screenshots.
- Visible WeChat UI text.
- Local CSV files created by the project.

## Forbidden Inputs

- WeChat databases.
- Decrypted WeChat files.
- Credential stores.
- Hidden app containers.

## OCR Pipeline

1. Capture or locate latest screenshot.
2. Run OCR with EasyOCR.
3. Normalize whitespace.
4. Remove empty lines.
5. Remove obvious UI noise.
6. Remove obvious乱码.
7. Deduplicate.
8. Save candidates to `data/contacts_cache.csv`.

## CSV Schema

```text
contact_name,source,confidence,created_at
```

## Improvement Ideas

- Add confidence threshold.
- Add allowlist and blocklist cleanup terms.
- Add screenshot crop regions.
- Add language configuration.
- Add manual review flags.
- Add tests for cleanup functions.

## Safety

OCR results are candidates, not verified contacts. Never use OCR candidates for real sending without explicit future approval and a separate safety milestone.
