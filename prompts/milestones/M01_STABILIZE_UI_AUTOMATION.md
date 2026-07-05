# M01 Stabilize UI Automation

## 1. Goal

Make existing WeChat window activation, search, paste, and screenshot flows more reliable on macOS without adding broad new product features.

## 2. Context

The project currently uses `open -a WeChat`, AppleScript activation, keyboard shortcuts, clipboard paste, and dry-run safety gates. This milestone improves robustness and observability.

## 3. Current Repository Assumptions

- `src/wechat_window.py` exists.
- `src/message_sender.py` keeps dry-run safe.
- `src/screenshot.py` can capture screenshots.
- Tests already run with `pytest`.

## 4. Files Likely To Modify

- `src/wechat_window.py`
- `src/message_sender.py`
- `src/config_loader.py`
- `tests/test_message_sender.py`
- new tests under `tests/`

## 5. Detailed Implementation Steps

1. Run `git status`.
2. Create the feature branch listed below.
3. Add structured return values for UI actions if needed.
4. Add configurable wait and retry behavior for activation and search.
5. Keep keyboard shortcuts as the default path.
6. Add failure screenshots where useful.
7. Add tests with mocked `pyautogui`, `pyperclip`, and subprocess calls.
8. Run `pytest`.
9. Commit only relevant files.

## 6. Safety Requirements

- Do not weaken dry-run behavior.
- Do not press Enter in dry-run.
- Do not enable sending to normal contacts.
- Do not read WeChat databases or hidden files.

## 7. Testing Requirements

- Mock successful activation.
- Mock activation failure.
- Mock search failure.
- Verify dry-run does not call UI actions.
- Run `pytest`.

## 8. Git Branch Name

`feature/stabilize-ui-automation`

## 9. Commit Message

`Stabilize WeChat UI automation`

## 10. Acceptance Criteria

- UI automation functions return clear success/failure values.
- Errors include actionable logs.
- Tests cover success and failure paths.
- `pytest` passes.

## 11. What Not To Do

- Do not add GUI.
- Do not add real contact sending.
- Do not hardcode absolute screen coordinates as the only strategy.

## 12. Final Report Format

Report branch, commit hash, changed files, tests run, safety checks, limitations, and next recommended milestone.
