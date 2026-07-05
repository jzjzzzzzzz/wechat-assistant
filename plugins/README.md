# Local Plugins

Plugins are local manifest-only extensions for WeChat Assistant.

This skeleton does not execute plugin Python code. A plugin may declare safe capabilities such as `template_provider` or `reminder_rule`, but any future action must still go through the core safety services.

Forbidden plugin behavior:

- reading WeChat databases
- collecting credentials
- calling `pyautogui` directly to send messages
- bypassing `dry_run` or `allow_real_send`
- loading remote code
