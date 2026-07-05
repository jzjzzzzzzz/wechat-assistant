# M17 Add Custom Reminders

## 1. Goal

Add local custom reminders that can preview messages or notes without sending by default.

## 2. Context

Reminders broaden the app beyond birthdays and festivals while keeping dry-run behavior.

## 3. Current Repository Assumptions

- Scheduler exists.
- Template system may exist.
- GUI may exist.

## 4. Files Likely To Modify

- `src/scheduler.py`
- new `src/reminders.py`
- `data/`
- tests

## 5. Detailed Implementation Steps

1. Define reminder schema.
2. Support one-time and repeating reminders if simple.
3. Add preview command or GUI view.
4. Keep messaging dry-run.
5. Log due reminders.
6. Add tests.
7. Run `pytest`.

## 6. Safety Requirements

- Reminders must not bypass send safety.
- No real sending to normal contacts.
- Do not store secrets in reminder text.

## 7. Testing Requirements

- Test due reminder matching.
- Test disabled reminders.
- Test repeat logic if added.
- Run `pytest`.

## 8. Git Branch Name

`feature/custom-reminders`

## 9. Commit Message

`Add custom reminder planning`

## 10. Acceptance Criteria

- Reminders can be stored and previewed.
- Scheduler remains dry-run safe.
- Tests pass.

## 11. What Not To Do

- Do not send reminders automatically.
- Do not add cloud sync.
- Do not store credentials.

## 12. Final Report Format

Report reminder schema, matching rules, tests, safety status, and next plugin work.
