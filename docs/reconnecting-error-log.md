# Reconnecting Error Log

Date: 2026-07-05

## Symptom

One message send could trigger repeated reconnect/search attempts. When `max_retry`
was set to 5, the send flow could delegate that same retry budget into the
contact-search flow, making each outer send attempt run its own inner search
retry loop.

## Evidence

Local `logs/app.log` showed nested retry behavior before the fix:

```text
Send attempt 1/3 for target=<redacted>
Searching WeChat contact by shortcuts. target=<redacted> attempt=1/3
```

This means the top-level send retry and the lower-level search retry were both
using the same `max_retry` value.

## Fix

`send_message` now passes a copied config with `max_retry` forced to `1` into
the contact-search step. The send layer remains the single owner of the total
retry count and still records every failed attempt with screenshot metadata in
the audit log.

## Verification

```text
.venv/bin/python -m pytest tests/test_message_sender.py tests/test_wechat_window.py
14 passed
```

Full suite status from the original local workspace:

```text
.venv/bin/python -m pytest
137 passed, 2 failed
```

The 2 failures were existing local configuration expectations:

```text
tests/test_config_loader.py::test_default_dry_run_is_true
tests/test_config_loader.py::test_default_allow_real_send_is_false
```

They failed because the local `config/settings.yaml` had real sending enabled
(`dry_run: false`, `allow_real_send: true`), while the tests expect the default
safe config.
