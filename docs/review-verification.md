# Review-phase verification harness

Codified 2026-07-21 after two adversarial-review subagents returned stub
approvals on consequential computations:

- phase-2b v2.1 fit review → `{"findings": [], "verdict": "test"}` (placeholder verdict)
- v2.2 pre-registration review → `{"verdict": "APPROVE", "findings": []}` (38 chars, no evidence)

Neither caused a bad commit — the controller independently re-verified before
committing in both cases — but each silently added zero assurance while
appearing to pass. The review schema `{verdict, findings}` is trivially
satisfiable with a no-work object, so a budget-starved or lazy agent emits the
minimal valid response.

## The controlling principle

**Reviews are corroboration, not the gate.** The commit gate for a consequential
result is the *controller's own* independent recomputation of the load-bearing
number, compared against both the implementer's claim and the review's. That is
what made both stubs harmless. Everything below makes stubs *loud* (detected
automatically) so the controller is not relying on catching them by hand — but
the controller recompute stays the real gate.

## The four hardening rules (apply to every consequential review phase)

1. **Enum the verdict.** `verdict ∈ {APPROVE, APPROVE-WITH-FIXES, REJECT}` in
   the review schema. A placeholder like `"test"` is then structurally
   impossible. (Cheapest catch; would have blocked stub #1.)

2. **Require a `reproduced` block.** Make `reproduced` a *required* schema object
   carrying the specific numbers the reviewer must have computed to verify (the
   coefficients, the sign fractions, N/clusters, the decision statistics,
   pass/fail). Empty `findings` is legal only alongside a populated `reproduced`.
   This raises the floor from "no work" to "at least produce the numbers."
   (Proven: added to the v2.2 *fit* review → came back genuine, where the two
   without it stubbed. Would have blocked both stubs.)

3. **Programmatic post-check in the workflow script.** After the review returns,
   the script itself asserts the reproduced numbers match the artifact within
   tolerance, and throws otherwise:
   ```js
   if (!review.reproduced ||
       Math.abs(review.reproduced.b1 - fit.b1) > TOL ||
       review.reproduced.ordinal_ok !== fit.ordinal_ok) {
     throw new Error('review did not reproduce the result — re-run required')
   }
   ```
   A stub then *fails the workflow* (and re-runs on resume) instead of passing.
   The harness rejects the stub, not the human.

4. **Tool-use / journal evidence (controller-side, hardest to fake).** Genuine
   independent recomputation *requires* running Python and reading files. A
   review claiming it recomputed the fit while making ~0 compute-tool
   (Bash/Read) calls did no work — schema-forcing (rule 2) can be satisfied by
   *copying* the implementer's numbers, but a fabricated tool trace cannot. After
   the workflow, inspect the review agent's `journal.jsonl` / `agent-*.jsonl`:
   a review agent with fewer than ~5 compute-tool calls that claims recomputation
   is a stub. This is the check that catches a schema-satisfying copy-paste.

## When to apply

Consequential computations only — fits, verdicts, irreversible commits,
governed-method-changes. Not routine doc edits. For the highest-stakes single
results (e.g. a stage verdict), escalate to refute-by-default framing (reviewer
defaults to REJECT unless it can independently reproduce) or 2–3 independent
reviewers whose disagreement with a stub is visible.

## Residual risk

Rules 1+2+3+4 together make a *silent* stub nearly impossible; rule 5 (controller
recompute) makes a stub that still slips through *harmless*. A determined agent
could copy numbers (defeats 2) but cannot fake the journal tool trace (caught by
4), and cannot make an independent controller recompute agree with a wrong result
(caught by 5). That combination is the standard for consequential reviews going
forward.
