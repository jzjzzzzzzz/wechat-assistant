# GUI Roadmap Prompt

## Goal

Add a local desktop GUI after command-line safety and automation are stable.

## Candidate GUI Toolkit

Prefer a simple Python-native GUI first:

- Tkinter for standard library simplicity.
- PySide/PyQt only if richer UI becomes necessary.

## GUI Views

- Dashboard
- Settings
- Contacts
- Tasks
- Message templates
- Logs
- Dry-run preview
- Safety confirmation for test sends

## UX Safety

- Dry-run status must be visible.
- Real-send controls must be disabled by default.
- Enabling real-send must require explicit settings changes.
- First real-send UI should only allow `文件传输助手`.
- Dangerous actions must show clear warnings.

## Architecture

GUI should call existing services rather than duplicating logic. Keep business logic in `src/` modules and keep GUI code thin.

## Testing

Keep core logic testable without launching GUI. GUI tests can focus on settings mapping and command dispatch.
