# M19 Add App Packaging

## 1. Goal

Prepare local macOS packaging for easier use after CLI and GUI are stable.

## 2. Context

Packaging should not hide permission requirements or safety settings.

## 3. Current Repository Assumptions

- GUI exists.
- Tests pass.
- Safety defaults are stable.

## 4. Files Likely To Modify

- packaging scripts
- `README.md`
- `requirements.txt`
- `pyproject.toml` if introduced
- tests

## 5. Detailed Implementation Steps

1. Choose packaging approach, likely PyInstaller.
2. Document build requirements.
3. Exclude `.venv`, logs, screenshots, caches, private data.
4. Preserve config defaults.
5. Add packaging smoke test where possible.
6. Update README.
7. Run `pytest`.

## 6. Safety Requirements

- Packaged app must default to dry-run.
- Do not package private logs or screenshots.
- Do not package credentials.

## 7. Testing Requirements

- Run unit tests.
- Run packaging smoke command if available.
- Manually verify app opens if GUI exists.

## 8. Git Branch Name

`feature/app-packaging`

## 9. Commit Message

`Add macOS packaging support`

## 10. Acceptance Criteria

- Packaging instructions are reproducible.
- Unsafe files are excluded.
- Tests pass.

## 11. What Not To Do

- Do not require disabling macOS security.
- Do not sign with unknown credentials.
- Do not ship private artifacts.

## 12. Final Report Format

Report package command, output path, exclusions, tests, and manual verification.
