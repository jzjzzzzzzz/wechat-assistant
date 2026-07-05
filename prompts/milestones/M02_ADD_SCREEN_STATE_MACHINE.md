# M02 Add Screen State Machine

## 1. Goal

Add a screen state model that describes visible WeChat UI states before automation actions run.

## 2. Context

Reliable automation needs to know whether WeChat is active, search is open, a chat is open, or an unknown state is visible.

## 3. Current Repository Assumptions

- Screenshot capture exists.
- UI automation exists but is mostly action-oriented.
- No formal state machine exists yet.

## 4. Files Likely To Modify

- `src/wechat_window.py`
- `src/screenshot.py`
- new `src/screen_state.py`
- `src/main.py`
- tests under `tests/`

## 5. Detailed Implementation Steps

1. Define `ScreenState` enum or dataclass.
2. Add states such as `UNKNOWN`, `WECHAT_ACTIVE`, `SEARCH_OPEN`, `CHAT_OPEN`, `INPUT_READY`.
3. Add detector stubs that can work from screenshots.
4. Log state transitions.
5. Use state checks in UI actions where low risk.
6. Keep detection conservative: unknown is acceptable.
7. Add unit tests for state values and fallback behavior.
8. Run `pytest`.

## 6. Safety Requirements

- Unknown state must not trigger real sending.
- State detection must not access hidden WeChat data.
- Detection must use visible UI screenshots only.

## 7. Testing Requirements

- Test enum/dataclass creation.
- Test unknown fallback.
- Test action blocking when state is unknown for real send.
- Run `pytest`.

## 8. Git Branch Name

`feature/screen-state-machine`

## 9. Commit Message

`Add screen state machine`

## 10. Acceptance Criteria

- A reusable screen state representation exists.
- Existing commands still run.
- Unknown state is handled safely.
- `pytest` passes.

## 11. What Not To Do

- Do not claim perfect visual detection.
- Do not enable sending based only on state detection.
- Do not add private screenshots to Git.

## 12. Final Report Format

List implemented states, files changed, test result, safety behavior, and next state-detection work.
