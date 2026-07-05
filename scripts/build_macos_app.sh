#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

python -m pytest
python -m pip show pyinstaller >/dev/null 2>&1 || {
  echo "PyInstaller is not installed. Run: python -m pip install pyinstaller"
  exit 1
}

pyinstaller \
  --noconfirm \
  --windowed \
  --name "WeChat Assistant" \
  --add-data "config/settings.yaml:config" \
  --add-data "data/birthday_tasks.csv:data" \
  --add-data "data/message_templates.csv:data" \
  --add-data "data/festival_tasks.csv:data" \
  --add-data "data/reminders.csv:data" \
  packaging/pyinstaller_entry.py
