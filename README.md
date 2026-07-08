# OC Transit Forecast

Corridor-level ridership forecasting for the Harbor Blvd (Fullerton → Santa
Ana) rapid-transit proposal, built as a fast, transparent alternative to a
full FTA STOPS run. Validated by backtesting the corridor's own natural
experiment (the 2013 Bravo! 543 launch).

## Method

Incremental (pivot-point) logit, Monte-Carlo'd, anchored to observed boardings:

    forecast = observed corridor boardings x (base-share-weighted mean of
               per-segment share-growth factors)

Absolute market size and unobserved local constants cancel; borrowed
coefficients act only on the *change* in level of service. Key structural
features (see `scripts/model.py`):

- **Service-level choice, not just corridor-level deltas.** Each transit
  service (existing local, existing rapid, proposed line) gets a full utility:
  in-vehicle time from its speed, wait from its headway, and **walk access
  from its stop spacing** (spacing/4 per leg at 3 mph, weighted like wait).
  Each market segment takes its *best* available service -- deliberately not a
  logsum, because parallel routes on one street are near-perfect substitutes
  and a logsum awards a fictitious red-bus/blue-bus "variety bonus" (the
  rejected spec is kept as a sensitivity row; it moves the answer -40%).
  The fold-vs-retain question and the new line's share of corridor riders are
  therefore *derived* (V_new vs V_local), replacing the earlier invented
  25-40% retained-share prior and coin-flip blend.
- **Arrival-strategy wait structure.** Walk-access wait is
  `min(headway/2, w0 + lambda*headway)` -- the closed form of a rider choosing
  between random and schedule-timed arrival. Transfers get
  `min(headway/2, transfer_cap)`; visitors get `headway/2` (no schedule
  adaptation).
- **Transfer / partial-ride market.** One-end-in-corridor LODES commute flows
  are routed onto the line via the nearest GTFS feeder route that crosses the
  corridor, pinned to the on-board-survey transfer share (25-40%) of base
  boardings.
- **Visitor market.** The Anaheim resort market rides as its own segment
  (share of base boardings 5-15%, short trips, random arrival). Note: this
  models the response of *existing* visitor riders; new visitor demand not in
  the anchor is out of scope (upside risk).
- **Non-work expansion.** Work-trip growth blended with a dampened non-work
  response (`kappa`), work share drawn 40-60%.
- **Uncertainty done honestly.** Behavioral parameters (bivt, ovt, asc) are
  triangular (peaked) so independent-uniform corner combinations aren't
  overweighted; base transit shares are jittered with **ACS-published margins
  of error** (delta-method SEs from B08141), not a blanket guess; distance
  bins are Dirichlet-resampled.
- **No empirical-envelope filter.** Reference-class uplift benchmarks
  (Twin Cities +33%, UW +35%, Cleveland HealthLine +78%) are *reported next
  to* the model's implied uplift, and the headline is shown under each
  envelope treatment -- the judgment is left to the reader. All structural
  knobs appear in the one-at-a-time sensitivity table.

## Backtest (scripts/backtest_543.py)

The model, with untuned midpoint parameters, is pointed at the 2013 launch of
the Bravo! 543 (add a 15 mph / 10-15-min rapid overlay to the existing Route
43 local, both retained):

- predicted 543 weekday boardings **P50 = 3,804** (central point 3,957);
  observed: **~3,500-3,900** (OCTA six-year average / 2017 figure)
