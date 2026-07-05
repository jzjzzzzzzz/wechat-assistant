# WeChat Assistant

WeChat Assistant is a macOS Python automation project for controlling the already logged-in WeChat for Mac UI with `pyautogui`, screenshots, OCR, and local configuration files.

The first phase focuses on environment checks, WeChat window control, screenshots, safe test-message sending, logging, configuration, OCR contact scanning, and a birthday-task skeleton.

## Project Status

Implemented:

- macOS environment and permission checks
- YAML configuration loading with defaults and type validation
- terminal and file logging
- WeChat for Mac launch, activation, and shortcut-based contact search
- screenshot capture
- safe dry-run test message flow
- OCR contact candidate extraction into `data/contacts_cache.csv`
- birthday task CSV matching skeleton
- pytest coverage for config, dry-run sending, and birthday matching

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

Run tests:

```bash
pytest
```

## macOS Permissions

Open System Settings and enable permissions for the terminal app you use:

- Privacy & Security > Accessibility
- Privacy & Security > Screen Recording

If screenshot or mouse control fails, enable these permissions, quit and reopen the terminal, then run the command again.

`python -m src.main check` prints the Python version, verifies that the platform is macOS, attempts a screenshot, and attempts a no-op mouse move. Permission failures are logged to `logs/app.log`.

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

The sender also refuses real sending to contacts other than `文件传输助手`.

For a real-send test, use only:

```yaml
test_contact: "文件传输助手"
dry_run: false
allow_real_send: true
require_known_screen_state_for_real_send: true
```

Then run:

```bash
python -m src.main test-send
```

The command must print `REAL SEND ENABLED`, the target, and the message before pressing Enter. If the visible screen state cannot be confirmed, the send is blocked. Do not use this path for normal contacts.

## Local Project Database

The optional SQLite database at `data/wechat_assistant.sqlite3` is owned by WeChat Assistant. It stores only project data such as reviewed contacts, local tasks, message templates, and audit events.

It must never read, import, decrypt, mirror, or inspect WeChat internal databases.

## Local Plugin Skeleton

The `plugins/` directory supports local manifest-only plugin discovery. The current skeleton validates `plugin.json` files but does not execute plugin code. Plugins cannot bypass `dry_run`, cannot call direct send actions, and cannot read WeChat databases.

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

## Roadmap

- GUI
- Birthday greetings
- Festival greetings
- Contact cache management
- Automatic reminders
