# Background WeChat scanning architecture

This document designs the next fallback unread scanner. It is architecture and skeleton code only; it does not enable real sending and does not implement full auto-reply behavior.

## Safety invariants

- Keep `dry_run: true`.
- Keep `allow_real_send: false`.
- Do not send WeChat messages.
- Do not read WeChat databases.
- Do not decrypt WeChat files.
- Do not extract passwords, cookies, tokens, sessions, or credentials.
- Do not bypass WeChat security.
- Do not OCR arbitrary apps.
- Do not rely on absolute coordinates as the only method.
- If the WeChat window is hidden, minimized, fully covered, off-screen, on another Space, or cannot be verified, skip scanning.

The first implementation target is: WeChat window is visible on the current display but not frontmost.

## Desired pipeline

```text
WindowLocator
  -> WindowCapture
  -> WeChatScreenshotVerifier
  -> OCR unread chat list
  -> AutoReplyEvent candidates
```

The existing activation-based scanner remains a later fallback only. It must be configurable and disabled by default.

## Config

```yaml
background_scan:
  enabled: true
  prefer_background_capture: true
  allow_activate_wechat_fallback: false
  require_screenshot_verification: true
  verifier_min_confidence: 0.70
  debug_screenshot_dir: "screenshots/background_scan"
  max_scan_interval_seconds: 30
```

`allow_activate_wechat_fallback` is intentionally false by default so background scanning cannot unexpectedly focus WeChat.

## WindowLocator

Module: `src/window_locator.py`

Responsibilities:

- Find WeChat windows without activating WeChat.
- Prefer Quartz Window Services because it can provide `window_id`, owner, title, onscreen status, and bounds.
- Use Accessibility or AppleScript only as a metadata fallback where Quartz is unavailable.
- Return structured window records:
  - `window_id`
  - `owner_name`
  - `window_title`
  - `bounds`
  - `is_visible`
  - `is_minimized_or_hidden`

Failure behavior:

- No visible WeChat window means no scan.
- Hidden, minimized, implausibly small, or off-screen windows are skipped.
- Errors are returned in `WindowLocatorResult` and logged, not raised into daemon code.

## WindowCapture

Module: `src/window_capture.py`

Responsibilities:

- Try to capture by `window_id` first.
- If window-id capture is unsupported, capture the visible screen region using the located window bounds.
- Save debug screenshots under `screenshots/background_scan/`.
- Return `WindowCaptureResult` with method, path, message, and error.

Important limitation:

Visible-region capture can only capture pixels visible on the current Space. If another app covers WeChat, macOS may capture the covering app. This is why screenshot verification is mandatory before OCR.

Permission requirement:

- Screen Recording permission is required.
- Capture failure must return a clear error result and skip scanning.

## WeChatScreenshotVerifier

Module: `src/wechat_screenshot_verifier.py`

Responsibilities:

- Verify a screenshot is likely WeChat before OCR unread extraction.
- Use conservative visual/OCR cues:
  - WeChat text markers such as `微信`, `WeChat`, `通讯录`, `聊天`, `文件传输助手`, `搜索`
  - plausible window dimensions and aspect ratio
  - future sidebar/chat-list structure detection
  - negative cues such as Terminal, browser, editor, and test-runner text
- Return confidence and cue details.
- Skip OCR when confidence is below `background_scan.verifier_min_confidence`.

This component is the guardrail that prevents OCR of Terminal, browsers, editors, or other apps.

## FallbackUnreadScanner integration plan

Current scanner:

```text
activate WeChat -> screenshot -> OCR
```

Target scanner:

```text
find visible WeChat window in background
  -> capture by window_id or visible region
  -> verify screenshot is likely WeChat
  -> OCR unread chat list
```

Integration rules:

- Use background scanner first when `background_scan.enabled` and `prefer_background_capture` are true.
- If background location, capture, or verification fails, return no unread candidates by default.
- Only use the older activation scanner when `allow_activate_wechat_fallback` is true.
- Keep activation fallback disabled by default.
- All scan paths remain dry-run and must not send messages.

## Testing strategy

Unit tests must not require real WeChat, real screenshots, macOS Screen Recording permission, or GUI activation.

Tests should use:

- Synthetic `ScreenshotMetadata`
- Mock window records
- Mock capture functions
- Mock OCR text lists

Required test coverage:

- verifier accepts likely WeChat metadata
- verifier rejects Terminal/browser/editor-like metadata
- verifier rejects low-confidence screenshots
- minimized or hidden windows are skipped
- activation fallback is disabled by default

## Known macOS limitations

- Quartz window capture behavior varies by macOS version and permission state.
- Screen Recording permission is mandatory for screen pixels.
- Minimized windows generally cannot be captured as useful visible pixels.
- Windows on another Space may be absent or stale in capture APIs.
- Fully covered windows may produce pixels from the covering app when using region capture.
- Accessibility permission may be needed for robust minimized/hidden detection.

The safe default is to skip scanning whenever visibility, capture, or screenshot identity is uncertain.
