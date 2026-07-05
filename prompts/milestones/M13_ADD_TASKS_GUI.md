# M13 Add Tasks GUI

## 1. Goal

Add a GUI view for birthday tasks and future reminders with dry-run preview.

## 2. Context

Task management should be understandable and safe before scheduling becomes automatic.

## 3. Current Repository Assumptions

- Scheduler exists.
- GUI foundation exists.
- Message templates may exist.

## 4. Files Likely To Modify

- `src/gui/`
- `src/scheduler.py`
- `src/templates.py`
- tests

## 5. Detailed Implementation Steps

1. Display tasks with enabled status.
2. Add create, edit, disable controls.
3. Add preview for today's matched tasks.
4. Keep execution dry-run.
5. Validate dates and messages.
6. Add tests for task view model.
7. Run `pytest`.

## 6. Safety Requirements

- No bulk real sending.
- Non-test targets are dry-run only.
- Log preview and blocked execution.

## 7. Testing Requirements

- Test date validation.
- Test enabled filtering.
- Test dry-run preview.
- Run `pytest`.

## 8. Git Branch Name

`feature/tasks-gui`

## 9. Commit Message

`Add tasks GUI`

## 10. Acceptance Criteria

- Tasks can be created and previewed.
- Invalid tasks are rejected.
- Tests pass.

## 11. What Not To Do

- Do not start background sending by default.
- Do not add real-send to normal contacts.
- Do not bypass scheduler validation.

## 12. Final Report Format

Report task fields, preview behavior, tests, safety status, and next GUI milestone.
