# Manual Smoke Testing

This workflow verifies the local WeChat Assistant setup without enabling real sending.

Safety defaults must stay:

```yaml
dry_run: true
allow_real_send: false
test_contact: "文件传输助手"
```

Do not change these values for normal smoke testing.

## Run The Plan Only

```bash
python -m src.main manual-test --plan-only
```

or:

```bash
python scripts/manual_smoke_test.py --plan-only
```

## Interactive Manual Smoke Test

```bash
python -m src.main manual-test
```

The workflow guides you through:

1. Checking that `dry_run` is true and `allow_real_send` is false.
2. Checking macOS Accessibility and Screen Recording permissions.
3. Confirming WeChat for Mac is open.
4. Optionally activating the WeChat window.
5. Taking a screenshot.
6. Optionally searching for `文件传输助手`.
7. Running dry-run `test-send`.
8. Confirming `logs/app.log` has entries.
9. Confirming the local project database initializes.
10. Printing the GUI command without launching a blocking GUI window.

Confirmation-gated UI actions can be run with:

```bash
python -m src.main manual-test --yes
```

This still does not enable real sending.

## GUI Check

The smoke workflow does not launch the GUI automatically because it blocks the terminal by design.
Start it manually when needed:

```bash
python -m src.main gui
```

## Expected Permission Failures

If `check` reports missing Screen Recording or Accessibility permission, you must
grant them in System Settings **and then completely restart the terminal**.

### Screen Recording

**System Settings → Privacy & Security → Screen Recording**

Add and enable whichever app you run Python from:

- **Terminal** — listed automatically (built-in)
- **iTerm2** — `/Applications/iTerm.app`
- **Visual Studio Code** — `/Applications/Visual Studio Code.app`
- **Cursor** — `/Applications/Cursor.app`

Without this permission, `screenshot` and `check` fail safely (they log the error
and exit without crashing).

### Accessibility

**System Settings → Privacy & Security → Accessibility**

Add and enable the same app listed above.

Without this permission, `pyautogui` cannot simulate keyboard or mouse events, so
WeChat window activation and input box interaction do not work.

### After Granting Either Permission

> **You must completely quit the terminal app (Cmd+Q — not just close the window)
> and reopen it.** macOS does not apply new permissions to an already-running
> process. This is the most common reason a permission appears enabled but commands
> still report a failure.

Steps:
1. System Settings → Privacy & Security → Screen Recording → add your app → toggle on.
2. System Settings → Privacy & Security → Accessibility → add your app → toggle on.
3. Quit the terminal completely with **Cmd+Q**.
4. Reopen the terminal.
5. `cd ~/学习资料/wechat-assistant && source .venv/bin/activate`
6. `python -m src.main check`

## Real Sending

This manual smoke test does not perform real sending. If a future real-send test is needed, it must only target `文件传输助手` and require explicit confirmation.
