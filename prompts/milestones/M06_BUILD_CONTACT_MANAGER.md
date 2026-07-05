# M06 Build Contact Manager

## 1. Goal

Create a local contact manager for project-owned contact records and OCR candidates.

## 2. Context

The app needs a reviewable contact list before any future scheduled messaging.

## 3. Current Repository Assumptions

- OCR contact cache exists.
- SQLite may exist if M05 is complete.
- Real sending to normal contacts remains forbidden.

## 4. Files Likely To Modify

- `src/contact_scanner.py`
- `src/database.py`
- `src/repositories.py`
- new `src/contact_manager.py`
- tests

## 5. Detailed Implementation Steps

1. Define contact fields: remark, source, confidence, reviewed, enabled.
2. Import OCR candidates as unreviewed records.
3. Add update and disable functions.
4. Add duplicate handling.
5. Add CLI preview command only if appropriate.
6. Add tests for import, dedupe, and review flags.
7. Run `pytest`.

## 6. Safety Requirements

- Contacts are local project records, not WeChat database records.
- Do not send to contacts from this manager.
- Keep all future send actions dry-run unless separately authorized.

## 7. Testing Requirements

- Test candidate import.
- Test duplicate contact behavior.
- Test disabled contacts are excluded from future task selection.
- Run `pytest`.

## 8. Git Branch Name

`feature/contact-manager`

## 9. Commit Message

`Build local contact manager`

## 10. Acceptance Criteria

- Contact records can be created, listed, updated, and disabled.
- OCR candidates remain reviewable.
- Tests pass.

## 11. What Not To Do

- Do not sync with WeChat internals.
- Do not auto-approve OCR contacts.
- Do not enable real sending.

## 12. Final Report Format

Report contact schema, commands or APIs, tests, safety decisions, and next GUI work.
