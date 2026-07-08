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

**Current headline: ~13,800 weekday boardings on the new line (P10–P90
11,900–16,100), implied corridor uplift +40/+57/+76% (P10/P50/P90).**
That uplift sits inside the empirical reference class for bus→rapid quality
jumps (Twin Cities +33%, UW +35%, Cleveland HealthLine +78%), so the
envelope caps barely bind. The model, backtested against the corridor's own
2013 Bravo! 543 launch with untuned midpoint parameters, predicted P50 3,804
weekday boardings vs ~3,500–3,900 observed (`outputs/backtest_543.json`).

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

## Pipeline (run in this order)

    scripts/download_data.py                  # ~175 MB -> data/raw (gitignored)
    scripts/build_derived.py                  # raw -> data/derived (committed, ~5 MB)
    scripts/build_corridor.py config/harbor.json   # -> data/derived/corridor_harbor.json
    scripts/model.py data/derived/corridor_harbor.json  # -> outputs/results_harbor.json
    scripts/backtest_543.py                   # -> outputs/backtest_543.json
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
| `scripts/backtest_543.py` | Reruns the model as of June 2013 (local-only base, 543 as the "new" line) and compares to observed 543 ridership. |
| `scripts/make_charts.py` | Interval chart (anchor + three envelope treatments) and sensitivity tornado. |
| `outputs/results_harbor.json` | Summary percentiles, full sensitivity table, design sweep. |

## Model internals (scripts/model.py)

- Three markets, each = distance bins × segments: **walk** (both-ends LODES,
  3 car-ownership segments from ACS), **transfer** (one-end LODES via feeder
  nodes; pinned to `tau` = 25–40% of base boardings), **visitor** (resort
  market; pinned to `phi` = 5–15%; its own S0).
- Each service (local / rapid / new line) gets utility: in-vehicle time from
  speed, wait from headway (walk access: `min(h/2, w0+lam*h)`; transfer:
  `min(h/2, xcap)`; visitor: `h/2`), walk time from stop spacing
  (`legs * spacing/4 @ 3 mph`, weighted by `ovt`), plus `asc` for the new
  line only.
- **Each segment takes its best service — deliberately NOT a logsum.** A
  logsum over parallel routes on the same street awards a red-bus/blue-bus
  "variety bonus" (up to ~1.4 utils); the first implementation had this bug
  and produced fold-scenario ridership LOSSES. `variety_logsum=True` keeps
  the rejected spec as a sensitivity row (−40%).
- Scenarios: **fold** (new line only) vs **retain** (new + local). The new
  line's share and the retained-local share are derived from the utilities
  (currently ~0% retained at central parameters — the model says fold the
  local, as Cleveland did). Headline = 50/50 blend of scenarios.
- Pivot: `S1 = S0·e^dV/(S0·e^dV+1−S0)` per cell; corridor ratio is
  base-share-weighted; non-work expansion via `ws`/`kappa`; forecast =
  anchor × ratio.
- Uncertainty: triangular priors on behavioral params (bivt, ovt, asc),
  uniform on the rest; S0 jittered with ACS-published MOEs; bins Dirichlet-
  resampled. Envelope treatments (uncapped / cap +80% / cap +55%) are
  REPORTED SIDE BY SIDE, never filtered — see user preferences below.

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

1. **Get real APC counts** (OCTA public-records request or bimonthly
   performance reports): current 43/543 route-level and ideally stop-level
   boardings. The anchor is the #1 sensitivity (±13%) and its derivation is
   inference, not measurement.
2. **Smooth the knife-edge service choice**: deterministic best-service
   makes rapid-vs-local switching binary per cell (visible as a kink in the
   design sweep and the wide backtest band). A taste-heterogeneity spread on
   the walk weight (distribution over riders within a cell) would fix it
   without reintroducing the variety bonus.
3. **Time-of-day split** — deliberately skipped by user instruction, but
   acknowledged as real: all-day 5-min headway applied to all-day boardings
   overstates; peak/off-peak would damp the frequency benefit.
4. Sub-half-mile trips are excluded (LODES bin floor), understating the
   local's advantage on short hops; affects the fold-vs-retain conclusion.
5. New visitor demand (tourists not already riding) is unmodeled upside.
6. No GitHub remote is configured yet; the user intends eventual push.

## Environment gotchas

- Windows. Always pass `encoding="utf-8"` to `open()` (config titles contain
  "→"); `model.py` reconfigures stdout to UTF-8. Avoid round-tripping file
  edits through PowerShell 5.1 (`Set-Content` mangles UTF-8; it bit this
  project once).
- Percent-encode spaces in octa.net PDF URLs; transit.dot.gov blocks
  non-browser fetches; the Census API now requires a key (use the
  table-based summary files on the FTP instead, as download_data.py does).