- predicted corridor uplift +3% -- matches the observed non-growth of total
  corridor ridership (an overlay on an already-frequent local mostly re-sorts
  riders; cf. FTA's Cleveland finding)

Caveats: P10-P90 is wide (1.2k-7.4k; rapid-vs-local switching is knife-edge
at near-parity headways), and 2022 LODES / 2023 ACS proxy for 2013 markets.

## Layout

    config/            corridor definition (route, anchor, services incl. stop
                       spacing, visitor market)
    scripts/
      download_data.py  fetch LODES, ACS B08141, gazetteer, OCTA GTFS -> data/raw
      build_derived.py  compress raw -> small committed tables in data/derived
      build_corridor.py corridor config -> model inputs json (tracts, segments
                        with MOE-based SEs, walk bins, feeder crossings,
                        transfer flows)
      route43_share.py  Route 43's corridor share (anchor consistency)
      model.py          the Monte-Carlo pivot model + sensitivities + sweep
      backtest_543.py   backtest vs the 2013 Bravo! 543 launch
      make_charts.py    interval + tornado charts -> outputs/
    data/derived/      small reproducible tables (committed)
    outputs/           results json + charts (committed)

`data/raw` is gitignored (~180 MB); `data/derived` is enough to run the model
without any downloads. To rebuild from scratch: `python scripts/download_data.py`
then `python scripts/build_derived.py`.

## Data provenance

- **LODES8** `ca_od_main_JT00_2022` (US Census LEHD) -- commute O-D, block level,
  aggregated to tract pairs within Orange County.
- **ACS 2023 5-yr B08141** (table-based summary file) -- workers by vehicle
  availability x transit use, tract level.
- **2023 Census gazetteer** -- tract centroids.
- **OCTA GTFS** (fetched 2026-07) -- shapes, headways, scheduled speeds.
- **Anchor (corridor-consistent):** 7,700-10,000. Derivation: current 43+543
  *route-total* boardings 9,500-11,000 (Harbor TSP study: ">10,000 daily
  boardings, 8% of all OCTA riders"; OCTA ~117k/weekday in 2024), times
  [543's share (0.25-0.35) counted fully + Route 43's share scaled by its
  corridor share 0.75 (LODES) - 0.86 (ACS transit workers), since Route 43
  runs ~18 mi vs the 12.1-mi corridor -- `scripts/route43_share.py`].
  Cross-check: 12,800 weekday boardings on Harbor itself in 2015 (Central
  Harbor Blvd Transit Corridor Study, via Streetsblog 2018-01-17) x system
  ridership trend x street-vs-corridor share ~ 8,400. Historical (backtest):
  Route 43 ~13,000 at the 543's June 2013 launch; 543 launched at 10-min
  peak / 15-min off-peak; 543 ~3,900/day in 2017, ~3,500/day six-year average.

## Known issues & judgment calls

Recorded as they were made; each is exposed in the sensitivity output.

1. **Transfer-market base share** has no direct data; it is pinned so that
   transfers are 25-40% of base boardings (typical on-board survey range).
2. **Transfer coordination cap** (10-15 min) proxies for schedule coordination
   on long-headway feeders; OCTA does not generally run timed transfers.
3. **Image/reliability ASC trimmed to 0-0.40** (from 0-0.55) because the
   explicit schedule-delay term now carries part of the turn-up-and-go
   benefit previously bundled in the ASC. Sensitivity reports 0 and 0.55.
   The backtest says some positive ASC is load-bearing: with asc=0 the 543
   would have attracted ~500 riders vs ~3,700 observed.
4. **One-transfer access only**; flows whose non-corridor end is not within
   0.9 mi of a crossing feeder are dropped (conservative). Flows to LA County
   are excluded (OC-only tract-pair table).
5. **LODES is commute-only**; the non-work market enters only through the
   work-share/kappa expansion, not its own O-D shape.
6. **Deterministic best-service choice** makes rapid-vs-local switching
   knife-edge near service parity (visible as a kink in the design sweep and
   the wide backtest band). The alternative (logsum) is worse -- it awards a
   variety bonus to duplicate services -- but a taste-heterogeneity spread on
   the walk weight would smooth it; not yet implemented.
7. **Sub-half-mile trips are excluded** from the O-D markets, so the model
   understates the local's advantage for the shortest hops; the retained-local
   share (~0% at central parameters) should be read with that in mind.
8. **Time-of-day is not modeled** (all-day headways applied to all-day
   boardings) -- deliberately deferred; would damp the 5-min-headway benefit.
9. **Harbor baseline rapid** uses the corridor-doc values (15 mph / 24-min);
   current GTFS shows 12.8 mph / 20-min -- a sensitivity row covers it (+0.2%).
