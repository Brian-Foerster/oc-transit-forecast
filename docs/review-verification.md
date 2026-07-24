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

## Mechanism finding (arc audit, 2026-07-21)

A full audit of all 25 review agents in the arc found NO unknown stubs (only the
two already known) and resolved that neither slipped through with nothing backing
it: stub #1 was caught by a dedicated reverify workflow; stub #2 by a controller
anti-tuning recompute documented in the commit message. But it corrected the
FAILURE MODEL. Both stubs are **clobbered records over genuine work**, not lazy
no-work approvals: each agent made ~36 Bash calls and populated real reproduced
numbers in intermediate StructuredOutput calls, then a final empty/placeholder
StructuredOutput overwrote the good record (the journal keeps only the last
submission). The review WORK happened; the RECORD is what is corrupt.

Consequence for the rules below: **rule 4 (tool-use count) is unreliable for this
failure mode** — these stubs had HIGH tool counts and rule 4 would misclassify
them as genuine. The reliable catch is **rule 3 (programmatic post-check on the
reproduced content)**, which fires on an empty/absent record regardless of how
much work the agent did. Rule 4 only catches a genuine no-work agent (0 tool
calls); treat it as a weak corroborating signal, not the primary gate.

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

4. **Tool-use / journal evidence (controller-side, WEAK signal — see mechanism
   finding).** A review claiming recomputation while making ~0 compute-tool calls
   did no work. BUT the audit showed the arc's actual stubs had ~36 tool calls
   each (clobbered records over genuine work), so a low-tool-count test produces
   FALSE NEGATIVES here and must not be the primary gate. Use it only to catch a
   genuine no-work agent; rely on rule 3 for the clobbered-record case. A stronger
   controller-side check when a record looks empty: inspect ALL of the agent's
   StructuredOutput submissions in its transcript (not just the last journal
   line) — a good intermediate submission clobbered by a final placeholder means
   the work exists and can be recovered, which is what happened to both arc stubs.

5b. **Reviewer instruction (prevents the clobber at the source).** Tell review
   agents to submit their StructuredOutput exactly ONCE, as the final action, with
   the complete reproduced block — never a placeholder/dry-run structured output
   before the real one, since the harness keeps only the last submission.

## Rule 6 — the universe-change class (perturbation-identity check)

The same error has now appeared THREE times in this project: computing a
comparison over a set that the perturbation itself changed.
1. window_10/window_15 — a length change alters the window UNIVERSE; naive
   scalar churn compared different denominators (resolved: separate host-shape
   unit + threshold).
2. rho-over-survivors — a correlation computed only over objects that survived
   the perturbation, silently dropping the churned ones (the tell-tale
   signature: churn 2.0 alongside rho 0.999; caught mid-run and fixed).
3. min_sep set-churn — the anchor-lattice change (90 to 57 anchors, 209 to 91
   corridors) counted as ranking churn; the headline 2.0 top-8 churn partly
   measured UNIVERSE change, not ranking instability, which is why it could
   exceed 1.0.

STANDING CHECK (binding for every perturbation/robustness row, and a required
reviewer assertion): state whether the perturbation (a) RESCORES a fixed object
set, or (b) CHANGES the object set. For (b), naive set-membership churn and
naive rank correlation are both INVALID — an IDENTITY-BASED metric is required:
match objects across universes by identity (host street / segment overlap /
stable key), and DECOMPOSE the result into no-longer-exists (universe change,
disclosed separately) vs exists-but-moved (genuine ranking instability). A
perturbation row that does not carry this statement is a review finding.

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


## Rule 7 — the spec-validity review (assumption-surfacing), distinct from reproduce-the-numbers

Every review harness above tests IMPLEMENTATION FIDELITY: does the code compute
what the spec says. A from-scratch reimplementation matching byte-for-byte
confirms exactly that and NOTHING about whether the spec is RIGHT. The same
party has written the spec, the code, and most of the review, so spec-validity
has had no structurally-independent check — every conceptual error this project
caught (the regime narrative, top-vs-margin stability, the version fork, the
tripwire min/max defect, the universe-change class) came from OUTSIDE review,
not from any reproduce-the-numbers pass.

For consequential runs, add a SECOND review with a different question. Not
"reproduce the numbers" but: **name the assumption that, if wrong, would most
change this answer.** The reviewer is instructed to (a) list the load-bearing
assumptions (estimand form, exposure convention, universe-defining constants,
the ranking measure, the cost model), (b) for each, state which way the answer
moves if it is wrong, and (c) name the single one it would most want an outside
expert to challenge. An APPROVE that cannot name a load-bearing assumption is
itself a finding. This does not replace the reproduce-the-numbers review; it
runs alongside it and targets the failure mode reproduction cannot reach.
