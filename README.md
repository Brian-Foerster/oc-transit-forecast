# OC Transit Forecast

Corridor-level ridership forecasting for the Harbor Blvd (Fullerton → Santa
Ana) rapid-transit proposal, built as a fast, transparent alternative to a
full FTA STOPS run. Disciplined by the corridor's own natural experiment
(the 2013 Bravo! 543 launch), which both tests the model and calibrates it
(ABC treatment, reported side by side with the uncalibrated headline).

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
  from the rider's position relative to each service's stop grid**. A rider's
  street position is uniform over one grid period; every service's walk time
  is computed from that *same* position (K=8 quadrature, exact for
  0.25/0.5/1.0-mi grids), so each sub-rider takes their *best* service --
  deliberately not a logsum, because parallel routes on one street are
  near-perfect substitutes and a logsum awards a fictitious red-bus/blue-bus
  "variety bonus" (the rejected spec is a sensitivity row, -37%; the old
  knife-edge point-value spec is another, +3%). The fold-vs-retain question
  and the new line's share of corridor riders are *derived* (V_new vs
  V_local), replacing the earlier invented 25-40% retained-share prior.
- **Time of day.** Headways may differ by period ({peak, offpeak}); utilities
  are computed per period and blended by a peak-share-of-boardings prior
  (45-60%). The proposed line runs 5-min peak / 10-min off-peak; GTFS
  measurement shows the base routes at flat 20-min peak AND midday, so they
  stay scalar. "Flat 5-min all day" is kept as a sensitivity row (+7%, the
  overstatement the old spec carried).
- **Arrival-strategy wait structure.** Walk-access wait is
  `min(headway/2, w0 + lambda*headway)` -- the closed form of a rider choosing
  between random and schedule-timed arrival. Transfers get
  `min(headway/2, transfer_cap)`; visitors get `headway/2` (no schedule
  adaptation).
- **Transfer / partial-ride market.** One-end-in-corridor LODES commute flows
  are routed onto the line via the nearest GTFS feeder route that crosses the
  corridor, pinned to the on-board-survey transfer share (25-40%) of base
  boardings.
- **Sub-half-mile market.** Intra-tract LODES flows enter with an imputed
  along-line distance sqrt(tract land area)/3 (clipped 0.1-0.45 mi), and
  short cross-tract pairs land in the same 0-0.5-mi bin -- 26% of the walk
  market. Short hops strongly favor the local's 0.25-mi stops, which is what
  makes the retained-local share (~8% at P50) non-zero. Sensitivity row
  "no sub-half-mile bin" restores the old market definition (+5%).
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
- **No baked-in filter; calibration shown side by side.** The headline is
  reported **uncapped** next to a **backtest-calibrated (ABC)** treatment:
  the same 40,000 draws are run through the 2013 Bravo! 543 configuration and
  weighted by how well each reproduces the observed 543 outcome
  (`scripts/reweight_abc.py`; Gaussian kernel mu=4,200, sigma=500, ESS ~8,600,
  seed-drift +0.1%). This calibrates against the corridor's own natural
  experiment -- categorically different from filtering by literature
  benchmarks, which remains rejected (the old cap +80%/+55% columns are
  gone). Reference-class uplifts (Twin Cities +33%, UW +35%, Cleveland
  HealthLine +78%) are still printed next to the model's implied uplift, and
  all structural knobs appear in the one-at-a-time sensitivity table.

**Headline (2026-07, measured anchor): uncapped blend P50 = 11,969 (P10-P90
9,963-13,995), implied corridor uplift +31/+45/+61%; backtest-calibrated
P50 = 10,757 (9,098-12,336). The calibration's main effect is on the
new-line ASC: posterior 0.06/0.11/0.16 vs prior 0.09/0.20/0.31.**

## Backtest (scripts/backtest_543.py)

The model is pointed at the 2013 launch of the Bravo! 543 (add a 15 mph
rapid overlay at its actual 10-min-peak / 15-min-off-peak launch service to
the existing Route 43 local, both retained):

- predicted 543 weekday boardings at prior-central parameters:
  **P50 = 6,169** (P10-P90 3,862-8,923); observed (measured route-level
  data, `scripts/anchor_from_apc.py`): **~3,700-4,600** weekday boardings
  (FY2019 / FY2017; six-year average ~4,250 -- the press figures
  ~3,500-3,900 previously used here were low). The model at its priors
  still **overpredicts the launch** -- honesty note: an earlier version
  reported a near-perfect 3,804, but that came from an unfaithful
  flat-15-min spec plus knife-edge choice artifacts.
