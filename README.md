# WeChat Assistant

WeChat Assistant is a macOS Python automation project for controlling the already logged-in WeChat for Mac UI with `pyautogui`, screenshots, OCR, and local configuration files.

License: MIT

The project now includes a safe CLI foundation, a Tkinter GUI dashboard, local SQLite support, OCR/contact tooling, dry-run schedulers, local templates, audit logs, plugin manifest discovery, and macOS packaging support.

## Project Status

Implemented:

- macOS environment and permission checks
- YAML configuration loading with defaults and type validation
- terminal and file logging
- WeChat for Mac launch, activation, and shortcut-based contact search
- screenshot capture
- safe dry-run test message flow
- OCR contact candidate extraction into `data/contacts_cache.csv`
- local SQLite database owned by this project
- contact manager for reviewed/disabled local contacts
- birthday, festival, and custom reminder dry-run planning
- local message template rendering
- structured audit events for dry-run and blocked send decisions
- Tkinter dashboard with settings, contacts, tasks, and log viewer windows
- manifest-only local plugin skeleton
- macOS packaging script and packaging exclusion rules
- pytest coverage for safety, config, UI automation, OCR cleanup, database, GUI view models, schedulers, templates, plugins, and packaging helpers

## Safety

- This project does not read WeChat databases.
- This project does not crack, bypass, or modify WeChat.
- This project does not collect account names, passwords, cookies, or tokens.
- It only controls the visible WeChat for Mac interface that the user has already logged into.
- Default target is only `文件传输助手`.
- Default mode is `dry_run: true`, so no real message is sent.
- Real sending is allowed only when both settings are true:
  - `dry_run: false`
  - `allow_real_send: true`
- Birthday and future batch features are dry-run first and must not be used for uncontrolled group sending.
- GUI views do not expose normal-contact real-send actions.
- Plugin manifests cannot enable direct sending or bypass safety gates.

## Setup

```bash
cd ~/学习资料/wechat-assistant
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
python -m src.main check
python -m src.main screenshot
python -m src.main test-send
python -m src.main ocr
python -m src.main scan-contacts
python -m src.main birthday-check
python -m src.main gui
```

To register the daily birthday job with macOS `launchd`:

```bash
./scripts/install_birthday_launchagent.sh
```

This installs a user LaunchAgent that calls `scripts/birthday_cron.sh` at `00:00`
while you are logged in. To remove it:

```bash
./scripts/uninstall_birthday_launchagent.sh
```

Run tests:

```bash
pytest
```

## macOS Permissions

WeChat Assistant needs two macOS permissions to take screenshots and control the keyboard/mouse.
Open **System Settings → Privacy & Security** and grant both to the app you run Python from.

### Screen Recording

Path: **System Settings → Privacy & Security → Screen Recording**

Add and enable the app you use to run Python:

| App | Common path |
|-----|-------------|
| Terminal | built-in, listed automatically |
| iTerm2 | `/Applications/iTerm.app` |
| Visual Studio Code | `/Applications/Visual Studio Code.app` |
| Cursor | `/Applications/Cursor.app` |

Without Screen Recording permission, `python -m src.main screenshot` and
`python -m src.main check` will fail with a permission error (safe failure — the
project does not crash, it logs and exits).

### Accessibility

Path: **System Settings → Privacy & Security → Accessibility**

Add and enable the same app (Terminal / iTerm2 / VS Code / Cursor).

Without Accessibility permission, `pyautogui` cannot move the mouse or type, so
`test-send` and `manual-test` will not be able to interact with WeChat windows.

### After Granting Permissions

> **Important:** After enabling either permission, you must **completely quit** the
> terminal app (Cmd+Q, not just close the window) and **reopen it**. macOS does not
> apply the new permission to an already-running process. Skipping this step is the
> most common reason the permission appears granted but commands still fail.

Quick checklist:
1. Open System Settings → Privacy & Security → Screen Recording, add your terminal app, toggle it on.
2. Open System Settings → Privacy & Security → Accessibility, add your terminal app, toggle it on.
3. Quit the terminal completely (Cmd+Q).
4. Reopen the terminal and reactivate the virtual environment: `source .venv/bin/activate`
5. Run `python -m src.main check` to verify.

`python -m src.main check` prints the Python version, verifies that the platform is
macOS, attempts a screenshot, and attempts a no-op mouse move. Permission failures are
logged to `logs/app.log`.

## Dry Run and Real Sending

The default configuration is safe:

```yaml
dry_run: true
allow_real_send: false
test_contact: "文件传输助手"
```

