# M16 Add Festival Messages

## 1. Goal

Add dry-run festival message planning using local templates and local task data.

## 2. Context

Festival greetings are similar to birthday tasks but require date rules and template categories.

## 3. Current Repository Assumptions

- Scheduler and templates exist.
- Normal-contact real sending is still forbidden.
- GUI may exist.

## 4. Files Likely To Modify

- `src/scheduler.py`
- `src/templates.py`
- new `data/festival_tasks.csv`
- tests

## 5. Detailed Implementation Steps

1. Define festival task schema.
2. Add local date matching.
3. Add preview output.
4. Reuse template renderer.
5. Keep execution dry-run.
6. Add tests.
7. Run `pytest`.

## 6. Safety Requirements

- Dry-run only by default.
- No group sending.
- No normal-contact real-send enablement.

## 7. Testing Requirements

- Test festival date matching.
- Test disabled festival tasks.
- Test template rendering.
- Test blocked execution.
- Run `pytest`.

## 8. Git Branch Name

`feature/festival-messages`

## 9. Commit Message

`Add festival message dry-run planning`

## 10. Acceptance Criteria

- Festival plans can be previewed.
- Invalid tasks fail clearly.
- Tests pass.

## 11. What Not To Do

- Do not send festival messages automatically.
- Do not add external calendar scraping.
- Do not create spam workflows.

## 12. Final Report Format

Report schema, date rules, tests, safety blocks, and next reminder work.
