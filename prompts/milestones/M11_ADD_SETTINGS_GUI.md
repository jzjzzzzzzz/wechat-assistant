# M11 Add Settings GUI

## 1. Goal

Add GUI controls for viewing and editing safe local settings.

## 2. Context

Users need to understand dry-run and permission settings without editing YAML manually.

## 3. Current Repository Assumptions

- GUI dashboard exists.
- Config loader validates settings.
- Safety defaults are dry-run.

## 4. Files Likely To Modify

- `src/gui/`
- `src/config_loader.py`
- tests
- README if GUI command changes

## 5. Detailed Implementation Steps

1. Display current settings.
2. Allow editing non-dangerous settings.
3. Require extra confirmation for `dry_run: false`.
4. Keep `allow_real_send` disabled unless explicitly edited.
5. Validate before saving.
6. Add rollback or cancel behavior.
7. Add tests for validation.
8. Run `pytest`.

## 6. Safety Requirements

- Make dangerous settings visually explicit.
- Do not silently enable real sending.
- Keep first real target restricted to `文件传输助手`.

## 7. Testing Requirements

- Test config save validation.
- Test dangerous setting confirmation logic.
- Test invalid type rejection.
- Run `pytest`.

## 8. Git Branch Name

`feature/settings-gui`

## 9. Commit Message

`Add settings GUI`

## 10. Acceptance Criteria

- Settings GUI reads and writes valid config.
- Dangerous settings require explicit confirmation.
- Tests pass.

## 11. What Not To Do

- Do not bypass config validation.
- Do not hide dry-run state.
- Do not enable normal-contact sending.

## 12. Final Report Format

Report settings supported, validation behavior, tests, and remaining GUI gaps.
