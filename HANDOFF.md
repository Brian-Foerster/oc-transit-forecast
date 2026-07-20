# Agent Handoff

Read this first if you are picking up the project cold. README.md describes
the method; this file explains how the project got here, what every file
does, decisions that are NOT derivable from the code, and where to go next.

## What this is

A ridership forecast for a proposed rapid transit line on **Harbor Blvd,
Fullerton Transportation Center → Harbor/MacArthur, Santa Ana (12.1 mi)**,
with an owner design of a **60 mph top speed / 5-minute headway** (stop
spacing ~1 mi). As of spec 02 §4.9 (2026-07-11) the average speed is
**derived** from grade-separated cruise/dwell priors and the spacing, not a
free config scalar; after the **owner 2026-07-17 60-mph top-speed decision**
(v_cruise prior recentred 80→96.6 km/h) the central design reproduces **~31.8
mph** average (~30 mph was the pre-2026-07-17 literature central, kept as the
exogenous fallback). It is an
incremental (pivot-point)
logit — the same philosophy as FTA STOPS's incremental mode — Monte-Carlo'd
for honest uncertainty, anchored to observed boardings, built to be run in
seconds instead of the person-months a STOPS run costs.

**Current headline (2026-07-17, measured anchor; launch-equivalent ABC
target; average speed DERIVED with jerk-limited kinematics at the owner 60-mph
design cruise, spec 02 §4.9/§4.9b): uncapped ~12,074 weekday boardings (P10–P90
10,066–14,127), implied uplift +30/+44/+61%; backtest-calibrated (ABC) ~11,947
(10,478–13,520), shown SIDE BY SIDE.** _Owner design change 2026-07-17: top
speed set to 60 mph outright (v_cruise 80→96.6 km/h; ~31.8 mph derived avg) and
a sub-5-min headway sweep ({2.5, 3.5, 5, 10, 15} peak, fleet annotated per
column); the faster line lifts the headline ~1% and the welfare BCA ~4%, and
trims the fleet 27→25 cars (capcost.fleet). The full frequency trade: the
2.5-min plan buys +10.6% riders for +23 cars (≈ +$171M LOW capital at
$7.44M/car) plus roughly doubled variable O&M — welfare-negative at a
~0.12-BCR corridor (LOW, ABC, P50); the sweep prices ridership, the BCA prices
the trade, and the 5/10 plan remains the design point. The 2013 backtest and
the ABC weights/ESS/posterior stay byte-identical — only the forward forecast
moved._
The derived-speed landing (R6)
restated the headline deliberately: the central barely moved (speed's central
still ~30 mph), the bands widened slightly (speed is now uncertain), and the
stop-spacing sensitivity rows shrank toward physical honesty (0.5-mi
+23.6%→+16.7%, 1.5-mi −22.3%→−20.1%). The jerk-limited refinement (§4.9b,
2026-07-11) then charged the realistic S-curve (~1% off the design-point speed,
29.8 mph) and a reachability cap at tight spacings, nudging the central ~20
boardings (12,056→12,036 tornado). The backtest and the ABC
weights/ESS/posterior stay byte-identical — only the forward forecast moved. The ABC target was retargeted (spec 02 §4.6) from the 543's
matured six-year average (mu=4,200) to a launch-equivalent mu=5,938 (FY2017
measured 4,615/wd × OCTA's measured FY2013/FY2017 bus-UPT back-trend 1.2868,
NTD ID 90036); the matured 4,200 is kept as a sensitivity row (calibrated
~10,750). See README known issue 15 (closed 2026-07-11).
The design is 5-min peak / 10-min off-peak (user decision). The old
cap +80%/+55% columns were removed (user decision); the companion treatment
is calibration against the corridor's own 2013 Bravo! 543 launch
(`outputs/abc_harbor.json`). **The anchor and the 543 calibration target
are now MEASURED**, not inferred: OCTA's quarterly performance reports
(FY2017/FY2019/FY2020-Q3, still live on octa.net) give route-level
boardings — `scripts/anchor_from_apc.py`. Honesty notes: the backtest at
prior-central parameters overpredicts the MATURED measurement (6,169 vs
measured ~3,700–4,600) but nearly matches the launch-equivalent target
(5,938, +3.9%) the ABC now uses — the earlier near-perfect 3,804 came from an
unfaithful flat-15-min spec plus knife-edge artifacts; the ABC posterior puts
the ASC at 0.14/0.19/0.24 vs prior 0.09/0.20/0.31 (matured-target row:
0.06/0.11/0.16).

