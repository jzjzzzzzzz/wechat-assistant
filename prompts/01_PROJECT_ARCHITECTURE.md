# Project Architecture Prompt

## Goal

Keep WeChat Assistant modular, testable, and safe while it grows from command-line automation into a GUI desktop assistant.

## Current Layers

- `config/`: local YAML settings.
- `data/`: CSV caches and task inputs.
- `logs/`: runtime log files.
- `screenshots/`: screenshot artifacts.
- `src/`: application modules.
- `tests/`: pytest test suite.
- `prompts/`: long-term Codex development instructions.

## Module Responsibilities

- `config_loader.py`: default settings, type validation, config file loading.
- `logger.py`: terminal and file logging setup.
- `mac_permissions.py`: macOS permission and environment checks.
- `wechat_window.py`: WeChat launch, activation, and keyboard navigation.
- `screenshot.py`: capture and locate screenshots.
- `ocr_reader.py`: OCR text extraction from screenshots.
- `contact_scanner.py`: OCR cleanup and contact candidate caching.
- `message_sender.py`: safe dry-run and real-send guarded message sending.
- `scheduler.py`: birthday and future scheduled task logic.
- `main.py`: CLI routing.

## Architecture Principles

- Keep UI automation separated from business logic.
- Keep safety gates centralized and easy to test.
- Keep OCR and computer vision modules replaceable.
- Keep persistent data behind clear interfaces.
- Avoid global mutable state except logging.
- Avoid absolute coordinates as the only control method.
- Prefer pure functions for matching, parsing, and validation.

## Future Direction

The app should evolve toward these internal services:

- `SafetyPolicy`
- `WeChatController`
- `ScreenStateDetector`
- `ContactRepository`
- `TaskRepository`
- `MessageTemplateService`
- `AuditLogService`
- `GuiApp`

Do not introduce these abstractions until they reduce real complexity.
