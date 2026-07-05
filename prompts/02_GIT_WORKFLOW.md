# Git Workflow Prompt

## Required Workflow

Always start with:

```bash
git status
```

If the worktree contains user changes, do not overwrite them. Read the relevant files and work with the changes.

## Branches

Every milestone should use a feature branch:

```bash
git checkout -b feature/<short-topic>
```

Recommended examples:

- `feature/stabilize-ui-automation`
- `feature/screen-state-machine`
- `feature/opencv-template-detection`
- `feature/gui-dashboard`

## Commits

Use one focused commit per completed milestone. Commit messages should be imperative and specific:

```bash
git commit -m "Add screen state machine"
```

Do not commit unrelated changes. Do not commit generated caches, virtual environments, or screenshots unless the milestone explicitly requires a fixture.

## Before Commit Checklist

- `pytest` passes or the failure is documented.
- Safety defaults remain dry-run.
- No WeChat databases, credentials, or private user data are added.
- Logs do not contain secrets.
- README or prompt docs are updated if behavior changes.
- `git status --short` shows only intended files.

## Merge Readiness

A branch is merge-ready when:

- Acceptance criteria are satisfied.
- Tests are passing.
- Safety rules are preserved.
- The final report states known limitations.
