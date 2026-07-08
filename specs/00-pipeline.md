# Spec 00 — Corridor Evaluation & Network Development Pipeline

Status: DRAFT for review · 2026-07-08
Companions: [01-screen-drm.md](01-screen-drm.md), [02-pivot-logit.md](02-pivot-logit.md),
[03-stops.md](03-stops.md). Decision record: [../PIPELINE.md](../PIPELINE.md).

## 1. Purpose

Select, compare, and forecast rapid-transit corridor investments in Orange
County with three models matched to three decisions:

| Stage | Decision | Model | Budget/run | Candidates in -> out |
|---|---|---|---|---|
| 1 | Which corridors deserve analysis? | Direct-demand regression screen | <= 1 hr (whole county) | all arterials -> 5-8 |
| 2 | Which corridor + service design? | Incremental pivot logit (this repo) | <= 1 hr (all finalists) | 5-8 -> 1-2 |
| 3 | What will the finalist carry? | FTA STOPS v2.53, incremental mode | <= 8 hr/run | 1-2 -> forecast of record |

A model may only inform the decision its stage owns. Stage-1 numbers are
never quoted as forecasts; stage-2 rankings are never republished as
final ridership; stage 3 is the number of record.

## 2. Consistency spine (shared across stages)

- **One anchor series**: measured OCTA route-level boardings
  (`scripts/anchor_from_apc.py`; FY2017 / FY2019 / FY2020-Q3 reports in
  `data/raw/apc/`, fetched by `scripts/download_data.py`).
- **One GTFS base** per analysis vintage (`data/raw/gtfs/`), with
  build-scenario service definitions expressed the same way at stage 2
  (config JSON) and stage 3 (build GTFS).
- **One demand fabric**: LODES 2022 tract O-D + ACS 2023 B08141
  (`data/derived/`), used by stages 1-2; stage 3 uses CTPP equivalents.
- **Validation registry** (section 5): every calibration target and
  held-out test is listed once, with its stage assignment. No experiment
  may be used for both calibration and validation.

## 3. Stage gates

- **Gate 1 -> 2**: top 5-8 corridors by stage-1 score, PLUS any corridor
  within one standard error of the cutoff (report ties, don't hide them),
  PLUS underservice-residual outliers (fundamentals >> current ridership).
- **Gate 2 -> 3**: highest ABC-calibrated P50 among finalists, unless
  bands overlap so much that secondary criteria (cost proxy, overlap
  conflicts, equity) decide — in which case the overlap is stated in the
  gate memo, not resolved silently.
- **Gate 3 -> publish**: stage-3 vs stage-2 reconciliation memo required
  (section 6).

## 4. Governance (binding, from project owner)

1. No baked-in filters or caps anywhere in the pipeline; calibrated and
   uncalibrated results shown side by side.
2. Every structural knob appears in a one-at-a-time sensitivity table.
3. Judgment calls and dilemmas are logged (README "Known issues" pattern)
   as they arise, not summarized after the fact.
4. Repos stay GitHub-committable: raw blobs gitignored, derived tables
   small and committed, seeds fixed, every figure regenerable by script.

## 5. Validation registry

| Event | Data status | Assignment |
|---|---|---|
| Bravo! 543 launch (Jun 2013) | measured (post: FY2017+; pre-anchor: press/history) | Stage-2 calibration (in use) |
| Bravo! 529 launch (Feb 2019) | measured (pre: Rt 29 FY2017/FY2019; post: FY2020-Q3) | Stage-2 calibration (planned) |
| FY2017->FY2020 service-change panel | boardings measured; service diffs need archived GTFS | Stage-2 calibration, down-weighted |
| Harbor TSP speed-up (Sep 2024, +7-8% speed) | needs post-2024 route data (records request) | **HELD OUT** — registered out-of-sample prediction |
| 543 launch ramp FY2014-16 | records request | sharpens 543 target when it arrives |
| Existing-route productivity cross-section | measured | Stage-1 fit + LOO validation |
| COVID collapse/recovery | measured | anchor/trend stress test ONLY (not a service experiment) |
| LA Metro Rapid / NextGen | public | optional transferability check, never calibration |

Cap: 3-4 same-agency calibration targets at stage 2. Marginal experiments
become validation. Rationale: with ~3 identifiable parameters, further
targets narrow the parameter posterior without narrowing true forecast
error (structural error binds), producing overconfident intervals.

## 6. Reconciliation protocol (stage 2 vs stage 3)

Before publishing a stage-3 forecast: run stage 2 on the identical build
definition; if P50s differ by more than the stage-2 P10-P90 half-width,
decompose the gap (anchor vs market coverage vs network effects vs
response coefficients) in a short memo committed to the repo.
Disagreement is signal about model risk, not an error to suppress.

## 7. Open questions for review

- Q1: Shortlist size — is 5-8 right, or should gate 1 pass more/fewer?
- Q2: Should the stage-2 induced-demand column (spec 02 §6) be shown at
  gate 2, or is it stage-3-adjacent scope?
- Q3: How many finalists get full STOPS treatment — 1 or 2?
- Q4: Is a cost proxy (route-miles x lane treatment) in scope for gate 2,
  or is this pipeline ridership-only?
