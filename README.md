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
- **Derived average speed (spec 02 §4.9).** The forward line's average speed
  is no longer an independent config knob: it is DERIVED from a cruise-speed
  prior, a station-dwell prior, and the stop spacing via a TCQSM-style
  decomposition `min/mi = 60/v_cruise + (dwell + accel/decel loss)/(60·spacing)`.
  The proposed elevated automated light-metro line uses the grade-separated
  variant (no signal delay; per-stop loss = accel+decel time at a comfortable
  1.0 m/s²) with **jerk-limited (S-curve) kinematics** (§4.9b): acceleration
  ramps at a finite jerk 0.75 m/s³ (comfort band ~0.5–1.0), and if the stop
  spacing is too short to reach cruise the reached speed is **capped** to the
  attainable peak (at 0.25-mi the train physically tops out near 70 km/h, not
  80). At the prior-central 80 km/h cruise / 25 s dwell / 1-mi spacing this
  gives ~29.8 mph (the ~1% jerk correction off R6's 30.09), still validating
  the old 30-mph value (kept as the exogenous fallback; the `exogenous speed
  (old spec)` sensitivity row and the `exogenous_speed=1` governance toggle
  restore the scalar path; `j→∞` with the cap retained is the `trapezoid
  kinematics (R6)` regression row). The street variant is calibrated **in
  code** from two measured OCTA points (Route 43 = 11.4 mph @ 0.25-mi, Route
  543 = 12.8 mph @ 1.0-mi → per-stop penalty ~0.19 min, no-stop street speed
  ~13.3 mph), prices hypothetical bus designs, and is exempt from the S-curve
  (its measured end-to-end speeds already embed real jerk); the measured base
  services keep their config scalar speeds (measured stays measured). The
  design sweep's speed axis is now the grade-separated **cruise** axis
  (60–90 km/h), and the stop-spacing sensitivity rows now recompute speed — so
  a tighter 0.5-mi grid is charged its added stops (that row shrank +23.6% →
  +16.7%; the 1.5-mi row eased −22.3% → −20.1%).
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
  weighted by how well each reproduces the launch-equivalent 543 outcome
  (`scripts/reweight_abc.py`; Gaussian kernel mu=5,938 -- the FY2017 measured
  4,615/wd scaled by OCTA's measured FY2013/FY2017 system back-trend 1.2868,
  spec 02 §4.6 -- sigma=500, ESS ~15,100, seed-drift 0.0%; the matured
  six-year average mu=4,200 is retained as a sensitivity row, not the target).
  This calibrates against the corridor's own natural
  experiment -- categorically different from filtering by literature
  benchmarks, which remains rejected (the old cap +80%/+55% columns are
  gone). Reference-class uplifts (Twin Cities +33%, UW +35%, Cleveland
  HealthLine +78%) are still printed next to the model's implied uplift, and
  all structural knobs appear in the one-at-a-time sensitivity table.

**Headline (2026-07, measured anchor; launch-equivalent ABC target; average
speed now DERIVED with jerk-limited kinematics, spec 02 §4.9/§4.9b): uncapped
blend P50 = 11,949 (P10-P90 9,938-13,971), implied corridor uplift
+31/+44/+60%; backtest-calibrated P50 = 11,811 (10,356-13,370). The
calibration's main effect is on the new-line ASC: posterior 0.14/0.19/0.24 vs
prior 0.09/0.20/0.31 -- now near the prior midpoint, since the
launch-equivalent target (mu=5,938) sits close to the model's backtest mass
(P50 6,169). The matured-target row (mu=4,200) still gives 10,733
(9,063-12,306), posterior 0.06/0.11/0.16 -- the old central, kept as a
sensitivity.**

## Backtest (scripts/backtest_543.py)

The model is pointed at the 2013 launch of the Bravo! 543 (add a 15 mph
rapid overlay at its actual 10-min-peak / 15-min-off-peak launch service to
the existing Route 43 local, both retained):

- predicted 543 weekday boardings at prior-central parameters:
  **P50 = 6,169** (P10-P90 3,862-8,923); observed (measured route-level
  data, `scripts/anchor_from_apc.py`): **~3,700-4,600** weekday boardings
  (FY2019 / FY2017; six-year average ~4,250 -- the press figures
  ~3,500-3,900 previously used here were low). The model at its priors
  overpredicts the MATURED measurement, but the calibration now targets a
  **launch-equivalent** level (spec 02 §4.6): the FY2017 4,615/wd scaled by
  OCTA's measured FY2013/FY2017 system back-trend (1.2868) gives mu=5,938,
  which the backtest P50 (6,169) overshoots by only ~4% -- honesty note: an
  earlier version reported a near-perfect 3,804, but that came from an
  unfaithful flat-15-min spec plus knife-edge choice artifacts.
- predicted corridor uplift +5/+9/+16% -- directionally consistent with the
  observed non-growth of total corridor ridership (an overlay on an
  already-frequent local mostly re-sorts riders; cf. FTA's Cleveland finding)
- the residual is what the ABC treatment consumes: reweighting draws by the
  launch-equivalent target (kernel mu = 5,938) leaves the new-line ASC near
  0.19 (prior midpoint 0.20) and pulls the forward headline only slightly,
  11,949 -> 11,811 (ESS 15,090, up from the matured target's 8,624 because
  the target now sits inside the prediction mass). The retired matured target
  (mu = 4,200) concentrated the ASC near 0.11 and pulled the headline to
  10,733 (ESS 8,624) -- kept as a sensitivity row (README known issue 15,
  closed).

Caveats: 2022 LODES / 2023 ACS proxy for 2013 markets; the 2013 Route 43's
peak headway is unknown (flat 15 assumed; the "43 at 10-min pk/15 off" row
moves the prediction -24%, which the ABC kernel's structural-error term
covers).

## Reading the outputs (two easy stumbles)

- The sensitivity tornado's central (12,036) is the *expected* fold/retain
  blend at fixed bins, n=4,000; the headline P50 (11,949) is the full-MC
  coin-flip blend at n=40,000. They differ by <1% by construction; the
  tornado measures deltas, not the headline.
- The design sweep's "h=5" cell is 5-min peak / 10-min off-peak (sweep
  convention: off-peak = 2x peak), while the sensitivity row "flat 5-min
  all day" is a different service definition — the two 5-minute numbers
  are not comparable.
- The design sweep's rows are now the grade-separated **cruise** speed
  (60–90 km/h), not the average speed — the derived average mph is printed in
  parentheses per row (`results_harbor.json` records `sweep_axis`). Adjacent
  cruise cells at fixed headway move ≤1.7% (spec 02 §5 continuity gate ≤8%);
  the large step across headway columns is the service effect, not a kink.

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
      extract_apc.py    all-route boardings table from the report PDFs
                        -> data/derived/route_boardings.csv
      anchor_streetcar.py  OC Streetcar cold-start anchor (spec 05 §3.3):
                        shape-share x measured boardings of parallel carriers
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
   treatment: the launch-equivalent 543 calibration puts the posterior at
   0.14/0.19/0.24 (near the prior midpoint 0.20), and the calibrated column
   shows what the corridor's own experiment implies. (The retired matured
   target pulled it lower, to 0.06/0.11/0.16 -- kept as a sensitivity row.)
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
    forward market, PLUS the launch-equivalent back-trend vintage uncertainty
    -- the FY2013-vs-FY2014 ratio spread is itself exposed as the
    543_launch14_s500 kernel, mu=5,647). At the launch-equivalent target
    (mu=5,938) the kernel sits inside the prediction mass, so sigma 350/800
    move the calibrated P50 by <0.2% (the matured target was more sensitive).
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
15. ~~The calibration target is matured, not launch, ridership — and the
    backtest residual is one-sided.~~ **Closed 2026-07-11:** launch-equivalent
    retarget landed (spec 02 §4.6). mu=4,200 was the six-year matured average;
    the earliest measurement (FY2017 = 4,615) is four years post-launch, after
    systemwide decline began, so it under-stated the launch response and
    over-pulled the ASC down (compounding issue 14). The retarget scales the
    FY2017 measurement to launch vintage by OCTA's measured FY2013/FY2017
    system bus-UPT back-trend (NTD ID 90036, dual-source verified):
    mu = 4,615 x 1.2868 = 5,938 (central kernel `543_launch_s500`). The
    matured 4,200 is kept as a sensitivity row (`543_matured_s500`), and the
    FY2014-vintage reading (mu=5,647, `543_launch14_s500`) as another. The
    central backtest residual, one-sided at +47% against the matured target
    (P50 6,169 vs 4,200), shrinks to +3.9% against the launch-equivalent
    target — the saturation signal (specs 00 §5 / 02 §4.4) is largely
    resolved, not smoothed away. Effect: calibrated headline 10,757 -> 11,836,
    ASC posterior 0.11 -> 0.19, ESS 8,624 -> 15,090.
