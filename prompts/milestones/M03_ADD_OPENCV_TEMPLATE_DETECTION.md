# M03 Add OpenCV Template Detection

## 1. Goal

Add OpenCV-based template matching for visible WeChat UI elements.

## 2. Context

Template detection will reduce dependence on fixed coordinates and support future state detection.

## 3. Current Repository Assumptions

- `opencv-python` is in requirements.
- Screenshot capture works.
- No template directory may exist yet.

## 4. Files Likely To Modify

- new `src/vision.py`
- new `assets/templates/` if sanitized templates are added
- `src/screen_state.py`
- `tests/`

## 5. Detailed Implementation Steps

1. Add a template matching helper using OpenCV.
2. Return bounding box, confidence, and template name.
3. Add config values for confidence threshold.
4. Add optional debug overlay support, disabled by default.
5. Use synthetic test images for unit tests.
6. Document where templates should live.
7. Run `pytest`.

## 6. Safety Requirements

- Use only visible screenshots.
- Do not commit private WeChat screenshots.
- Detection must not override sending gates.

## 7. Testing Requirements

- Test positive template match with synthetic image.
- Test no-match behavior.
- Test confidence threshold.
- Run `pytest`.

## 8. Git Branch Name

`feature/opencv-template-detection`

## 9. Commit Message

`Add OpenCV template detection`

## 10. Acceptance Criteria

- Template matching function is reusable and tested.
- No private image fixtures are committed.
- Debug artifacts are ignored unless sanitized.

## 11. What Not To Do

- Do not rely on OCR for every UI element.
- Do not use absolute coordinates as the primary detection result.
- Do not add unsafe send behavior.

## 12. Final Report Format

Report detector API, test fixtures, thresholds, test results, and limitations.
