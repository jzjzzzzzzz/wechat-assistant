# M18 Add Plugin System

## 1. Goal

Design a small local plugin system for safe extensions such as custom templates or reminder rules.

## 2. Context

Plugins can make the project flexible, but they must not bypass safety gates.

## 3. Current Repository Assumptions

- Core services exist.
- Safety policy is centralized.
- GUI or CLI can list available capabilities.

## 4. Files Likely To Modify

- new `src/plugins.py`
- new `plugins/`
- tests
- README

## 5. Detailed Implementation Steps

1. Define plugin manifest schema.
2. Load only local project plugin files.
3. Expose limited extension points.
4. Prevent plugins from sending directly.
5. Route any action through core safety services.
6. Add tests for plugin validation.
7. Run `pytest`.

## 6. Safety Requirements

- Plugins cannot access credentials.
- Plugins cannot bypass `dry_run` or `allow_real_send`.
- Plugins cannot read WeChat databases.

## 7. Testing Requirements

- Test valid manifest.
- Test invalid manifest.
- Test plugin send attempt must use safety service.
- Run `pytest`.

## 8. Git Branch Name

`feature/plugin-system`

## 9. Commit Message

`Add safe plugin system skeleton`

## 10. Acceptance Criteria

- Plugin loader is local and restricted.
- Invalid plugins fail safely.
- Tests pass.

## 11. What Not To Do

- Do not execute arbitrary remote code.
- Do not add plugin network marketplace.
- Do not let plugins call `pyautogui` directly for sends.

## 12. Final Report Format

Report plugin API, safety restrictions, tests, and extension examples.