- predicted corridor uplift +5/+9/+16% -- directionally consistent with the
  observed non-growth of total corridor ridership (an overlay on an
  already-frequent local mostly re-sorts riders; cf. FTA's Cleveland finding)
- the discrepancy is what the ABC treatment consumes: reweighting draws by
  the measured outcome (kernel mu = 4,200) concentrates the new-line ASC
  near 0.11 (vs prior midpoint 0.20) and pulls the forward headline from
  11,969 to 10,757 (ESS 8,624).

Caveats: 2022 LODES / 2023 ACS proxy for 2013 markets; the 2013 Route 43's
peak headway is unknown (flat 15 assumed; the "43 at 10-min pk/15 off" row
moves the prediction -24%, which the ABC kernel's structural-error term
covers).

## Reading the outputs (two easy stumbles)

- The sensitivity tornado's central (12,051) is the *expected* fold/retain
  blend at fixed bins, n=4,000; the headline P50 (11,969) is the full-MC
  coin-flip blend at n=40,000. They differ by <1% by construction; the
  tornado measures deltas, not the headline.
- The design sweep's "h=5" cell is 5-min peak / 10-min off-peak (sweep
  convention: off-peak = 2x peak), while the sensitivity row "flat 5-min
  all day" is a different service definition — the two 5-minute numbers
  are not comparable.

## Layout

    config/            corridor definition (route, anchor, services incl. stop
                       spacing, visitor market)
    scripts/
      download_data.py  fetch LODES, ACS B08141, gazetteer, OCTA GTFS -> data/raw
      build_derived.py  compress raw -> small committed tables in data/derived
      build_corridor.py corridor config -> model inputs json (tracts, segments
                        with MOE-based SEs, walk bins, feeder crossings,
                        transfer flows)
      anchor_from_apc.py  anchor derivation from measured OCTA route-level
                        boardings (source URLs + full data table inside)
      route43_share.py  Route 43's corridor share (anchor consistency)
      model.py          the Monte-Carlo pivot model + sensitivities + sweep
      backtest_543.py   backtest vs the 2013 Bravo! 543 launch
      reweight_abc.py   backtest-calibrated (ABC) treatment + ASC posterior
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
- **Anchor (MEASURED, 2026-07):** 7,650-9,650. OCTA's quarterly "Bus
  Operations Performance Measurements" reports (still live on octa.net --
  found by URL-pattern probing; `scripts/anchor_from_apc.py` has the URLs
  and the full table) give route-level annual boardings: FY2019 Route 43 =
  2,095,510, Route 543 = 953,471 (FY2017: 2,190,951 / 1,176,910; FY2020
  YTD-Q3: 1,515,585 / 641,470). Weekday: 543 (weekday-only) = 3,739; 43
  (7-day) = 6,350-6,985; scaled by the FY2019->FY2024 system trend
  0.90-0.99 (per-month ratio 0.94, from the OC_Bus_Ridership monthly
  report), times [543 fully + Route 43 x corridor share 0.75 (LODES) - 0.86
  (ACS) -- `scripts/route43_share.py`]. 43+543 held 8.3-8.7% of system
  boardings FY2017-FY2020, matching -- and superseding -- the TSP study's
  ">10,000 daily boardings, 8% of all OCTA riders" quote the old anchor
  inferred from. Cross-check: 12,800 on-Harbor boardings in 2015 (Central
  Harbor Blvd Transit Corridor Study) x trend x street-vs-corridor share
  ~ 8,400. Historical (backtest): Route 43 ~13,000 at the 543's June 2013
  launch; 543 launched at 10-min peak / 15-min off-peak; 543 measured
  weekday boardings FY2017 = 4,615, FY2019 = 3,739, six-year cumulative
  6.4M ~ 4,250/wd (the old press figures ~3,500-3,900 were low).

## Known issues & judgment calls

Recorded as they were made; each is exposed in the sensitivity output.
(Items closed 2026-07 are struck through with their resolution.)

1. **Transfer-market base share** has no direct data; it is pinned so that
   transfers are 25-40% of base boardings (typical on-board survey range).
   Web research found no published OCTA transfer rate; it is item 4 of
   `outputs/records_request_draft.md`.
2. **Transfer coordination cap** (10-15 min) proxies for schedule coordination
   on long-headway feeders; OCTA does not generally run timed transfers.
