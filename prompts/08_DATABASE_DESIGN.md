# Database Design Prompt

## Goal

Introduce a local project-owned database when CSV files become insufficient.

## Important Boundary

This database must be created and owned by WeChat Assistant. It must never read, import, decrypt, mirror, or inspect WeChat internal databases.

## Candidate Technology

Use SQLite with Python standard library `sqlite3` unless a future feature clearly needs an ORM.

## Possible Tables

- `contacts`
- `birthday_tasks`
- `message_templates`
- `send_attempts`
- `audit_events`
- `settings_overrides`

## Design Principles

- Keep migrations simple and explicit.
- Store only user-provided or visible UI-derived data.
- Add `created_at` and `updated_at`.
- Add `enabled` flags for tasks.
- Add audit fields for safety decisions.
- Never store credentials.

## Migration Path

1. Keep CSV support.
2. Add SQLite repository layer.
3. Import existing CSV project data only after user confirmation.
4. Add tests for schema creation and repository methods.

## Safety

Database additions must not enable real sending. Sending remains governed by `dry_run` and `allow_real_send`.
