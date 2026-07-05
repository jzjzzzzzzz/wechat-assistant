# M14 Add Log Viewer GUI

## 1. Goal

Add a GUI log viewer for `logs/app.log` and future audit events.

## 2. Context

Users need to inspect errors, permission issues, dry-run decisions, and blocked actions.

## 3. Current Repository Assumptions

- Logging exists.
- GUI foundation exists.
- Audit logs may exist.

## 4. Files Likely To Modify

- `src/gui/`
- `src/logger.py`
- `src/audit.py`
- tests

## 5. Detailed Implementation Steps

1. Display recent log lines.
2. Add refresh control.
3. Add level filtering if simple.
4. Add open log file location action if safe.
5. Avoid loading huge files entirely if logs grow.
6. Add tests for log parsing.
7. Run `pytest`.

## 6. Safety Requirements

- Do not display secrets.
- Do not add hidden data readers.
- Keep log viewer read-only.

## 7. Testing Requirements

- Test tailing log lines.
- Test missing log file behavior.
- Test level filtering if added.
- Run `pytest`.

## 8. Git Branch Name

`feature/log-viewer-gui`

## 9. Commit Message

`Add log viewer GUI`

## 10. Acceptance Criteria

- GUI can show recent logs.
- Missing log file does not crash.
- Tests pass.

## 11. What Not To Do

- Do not edit logs from GUI.
- Do not display private screenshots.
- Do not expose hidden system files.

## 12. Final Report Format

Report viewer behavior, filters, tests, privacy considerations, and next step.