16. **The streetcar anchor is measured but WEAK, and its rail ASC is
    borrowed** (spec 05). The OC Streetcar corridor (config/streetcar.json)
    has no co-located route pair like Harbor's 43/543 — its anchor
    (3,600-5,500) is a composite of partial overlaps (Rt 60/64/560/150
    shape-shares x measured boardings), with SARTC rail transfers and
    greenfield new access excluded (upside risk, out of scope by
    construction). Its ASC bracket {1.0, 1.5, 2.0} is borrowed from the
    metro scenario; an at-grade slow streetcar premium may differ. The
    result (P50 ~5,600, inside OCTA's 5,000-7,300 band) should be read
    with both caveats. Post-launch APC (~2027) becomes the first
    rail-class ABC target (records request item 4).

Items 17-24 were opened by **spec 06 (BCA integration, `specs/06-bca-integration.md`
§10)**. Entries 17-18 are stage-2 exposures visible in this repo's exports;
19-24 bind the BCA wrapper/engine side (`transit-benefit-cost`, not yet built)
and become live sensitivity rows when W1 lands.

17. **Behavioral VOT ≠ social VOT** — deliberate, both exposed as priors:
    `vot_behav` ($10-22/hr) governs fare response in stage 2, social `VOT`
    ($15-30/hr) converts minutes to dollars in the BCA. Rows `vot_behav` lo/hi
    and `VOT` lo/hi must NOT be read jointly at opposite extremes (jointly
    implausible preferences); the tornado prints the caution (spec 06 D3).
18. **Transfer-market diverted car-miles use the corridor-leg distance** — an
    undercount, since the diverted car trip covers the full O-D. The
    `cm_seg_fullod` stream (full-O-D straight-line distance per transfer bin)
    bounds it, but DIRECTIONALLY (a flow-weighted-mean bound), not per-bin: the
    longest harbor transfer bin has full-OD 7.83 mi < corridor-leg 11.48 mi, so
    the "bound" sits below the base for individual long bins. Wrapper row
    `transfer-full-OD` (spec 06 D7).
19. **Growth vs ramp asymmetry** — growth (`g`) scales all quantity streams
    proportionally (whole-market scaling is coherent); the ramp is margin-only
    by construction (`um_infra`/existing riders are never ramped). The earlier
    all-streams linear ramp had opposite-signed biases by stream and was
    rejected at review. BCA time-profile knobs (spec 06 D6).
20. **R1 retarget and the BCA ramp prior pull opposite directions** on the
    543's launch shape: R1's FY2017 × back-trend retarget implies the 543
    launched HIGHER and eroded, while the BCA ramp prior assumes launch BELOW
    steady state — and the observable 543 series (FY2017 4,615 → FY2019 3,739)
    shows no visible ramp-up. Logged, not hidden; records item 1a (FY2014-16
    route-level) disciplines both when it lands (spec 06 D6).
21. **γ / SCC / pcar / O&M priors are literature-informed** exposed knobs, each
    carrying a zero or lo row (γ=0 central, SCC 0/190, pcar set lo/hi,
    avoidable-cost marginal end). Allowed as exposed priors with rows;
    literature-envelope FILTERS remain rejected (standing user decision) — spec
    06 D8/E4.
22. **Crowding deliberately out of stage 2** — a diagnostic load flag only, no
    CS haircut in v1 (wrapper "CS haircut when load > comfort" row keeps the
    tail exposure visible). D4's load arithmetic uses a conservative peak
    decomposition ~2× spec 04 §3.1's; the two bases are cross-referenced and
    the below-comfort-threshold conclusion is robust to either (spec 06 D4).
23. **Single VOT across trip purposes, and the κ-blend as a QUANTITY blend** —
    both named judgments with rows: "non-work minutes at 0.7×VOT" and κ→1. The
    κ-blend expands non-work quantities; it does NOT revalue them (spec 06
    D3/D8).
24. **Avoided-cost rate: fully-allocated NTD $/rev-hr overstates** what folding
    routes actually sheds (folding two routes does not shed their full
    allocated cost). The E4 avoidable-cost knob spans marginal → fully-allocated
    $/rev-hr, with a row at the marginal end (spec 06 E4).

25. **Derived average speed — two deliberate simplifications** (spec 02 §4.9,
    landed 2026-07-11). (a) **Dwell-loading feedback ignored:** station dwell
    is a prior (20–30 s), but real dwell grows with boardings, so a small
    ridership→speed→ridership feedback is left out at this stage (it would
    modestly damp the busiest cells). (b) **Measured stays measured:** the
    grade-separated derivation drives only the forward line; the base services
    (43 local, 543 rapid) and the 2013 backtest keep their measured config
    scalar speeds, and the OC Streetcar stays exogenous (a built, scheduled,
    at-grade line). The street-calibrated curve (Route 43 11.4 mph @ 0.25-mi,
    Route 543 12.8 mph @ 1.0-mi → ~13.3 mph no-stop, ~0.19 min/stop) exists to
    reproduce those two points and to price hypothetical bus designs, not to
    overwrite measurement. It also gives item 9 a physical reading: the 543's
    corridor-doc 15 mph sits ABOVE this street curve's 12.8 mph @ 1.0-mi, so
    that doc value implies TSP/priority the current street does not have — the
    "rapid → GTFS current" sensitivity row already brackets it. (c) **Uniform
    running way** (spec 02 §4.9b, jerk-limited kinematics landed 2026-07-11):
    the grade-separated S-curve now models finite jerk (0.75 m/s³) and caps
    speed to what the stop spacing allows, but the alignment is still treated
    as uniform — grade profile, curves, and civil speed restrictions (which
    would impose local caps below cruise) are ignored. A stage-3 (STOPS)
    concern, like the dwell-loading feedback.