`python -m src.main test-send` searches for `文件传输助手` and prepares the configured test message. In dry-run mode it logs what would happen and does not press Enter to send.

Real sending requires both:

```yaml
dry_run: false
allow_real_send: true
```

The sender refuses real sending unless the target is explicitly present in
`allowed_real_contacts`. `文件传输助手` is always included as the built-in safe
test target.

For a real-send test, use only:

```yaml
test_contact: "文件传输助手"
dry_run: false
allow_real_send: true
require_known_screen_state_for_real_send: true
```

For a real birthday send to a personal contact, keep `dry_run: true` in
`config/settings.yaml` and add the exact WeChat remark/display name to
`allowed_real_contacts`. The scheduled script uses `--force-send` to enable real
sending in memory for that run only, then the same whitelist and screen-state
checks still apply.

Then run:

```bash
python -m src.main test-send
```

The command must print `REAL SEND ENABLED`, the target, and the message before pressing Enter. If the visible screen state cannot be confirmed, the send is blocked. Do not use this path for normal contacts.

## GUI

Start the local dashboard:

```bash
python -m src.main gui
```

The dashboard shows dry-run status and opens safe local tools:

- environment check
- screenshot
- dry-run test send
- settings editor
- contacts reviewer
- birthday task manager
- read-only log viewer

The GUI calls existing services. It does not duplicate or weaken sending safety rules.

## Local Data Files

Project-owned local data lives under `data/`. The tracked CSV files in this
repository are sample placeholders for local development, not production
records. Before publishing your own fork, replace any personal names, remarks,
dates, or messages with neutral examples.

- `contacts_cache.csv`: OCR candidate cache
- `birthday_tasks.csv`: birthday dry-run task input
- `message_templates.csv`: local message templates
- `festival_tasks.csv`: festival dry-run task input
- `reminders.csv`: custom reminder dry-run input
- `wechat_assistant.sqlite3`: optional project-owned runtime database, ignored by Git

These files are not WeChat internal data.

## Local Project Database

The optional SQLite database at `data/wechat_assistant.sqlite3` is owned by WeChat Assistant. It stores only project data such as reviewed contacts, local tasks, message templates, and audit events.

It must never read, import, decrypt, mirror, or inspect WeChat internal databases.

## Local Plugin Skeleton

The `plugins/` directory supports local manifest-only plugin discovery. The current skeleton validates `plugin.json` files but does not execute plugin code. Plugins cannot bypass `dry_run`, cannot call direct send actions, and cannot read WeChat databases.

## Packaging

Local macOS packaging is documented in `packaging/README.md`. Packaging must exclude runtime logs, screenshots, local SQLite databases, caches, and virtual environments. The packaged app keeps dry-run defaults and still requires macOS Accessibility and Screen Recording permissions.

Packaging helper:

```bash
./scripts/build_macos_app.sh
```

The script requires PyInstaller to be installed and runs `pytest` before building.

## Testing Only 文件传输助手

Keep this default in `config/settings.yaml`:

```yaml
test_contact: "文件传输助手"
test_message: "WeChat Assistant test message"
dry_run: true
allow_real_send: false
```

Then run:

```bash
python -m src.main test-send
```

With the default dry-run settings, the command prints and logs the planned action without touching the WeChat input box or sending a message.

## Troubleshooting

- Screenshot fails: enable Screen Recording permission for your terminal, then restart the terminal app.
- `pyautogui` has no permission: enable Accessibility permission for your terminal, then restart the terminal app.
- WeChat is not open: the project attempts `open -a WeChat`; if that fails, open WeChat manually and make sure you are logged in.
- Chinese input fails: messages are pasted with `pyperclip` to avoid input-method issues.
- OCR is inaccurate: OCR is best-effort and writes cleaned candidate results to `data/contacts_cache.csv`; take a clearer screenshot and retry.
- `easyocr` downloads models slowly: this is expected on first use.
- `pytest` is missing: activate the virtual environment and run `pip install -r requirements.txt`.
- GUI does not open: verify Python was installed with Tkinter support.
- Real-send test is blocked: confirm both config flags are set, the target is in `allowed_real_contacts`, and screen state can be recognized; blocked is the safe default.
- Packaging fails: install PyInstaller in the active virtual environment and retry.

## Roadmap

- Improve computer vision templates with sanitized assets
- Improve OCR accuracy with crop regions and manual review
- Expand GUI polish
- Add controlled packaging verification
- Keep normal-contact real sending disabled unless a future safety prompt explicitly authorizes it
