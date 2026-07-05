# Computer Vision Roadmap Prompt

## Goal

Use computer vision to identify WeChat UI state and reduce coordinate fragility.

## Recommended Tools

- Pillow for image loading and simple operations.
- OpenCV for template matching, thresholding, contours, and feature detection.
- OCR only when text content is needed.

## Detection Targets

- WeChat main window active.
- Search box visible.
- Search result list visible.
- Chat input area visible.
- Send button visible.
- Empty or failed search state.

## Template Strategy

Keep templates under a future directory such as:

```text
assets/templates/
```

Template names should describe UI states:

- `wechat_search_box.png`
- `wechat_chat_input.png`
- `wechat_send_button.png`

Do not include private user content in templates.

## Implementation Guidance

- Use confidence thresholds from config.
- Return structured detection results with bounding boxes and confidence.
- Save debug overlays only when requested.
- Prefer relative coordinates from detected boxes.
- Make detection functions testable with fixture images.

## Safety

Computer vision may guide UI actions, but it must not weaken sending gates. Detection success does not imply permission to send.
