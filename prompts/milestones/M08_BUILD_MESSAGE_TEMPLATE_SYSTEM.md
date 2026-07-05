# M08 Build Message Template System

## 1. Goal

Add reusable local message templates for birthday, festival, and reminder messages.

## 2. Context

Templates should support personalization while keeping previews and dry-run behavior clear.

## 3. Current Repository Assumptions

- Scheduler exists.
- Contact records may exist.
- Sending is dry-run by default.

## 4. Files Likely To Modify

- new `src/templates.py`
- `data/`
- `src/scheduler.py`
- tests

## 5. Detailed Implementation Steps

1. Define template fields: name, category, body, enabled.
2. Support placeholders such as `{name}` and `{date}`.
3. Add safe rendering with missing placeholder errors.
4. Add preview command or function.
5. Keep rendered messages local until explicitly sent.
6. Add tests for rendering and validation.
7. Run `pytest`.

## 6. Safety Requirements

- Template rendering must not trigger sending.
- Preview before any send action.
- Do not store credentials or private conversations.

## 7. Testing Requirements

- Test placeholder rendering.
- Test missing variables.
- Test disabled templates.
- Run `pytest`.

## 8. Git Branch Name

`feature/message-template-system`

## 9. Commit Message

`Add message template system`

## 10. Acceptance Criteria

- Templates render deterministically.
- Bad templates fail clearly.
- Tests pass.

## 11. What Not To Do

- Do not connect templates to real sending by default.
- Do not add network template downloads.
- Do not generate spam-like behavior.

## 12. Final Report Format

Report template schema, rendering examples, tests, and safety limitations.
