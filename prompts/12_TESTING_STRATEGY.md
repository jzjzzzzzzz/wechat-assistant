# Testing Strategy Prompt

## Goal

Build confidence without requiring live WeChat for normal test runs.

## Test Categories

- Unit tests for config validation.
- Unit tests for safety policy.
- Unit tests for birthday matching.
- Unit tests for OCR cleanup.
- Unit tests for repository/database logic.
- Mocked tests for UI automation calls.
- Optional manual integration tests for live macOS WeChat.

## Default Test Command

```bash
pytest
```

## Mocking Rules

Mock:

- `pyautogui`
- `pyperclip`
- screenshots
- subprocess AppleScript calls
- EasyOCR model loading
- time delays

## Safety Tests

Every sending-related milestone must test blocked paths:

- dry-run prevents real UI action
- missing `allow_real_send` prevents send
- unsafe target prevents send
- retry logic stops after `max_retry`

## Fixtures

Future fixture screenshots should be synthetic or sanitized. Do not commit private WeChat screenshots unless explicitly sanitized.
