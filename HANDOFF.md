# Agent Handoff

Read this first if you are picking up the project cold. README.md describes
the method; this file explains how the project got here, what every file
does, decisions that are NOT derivable from the code, and where to go next.

## What this is

A ridership forecast for a proposed rapid transit line on **Harbor Blvd,
Fullerton Transportation Center → Harbor/MacArthur, Santa Ana (12.1 mi)**,
with a user-specified design of **30 mph average speed / 5-minute headway**
(stop spacing ~1 mi, a config parameter). It is an incremental (pivot-point)
logit — the same philosophy as FTA STOPS's incremental mode — Monte-Carlo'd
for honest uncertainty, anchored to observed boardings, built to be run in
seconds instead of the person-months a STOPS run costs.

**Current headline (2026-07, post top-5-flaw fixes): uncapped ~12,200
weekday boardings (P10–P90 10,100–14,400), implied uplift +31/+45/+61%;
backtest-calibrated (ABC) ~10,700 (8,900–12,500), shown SIDE BY SIDE.**
The design is now 5-min peak / 10-min off-peak (user decision). The old
cap +80%/+55% columns were removed (user decision); the companion treatment
is calibration against the corridor's own 2013 Bravo! 543 launch
(`outputs/abc_harbor.json`). Honesty note: the backtest at prior-central
parameters now OVERPREDICTS the 543 launch (6,169 vs ~3,500–3,900) — the
earlier near-perfect 3,804 came from an unfaithful flat-15-min spec plus
knife-edge artifacts; the ABC treatment turns that discrepancy into an ASC
posterior (0.05/0.08/0.13 vs prior 0.09/0.20/0.31).

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

## Pipeline (run in this order)

    scripts/download_data.py                  # ~175 MB -> data/raw (gitignored)
    scripts/build_derived.py                  # raw -> data/derived (committed, ~5 MB)
    scripts/build_corridor.py config/harbor.json   # -> data/derived/corridor_harbor.json
    scripts/model.py data/derived/corridor_harbor.json  # -> outputs/results_harbor.json
    scripts/backtest_543.py                   # -> outputs/backtest_543.json
    scripts/reweight_abc.py                   # -> outputs/abc_harbor.json (ABC treatment)
    scripts/make_charts.py harbor             # -> outputs/*.png

`data/derived` is committed, so **model.py runs with zero downloads** on a
fresh clone. Everything is plain numpy/pandas/matplotlib (requirements.txt);
model runs take seconds (N=40,000 draws, vectorized, seed=42).

## Files

| File | Role |
|---|---|
| `config/harbor.json` | The corridor definition: anchor range + derivation note, base services (Route 43 local, Route 543 rapid) with speed/headway/stop-spacing, the proposed line, visitor-market parameters. Change the design here. |
| `scripts/download_data.py` | Fetches the four raw sources (URLs inside). |
| `scripts/build_derived.py` | Raw → `oc_tracts.csv` (614 OC tract centroids), `oc_b08141.csv` (ACS workers/transit × vehicle availability, estimates AND margins of error), `oc_tract_od.csv.gz` (LODES commute flows aggregated to 178,900 OC tract pairs). |
| `scripts/build_corridor.py` | Projects tracts onto the corridor route's GTFS shape (0.9-mi buffer), builds: ACS segments with delta-method SEs, walk-market distance bins (both-ends-in-corridor flows), feeder crossings (routes that genuinely cross the line, with crossing position + headway), transfer-market bins (one-end flows entering via nearest crossing feeder). |
| `scripts/route43_share.py` | Route 43 runs ~18 mi but the corridor is 12.1; this measures the share of 43's market inside the corridor (0.75 by LODES, 0.86 by ACS) used in the anchor derivation. |
| `scripts/model.py` | The model. See "Model internals". |
| `scripts/backtest_543.py` | Reruns the model as of June 2013 (local-only base, 543 at its actual 10/15 launch service) vs observed 543 ridership; exports `backtest_corridor()` for the ABC script. |
| `scripts/reweight_abc.py` | Backtest-calibrated treatment: same draws through 2013 + forward configs, Gaussian kernel on the 543 prediction (mu 3,700, sigma 500; sens 350/800), weighted percentiles + ASC posterior + ESS + seed check. |
| `scripts/make_charts.py` | Interval chart (anchor, uncapped, ABC-calibrated) and sensitivity tornado. |
| `outputs/results_harbor.json` | Summary percentiles, full sensitivity table, design sweep. |
| `outputs/records_request_draft.md` | Ready-to-send CPRA request for route/stop-level APC + on-board transfer rate (anchor research came up dry online). |

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

1. **Send the records request** (`outputs/records_request_draft.md`, ready
   to submit): route- and stop-level APC for 43/543 + on-board transfer
   rate. The anchor is a top-2 sensitivity (±13%) and its derivation is
   inference, not measurement; web research 2026-07 confirmed the reports
   exist but are not retrievable online (boarding-report PDF 404s, Legistar
   item deleted, dot.gov blocks fetches).
2. **Pin down the 2013 Route 43's peak headway** (same records request):
   the backtest assumes flat 15-min; the 10/15 variant moves the backtest
   prediction −24%, which directly moves the ABC-calibrated headline.
3. **ABC kernel width** (sigma=500) is a documented judgment call; revisit
   when real APC data narrows the structural-error term.
4. New visitor demand (tourists not already riding) is unmodeled upside.
5. No GitHub remote is configured yet; the user intends eventual push.

(Closed 2026-07: knife-edge smoothing — rider-position quadrature;
time-of-day — 5/10 peak/off design; sub-half-mile market — intra-tract
LODES bin. Each keeps its old spec as a sensitivity row.)

## Environment gotchas

- Windows. Always pass `encoding="utf-8"` to `open()` (config titles contain
  "→"); `model.py` reconfigures stdout to UTF-8. Avoid round-tripping file
  edits through PowerShell 5.1 (`Set-Content` mangles UTF-8; it bit this
  project once).
- Percent-encode spaces in octa.net PDF URLs; transit.dot.gov blocks
  non-browser fetches; the Census API now requires a key (use the
  table-based summary files on the FTP instead, as download_data.py does).
