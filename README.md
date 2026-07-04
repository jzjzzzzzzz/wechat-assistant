# WeChat Assistant

WeChat Assistant is a macOS Python automation project for controlling the already logged-in WeChat for Mac UI with `pyautogui`, screenshots, OCR, and local configuration files.

The first phase focuses on environment checks, WeChat window control, screenshots, safe test-message sending, logging, configuration, OCR contact scanning, and a birthday-task skeleton.

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
```

## macOS Permissions

Open System Settings and enable permissions for the terminal app you use:

- Privacy & Security > Accessibility
- Privacy & Security > Screen Recording

If screenshot or mouse control fails, enable these permissions, quit and reopen the terminal, then run the command again.

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

The sender also refuses real sending to contacts other than `文件传输助手` by default.

## Troubleshooting

- Screenshot fails: enable Screen Recording permission for your terminal.
- `pyautogui` has no permission: enable Accessibility permission for your terminal.
- WeChat is not open: the project attempts `open -a WeChat`.
- Chinese input fails: messages are pasted with `pyperclip` to avoid input-method issues.
- OCR is inaccurate: OCR is best-effort and writes low-confidence results to `data/contacts_cache.csv`.

## Roadmap

- GUI
- Birthday greetings
- Festival greetings
- Contact cache management
- Automatic reminders
