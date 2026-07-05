# macOS Environment Prompt

## Target Environment

- macOS
- Python 3.10+
- WeChat for Mac
- Terminal, iTerm2, or another shell app with permissions

## Required Permissions

The terminal app running Python needs:

- System Settings > Privacy & Security > Accessibility
- System Settings > Privacy & Security > Screen Recording

## Environment Checks

Use `python -m src.main check` to verify:

- platform is Darwin
- Python version is printed
- screenshot capture works
- mouse movement permission works

The command must not crash on missing permissions. It should print and log actionable instructions.

## Automation Practices

- Prefer `open -a WeChat` to launch WeChat.
- Prefer AppleScript activation over coordinates.
- Prefer `Command + F`, `Command + A`, `Enter`, and clipboard paste.
- Add small configurable delays after UI transitions.
- Keep timeout and retry behavior explicit.

## Common Failures

- Screenshot returns blank or fails: Screen Recording permission is missing.
- Mouse control fails: Accessibility permission is missing.
- WeChat does not activate: app name may differ or WeChat is not installed.
- Clipboard paste fails: clipboard permissions or focus may be wrong.

## Testing Notes

Unit tests should not require live WeChat. Mock `pyautogui`, `pyperclip`, subprocess calls, and screenshot capture.
