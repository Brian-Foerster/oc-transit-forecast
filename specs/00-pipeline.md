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
  - *Division of labor (review 2026-07-08):* the ABC-calibrated number is
    the **decision metric** at gates; the uncapped number is the
    **transparency companion**, always shown alongside. This is
    calibration against local observed data, not a literature filter, and
    so does not violate governance rule 1 — but the two roles are
    distinct and both numbers always appear together. Final gate
    authority remains with the project owner via the gate memo.
  - *Cost proxy:* SUPERSEDED for the chosen mode (elevated automated
    light metro, decision 2026-07-08) by the capital-cost module,
    [04-capital-cost.md](04-capital-cost.md) — LOW / US-TYPICAL bands,
    tiebreak-only, never combined with ridership into a single score.
    The old route-miles x lane-treatment proxy is retained only if BRT
    alternatives re-enter the study.
  - *Economic-potential layer (defined, adopted 2026-07-08):* a
    per-finalist descriptive column read alongside ridership — never
    fused into a score, never additive with user benefits (land markets
    largely capitalize the same time savings the ridership model already
    values; two lenses on one benefit). Per station catchment (1/2-mi
    buffer): (1) **capacity ceiling** — developable/underused parcels x
    zoning headroom -> potential net new units / commercial sq ft,
    computed as TWO ceilings (base municipal zoning vs base + CA
    state-law overlays: SB 9, AB 2011, density bonus — the static local
    ceiling is soft in CA); (2) **value base x premium band** — market-
    adjusted property value (NOT raw assessed value; Prop 13 makes
    assessor rolls lag decades, worst in the underused catchments where
    capacity is best) x a mode-matched hedonic premium band — with the
    2026-07-08 mode decision (elevated automated light metro) this is
    the rail-class band, ~5-25%, permanence-keyed (elevated guideway =
    high permanence; comparators: SkyTrain / Canada Line-class hedonics,
    not bus-rapid studies), positioned secondarily by ordinal ridership
    rank within the finalist set; (3) **realization gate** —
    permitted-density and market-demand markdown from "physically
    possible" to "realizable". Output: one table row per finalist
    (capacity band, uplift $ band, realization flag) + a one-line read,
    in the gate memo. Implemented as a script + committed CSV
    (repo rule: regenerable by script), built once gate 1 produces a
    finalist set. Corridor spans five cities' zoning codes — that is
    the layer's main cost, and why it runs at finalist scale only.
  - *Second finalist:* advances to stage 3 only when gate-2 bands
    overlap (conditional, not a fixed count).
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
5. **Two-way firewall between ridership and economic layers.** The
   economic-potential column never informs the ridership number, and the
   ridership machinery's induced-demand sensitivity (spec 02 §4.5b) is
   never justified by the development column — otherwise the "two
   lenses" silently become a cascade of speculative elasticities. Value
   uplift and user benefits are presented as alternative measurements of
   the same benefit, never summed.
6. **Every asserted quantity is an assumptions-registry entry;
   `check_assumptions.py` green is a standing validation gate.** The
   single-source registry (`scripts/assumptions.py`, spec 08) owns every
   value code imports and enumerates every structural choice as a
   sensitivity row keyed by a stable id; the enforcement script mechanizes
   governance rules 2–3 (row coverage, no orphans) and the citation-drift
   check. It runs green before any commit that touches values, rows, specs,
   or the README.

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

**Stated plainly (review 2026-07-08):** with ~3 identifiable parameters
and ~3 clean experiments on this system, one can calibrate or validate,
not both. This pipeline chooses CALIBRATE; stage 2 therefore has **no
completed out-of-sample validation today**. Mitigations: (a) the 529 is
used validate-then-calibrate — the 543-calibrated model's prediction of
the 529 outcome is committed BEFORE the 529 enters the joint kernel
(spec 02 §4.4); (b) the TSP speed-up remains fully held out as the
registered prospective test.

**543 cross-stage note:** the 543 launch calibrates stage 2 and also
appears in spec 03 §6 as a stage-3 sanity replication. This is a soft
double-use, tolerated because STOPS's parameters are nationally
estimated (not fit to the 543) — the replication tests STOPS's
transferability, not shared fitted parameters. It is a diagnostic, and
is never claimed as independent validation of the pipeline; the TSP
event is the preferred stage-3 check once its data lands.

## 6. Reconciliation protocol (stage 2 vs stage 3)

Before publishing a stage-3 forecast: run stage 2 on the identical build
definition; if P50s differ by more than the stage-2 P10-P90 half-width,
decompose the gap (anchor vs market coverage vs network effects vs
response coefficients) in a short memo committed to the repo.
Disagreement is signal about model risk, not an error to suppress.

**Agreement is not a free pass (review 2026-07-08):** stages 2 and 3
share the anchor series, GTFS, and incremental philosophy, so some
agreement is mechanical and validates none of the shared assumptions
(market composition, ASC transportability). The memo must separate
agreement attributable to shared inputs from informative agreement, and
pre-registered divergence sources (e.g., park-and-ride at Fullerton,
which stage 3 models and stage 2 omits) are itemized so they are not
misread as model disagreement.

## 7. Questions resolved (review 2026-07-08)

- Q1 (shortlist size): anchor on 5; the tie and underservice-outlier
  clauses widen it — no fixed debate over 5 vs 8.
- Q2 (induced demand at gate 2): labeled sensitivity column only, NEVER a
  gate criterion — showing it at the gate risks a de facto headline.
- Q3 (finalists to STOPS): conditional — a second finalist earns STOPS
  only when gate-2 bands overlap (see §3).
- Q4 (cost proxy): in scope, tiebreak-only, defined in §3.
