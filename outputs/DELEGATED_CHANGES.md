# Delegated changes — the accumulating diff

**Purpose.** A running, append-only log of changes the controller made WITHOUT
owner ratification, under the delegation authority of
[docs/review-verification.md → Delegation](../docs/review-verification.md).
Drift is invisible per-item and obvious in a list. The NEXT pre-registration
FOLDS THIS LOG IN as an explicit aggregate diff and states, in aggregate, what
the delegated changes did to the pipeline since the last one.

**The two guards** (restated so this file stands alone):

- **GUARD 1 — escalation tripwire.** A delegated change that alters ANY
  published number OR flips ANY pass/fail STOPS being housekeeping and RETURNS
  for owner ratification with BOTH versions (before/after). The test is on the
  OUTPUT, not the intent. Every row below carries an explicit
  *number/verdict moved?* column; a "YES" row is one that was escalated (it does
  not stay in the delegated set).
- **GUARD 2 — accumulating diff.** This file. Quoted in full by the next
  pre-registration.

**Never delegated** (owner-only, always): values that bind an UNRUN fit —
thresholds, the estimand, the failure-mode subset (`screen_gate_failure_modes`),
cost-model parameters, the ranking measure.

---

## Log (append-only; newest at the bottom)

Seeded 2026-07-22 with the changes already delegated this stage-1 arc.

| # | date | class | change | number / verdict moved? | frozen artifacts |
|---|------|-------|--------|-------------------------|------------------|
| 1 | 2026-07-21 | metric-definition correction | **Rule 6 — universe-change / perturbation-identity check** (docs/review-verification.md). Codified that a perturbation which CHANGES the object set requires an identity-based metric, decomposed into no-longer-exists (universe change, disclosed separately) vs exists-but-moved (genuine ranking instability); naive set-membership churn and naive rank correlation over a changed universe are INVALID. | NO — a review-harness rule; recomputes no committed statistic | byte-identical (b88f9b65 / 83aeb032 / 3b1d5526) |
| 2 | 2026-07-21 | housekeeping | **Rule 7 — spec-validity (assumption-surfacing) review** (docs/review-verification.md). Added a second review question ("name the load-bearing assumption that, if wrong, most changes the answer") alongside reproduce-the-numbers. | NO — adds a review question; changes no artifact | byte-identical |
| 3 | 2026-07-21 | universe-invariance / identity fix | **min_sep identity-unit correction.** The anchor-lattice de-risk read scored min_sep churn in IDENTITY units (host street / segment overlap), decomposing the 90→57 anchor / 209→91 corridor universe change out of the ranking-instability signal (the concrete rule-6 instance). Applies to the anchor-world de-risk read, not to any committed verdict. | NO — corrects a de-risk read; no published verdict flips; the v2.0/v2.1/v2.2 window-world verdicts are untouched | byte-identical |
| 4 | 2026-07-22 | housekeeping | **Screen-fork consolidation.** v2.1 and v2.2 consolidated onto ONE shared block predictor object (`screen_common_v21.compute_predictors_v21`), fit and scan single-sourced across versions; no `screen_common_v22` fork. Pure refactor, guarded by the cross-version byte-identity gate (test_screen_cross_version XV1/XV3). | NO — byte-identity preserved (guard-1 satisfied: no committed sha moved) | byte-identical |
| 5 | 2026-07-22 | housekeeping | **Canonical pointer file** `outputs/STAGE1_CANONICAL.md`. Single authority on which `screen_results*.json` a downstream product may consume; supersession rule requires updating it in the same commit that lands a new decision-grade artifact. | NO — a pointer/doc; consumes no number | byte-identical |

**Aggregate read (for the next pre-registration to fold in).** As of 2026-07-22
the five delegated changes are, in aggregate, TWO review-harness rules (6, 7),
ONE identity-unit metric correction applied to a de-risk read only (3), and TWO
pure-housekeeping items (4 consolidation, 5 canonical pointer). NONE moved a
published number or flipped a pass/fail: the three frozen screen artifacts stay
byte-identical at b88f9b65 / 83aeb032 / 3b1d5526, and no `ordinal_ok` changed.
No delegated change set a bar an unrun fit will be judged against — every
threshold, the estimand, and the `screen_gate_failure_modes` subset remain
owner-ratified. Guard 1 fired zero escalations because zero numbers moved.

## 2026-07-22 (owner-review round)
- item-9 pass-condition resolution (spec 01 §12.1): NOT delegated — fit-binding,
  ratified by the owner review directing pick-one-reading-or-demote; implemented
  as demote-the-undecidable-component (clean-benchmark top-8 membership stays the
  necessary condition; discrimination vs naive baseline -> reported diagnostic
  with mandatory consistent-with-population-count disclosure).
- README-47 plain-terms statement (item 1 scoped OUT, not closed) — tier 2.
- Harness tiering + premise-check + tree-only-record rules — tier 2.
