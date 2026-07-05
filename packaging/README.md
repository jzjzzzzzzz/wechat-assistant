# Packaging

The recommended local macOS packaging path is PyInstaller.

Packaging must preserve safe defaults:

- `dry_run: true`
- `allow_real_send: false`
- `test_contact: "文件传输助手"`

Private runtime artifacts must not be packaged:

- `.venv/`
- `logs/`
- `screenshots/`
- `debug/`
- SQLite runtime databases
- pytest caches

Build command:

```bash
./scripts/build_macos_app.sh
```

The output is expected under `dist/`. The generated app still requires macOS Accessibility and Screen Recording permissions.
