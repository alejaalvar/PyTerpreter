# Development Journal

## 2026-06-04 - Feature: just_parse + test3.py bug fixes (146/146)

- **Goal**: Add the missing `just_parse` function required by the professor's test suite and fix all failures revealed by running test3.py.

- **Decisions**: Six distinct bugs were found and fixed. `just_parse` returns `None` on errors rather than raising, matching the professor's convention for testing invalid syntax. The `else` clause of if-then-else was changed from `expr` to `assign_level` to eliminate the seq ambiguity without affecting the then-clause (which correctly keeps `expr` so semicolons inside then-branches still parse). The `_ambig` handler was given a targeted override for the `show(x)` case rather than a global rule, to preserve strict ambiguity detection elsewhere. The `Assign` case was given a new guard: assigning to a variable currently holding a `Closure` raises an error, which differs from assigning to a `FunLoc` (letfun-bound name) but follows the same principle.

- **Done**:
  - `just_parse` added to `parse_run.py` (returns `None` on parse/ambiguity errors)
  - `id` transformer fixed: `"show"` → `"read"` for `Read()` special-casing
  - Grammar: `"else" assign_level` removes if/seq ambiguity (tests 29, 92)
  - `_ambig` prefers `Show` alternatives to resolve `show(x)` ambiguity (test 89)
  - `Show` case now prints just `v` instead of `"result: v"` (tests 23, 24, 27, 28, etc.)
  - `Assign` case raises error when variable currently holds a `Closure` (test 37)
  - 146/146 test3.py passing, 77/77 across all suites

- **Next Steps**: Commit and push. Milestone 3 is now complete.

- **Debt/TODOs**: The `Closure`-check in `Assign` means that once a variable is assigned a closure, it can't be reassigned. This follows from test_37 but the rule isn't explicitly stated in the spec — worth confirming with the professor if time allows.

- **Lessons**: `just_parse` returning `None` vs raising is a subtle API contract — the professor's tests use `assertEqual(got, None)` not `assertRaises`. The `else expr` → `else assign_level` grammar fix is the classic "dangling else"-style ambiguity: the else clause must not greedily consume sequence operators at the same level.

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
