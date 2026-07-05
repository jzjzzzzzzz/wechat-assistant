# Safety Rules Prompt

## Absolute Prohibitions

- Do not read WeChat database files.
- Do not decrypt WeChat files.
- Do not inspect private WeChat storage.
- Do not extract passwords, cookies, tokens, sessions, or credentials.
- Do not bypass WeChat security, login, or anti-abuse controls.
- Do not automate hidden APIs or undocumented network endpoints.

## Allowed Operating Model

Only control the already logged-in WeChat Mac desktop interface using:

- keyboard shortcuts
- clipboard paste
- screenshots
- OCR
- computer vision
- visible UI state

## Default Sending Policy

Default configuration must remain:

```yaml
dry_run: true
allow_real_send: false
test_contact: "文件传输助手"
```

Real sending is forbidden unless:

```yaml
dry_run: false
allow_real_send: true
```

Even then, the first real-send target must only be `文件传输助手`.

## Logging Policy

Log:

- command start and end
- safety decisions
- dry-run decisions
- target contact name
- message template identifier or short message preview
- screenshot path
- errors and retry attempts

Do not log:

- credentials
- tokens
- full private conversations
- WeChat database paths
- sensitive personal data beyond user-provided task inputs

## Review Questions

Before implementing any automation feature, answer:

- Does this require reading hidden WeChat data? If yes, stop.
- Can it be done through visible UI state? If no, stop.
- Is dry-run the default? If no, fix it.
- Is real sending guarded by two independent settings? If no, fix it.
- Does it have tests for blocked sending paths? If no, add them.
