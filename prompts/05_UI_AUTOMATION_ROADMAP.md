# UI Automation Roadmap Prompt

## Goal

Make WeChat UI automation reliable without relying on fragile absolute coordinates.

## Priority Order

1. Keyboard shortcuts.
2. Clipboard paste.
3. AppleScript app activation.
4. Screenshot state detection.
5. Computer vision template matching.
6. Relative coordinates derived from detected UI elements.
7. Absolute coordinates only as a last resort.

## Core Workflows

- Launch or activate WeChat.
- Search for `文件传输助手`.
- Enter chat.
- Paste message.
- Dry-run without pressing send.
- Real-send only under strict safety policy.
- Capture screenshot after significant actions.

## Reliability Features

- Add explicit state checks before each action.
- Add retry with capped attempts.
- Log every state transition.
- Store screenshots on failure for debugging.
- Make delays configurable.

## Future Components

- `ScreenState`
- `ScreenStateDetector`
- `UiAction`
- `ActionResult`
- `WeChatController`

Only add these once existing functions become too hard to maintain.
