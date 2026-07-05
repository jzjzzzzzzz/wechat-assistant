# M05 Add SQLite Database

## 1. Goal

Add a local SQLite database owned by WeChat Assistant for contacts, tasks, templates, and audit metadata.

## 2. Context

CSV is acceptable for early development, but a database will support GUI and history features.

## 3. Current Repository Assumptions

- CSV files exist under `data/`.
- No app-owned SQLite database exists.
- WeChat databases are forbidden.

## 4. Files Likely To Modify

- new `src/database.py`
- new `src/repositories.py`
- `config/settings.yaml`
- `tests/`
- `README.md`

## 5. Detailed Implementation Steps

1. Add `data/wechat_assistant.sqlite3` path to config.
2. Create schema initialization function.
3. Add tables for contacts, birthday tasks, templates, audit events.
4. Add repository functions with tests.
5. Keep CSV import optional and user-controlled.
6. Ensure database file is ignored unless intentionally tracked as fixture.
7. Run `pytest`.

## 6. Safety Requirements

- Never read or connect to WeChat databases.
- Store no credentials.
- Store only user-provided or visible UI-derived project data.

## 7. Testing Requirements

- Use temporary SQLite files.
- Test schema creation.
- Test insert and query for each repository.
- Run `pytest`.

## 8. Git Branch Name

`feature/sqlite-database`

## 9. Commit Message

`Add SQLite project database`

## 10. Acceptance Criteria

- Database initializes from empty state.
- Tests use temporary database paths.
- README documents the app-owned database boundary.

## 11. What Not To Do

- Do not inspect WeChat app storage.
- Do not migrate private WeChat data.
- Do not remove CSV support unless explicitly requested.

## 12. Final Report Format

Report schema, repository API, tests, safety boundary, and migration notes.