## How it got here (session history, oldest → newest)

1. Started from an external writeup of a pivot-logit Monte Carlo whose raw
   output (~24,600) implied +103% corridor uplift — ~2× the incremental-BRT
   empirical band — and was manually "disciplined" down to ~13,300.
2. Real data was pulled (LODES O-D, ACS B08141): real trip lengths were
   low-leverage (−4.6%) but real car-ownership segmentation pushed the raw
   model UP (+16.7%, raw median 27,250, +123% uplift).
3. The reference class was revised upward (+25–55% → +50–80%) after
   Cleveland-class "ordinary bus → rapid" analogs were reviewed; disciplined
   headline became ~15,700.
4. A Beach Blvd analysis and a 13-arterial screen were done (see "Dropped
   work" below). Beach was later cut by user instruction.
5. The model was rebuilt structurally (this repo): arrival-strategy wait,
   transfer market, non-work expansion, then service-level utilities with
   stop-spacing walk time, best-of-services choice, visitor market, ACS-MOE
   jitter, and a corridor-consistent anchor. Each fix moved the mechanistic
   forecast toward the empirical band; they now agree without filtering.
6. A top-5-flaws review (2026-07) drove five fixes, committed stepwise:
   sub-half-mile market from intra-tract LODES (−4%); rider-position
   quadrature replacing the knife-edge choice (sweep kink gone, backtest
   band 6.2×→2.3×); peak/off-peak time-of-day (−6%, design now 5/10);
   ABC calibration against the 543 launch replacing the cap columns
   (plus a latent rng bug fix: pinning a prior used to shift all other
   draws); web research for a measured anchor came up dry →
   `outputs/records_request_draft.md`.
7. Same session, second pass: the "unretrievable" data was recovered from
   octa.net itself — URL-pattern probing found the FY2017–FY2021 quarterly
   detailed reports (route-level boardings) still live, and the Wayback CDX
   index revealed the monthly ridership report's real filename contains a
   stray space (the clean URL 404s). Anchor re-derived from measurement
   (7,650–9,650); the 543 calibration target rose to mu=4,200 (measured
   FY2017 4,615/wd, FY2019 3,739/wd — press figures were low). (Later
   retargeted 2026-07-11 to launch-equivalent mu=5,938; spec 02 §4.6 /
   README issue 15.) Records request narrowed to stop-level APC, FY2014–16,
   post-2020 route-level, and the transfer rate.
8. **MODE DECISION (user, 2026-07-08): the proposed line is an ELEVATED
   AUTOMATED LIGHT METRO, REM-class (GoA4 driverless)** — not arterial
   BRT. Capital cost model: `costs/metro_cost_model.xlsx` (user-supplied,
   REM-calibrated, intentionally aggressive = LOW scenario) + spec
   `specs/04-capital-cost.md` (fleet derived from service plan, LOW /
   US-TYPICAL band, special structures, land flag). Back-propagation:
   ASC premium bracket widened to {1.0, 1.5, 2.0} (bus-calibrated ASC on
   a rail-class product), derived-speed model split grade-separated
   (forward) vs street (bus backtests), economic-layer premium band to
   rail-class 5-25%, stage-3 build GTFS as rail mode. Grade-separated
   physics at the owner 60-mph design cruise (96.6 km/h) / 25-s dwell / 1-mi
   stops gives ~31.8 mph — the ~30-mph config value is retained as the
   exogenous fallback (80 km/h literature cruise gave ~29.5 mph).
9. **Spec 05 implemented (2026-07-09):** (a) REFERENCE relabeled into a
   basis-tagged, display-only object (regime x horizon; Cleveland split
   launch +40 / matured +78; ALM analogs Canada Line / REM South Shore in
   absolute-accuracy-only columns; Flyvbjerg 2005 optimism prior printed
   beside every headline; nothing filters draws). (b) OC Streetcar
   cold-start: alignment recovered from OSM (corridor_waypoints polyline
   support in build_corridor.py), anchor derived from parallel carriers'
   measured boardings x shape-share (3,600-5,500, WEAK -- see README
   issue 16), result P50 ~5,600 (4,500-6,800), inside OCTA's 5,000-7,300
   projection band; rail-ASC bracket printed as a band. Post-launch APC
   (~2027) is the future rail-class ABC target (records request item 4).

## Pipeline (run in this order)

    scripts/download_data.py                  # ~175 MB -> data/raw (gitignored)
    scripts/build_derived.py                  # raw -> data/derived (committed, ~5 MB)
    scripts/build_corridor.py config/harbor.json   # -> data/derived/corridor_harbor.json
    scripts/model.py data/derived/corridor_harbor.json  # -> outputs/results_harbor.json
    scripts/backtest_543.py                   # -> outputs/backtest_543.json
    scripts/reweight_abc.py                   # -> outputs/abc_harbor.json (ABC treatment)
    scripts/make_charts.py harbor             # -> outputs/*.png
    scripts/bca_export.py harbor [--seed-check]  # OPTIONAL: -> outputs/bca_export_harbor.json.gz (spec 06 B4 BCA handoff; post-ABC, gitignored)
    scripts/make_charts.py bca harbor         # OPTIONAL (spec 06 W2): -> outputs/bca_harbor.png + bca_tornado_harbor.png; reads the tbc welfare-BCA artifact (existence-gated), skips if absent
    scripts/sequence_network.py               # spec 07 BUILT greedy portfolio harness. DEFAULT --objective npv: prices each candidate-given-network through the tbc v3 wrapper (node, synchronous), within-draw CV in PV$ -> outputs/network_sequence.json (~3 min at N=40,000; needs the sibling transit-benefit-cost repo + node). --objective interim: Δwelfare-min level -> outputs/network_sequence_interim.json (the byte-identical N4 regression anchor; ~20 min w/ sensitivity)
    scripts/make_charts.py network            # spec 07: -> outputs/network_frontier.png + network_build_sequence.png + network_channels.png (NPV-aware: ΔNPV-vs-ΔK_PV scatter + marginal-BCR bars when the artifact is the NPV objective)
    scripts/check_assumptions.py [--appendix] # STANDING GATE (spec 08): 7 registry checks, exit nonzero on drift; --appendix regenerates outputs/assumptions.{md,json}

`data/derived` is committed, so **model.py `run()` and a fresh clone's
committed outputs need zero downloads**; but `model.py main()`'s FULL
sensitivity table now rebuilds a scratch corridor for the `intra_tract_alt`
row (`build_corridor.py`, which reads `data/raw`), so regenerating the full
table from scratch needs the raw data (accepted, spec 08 §9 Q6; README issue
26). `check_assumptions.py` joins `test_bca_export.py` as a standing gate —
run it (green: 0 failures, spec-pending warnings counted; 4 after the spec 07
N4 registry conversion) before any commit that touches values, rows, specs, or
the README. Since W1 it also
scans the cross-repo welfare-BCA artifact (`transit-benefit-cost/outputs/
bca_harbor.json`, existence-gated, override path via `BCA_WRAPPER_ARTIFACT`)
for oc-claimed tornado ids — a check-2 coverage claim, engine-owned ids exempt
from check-3 (spec 08 §9 Q7); absent sibling ⇒ pending warnings, never a fail.
Since spec 07 N4 it ALSO scans `outputs/network_sequence.json` (override
`NETWORK_SEQUENCE_ARTIFACT`) the same way: the 17 capital + network-mechanics
registry leaves claim its `assumptions_manifest` rows, and the harness-internal
sensitivity ids are engine-owned/exempt (`ENGINE_OWNED_NETWORK`). (Since spec 07
N5 that artifact is the NPV objective; its `assumptions_manifest` is unchanged in
shape, so the scan is identical. The interim N4 anchor now lives at
`outputs/network_sequence_interim.json`.) That
conversion dropped the spec-pending warnings 21 → 4 (the remaining 4 are the
spec-02 §4.8/§4.9 street-cal + LODES rows).
Everything is plain
numpy/pandas/matplotlib (requirements.txt); model runs take seconds
(N=40,000 draws, vectorized, seed=42).

## Files

| File | Role |
|---|---|
| `config/harbor.json` | The corridor definition: anchor range + derivation note, base services (Route 43 local, Route 543 rapid) with speed/headway/stop-spacing, the proposed line, visitor-market parameters. Change the design here. Spec 06 added a `bca` block (`routes_removed` per scenario + `rev_hours_weekday` per route for the BCA's avoided base O&M, plus prose notes that are NOT shipped in the export) and an optional `fare_base` (defaults to `DEFAULT_FARE`, the OCTA flat cash fare in `model.py`). Spec 08 A2b promoted `anchor_derivation` (trend / corr_share / uniformity) to structured keys the registry owns. |
| `config/backtest_543.json` | The 2013 Bravo! 543 backtest world, promoted out of `backtest_543.py` (spec 08 A2b): the 2013 local/rapid services + the Route-43 route-total anchor leaf. `backtest_543.py` reads it and computes the anchor band in code from the SHARED `corr_share` (read from `config/harbor.json`, never duplicated). |
| `scripts/assumptions.py` | The assumptions registry (spec 08): single source of every asserted value (`val(id)` / `band(id)` / `build_priors()`) and every structural choice, keyed by stable id with tier / basis / dated history / per-artifact sensitivity rows / disposition bookkeeping. Dependency-free; code imports from here. |
| `scripts/check_assumptions.py` | Enforces the registry (spec 08 §5): seven checks — schema, coverage, no-orphans, prior-order fingerprint, materiality, pointers, citation sync — exit nonzero on any failure (spec-pending dispositions are counted warnings). Since W1 (spec 08 §9 Q7): scans the existence-gated welfare-BCA wrapper artifact (`BCA_WRAPPER_ARTIFACT`, default the `transit-benefit-cost` sibling) for oc-claimed tornado ids, engine-owned ids exempt from check-3; per-corridor width blocks. `--appendix` regenerates `outputs/assumptions.{md,json}` (schema `08-A3.3`: + a machine `values` section — eq_days, default_fare, kernel labels + central flag, and the five wrapper-re-priced priors — that the tbc wrapper resolves instead of hardcoding). A standing gate. |
| `scripts/download_data.py` | Fetches the raw sources incl. the OCTA performance-report PDFs (URLs inside; note the %20 filename quirk). |
| `scripts/anchor_from_apc.py` | Anchor derivation from MEASURED route-level boardings (data table + source URLs + the trend assumptions). |
| `scripts/build_derived.py` | Raw → `oc_tracts.csv` (614 OC tract centroids), `oc_b08141.csv` (ACS workers/transit × vehicle availability, estimates AND margins of error), `oc_tract_od.csv.gz` (LODES commute flows aggregated to 178,900 OC tract pairs). |
| `scripts/build_corridor.py` | Projects tracts onto the corridor route's GTFS shape (0.9-mi buffer), builds: ACS segments with delta-method SEs, walk-market distance bins (both-ends-in-corridor flows), feeder crossings (routes that genuinely cross the line, with crossing position + headway), transfer-market bins (one-end flows entering via nearest crossing feeder). |
| `scripts/route43_share.py` | Route 43 runs ~18 mi but the corridor is 12.1; this measures the share of 43's market inside the corridor (0.75 by LODES, 0.86 by ACS) used in the anchor derivation. |
| `scripts/model.py` | The model. See "Model internals". |
| `scripts/backtest_543.py` | Reruns the model as of June 2013 (local-only base, 543 at its actual 10/15 launch service) vs observed 543 ridership; exports `backtest_corridor()` for the ABC script. |
| `scripts/reweight_abc.py` | Backtest-calibrated treatment: same draws through 2013 + forward configs, Gaussian kernel on the 543 prediction. Six kernels (single source of truth `KERNELS` / `get_kernels()`): launch-equivalent central mu=5,938 (=FY2017 4,615 × NTD FY2013/FY2017 back-trend 1.2868, spec 02 §4.6) at sigma 500, width sensitivities 350/800, an FY2014-vintage row (mu=5,647), a back-trend-BAND row `543_launch_bt_s507` (R2 batch: the vintage factor carried as U(1.2236, 1.2868) — the June-2013 launch sits on the FY2013/FY2014 boundary, so the two annual readings bracket it — marginalized to mu≈5,793 / sigma≈507; the tbc wrapper stays on the central kernel), and the retired matured mu=4,200 row. Weighted percentiles + ASC posterior + ESS + central residual + seed check. JSON keyed by kernel label (`kernels` block), not bare sigma. |
| `scripts/make_charts.py` | Interval chart (anchor, uncapped, ABC-calibrated) and sensitivity tornado. The `bca` mode (`make_charts.py bca harbor`, spec 06 W2) instead reads the cross-repo welfare-BCA artifact and draws the NPV interval chart (scenario × treatment × band, PV-BCR + Flyvbjerg annotation) and the BCA ΔNPV tornado; existence-gated, skips if the sibling artifact is absent. |
| `scripts/bca_export.py` | Freezes the stage-2 per-draw BCA quantity streams (spec 06 §3) to `outputs/bca_export_<corridor>.json.gz` — the file interface the downstream `transit-benefit-cost` wrapper prices. Runs `run()` once per design point, packages the welfare / car-mile / fare-burden arrays + ABC weights (harbor) at float32; `--seed-check` adds a seed+1 companion (gate G4). W1 added four streams: `um_roh_{infra,margin}` (rule-of-half welfare alternative, un-blocks the tbc `roh` row — carries ~3.4% ROH-vs-exact-logsum divergence by design, full magnitude ~128k/57k min) and `fare_receipts_{infra,margin}` (fiscal counterpart to `fare_burden`, un-blocks `fare_sweep`; both 0 at today's flat fare). Computes NO prices or valuation. Optional; not on the critical path; output gitignored. |
| `scripts/test_bca_export.py` | Executable statement of the §3 interface contract: schema shape, array lengths (N), `abc_weights` present iff a calibration target exists, and the round-trip P50 vs the committed reference to 4 significant figures. Run the exports first. |
| `outputs/results_harbor.json` | Summary percentiles, full sensitivity table (each row carries a stable `id` + display `label`), design sweep, width sensitivities. |
| `outputs/assumptions.md` / `.json` | Generated by `check_assumptions.py --appendix` (committed, byte-deterministic): the auditable inventory — unpropagated exposures sorted by effect, priors (already-propagated), width sensitivities, rowless dispositions with accepted stamps, basis census + what-changed. The `.json` is the schema-versioned cross-repo artifact. |
| `outputs/records_request_draft.md` | Ready-to-send CPRA request for route/stop-level APC + on-board transfer rate (anchor research came up dry online). |
| `outputs/bca_harbor.png` / `bca_tornado_harbor.png` | Welfare-BCA charts (spec 06 W2, committed): the NPV interval chart (scenario × treatment × band, PV-BCR + Flyvbjerg annotation) and the ΔNPV tornado. Regenerate with `make_charts.py bca harbor` from the cross-repo `transit-benefit-cost/outputs/bca_harbor.json`. |

## Model internals (scripts/model.py)

- Three markets, each = distance bins × segments: **walk** (both-ends LODES,
  3 car-ownership segments from ACS), **transfer** (one-end LODES via feeder
  nodes; pinned to `tau` = 25–40% of base boardings), **visitor** (resort
  market; pinned to `phi` = 5–15%; its own S0).
- Each service (local / rapid / new line) gets utility: in-vehicle time from
  speed, wait from headway (walk access: `min(h/2, w0+lam*h)`; transfer:
  `min(h/2, xcap)`; visitor: `h/2`), walk time from the rider's position
  vs the service's stop grid (weighted by `ovt`), plus `asc` for the new
  line only. Headways may be scalar or `{peak, offpeak}`; per-period
  utilities blend by the `pkshare` prior (45–60%).
- **Derived average speed (spec 02 §4.9; jerk-limited §4.9b).** A service
  carrying a `derived_speed` block gets its average speed DERIVED per draw from
  cruise + dwell priors and its spacing (`grade_sep_min_per_mile` /
  `derived_speed_mph`, module-level + unit-testable), so `util()`'s `60/speed`
  becomes an `(n,1)` column via the `inv_speed` helper; exogenous services stay
  a scalar (old path bitwise unchanged). Harbor's `service_new` uses the
  grade-separated variant (`A_COMFORT = 1.0` m/s², no signals) with jerk-limited
  S-curve kinematics (`J_COMFORT = 0.75` m/s³; per-stop loss = phase time
  `v/a + a/j`, and speed is capped to the reachable peak `v_p` when the spacing
  is too short — `s_curve_phase_time` / `stop_run_time`; optional `accel`/`jerk`
  override keys on the block are the row mechanism). The two new priors
  `v_cruise` (**90–103.2 km/h**, central 96.6 = 60 mph; owner 2026-07-17
  design decision, was 70–90 km/h literature) / `dwell` (20–30 s) are appended
  LAST in `PRIORS`.
  The street variant (`calibrate_street`) is solved in code from the 43/543
  measured points, prices hypothetical bus designs only, and is exempt from the
  S-curve (its measured end-to-end speeds already embed jerk). Governance:
  `over` key `exogenous_speed=1` (sensitivity row "exogenous speed (old spec)")
  restores the config scalar; `j→∞` with the cap retained is the "trapezoid
  kinematics (R6)" regression row. The design sweep's speed axis is the
  grade-separated cruise axis (`sweep_axis` in the results JSON); its peak-
  headway axis was extended below 5 min (owner 2026-07-17 sub-5-min frequency
  test: `{2.5, 3.5, 5, 10, 15}`), each column annotated with the derived
  `capcost.fleet` car count at the 60-mph central (`sweep_headways` /
  `sweep_fleet` in the results JSON; `headway_35_7` / `headway_25_5` are the
  matching one-at-a-time rows). Streetcar stays exogenous and keeps the
  `{5, 10, 15}` axis (sub-5-min is a grade-separated-ALM question).
- **Each sub-rider takes their best service — deliberately NOT a logsum.**
  Within a cell, rider street-position is a K=8 quadrature over one stop-grid
  period; every service's walk time comes from the SAME position
  (`subcell_walks`), so the choice is smooth at cell level with no
  red-bus/blue-bus variety bonus. `variety_logsum=True` keeps the rejected
  logsum (−37%); `smooth_k=0` keeps the old knife-edge point value (+3%).
- Scenarios: **fold** (new line only) vs **retain** (new + local). The new
  line's share and the retained-local share are derived from the utilities
  (~8% retained at P50 now that sub-half-mile trips are in). Headline =
  50/50 blend of scenarios.
- Pivot: `S1 = S0·e^dV/(S0·e^dV+1−S0)` per sub-cell; corridor ratio is
  base-share-weighted; non-work expansion via `ws`/`kappa` (optional
  `nonwork_short` tilt); forecast = anchor × ratio.
- Uncertainty: triangular priors on behavioral params (bivt, ovt, asc),
  uniform on the rest; S0 jittered with ACS-published MOEs; bins Dirichlet-
  resampled. `draw_params()` draws priors on a child stream and ALWAYS
  consumes the rng before pinning (a latent bug fix — pinning used to shift
  every later draw); `run(params=...)` gives common random numbers across
  configurations, which is what makes the ABC reweighting coherent.
- Treatments: **uncapped** and **backtest-calibrated (ABC)** reported side
  by side, never filtered — see user preferences below. Cap columns removed
  by user decision 2026-07.
- **BCA quantity streams (spec 06 B1–B3).** `run()` now also returns, per
  scenario, exact-logsum consumer-surplus accumulators (equivalent-IVT
  minutes, split `um_infra`/`um_margin` for the D6 margin-only ramp, plus a
  no-ASC counterfactual variant `um0_*`); per-segment diverted-trip-mile
  masses (`cm_seg`/`cm_visitor`, PRE-pcar, plus the full-O-D transfer variant
  `cm_seg_fullod` via the derived `centers_od` field); and a money-metric
  `fare_burden` dollar stream (fare enters utility through `vot_behav` for
  BEHAVIOR but is never monetized through the social VOT — D3). All are
  work-shaped and PRE-BLEND (the wrapper applies the D8 ws/κ blend), and the
  accumulators consume no rng. The 5 new priors (`vot_behav`, `pcar0/1/2/v`)
  are appended LAST in `PRIORS` for rng-stream stability and show as 0.0%
  sensitivity rows (no fare sweep / wrapper re-pricing exists yet). `bca_export.py`
  packages these to the §3 file; the model itself prices nothing.

## User's working preferences (binding)

- **Do not bake reference-class/envelope judgments into the model.** The
  user explicitly rejected filtering Monte-Carlo draws by an empirical
  uplift band ("I don't trust the literature to be deep and detailed
  enough"). Report the model's implied uplift next to the benchmarks and
  show the headline under each treatment; the user judges.
- **Expose every structural knob in the one-at-a-time sensitivity table**,
  including rejected specs (linear wait, variety logsum, no-transfer,
  no-visitor, untrimmed ASC).
- **Report issues and dilemmas as they arise** — the user asked to be told
  about judgment calls, not shielded from them. README "Known issues"
  section is the running log; keep it updated.
- Keep the repo GitHub-committable (no raw-data blobs; derived data small).

## Key provenance (details in README)

- Anchor 7,700–10,000: current 43+543 route totals ~9.5–11k ("more than
  10,000 daily boardings, 8% of all OCTA riders" — Harbor TSP study, 2024)
  × corridor share. Cross-check: 12,800 on-Harbor boardings in 2015
  (Central Harbor Blvd Transit Corridor Study, corridor = Chapman Ave →
  Westminster Blvd, ~7.5 mi; study revoked June 2018).
- Historical: Route 43 ≈ 13,000/day at the 543's June 2013 launch; 543
  launched at 10-min peak/15-min off-peak; 543 ≈ 3,900/day (2017,
  Streetsblog), ~3,500/day six-year average (OCTA 2019 release).
- OCTA GTFS (fetched July 2026): 43 = 11.4 mph/20-min; 543 = 12.8 mph/20-min
  (config uses doc values 15 mph/24-min; sensitivity row covers GTFS values).

## Dropped/adjacent work not in the repo

- **Beach Blvd corridor** (La Palma→Yorktown window): built, then cut by
  user instruction. Fully recoverable from git history (commit e2d518e has
  `config/beach.json`, corridor inputs, results). Its anchor derivation:
  Route 29 = 5,888 (Oct 2018, Beach Blvd Corridor Study baseline report
  p.62) — that PDF is public if needed again.
- **13-arterial screen** (session scratchpad only, not ported): ranked OC
  corridors by ACS transit workers / LODES within-corridor flows in the best
  12.5-mi window. Result: Harbor #1 overall; closest competitors
  Bolsa/1st (Rt 64, transit workers 3,333, 2018 ridership 6,855),
  State College/Bristol (Rt 57, 3,163, ridership unverified ~8–10k),
  Main St (Rt 53, highest O-D flows 12,402, ridership 6,000+ Dec 2018),
  Anaheim/Haster/Fairview (Rt 47, O-D 11,031). Caution: these corridors
  share central Santa Ana tracts — their markets overlap. The screen is
  easily rebuilt from `data/derived` (slide a 12.5-mi window along a GTFS
  shape, score LODES flows + ACS transit workers).

## Open threads (ranked)

1. **Send the narrowed records request** (`outputs/records_request_draft.md`):
   stop-level APC, FY2014–16 route-level (543 launch ramp — sharpens the
   ABC target), post-FY2021 route-level (pins the 0.90–0.99 trend factor),
   and the on-board transfer rate (narrows tau).
2. **Pin down the 2013 Route 43's peak headway** (same records request):
   the backtest assumes flat 15-min; the 10/15 variant moves the backtest
   prediction −24%, which directly moves the ABC-calibrated headline.
3. **ABC kernel width** (sigma=500) is a documented judgment call; revisit
   when launch-ramp data narrows the observation term.
4. New visitor demand (tourists not already riding) is unmodeled upside.
5. ~~No GitHub remote~~ **Closed 2026-07-08:** pushed to
   https://github.com/Brian-Foerster/oc-transit-forecast (private).

(Closed 2026-07: knife-edge smoothing — rider-position quadrature;
time-of-day — 5/10 peak/off design; sub-half-mile market — intra-tract
LODES bin; anchor — measured from OCTA quarterly reports. Old specs kept
as sensitivity rows.)

## Environment gotchas

- Windows. Always pass `encoding="utf-8"` to `open()` (config titles contain
  "→"); `model.py` reconfigures stdout to UTF-8. Avoid round-tripping file
  edits through PowerShell 5.1 (`Set-Content` mangles UTF-8; it bit this
  project once).
- Percent-encode spaces in octa.net PDF URLs; transit.dot.gov blocks
  non-browser fetches; the Census API now requires a key (use the
  table-based summary files on the FTP instead, as download_data.py does).
- octa.net "not found" is often a filename quirk, not a missing file: the
  monthly ridership report's real name contains a space before "March"
  (`OC_Bus_Ridership_July_2022_to_%20March_2024.pdf`), and older quarterly
  reports use three different naming patterns (see download_data.py).
  URL-pattern probing + the Wayback CDX index (`web.archive.org/cdx/search/
  cdx?url=octa.net/pdf/*`) recovered everything a records request would
  have taken weeks for.
