# Release and Packaging Prompt

## Goal

Eventually package WeChat Assistant for local macOS use while preserving safety defaults.

## Packaging Candidates

- Python virtual environment for development.
- `pipx` style local install for advanced users.
- PyInstaller app bundle for non-technical users.

## Release Requirements

- README installation instructions are current.
- Safety defaults are documented.
- `pytest` passes.
- No private screenshots or logs are packaged.
- No credentials or secrets are packaged.
- macOS permissions are documented.

## Packaging Notes

GUI packaging may require special handling for:

- Screen Recording permission prompt.
- Accessibility permission prompt.
- EasyOCR/PyTorch model size.
- app bundle signing or quarantine behavior.

## Versioning

Use simple semantic versions once packaging starts:

```text
0.1.0
0.2.0
1.0.0
```

Keep release notes focused on safety, automation reliability, and user-visible behavior.
