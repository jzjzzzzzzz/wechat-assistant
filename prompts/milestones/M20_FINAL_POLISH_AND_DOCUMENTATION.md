# M20 Final Polish and Documentation

## 1. Goal

Polish documentation, safety explanations, troubleshooting, and user workflows for a stable local release.

## 2. Context

After major features exist, the project needs coherent docs and final safety review.

## 3. Current Repository Assumptions

- Core automation exists.
- GUI and packaging may exist.
- Tests pass.

## 4. Files Likely To Modify

- `README.md`
- `prompts/`
- docs if present
- tests only if doc examples need verification

## 5. Detailed Implementation Steps

1. Review README end to end.
2. Document safety model clearly.
3. Document install, permissions, run commands, GUI, packaging.
4. Add troubleshooting for macOS permissions and OCR.
5. Verify command examples.
6. Update long-term prompts if architecture changed.
7. Run `pytest`.
8. Commit docs.

## 6. Safety Requirements

- Safety defaults must be prominent.
- Real-send risk must be explicit.
- Do not include private screenshots or logs.

## 7. Testing Requirements

- Run `pytest`.
- Run documented smoke commands if safe.
- Check links and command snippets manually.

## 8. Git Branch Name

`feature/final-polish-documentation`

## 9. Commit Message

`Polish documentation for local release`

## 10. Acceptance Criteria

- README is complete and accurate.
- Safety rules are clear.
- Setup and run commands are verified.
- Tests pass.

## 11. What Not To Do

- Do not add new features during polish.
- Do not rewrite working code unnecessarily.
- Do not minimize safety warnings.

## 12. Final Report Format

Report docs updated, commands verified, tests, remaining known issues, and release readiness.
