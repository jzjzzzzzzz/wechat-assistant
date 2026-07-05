# M10 Build GUI Dashboard

## 1. Goal

Create the first local GUI dashboard showing project status, safety mode, and common commands.

## 2. Context

The GUI should wrap existing safe services, not replace them.

## 3. Current Repository Assumptions

- CLI commands exist.
- Safety config exists.
- Core logic is testable without GUI.

## 4. Files Likely To Modify

- new `src/gui/`
- `src/main.py`
- `requirements.txt` only if a non-stdlib GUI toolkit is chosen
- tests

## 5. Detailed Implementation Steps

1. Choose Tkinter unless there is a strong reason otherwise.
2. Show dry-run and allow-real-send status.
3. Add buttons for check, screenshot, dry-run test-send, and log open.
4. Route actions to existing functions.
5. Keep long actions from freezing the UI if practical.
6. Add tests for command dispatch where reasonable.
7. Run `pytest`.

## 6. Safety Requirements

- GUI must show dry-run status clearly.
- Real-send controls disabled by default.
- No normal-contact real-send controls.

## 7. Testing Requirements

- Test dashboard config mapping.
- Test command callback dispatch with mocks.
- Run `pytest`.

## 8. Git Branch Name

`feature/gui-dashboard`

## 9. Commit Message

`Build GUI dashboard`

## 10. Acceptance Criteria

- GUI starts locally.
- Dashboard shows safety settings.
- Existing CLI still works.
- Tests pass.

## 11. What Not To Do

- Do not add marketing landing pages.
- Do not duplicate business logic in GUI.
- Do not enable real sending.

## 12. Final Report Format

Report GUI command, screenshots if useful, tests, safety behavior, and next GUI milestone.
