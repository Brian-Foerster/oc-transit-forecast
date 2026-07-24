# Stage-1 canonical artifact pointer

**This file is the single authority on which stage-1 screen artifact a
downstream product (the gate-1 memo) may consume.** Do not read any other
`screen_results*.json` into a downstream product without updating this file.

## Current canonical: `outputs/screen_results_v22.json`  (v2.2, productivity estimand)

- Fit: `log(boardings/RVH)` on the 300-route-year / 63-cluster OC panel
  (commit `c0d1f97`→`… v2.2 fit` lineage; sha `3b1d5526`).
- **Verdict: `ordinal_ok = FALSE`, `decision_format = threshold_shortlist`.**
  Criterion 1 (demand signal) PASSES (b1/b2 sign fractions 0.908/0.997);
  criteria 2/3 (ranking stability) FAIL. So the canonical stage-1 output is
  the **threshold shortlist + measured indicators, NOT an ordinal ranking.**
- The gate-1 memo consumes the shortlist from THIS file, per spec 01 §4b.

## Superseded / do-not-consume
- `outputs/screen_results.json` (v2.0) — preserved byte-identical (`b88f9b65`)
  as the pre-registration regression anchor only. NOT current.
- `outputs/screen_results_v21.json` (v2.1) — preserved byte-identical
  (`83aeb032`) as a pre-registration record only. NOT current.

## Supersession rule
When a later governed-method-change (e.g. a v2.4 BCA-queue build) lands a new
decision-grade artifact, update the "Current canonical" line here **in the same
commit** that lands it, and record the prior canonical under superseded. The
canonical pointer changing is itself a reviewable event.
