# Three-Stage Ridership Modeling Pipeline (decision record, 2026-07)

> Full reviewable specifications: [specs/00-pipeline.md](specs/00-pipeline.md)
> (stage gates, validation registry, governance) and per-method specs
> [01-screen-drm](specs/01-screen-drm.md) · [02-pivot-logit](specs/02-pivot-logit.md)
> · [03-stops](specs/03-stops.md).

Roles and runtime budgets set by the user: shortlist selection (<= 1 hr),
finalist picking (<= 1 hr), full modeling of the finalist (<= 8 hr/run).

| Stage | Model | Runtime | Status |
|---|---|---|---|
| 1. Shortlist | Direct-ridership screen (in-house, from the 13-arterial screen) | minutes for all of OC | rebuild from `data/derived` |
| 2. Finalists | Incremental pivot logit (this repo: `scripts/model.py` + ABC) | ~2-10 min per corridor-design | built; needs per-corridor configs |
| 3. Finalist | FTA STOPS v2.53, incremental mode | setup 2-4 wks once; ~1-6 hr/run | acquire from FTA; APC records request feeds calibration |

## Stage 1 — Direct-ridership screen (candidate generation)

A sliding-window corridor screen over `data/derived`: score every 10-15-mi
window along every major GTFS shape on (a) LODES within-corridor flows,
(b) ACS transit workers, (c) existing route-level boardings (measured APC
series, `scripts/anchor_from_apc.py` sources), (d) density/CBD anchors.
Calibrate the score's weights so it reproduces the observed ranking of
existing route productivity (boardings/revenue-hour from the same reports)
-- that turns an index into a validated direct-ridership model (DRM,
Cervero-style). Seconds per candidate; the 13-arterial screen (session
scratchpad, summarized in HANDOFF) is the prototype. Output: top 5-8
corridors with score decomposition.

Rejected for this role: TBEST (GIS/land-use setup per scenario is heavy for
dozens of windows; sketch accuracy no better than a locally-validated DRM);
Conveyal/R5 (accessibility deltas, not ridership -- useful optional overlay).

## Stage 2 — Incremental pivot logit (design comparison)

This repo, generalized: one `config/<corridor>.json` per finalist (anchor
derivation from the APC reports x route corridor-share), same model
everywhere. Rank corridor x service-design combinations on the uncapped and
ABC-calibrated headlines with FULL uncertainty; use common random numbers
(`draw_params`, shared seed) across candidates so ranking noise cancels.
Design sweeps (speed x headway x stop spacing) fall out for free.

Known gaps at this stage (acceptable for ranking, documented in README):
frozen market composition (no induced demand), small-dV-calibrated ASC.
Overlapping corridors share central Santa Ana tracts -- for joint decisions
run overlapping pairs with exclusive tract assignment as a sensitivity.

## Stage 3 — FTA STOPS v2.53 incremental mode (finalist deep model)

The de facto national standard for transit project forecasts (required
lineage for CIG/Small Starts federal funding). Free from FTA; Windows;
nationally calibrated, locally adjusted to counts. Inputs: CTPP
journey-to-work flows, Census, current + build GTFS (we already construct
build-scenario service definitions), and station/stop-level counts -- which
is exactly item 2 of `outputs/records_request_draft.md`. FTA estimates 1-2
weeks setup + 1-3 weeks forecast prep (one-time); individual runs are
typically ~1-6 hours depending on resolution -- inside the 8-hr budget for
reruns. Same incremental philosophy as stage 2, so the two cross-validate:
STOPS gets network effects (feeders, transfers, park-and-ride, full-network
cannibalization) that stage 2 approximates.

Rejected for this role: regional ABM (SCAG ActivitySim -- 12-48 hr runs,
licensing, calibration burden violates the budget and the solo-analyst
reality); TBEST (weaker mode-shift response for dramatic service changes;
not CIG-grade).

## Consistency spine

All three stages share: the measured APC anchor series, one GTFS base, and
a validation story (stage 1 validated on existing-route productivity;
stage 2 backtested/calibrated on the 2013 Bravo! 543 launch; stage 3
calibrated to current counts). Disagreement between stage 2 and stage 3 on
the finalist is signal, not error -- reconcile before publishing.

Sources: FTA STOPS page and v2.53 user guide (transit.dot.gov), TF Resource
STOPS topic, TBEST 5.0 user guide (tbest.org, updated Dec 2025), Conveyal
R5 (github.com/conveyal/r5).
