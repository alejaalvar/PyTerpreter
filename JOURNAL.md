# Development Journal

## 2026-06-04 - Feature: Append Redirect and Tee operators

- **Goal**: Add two new domain-specific shell operators (`>>` and `tee`) to satisfy the Milestone 3 requirement of two new DSL operators.

- **Decisions**: Extended the `Proc` dataclass with two new nullable fields (`stdout_append`, `tee`) rather than a mode flag on the existing `stdout` field, mirroring the existing pattern of independent nullable fields for each stream. Tee is implemented by injecting a Unix `tee` subprocess stage at the end of the pipeline in `execProc`, delegating the output-splitting logic to the OS rather than reimplementing it in Python. Both operators sit at `redir_level` in the grammar alongside the existing redirects.

- **Done**:
  - `RedirectAppend` and `Tee` AST dataclasses with `__str__`
  - `Proc` extended with `stdout_append` and `tee` fields
  - `evalInEnv` cases for both operators with full mutual-exclusivity error checking
  - `Pipe` case updated to block left sides that have `stdout_append` or `tee` set
  - `execProc` updated for append mode (open with `"a"`) and tee (injected stage)
  - Grammar rules added at `redir_level` in `expr.lark`
  - Transformer methods in `parse_run.py`
  - 14 unit tests in `interp_test.py`, all passing
  - 63 core regression tests passing
  - Demo test cases in `parse_run.py` verified manually

- **Next Steps**: Commit this work, then review the full Milestone 3 checklist against the PDF to confirm nothing is missing before submission.

- **Debt/TODOs**: The old `RedirectOut` case in `evalInEnv` now also checks for `stdout_append` and `tee` conflicts — this is correct but means three separate error guards exist in that case. Could be consolidated into a helper if more stdout-related operators are added in the future.

- **Lessons**: The `execProc` loop variable was originally `v.stages` — when injecting the tee stage, it was important to bind a local `stages` variable first and use that consistently in both `enumerate()` and `len()`, otherwise the stage count would be wrong.
