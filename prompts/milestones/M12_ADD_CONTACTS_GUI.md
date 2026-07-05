# M12 Add Contacts GUI

## 1. Goal

Add a GUI view for reviewing local contacts and OCR candidates.

## 2. Context

OCR contacts need human review before they become useful for scheduling.

## 3. Current Repository Assumptions

- Contact manager exists or CSV cache exists.
- GUI foundation exists.
- Contacts are local project records.

## 4. Files Likely To Modify

- `src/gui/`
- `src/contact_manager.py`
- `src/contact_scanner.py`
- tests

## 5. Detailed Implementation Steps

1. Display contact candidates.
2. Show source and confidence.
3. Allow marking reviewed or disabled.
4. Add refresh from OCR cache.
5. Do not add send buttons to normal contacts.
6. Add tests for view model logic.
7. Run `pytest`.

## 6. Safety Requirements

- No real-send action from contacts GUI.
- OCR candidates must remain untrusted until reviewed.
- Do not read WeChat databases.

## 7. Testing Requirements

- Test contact list loading.
- Test review and disable actions.
- Test no send command is exposed in view model.
- Run `pytest`.

## 8. Git Branch Name

`feature/contacts-gui`

## 9. Commit Message

`Add contacts GUI`

## 10. Acceptance Criteria

- Contacts can be viewed and reviewed.
- No sending is enabled.
- Tests pass.

## 11. What Not To Do

- Do not auto-import hidden contacts.
- Do not auto-send to selected contacts.
- Do not store private conversations.

## 12. Final Report Format

Report GUI behavior, contact fields, tests, safety limits, and next task GUI work.
