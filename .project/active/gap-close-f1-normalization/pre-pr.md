# Pre-PR Report: GAP-CLOSE F1 TEAx Normalization

**Stage:** Pre-PR
**Date:** 2026-07-18
**Branch:** `constraint-exec-epic`
**Base:** `main` at `7560d65`
**Audit verdict:** Certify

## Scope

The focused GAP-CLOSE F1 changes add the executor failure-context marker, shared evaluator
normalization, focused regressions, a locked fixture producer and provenance record, seven external
cases, the sealed generated package, the feature workflow artifacts, and the `CURRENT_WORK.md`
update. The existing branch contains 69 earlier commits over `main`; this stage does not rewrite or
remove them.

`.orchestrate-logs/` remains untracked and is excluded from the focused commit and PR contents.

## Project-Defined Checks

- `.venv/bin/pytest`: 346 passed in 14.44 seconds.
- `git diff --check`: passed.
- No project ruff, black, mypy, or other required lint configuration or script exists, so no
  unrelated lint tooling was added to the gate.

## Diff and Artifact Hygiene

- Reviewed the complete focused runtime, test, producer, provenance, case, generated-output, and
  project-artifact scope.
- No secret or credential patterns were found in the scoped files.
- No `__pycache__`, `.pyc`, `.pyo`, editor backup, or platform transient files were found in the
  feature or sealed fixture trees.
- No debug breakpoint or debug-print artifacts were found. TODO-like matches are workflow prose or
  the sealed generator's deterministic, contract-hashed `IMPLEMENTATION_BACKLOG.md`.
- No unexpected large or binary artifact was found. The largest scoped non-document artifact is
  the generated contract verifier at 15,315 bytes.
- The sealed fixture acceptance check passed as part of the repository suite. It verifies package
  name, executable fingerprint, graph/YAML/TEAx order, seal loading, and exact contract file
  coverage.
- No unrelated uncommitted user change was included.

## Submission Status

Local commit `Normalize exceptional arithmetic failures` was created with the complete focused
scope. Remote submission is not available in this environment. `gh auth status` reports that the
configured token for `rwestwood89` is invalid. The sandboxed push could not resolve GitHub, and the
approved external push reached GitHub but failed with `Permission denied (publickey)`.

After restoring GitHub authentication and authorizing an SSH key for `git@github.com`, run:

```bash
gh auth login -h github.com
git push -u origin constraint-exec-epic
gh pr create --base main --head constraint-exec-epic \
  --title "Add constraint evaluation, study workflow, and F1 normalization" \
  --body-file .project/CONSTRAINT_EXEC_PR_BODY.md
```

Do not archive or close the feature item during this action.