3. **Image/reliability ASC trimmed to 0-0.40** (from 0-0.55). Still the #1
   sensitivity (+38% at 0.55 / -21% at 0), but now disciplined by the ABC
   treatment: the 543-launch calibration concentrates the posterior at
   0.05/0.08/0.13 -- the priors are generous to the new line, and the
   calibrated column shows what the corridor's own experiment implies.
4. **One-transfer access only**; flows whose non-corridor end is not within
   0.9 mi of a crossing feeder are dropped (conservative). Flows to LA County
   are excluded (OC-only tract-pair table).
5. **LODES is commute-only**; the non-work market enters through the
   work-share/kappa expansion. New sensitivity row "non-work trips shorter
   (4-mi tilt)" probes the inherited-shape assumption (-3.4%).
6. ~~Deterministic best-service choice is knife-edge~~ **Closed:** rider-
   position quadrature (K=8, exact for the grids in use) smooths the choice
   without a variety bonus; sweep kink gone, backtest band 6.2x -> 2.3x,
   old spec kept as a sensitivity row (+3.4%).
7. ~~Sub-half-mile trips excluded~~ **Closed:** intra-tract flows enter with
   an imputed sqrt(area)/3 distance (0-0.5-mi bin, 26% of the walk market);
   retained-local share now ~8%. Judgment call: visitor bin_weights' first
   bin split 0.25/0.30 (see config note).
8. ~~Time-of-day not modeled~~ **Closed:** peak/off-peak headways with a
   45-60% peak-share blend; the proposed line is 5-min peak / 10-min
   off-peak per the operating-plan decision; flat-5 kept as a row (+7%).
9. **Harbor baseline rapid** uses the corridor-doc values (15 mph / 24-min);
   current GTFS shows 12.8 mph / 20-min -- a sensitivity row covers it (+0.2%).
10. ~~The anchor is inference, not measurement~~ **Largely closed (2026-07):**
    route-level boardings through FY2020-Q3 and monthly system ridership
    through Mar 2024 were recovered from OCTA's own site (URL-pattern
    probing + a filename with a stray space; `scripts/anchor_from_apc.py`).
    Anchor now 7,650-9,650 measured. Remaining gaps for the records request:
    stop-level APC, post-2020 route-level, FY2014-16 (launch ramp), and the
    on-board transfer rate.
11. **The 2013 Route 43's peak headway is unknown** (backtest assumes flat
    15-min; the 10/15 variant moves the backtest -24%). Covered by the ABC
    kernel's structural-error term; a records request would settle it.
12. **The FY2019->FY2024 trend factor (0.90-0.99)** applies the SYSTEM
    per-month ratio and assumes the corridor's share held through the
    COVID recovery. The share was stable pre-COVID (8.3-8.7% measured,
    FY2017-FY2020), but "held through recovery" is an assumption, and a
    possibly conservative one: dense transit-dependent corridors generally
    recovered above system average. FY2021 route-level reports (live on
    octa.net) can partially test this; post-2020 data (records request)
    would pin it.
13. **ABC kernel width is a judgment call** (sigma=500 = obs spread (+)
    structural error, the latter now explicitly including the post-COVID
    2022 LODES commute *shape* proxying both the 2013 experiment and the
    forward market); sigma 350/800 move the calibrated P50 by <1.3%.
14. **ASC transportability is assumed, not shown** (review 2026-07-08).
    The ABC posterior moves essentially only the ASC (bivt/ovt barely
    shift), so the calibrated headline rests on one assumption: the new
    line's image/reliability premium equals the 2013 Bravo! 543's. The
    543 was a modest overlay; the proposed line is a categorically larger
    jump, which plausibly earns a LARGER premium — the calibration treats
    the weaker experiment's premium as a ceiling for a stronger
    intervention. Defensible conservatism, now named. An
    ASC-transportability sensitivity (forward ASC = calibrated x premium
    factor) is queued.
15. **The calibration target is matured, not launch, ridership — and the
    backtest residual is one-sided.** mu=4,200 is the six-year matured
    average; the earliest measurement (FY2017 = 4,615) is four years
    post-launch, after systemwide decline began. If the 543 launched
    higher and eroded, the target under-states the launch response and
    over-pulls the ASC down (compounding issue 14 in the same direction).
    A launch-equivalent retarget (FY2017 x 2013/2017 system back-trend,
    needs OCTA FY2013 UPT from NTD) is queued. Relatedly, per the
    saturation rule (specs 00 §5 / 02 §4.4): the central backtest residual
    is one-sided (P50 6,169 vs target 4,200; even P10 barely reaches the
    observed band) — reported here as a model-saturation signal, not
    smoothed away by the kernel.
