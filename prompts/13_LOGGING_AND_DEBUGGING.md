# Logging and Debugging Prompt

## Goal

Make every automation decision understandable after the fact.

## Required Logging Format

Logs should include:

- timestamp
- level
- module name
- message

Current log file:

```text
logs/app.log
```

## What To Log

- command start
- config file load
- safety gate result
- WeChat activation attempt
- screenshot path
- OCR result count
- contact scan result count
- scheduler match count
- retry attempts
- exceptions with actionable guidance

## What Not To Log

- passwords
- cookies
- tokens
- sessions
- private full conversations
- WeChat database paths

## Debugging Artifacts

Screenshots and future debug overlays should be stored in project-controlled directories and should be excluded from Git unless they are sanitized fixtures.

## Failure Handling

Permission and UI failures should not crash with raw tracebacks in normal CLI usage. Return clear errors and write full details to logs.
