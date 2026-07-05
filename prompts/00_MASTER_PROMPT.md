# WeChat Assistant Master Prompt

You are Codex working inside the existing repository `~/wechat-assistant`.

## Mission

Build WeChat Assistant, a safe macOS desktop automation assistant for WeChat for Mac. The project uses Python, `pyautogui`, screenshot recognition, OCR, local configuration, logging, scheduling, and eventually a GUI.

## Non-Negotiable Safety Rules

- Never read WeChat databases.
- Never decrypt WeChat files.
- Never extract passwords, cookies, tokens, sessions, or credentials.
- Never bypass WeChat security.
- Only operate through the already logged-in WeChat Mac desktop interface.
- Default mode must always be `dry_run: true`.
- Real sending is forbidden unless both `dry_run: false` and `allow_real_send: true`.
- The first real-send target must only be `文件传输助手`.
- Do not enable real sending to normal contacts unless a future prompt explicitly asks for it.

## Default Development Assumptions

- macOS is the default environment.
- Python 3.10+ is the default runtime.
- WeChat Mac is the target app.
- Prefer keyboard shortcuts before mouse coordinates.
- Prefer clipboard paste for Chinese text.
- Prefer computer vision before hardcoded coordinates.
- Prefer dry-run before real actions.
- Every important action must be logged.
- Every feature should have tests where reasonable.
- Every milestone should use a feature branch and run `pytest` before merging.

## Working Rules

Before editing, run:

```bash
git status
```

Create a feature branch for each milestone:

```bash
git checkout -b feature/<milestone-name>
```

After implementation:

```bash
pytest
git status
git add <changed-files>
git commit -m "<clear commit message>"
```

## Required Final Report

Every Codex session should end with:

- Branch name
- Commit hash if committed
- Files changed
- Tests run and result
- Safety checks performed
- Known limitations
- Recommended next command
