# OC Transit Forecast

Corridor-level ridership forecasting for Orange County arterial rapid-transit
proposals (Harbor Blvd, Beach Blvd, and screening of other arterials), built as
a fast, transparent alternative to a full FTA STOPS run.

## Method

Incremental (pivot-point) logit, Monte-Carlo'd, anchored to observed boardings:

    forecast = observed corridor boardings x (base-share-weighted mean of
               per-segment share-growth factors)

Absolute market size and unobserved local constants cancel; borrowed
coefficients act only on the *change* in level of service. Key structural
features (see `scripts/model.py`):

- **Arrival-strategy wait structure.** Initial wait for walk-access riders is
  `min(headway/2, w0 + lambda*headway)` -- the closed form of a rider choosing
  between random arrival and schedule-timed arrival. Removes the linear
  `headway/2` credit that over-rewards frequency jumps from long headways.
  Transfer-access riders get `min(headway/2, transfer_cap)` (arrival time set
  by the feeder, so random arrival applies until schedule coordination caps it).
- **Transfer / partial-ride market.** One-end-in-corridor LODES commute flows
  are routed onto the line via the nearest GTFS feeder route that crosses the
  corridor; they ride from the feeder's crossing node to their corridor-end
  position. Their share of base boardings is pinned to the on-board-survey
  transfer share (25-40%), drawn in the Monte Carlo.
- **Non-work expansion.** Work-trip growth is blended with a dampened non-work
  response (`kappa`), with the work share of boardings drawn 40-60%.
- **Parametrized build.** The proposed line is (speed, headway); a design
  sweep is part of standard output.
- **No empirical-envelope filter.** Reference-class uplift benchmarks
  (Twin Cities +33%, UW +35%, Cleveland HealthLine +78%) are *reported next
  to* the model's implied uplift, and the headline is shown under each
  envelope treatment -- the judgment is left to the reader. All structural
  knobs appear in the one-at-a-time sensitivity table.

## Layout

    config/            corridor definitions (route, window, anchor, service)
    scripts/
      download_data.py  fetch LODES, ACS B08141, gazetteer, OCTA GTFS -> data/raw
      build_derived.py  compress raw -> small committed tables in data/derived
      build_corridor.py corridor config -> model inputs json (tracts, segments,
                        walk bins, feeder crossings, transfer flows)
      model.py          the Monte-Carlo pivot model + sensitivities + sweep
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
- **Anchors:** Harbor = 10,000-13,000 (43+543; TSP study ~10k post-COVID,
  Route 43 ~13k at 2013 launch). Beach = 4,300-7,500 window share of a
  6,000-9,000 full-route range (Route 29 = 5,888 in Oct 2018 per the Beach
  Blvd Corridor Study baseline report, pre-529 and at twice today's frequency).

## Known issues & judgment calls

Recorded as they were made; each is exposed in the sensitivity output.

1. **Transfer-market base share** has no direct data; it is pinned so that
   transfers are 25-40% of base boardings (typical on-board survey range).
2. **Transfer coordination cap** (10-15 min) proxies for schedule coordination
   on long-headway feeders; OCTA does not generally run timed transfers.
3. **Image/reliability ASC trimmed to 0-0.40** (from 0-0.55) because the
   explicit schedule-delay term now carries part of the turn-up-and-go
   benefit previously bundled in the ASC. Sensitivity reports 0 and 0.55.
4. **One-transfer access only**; flows whose non-corridor end is not within
   0.9 mi of a crossing feeder are dropped (conservative). Flows to LA County
   are excluded (OC-only tract-pair table).
5. **LODES is commute-only**; the non-work market enters only through the
   work-share/kappa expansion, not its own O-D shape.
6. **Harbor baseline service** uses the corridor-study values (15 mph, 24-min
   headway); current GTFS shows 12.8 mph and 20-min -- sensitivity rows cover
   both.
7. **Beach anchor scaling** (full route -> window) uses the window's share of
   ACS transit workers (0.84) and of LODES O-D flows (0.71) as the range.
