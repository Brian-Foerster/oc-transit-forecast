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
  attainable peak (at 0.25-mi the train physically tops out near 70 km/h, well
  under the cruise setting). At the **owner 2026-07-17 60-mph design central
  (v_cruise 96.6 km/h)** / 25 s dwell / 1-mi spacing this gives **~31.8 mph**
  (was ~29.8 mph at the old 80 km/h literature central); the ~30-mph value is
  kept as the exogenous fallback (the `exogenous speed
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

**Owner design change 2026-07-17:** the line's top speed is set to **60 mph
outright** (v_cruise prior recentred 80→96.6 km/h; ~31.8 mph derived average,
was ~29.8), and the design sweep now tests **sub-5-minute** peak headways
({2.5, 3.5, 5, 10, 15}) with the derived fleet (`capcost.fleet`) annotated per
column — a 2.5-min headway ≈ doubles the fleet (25→48 cars). The faster line
raises the headline ~1% and the welfare BCA ~4%; the fleet drops 27→25 cars.
The full frequency trade: the 2.5-min plan buys +10.6% riders for +23 cars
(≈ +$171M LOW capital at $7.44M/car) plus roughly doubled variable O&M —
welfare-negative at a ~0.12-BCR corridor (LOW, ABC, P50); the sweep prices
ridership, the BCA prices the trade, and the 5/10 plan remains the design
point.

**Headline (2026-07-17, measured anchor; launch-equivalent ABC target; average
speed DERIVED with jerk-limited kinematics at the 60-mph design cruise, spec 02
§4.9/§4.9b): uncapped blend P50 = 12,074 (P10-P90 10,066-14,127), implied
corridor uplift +30/+44/+61%; backtest-calibrated P50 = 11,947 (10,478-13,520). The
calibration's main effect is on the new-line ASC: posterior 0.14/0.19/0.24 vs
prior 0.09/0.20/0.31 -- now near the prior midpoint, since the
launch-equivalent target (mu=5,938) sits close to the model's backtest mass
(P50 6,169). The matured-target row (mu=4,200) still gives 10,868
(9,213-12,448), posterior 0.06/0.11/0.16 -- the old central, kept as a
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
  12,074 -> 11,947 (ESS 15,090, up from the matured target's 8,624 because
  the target now sits inside the prediction mass). The retired matured target
  (mu = 4,200) concentrated the ASC near 0.11 and pulled the headline to
  10,868 (ESS 8,624) -- kept as a sensitivity row (README known issue 15,
  closed).

Caveats: 2022 LODES / 2023 ACS proxy for 2013 markets; the 2013 Route 43's
peak headway is unknown (flat 15 assumed; the "43 at 10-min pk/15 off" row
moves the prediction -24%, which the ABC kernel's structural-error term
covers).

## Reading the outputs (two easy stumbles)

- The sensitivity tornado's central (12,155) is the *expected* fold/retain
  blend at fixed bins, n=4,000; the headline P50 (12,074) is the full-MC
  coin-flip blend at n=40,000. They differ by <1% by construction; the
  tornado measures deltas, not the headline.
- The design sweep's "h=5" cell is 5-min peak / 10-min off-peak (sweep
  convention: off-peak = 2x peak), while the sensitivity row "flat 5-min
  all day" is a different service definition — the two 5-minute numbers
  are not comparable. The sweep's headway axis was extended below 5 min
  (owner 2026-07-17 sub-5-min frequency test): peak {2.5, 3.5, 5, 10, 15},
  each column annotated with the derived `capcost.fleet` car count at the
  60-mph design central (`results_harbor.json` records `sweep_headways` +
  `sweep_fleet`; the `headway_35_7` / `headway_25_5` one-at-a-time rows carry
  the same 3.5/7 & 2.5/5 plans into the tornado).
- The design sweep's rows are the grade-separated **cruise** speed
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
      assumptions.py    single-source registry of every asserted value +
                        structural choice (spec 08); code imports from here
      check_assumptions.py  the seven §5 enforcement checks + `--appendix`
    data/derived/      small reproducible tables (committed)
    outputs/           results json + charts (committed)

**Assumptions inventory.** Every value the model imports and every structural
knob is one entry in `scripts/assumptions.py`; `python scripts/check_assumptions.py`
enforces coverage/no-orphans/pointers/citations and `--appendix` regenerates
`outputs/assumptions.md` + `outputs/assumptions.json` (the auditable inventory:
unpropagated exposures, priors, width sensitivities, dispositions, basis census).

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
    **R2 addendum (2026-07-20):** the vintage factor is now ALSO carried as
    an explicit uncertainty band, not only a discrete alternative: kernel
    `543_launch_bt_s507` marginalizes B ~ U(1.2236, 1.2868) -- the June-2013
    launch sits exactly on the FY2013/FY2014 fiscal boundary, so the two
    annual readings bracket it -- into Gaussian form (mu~5,793, sigma~507;
    reweight_abc.py KERNELS block). The tbc welfare-BCA wrapper stays on the
    central kernel; the band kernel is an oc-side sensitivity row.
14. **ASC transportability is assumed, not shown** (review 2026-07-08).
    The ABC posterior moves essentially only the ASC (bivt/ovt barely
    shift), so the calibrated headline rests on one assumption: the new
    line's image/reliability premium equals the 2013 Bravo! 543's. The
    543 was a modest overlay; the proposed line is a categorically larger
    jump, which plausibly earns a LARGER premium — the calibration treats
    the weaker experiment's premium as a ceiling for a stronger
    intervention. Defensible conservatism, now named. **Landed 2026-07-20
    (R2 batch, spec 02 §4.5c):** the ASC-transportability sensitivity is now
    three rows in both corridor tables (`asc_premium_10/15/20`: forward ASC =
    launch-calibrated 0.189 x premium {1.0, 1.5, 2.0}, registry entry
    `asc_calibrated_launch`), alongside the §4.5a damped-time rows
    (`gamma_07/08/09`), the §4.5d small-theta choice rows (`theta_01/02`),
    and the §4.5b "with induced demand" side column + `induced_lo/hi` rows
    (never the headline).
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
19-24 bind the BCA wrapper/engine side (`transit-benefit-cost`). **W1 landed
2026-07-15** (item 27): these are now live sensitivity rows in the welfare-BCA
tornado (`bca_harbor.json`).

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
26. **Assumptions registry landed (spec 08, 2026-07-14):** every asserted
    value and structural choice is now a single-source `scripts/assumptions.py`
    entry, enforced by `scripts/check_assumptions.py` (a standing gate).
    Accepted disposition: the `intra_tract_alt` rebuilt-variant row makes
    `model.py main()`'s FULL sensitivity table rebuild a scratch corridor via
    `build_corridor.py`, which reads `data/raw` — so the zero-download property
    holds for `run()` and a fresh clone's committed outputs, but NOT for
    regenerating the full table from scratch (spec 08 §9 Q6).
27. **Welfare BCA landed, and it is deeply negative** (spec 06 W1, 2026-07-15;
    cross-repo `transit-benefit-cost` pipeline mode, tbc `aa16e0d`). The engine
    prices this repo's per-draw quantity streams: headline **NPV −$4.17B /
    PV-BCR 0.075** (fold, ABC-weighted, US-TYPICAL capital band, P50); every
    scenario × treatment × band is negative with P(NPV>0)=0. Read with the
    caveats that BOUND what this is and is not: (a) **existing-market only** —
    the ridership model prices diversion within today's OC travel market; it
    does not model the land-use / induced ridership a grade-separated line
    accrues over decades (the economic-potential layer, spec 00 §3, is a
    SEPARATE lens, never summed — governance rule 5). (b) **corridor-only, no
    network** — a single line priced in isolation; spec 07's network sequencing
    is where corridors earn feeder/interchange value. (c) the swing is
    dominated by **λ (MCPF) and the capital band**, not any ridership knob — the
    ridership-side rows (VOT, pcar, κ, no-ASC) move NPV by <$160M against a
    −$4.2B central. It is a gate-2 **companion**, not a decision metric (spec 00
    §3 amendment); the negative reflects rail-class capital against a mid-size
    corridor — the honest read the pipeline exists to produce, not a number to
    force. The W1 rider batch also added the `um_roh_*` (rule-of-half welfare
    alternative, ~3.4% divergence from exact-logsum by design) and
    `fare_receipts_*` export streams (un-blocking the tbc `roh` / `fare_sweep`
    tornado rows, the latter 0 at today's flat fare). Charts: `outputs/bca_harbor.png` +
    `bca_tornado_harbor.png` (`python scripts/make_charts.py bca harbor`).

28. **Network-sequencing harness — the sequencing headline is now an NPV
    statement (spec 07 BUILT, N1–N6).** A greedy portfolio harness ABOVE the
    pipeline (`scripts/sequence_network.py`) evaluates each candidate ALM line
    against the network built so far, producing a build ORDER + a portfolio
    frontier as the planning layer's primary output (`outputs/network_sequence.json`,
    G6-deterministic). **N5 landed the full NPV objective (the DEFAULT).** Per
    candidate-given-network the harness builds a spec 06 §3 export from the
    in-memory `run()` result (no re-run) and prices it through the tbc v3 wrapper
    (`bca-pipeline.mjs`, node, synchronous), reading per-draw ΔNPV back for the
    within-draw CV in common-base-year PV dollars (§3), δ = one-cycle_gap deferral
    on the profile 4% clock, both spec 04 cost bands carried. **Headline: at the
    welfare-BCA central profile NO Orange County ALM corridor clears BCR=1 — the
    §7 marginal stop fires at CYCLE 1 and the decision-grade recommended build
    order is EMPTY** (build nothing). Scoping (rule-3 log, 2026-07-20;
    STRENGTHENED 2026-07-21): that verdict is a statement about the
    hand-supplied `config/candidates.json` universe, **NOT a claim over all
    Orange County alignments.** The scope note is now firmer because stage 1
    has failed to supply an empirical corridor-selection warrant **THREE
    TIMES** — the v2.0 screen, the v2.1 rebuild, AND the v2.2 productivity fit
    all landed `ordinal_ok = FALSE` (issues 35–44, spec 01 §10). The v2.2
    productivity move RESCUED criterion 1 (the demand block DOES predict
    productivity once the RVH tautology is removed: b1/b2 bootstrap pos_frac
    0.9075 / 0.9965 ≥ 0.841, up from v2.1's failing 0.8115 / 0.7435) but
    criteria 2/3 still fail on the LENGTH ARTIFACT (min battery rho 0.207 at
    `offset_variant`; issue 44). With no decision-grade window-level
    screen product in hand, `config/candidates.json` remains **analyst-chosen**
    (`hand_supplied: true`), so "no OC ALM corridor clears BCR=1" is a
    statement about the analyst's candidate set, never a screen-warranted
    census of Orange County corridors. Best marginal BCR ≈ 0.09 US-TYPICAL / 0.14
    LOW (harbor); streetcar wins by NPV level (least-negative, −$2.2B US-TYPICAL)
    but has the lower ratio (0.042/0.060). The stopping record prints the economic
    margin (the marginal BCR + the R2 premium-bracket {1,1.5,2} rows — even a 2×
    ASC premium leaves it far below 1), never "candidates ran out." The N5
    follow-ups also made std-based σ_struct widening the PRIMARY reported measure
    (P90−P10 secondary) and added a channel-split P50 non-additivity note. The
    interim welfare-minutes objective is retained as `--objective interim` (the
    byte-identical N4 regression anchor, `outputs/network_sequence_interim.json`).
    N6 landed the amendments: spec 00 §3 gains the network-sequence gate row, and
    spec 06 §1/§7's degrade-to-uncapped convention is amended (ABC weights are
    properties of the shared county posterior, applicable to any corridor under
    the same draws). The N4 batch added: the per-cycle
    **anchor-vs-rebuild channel split** (the reviewer's toggle method — separates
    synthetic-feeder MARKET ENLARGEMENT from crossing complementarity; the cycle-2
    streetcar|{harbor} lift is ~all the anchor-margin channel, rebuild ≈0); the
    **σ_struct** per-line independent structural-error row on the portfolio bands
    (harness-side, N(0, 400 boardings) seeded from the run fingerprint — NO new
    prior); the ω **walk-bin-mass** margin-distribution and spec-02-§4.3
    **exclusive-tract** (harbor/streetcar 27.3% catchment overlap) sensitivity
    rows; and the **run_id assumptions-values-hash** (the id now moves when the
    rate card or a prior band changes). The 17 capital + network-mechanics registry
    leaves now claim network-artifact rows — `check_assumptions.py` scans
    `network_sequence.json` (claimed ids; harness-internal sensitivity ids
    engine-owned/exempt, the spec 08 §9 Q7 precedent). Charts:
    `outputs/network_frontier.png` / `network_build_sequence.png` /
    `network_channels.png` (`python scripts/make_charts.py network`).

Items 29-33 were opened by the **spec 01 stage-1 screen panel revision
(2026-07-18, 3-lens adversarial panel; `specs/01-screen-drm.md` §5b)**. Each
is the `logged` pointer of a screen registry entry; the screen's sensitivity
rows land with the S34 build (`outputs/screen_results.json`).

29. **Standardized-service scoring is a presentation convention, not an
    identification fix** (spec 01 §1). Both revenue hours (b3) and ACS E016
    transit workers are endogenous to service: OCTA allocates service partly
    on unobserved demand (bad-control/collider risk that biases the demand
    coefficients generating every ranking), and tracts commute by transit
    because service exists (scoring on E016 would mechanically penalize
    never-served arterials — the exact corridors the underservice mechanism
    exists to surface). The dilemma: no cross-sectional fit on observed
    OCTA routes can fully identify fundamentals separate from service
    history. Resolution, mechanized rather than prose: E016 removed (E002
    zero-vehicle workers in; `e016_swap` row), RH kept as an allocation
    control with a `drop_rh` battery row, standing tests forbid published
    predictions at any counterfactual service level, and scoring at
    standardized service is labeled a comparison convention (registry
    `screen_endog_controls`).
30. **The 0.9-mi catchment buffer is ONE entry with TWO consumers, and it is
    under external challenge** (2026-07-17). Spec 01's screen reuses stage
    2's `buffer_mi` rather than minting a duplicate (the `corr_share`
    unification precedent); the entry's basis moved definitional→judgment
    with band (0.5, 1.25) and both-edge screen rescan rows
    (`buffer_lo`/`buffer_hi`). The stage-2 corridor-membership
    rebuilt-variant rows (0.5/0.75) are queued, not landed — until they land,
    the challenge is answered at stage 1 only.
31. **The 13-arterial prototype reproduction is a near-circular smoke test**
    (spec 01 §5). The prototype is what the fitted screen supersedes, so
    reproducing its ranking cannot validate the model — it is demoted to a
    smoke test (failure prompts investigation, not rejection). The 12.5-mi
    window length (`screen_window_mi`) also inherits the prototype's
    precedent as its judgment basis; the (10, 15) band edges are full-rescan
    sensitivity rows so the inheritance is probed, not assumed.
32. **Special-generator flags are hand-coded judgment data**
    (`config/special_generators.json`, 13 sites: resort/college/medical;
    registry `special_generators`, append-only history per edit). The b4
    dummy is identified from a handful of routes that are also the
    highest-boardings ones (Harbor/Disneyland), so it is high-leverage where
    the screen's discrimination matters most: `b4_off` and
    `gen_leave_class_out` rows plus mandatory dfbetas and Harbor-area
    with/without-b4 diagnostics keep the exposure visible. Upgrade: measured
    magnitudes (enrollment/attendance/LEHD workplace counts).
33. **The screen index normalization is a choice** (spec 01 §3.2/§4):
    `screen_index` = 100 × predicted-at-standardized-service / a baseline
    prediction, with standardized service = median fitted-route
    FY2019 revenue hours per route-mile × window length (`screen_svc_std`,
    measured 1577.65 rev-hr/route-mi/yr; p25/p75 probe rows expected
    rank-inert). Chosen so no field in `screen_results.json` is denominated
    in boardings — an ordinal screening index, never a ridership forecast
    (spec 00 §1); standing tests assert the guardrail. **Rebased
    2026-07-19** to the same-exposure baseline — see issue 36.
34. **Overlap grouping is measured-degenerate at county scale** (spec 01
    §3.3, review 2026-07-19). The connected components over >0.30
    shared-catchment windows collapse to ONE county-wide group on the real
    universe (one at the 0.2 band edge, two at 0.4): single-linkage
    transitivity chains ~96%-overlapping adjacent windows and the
    min-denominator share links parallel/crossing routes. `overlap_group`
    is kept in the artifact as specced but CANNOT deduplicate the gate-1
    shortlist; the artifact's `overlap_diagnostics` block (best window per
    host shape + per-pair overlap shares, no transitive closure) is what
    gate 1 uses. Replacing the grouping with a non-chaining rule
    (complete-linkage or host-shape-scoped) is an open owner decision.

Items 35-37 were opened by the **external critique of the stage-1 screen
(2026-07-19; verified claim-by-claim, accepted, and implemented as the SC
mechanical-correction batch)**. Items 35 and 36 are the `logged` pointers
of the tripwire entries and the normalization entry respectively.

35. **The screen's primary gate was thresholdless** — the rank-stability
    battery reported rho and churn but pre-registered no pass/fail rule,
    so any measured instability could be narrated past. Fixed by the
    pre-registered tripwire (registry `screen_t_min` = 1.0,
    `screen_battery_rho_min` = 0.7, `screen_top8_churn_max` = 2 — all
    pending owner ratification, 2026-07-19): the screen emits a
    decision-grade ORDINAL ranking only if every demand-block
    coefficient's cluster-robust |t| ≥ 1, the battery's minimum Spearman
    rho ≥ 0.7 (the leave-one-year-out consistency check excluded — it is
    mechanically ~0.99 under a single time-invariant X snapshot), and
    top-8 churn ≤ 2 under every perturbation; otherwise gate 1 consumes
    the THRESHOLD SHORTLIST (all `tie_with_cutoff` windows grouped by
    host shape) and the ordinal index is diagnostic-only. Mechanized as
    the artifact's `decision_output` block (spec 01 §5, screen_scan.py;
    standing test recomputes the pass booleans). Measured outcome at
    landing: ordinal_ok = FALSE (min |t| 0.81 on b2; min rho 0.39 at
    buffer_lo; max churn 8) — the screen currently delivers a shortlist,
    not a ranking. (Tripwire as written NOT ratified — superseded by the
    2026-07-20 owner review, issue 38: criterion 1 revised to the signed
    bootstrap fraction; criteria 2/3 statistics rebuilt, values
    deferred.)
36. **The old index ceiling ~72 was a mechanical length artifact** (spec
    01 §3.2). The superseded baseline normalized every 12.5-mi window by
    the median fitted route's prediction AT ITS OWN LENGTH (~18 mi); with
    b3+b5 = +0.917 per log-mile, no window of any quality could exceed
    ~72 by construction. Rebased 2026-07-19 to the SAME-EXPOSURE
    baseline: 100 = median over fitted host routes of that route's own
    best 12.5-mi-window prediction at standardized service. The rebase
    is a positive scalar multiple of the old index — ranks unchanged,
    asserted by a standing test (test_screen.py D5).
37. **Spec 01 justified grouped decomposition with "VIF>10" — the
    measured VIFs are all < 4** (max 3.81, b1_lodes; artifact
    `fit_diagnostics.vif`). The grouping itself survives on the correct
    ground: the demand coefficients are individually WEAK (cluster-robust
    |t| < 1: b1 ≈ 0.93, b2 ≈ 0.81), so per-coefficient attribution would
    be noise attribution; collinearity is mild and was never the real
    rationale. Spec §3.1 and the artifact's decomposition note now cite
    the measured values (corrected 2026-07-19).
38. **Owner review of the stage-1 tripwire (2026-07-20): criterion 1
    revised and ratified; criteria 2/3 statistics rebuilt, values
    deferred; §9.5 permanence clause softened.** The SC-batch tripwire
    (issue 35) was NOT ratified as written. (a) Criterion 1 is now the
    SIGNED BOOTSTRAP FRACTION (registry `screen_pos_frac_min` = 0.841,
    owner-ratified): each demand-block coefficient — the block is
    {b1_lodes, b2_e002}; b4 sits outside it per the grouped
    decomposition, its wrong-sign risk priced by the `b4_off` row, its
    per-replicate sign kept as a diagnostic — must be strictly positive
    in ≥ 0.841 = Φ(1) of the B=2000 bootstrap replicates (the one-sided
    |t| ≥ 1 translation with the sign requirement added; t = 1 is where
    a regressor starts improving adjusted R² and out-of-sample error).
    The analytic cluster-robust |t| (`screen_t_min`, superseded) is
    demoted to a diagnostic: cluster SEs are downward-biased at ~41
    clusters and the bias runs toward pass. Measured: b1_pos_frac
    0.8115, b2_pos_frac 0.7435 → criterion 1 FAILS on the v2.0 build.
    (b) Criterion 2 keeps its statistic (battery min Spearman ρ); the
    0.7 value is PROVISIONAL pending the owner's decision on the new
    `shortlist_stability` report (every frozen battery row's own
    bootstrap tie set vs the margin-defined headline tie set; CRN
    per-row seed rule); any e016-anchored calibration story for 0.7 is
    RETRACTED — it tuned the bar to an observed row (e016_swap ρ 0.746)
    whose own example fails criterion 3 anyway (recorded in the registry
    entry's history). (c) Criterion 3's statistic is REBUILT as
    margin-defined tie-set churn (max `tie_churn_frac` across battery
    rows; `screen_top8_churn_max` superseded, hard-top-8 churn demoted
    to a unit-tagged per-row diagnostic); its threshold is UNSET until
    the owner reads the report — and since an unset threshold cannot
    pass, `ordinal_ok` is FALSE BY CONSTRUCTION until then (the intended
    fail-safe). Measured stability: min Jaccard 0.109 (e016_swap), max
    tie churn 0.848 (e016_swap), STABLE CORE EMPTY (0 of 46 headline tie
    windows survive every battery row) — the gate-1 memo must say the
    honest stage-1 output is narrower than the shortlist. (d) The
    battery row list is FROZEN (registry `screen_battery_rows`; the
    battery is a MIN, so list edits are owner-approved spec amendments).
    (e) Spec §9.5's "no v2.2, permanent, no re-tuning" clause is
    SOFTENED: failure ⇒ threshold-shortlist (or narrower) output UNTIL a
    documented, owner-approved change of method; the frozen object is
    the §9 rebuild spec itself — same-spec re-runs are barred, method
    changes are governed, not banned. (f) Epistemics (owner item 4c,
    2026-07-20): the SB reviewer's byte-match of the screen artifact is
    recorded as IMPLEMENTATION verification — it shows no coding slip
    and nothing more; it does not validate the route-cluster bootstrap
    as the right uncertainty model, because reviewer and author share
    the same author-spec-seed family (spec 01 §5c note). Follow-up
    batch landed 2026-07-20: criterion 3's churn max now scans
    WINDOW-UNIT rows only (window_10/window_15 excluded — host-shape
    churn is a cross-universe category mismatch; implemented, pending
    owner ratification with the threshold values; the sorted
    criterion-3 column now shows a genuine gap, 0.043 → 0.522); the
    CLOSED v2.1 battery is frozen pre-fit (registry
    `screen_battery_rows_v21`, 20 rows: generator rows redefined
    against the §9.1 WAC term, sld_swap excluded on acquisition facts,
    LOYO returned on the measured input-side X-variance); and the
    DESIGN-STAGE power check (`scripts/screen_power.py` →
    `outputs/screen_power_check.json`) reads criterion 1 as
    UNDERPOWERED at plausible effect sizes: required-at-80%-power true
    elasticities ≈ 0.32 (b1) / 0.19 (b2) at 47 clusters vs committed
    v2.0 estimates 0.099 / 0.087 — on synthetic outcomes with the
    v2.1 predictor design; the v2.1 fit itself stays unrun.
39. **Owner directive (2026-07-20): "extend the panel" — a governed
    §9.5 design change (rule-3 log), made on the power arithmetic and
    BEFORE any v2.1 fit exists (issue 38).** The design-stage power
    check read criterion 1 as underpowered at the committed effect
    sizes, so the owner directed extending the fit panel with more
    route-years. Recorded in spec 01 §9.9 (the pre-fit governance
    record): the extended year set is FROZEN on availability facts
    alone — the OCTA Legistar board record yields, with passing 2dp
    validation, exactly four new fiscal years (registry
    `screen_panel_ext_fys` = FY2017/FY2019/FY2020/FY2021/FY2022/FY2023;
    the four NEW are FY2020 full-year, FY2021, FY2022, FY2023 in
    `data/derived/route_boardings_ext.csv`, 218 route-years,
    `apc_ext_fy20_23`). FY2020 full-year SUPERSEDES the committed
    9-month FY2020-Q3; FY2013–16 (no route-level table in the older
    format), FY2018 (raster-strip tables, no text layer) and FY2024+
    (successor bimonthly deck has no route-level statistics) did NOT
    land, so no year set is tuned to fit results. Vintages are
    matched per §9.9.2 (FY2021 → LODES 2021 / ACS 2017-21, the first
    5-yr vintage on 2020 tracts so no bridge — `lodes_od_2021`,
    `acs_2021_5yr`; FY2022-23 → LODES 2022 / ACS 2019-23 with FY2023
    frozen on 2022 by the stated decision, `lodes_2022`). The
    CONTAMINATION GUARD holds: the new boardings are outcome data,
    barred from any predictor matrix until phase 2b — the power check
    reads them through a guarded loader for the route-year PRESENCE
    mask and the validated b3 RVH ONLY (values dropped inside the
    loader; test `G1/G2e`), and keeps using ONLY the committed v2.0
    variance decomposition. The power check re-ran on the extended
    design (`outputs/screen_power_check.json` `panel_ext` block, schema
    01-P2): current-shape clusters 41→50, with-replicas 47→63, rows
    130→333, same grid/S/B/seed knobs, six vintage-matched years vs
    three. Required-at-80% elasticities drop about a third (with-
    replicas: b1 0.321→0.219, b2 0.187→0.126, joint 0.333→0.224;
    current-shape: b1 0.308→0.240, b2 0.188→0.150) — the extra
    route-years add clusters, rows and within-route covariate spread.
    The verdict MOVES from UNDERPOWERED to **MARGINAL**: the required
    true elasticities now sit within 2 cluster-SEs of the committed
    v2.0 estimates (b1 est 0.099 / est+2se 0.312 vs required 0.219;
    b2 est 0.087 / est+2se 0.302 vs required 0.126) but still ABOVE the
    point estimates, so not adequately powered. The baseline 3-year
    blocks regenerate bit-identically (BEFORE numbers unchanged;
    committed-run `underpowered`). The v2.1 fit itself still stays
    unrun — this remains a design-stage read on synthetic outcomes.
40. **Owner review (2026-07-20 tripwire ratification batch): a
    pre-registered REGIME-SPLIT gate for the phase-2b v2.1 demand block —
    one governed gate (rule-3 log), written before the fit exists,
    reusing the exact criterion-1 statistic (no new threshold).** In
    phase 2b the demand block is fit THREE ways — POOLED (all 6
    fit-panel FYs), PRE-2020-ONLY (FY2017+FY2019), and a full-panel fit
    with a post2020 × {l_flows, l_zveh_hh} interaction — and the artifact
    reports the pre-2020 b1/b2 bootstrap sign-fractions and the
    interaction coefficients alongside pooled. BINDING DOWNGRADE RULE
    (registry `screen_regime_split`, spec 01 §9.10): if the pooled demand
    block PASSES tripwire criterion 1 but the pre-2020-only block does
    NOT independently pass it (the same `screen_pos_frac_min` = 0.841 bar
    applied to each demand coefficient), the pooled pass is DOWNGRADED to
    reported-only — `ordinal_ok` forced false, `decision_format` =
    threshold_shortlist, a `regime_split_downgrade` flag set. Rationale:
    year FE absorb LEVEL shifts, not SLOPE changes, and LODES 2021
    measures remote-work-era workplace geography, so a pooled pass
    uncorroborated by the pre-period cannot be distinguished from a
    pooling artifact. It is ONE pre-registered gate reusing the exact
    criterion-1 statistic — no new threshold beyond 0.841. Runs in phase
    2b; the current v2.0 artifact does not consume it. (Registry entry
    carried at constant tier in the structural-governance role — the
    `screen_battery_rows` precedent: a rowless structural-tier entry
    fails the check-5 enumerated-alternative rule, and the gate produces
    phase-2b fit_diagnostics reports, not swept battery rows.)
41. **Owner adjudication (2026-07-20) of the v2.1 fit-side UNIVERSE
    (spec 01 §9.3 / §9.9) — three governed changes to
    universe-determining keys, recorded as measured/availability facts
    before the phase-2b fit (rule-3 log).** (a) ROUTE-ID CASE
    NORMALIZATION: the fit-side APC↔GTFS join case-normalizes route ids
    (APC 53X/57X/64X match the archived GTFS 53x/57x/64x) — a
    post-acquisition change to a universe-determining key, disclosed; it
    adds the three Express routes to the recoverable set on FY2019
    shapes. (b) FY2017 EXPRESS DROP: 53X/57X/64X HAVE FY2017 boardings
    (228,478 / 1,145,261 / 615,387) but the FY2017 archived feed has NO
    Express shape (they are not separate GTFS routes until FY2019), so
    per the §9.3 vintage-consistency rule those 3 FY2017 Express
    route-years are DROPPED (never matched to a FY2019 shape); the routes
    still contribute FY2019+ rows. (c) SHAPELESS-ROUTE RULE
    (pre-registered general rule): a route-year whose route has NO
    contemporaneous shape in that fiscal year's archived feed is DROPPED
    — a catchment is uncomputable without a shape, and carrying it on a
    wrong-year shape is REJECTED as reintroducing the vintage mismatch
    the rebuild exists to remove. Measured on the current extended panel,
    the shapeless feed routes are overwhelmingly branch variants
    (150A/29A/42A/47A/79A) and suspended Express (53x/57x/64x) carrying
    NO boardings; the only boardings-carrying route-year affected is
    529/FY2022 (86,674 boardings) — route 529 is ABSENT from the fy2022
    archived feed entirely (no contemporaneous shape by absence; it has
    resolved shapes in the fy2020 and fy2023 feeds), so only its fy2022
    row drops → 1 route-year. Total contemporaneous-shape drops from the
    extended panel = 3 (FY2017 Express) + 1 = 4 route-years. CORRECTION
    (governance rule 3, 2026-07-21): an earlier draft also dropped
    553/FY2023 (266,142 boardings) and reported a total of 5; that was a
    miscount — route 553 IS present in the fy2023 archived feed
    (route_ids 553_merged_10882877/78, 74 weekday MTUWTF trips each,
    shapes 5535–5538 all resolved), so under the pre-registered
    shapeless rule it must be KEPT. Corrected total is 4, not 5. These
    are availability/measured facts recorded now, not fitted quantities;
    the phase-2b fit stays unrun.
42. **Phase 2b LANDED (2026-07-21): the pre-registered v2.1 rebuilt fit ran
    ONCE and the screen still FAILS the decision tripwire — OC data does not
    support a decision-grade ordinal corridor screen (`outputs/
    screen_results_v21.json`, `scripts/screen_fit_v21.py` +
    `scripts/screen_scan_v21.py`).** Fit universe: 300 route-years / 63
    route clusters (the six discontinued routes re-entered on their
    contemporaneous archived shapes, §9.4); dropped exactly the pre-registered
    4 shapeless route-years (53X/57X/64X FY2017, 529/FY2022) plus 4 no-RVH
    cells (35/70/150 FY2017 KNOWN_BAD_RVH, 560/FY2022 KNOWN_DUP_RVH_EXT).
    Headline coefficients (cluster-robust SE): b1_flows +0.121 (0.151),
    b2_zveh +0.142 (0.119), b3_rvh +1.340 (0.060), b4_genjobs **−0.094**
    (0.114), b5_len −0.340 (0.137). **VERDICT `ordinal_ok = FALSE`,
    `decision_format = threshold_shortlist`.** All three criteria fail:
    criterion 1 (b1 bootstrap pos_frac 0.766 < 0.841; b2 0.879 ≥ 0.841 but
    both required); criterion 2 (battery min Spearman rho −0.486 at
    `offset_variant`, far below 0.7); criterion 3 DUAL (window-unit tie-churn
    0.941 at `offset_variant` > 0.20; host-shape 0.750 at `window_10` > 2/14).
    Stable core is EMPTY (0/34 tie windows survive the whole battery), so per
    §4b the honest stage-1 output is narrower than even the 34-window
    threshold shortlist: no window survives every battery row. REGIME SPLIT
    (§9.10): the **pre-2020 period PASSES criterion 1** (b1 pos_frac 0.958,
    b2 0.932 on fy2017+fy2019) while the pooled 6-FY panel FAILS, and the direct slope-shift test is NULL: i_flows_post = -0.005 (SE 0.144), statistically indistinguishable from zero (i_zveh_post -0.109, SE 0.145, also insignificant). So this is NOT the regime slope-shift 9.10 was written to catch. (CORRECTION 2026-07-21, rule-3 log: an earlier draft of this entry and the c0d1f97 commit message mislabeled the -0.005 interaction as confirming a remote-work pooling artifact; the interaction IS the direct test of that hypothesis and it came back null -- a narrative-vs-artifact divergence caught in external review.) With no detectable slope difference, the 0.958->0.766 drop is ATTENUATION, not regime instability: the post-2020 rows carry noisier X (shapeless/COVID-era archived feeds, remote-work-era LODES 2021 workplace geography) and higher residual variance (v2.1 sig2_resid 0.017 vs pre-COVID 0.003), and measurement error in X pulls b1 toward zero without shifting the conditional-mean slope -- exactly the signature the interaction test shows. regime_split_downgrade is correctly FALSE because the pooled block fails criterion 1 directly (nothing to downgrade).
    **b4_wrong_sign obligation (§9.1, this entry is the required
    governance-rule-3 log):** the measured `l_genjobs` coefficient came back
    NEGATIVE (−0.094), so the pre-registered `b4_wrong_sign` flag is SET in
    the artifact's `fit_diagnostics`. It does NOT trip the demand-block
    criterion (b4 is outside the {b1, b2} block by construction) but it is a
    specification signal that b3 (allocation control, +1.34) and/or b5 (scale,
    −0.34) are absorbing generator-attraction effects; the measured WAC
    generator-jobs magnitude did not resolve into a positive attraction term
    on this panel. **BINDING CONSTRAINT (the arc's most informative result):** the rebuild fixed every v2.0 input defect -- vintage-matched X, block catchments, contemporaneous archived shapes, six recovered routes, panel tripled to 300 route-years / 63 clusters -- and b1 moved only 0.099 -> 0.121. Data quality was never the binding constraint. It is the endogeneity confessed in spec 01 §1: b3 (RVH) sits at t=22.5 while b1 sits at t=0.80; boardings are set by service allocation, service is allocated on the same fundamentals the demand block measures, and once RVH is conditioned on the fundamentals have almost nothing left to explain. **SCOPE (corrected 2026-07-21):** this verdict is for ONE estimand -- boardings LEVEL with an RVH control -- on OC-ONLY clusters; it is NOT the broader claim "OC data cannot support a screen." A productivity estimand (boardings per RVH, dropping b3, which removes the near-tautology and the b1/b3 collinearity in one step) and/or a wider regional cluster base (LA Metro, Long Beach, Foothill, OmniTrans, RTA, Big Blue Bus via NTD + archived GTFS + LODES + ACS, several hundred clusters with agency FE) are UNTESTED and are the spec §9.5 GOVERNED-METHOD-CHANGE path for a v2.2 -- a documented, owner-approved new pre-registration, never a same-spec re-run. BOOTSTRAP NOTE: the §3.4 within-replicate ACS-MOE
    perturbation is NOT applied in v2.1 — the committed §9.2 block-
    apportionment input machinery (`screen_common_v21`, frozen phase-2a under
    its no-fit hold) carries no ACS MOE, and the design-stage power check
    pre-registered the omission as a stated stylization; it removes one noise
    source, so criterion 1 is marginally MORE lenient (an availability fact,
    not a tuning choice, recorded in the artifact `bootstrap` block). The once-
    only fit discipline held: no predictor, threshold, or spec choice was
    changed in response to the coefficients. Registry: the `screen_v21`
    swap-row claims (`popden_swap`/`e002_swap`/`gen_dummy_swap`) and the nine
    §9 fit-side data entries flipped from `spec-pending:01§9` to landed
    `covered-elsewhere` dispositions; `check_assumptions.py` gained a scoped
    `screen_v21` artifact scan (the 01§9 pending warnings cleared, 16 → 4; no
    new priors, fingerprint `f0bb42f69644` unchanged).
43. **v2.2 GOVERNED-METHOD-CHANGE PRE-REGISTERED (2026-07-21): a
    PRODUCTIVITY estimand, OC-only, written BEFORE any v2.2 fit (spec 01
    §10; rule-3 log).** Owner directive (verbatim): the v2.1 failure is
    the §1 ENDOGENEITY, not data quality — b3 (RVH) sits at t=22.5 while
    b1 sits at t=0.80, because service is allocated on the same
    fundamentals the demand block measures, so conditioning on RVH leaves
    the fundamentals nothing to explain — so pre-register a v2.2 governed-
    method-change (spec §9.5) with a productivity estimand, OC-only (NOT a
    cluster-base expansion, which is a separate future decision). §9.5
    basis: v2.1 ran ONCE and FAILED its pre-registration (issue 42), which
    under the softened §9.5 authorizes a documented owner-approved change
    of METHOD — not a barred same-spec re-run. FROZEN decisions (D1–D9):
    **D1** the DV is `log(boardings/RVH)` = productivity; by the identity
    `log(b/RVH)=log(b)−log(RVH)` this IS the v2.1 level regression with the
    RVH coefficient PINNED at +1 and moved to the LHS — removing the b1/b3
    collinearity and the tautology in one step (b3 no longer competes for
    the fundamentals' variance). **D2** RHS = b1 log1p(flows), b2
    log1p(zero-veh HH), b4 log1p(WAC genjobs CNS15-18), b5 log(length) +
    year FE; b3 GONE from the RHS; NO agency FE (OC-only, 63 clusters). The
    length loading is now b5 alone (was b3+b5), so the length artifact is
    EXPECTED to shrink — but that is left for the fit to show, not
    pre-judged (b5 and the length rows are KEPT). **D3** criterion 1
    unchanged (demand block {b1,b2}, each pos_frac ≥ 0.841); b4 sign a
    diagnostic (`b4_wrong_sign` carries over). **D4** thresholds carried
    over UNCHANGED (0.841 / 0.7 / 0.20 / 2⁄14) via the SAME registry ids —
    a method change never moves the decision bar; reusing the frozen bar is
    the anti-tuning guarantee; NO new threshold entry. **D5**
    `screen_battery_rows_v22` = `screen_battery_rows_v21` MINUS {`drop_rh`,
    `svc_p25`, `svc_p75`} = **17 rows** (the three are undefined under
    productivity: RVH is the DV denominator, not an RHS predictor to drop,
    and standardized-RVH service scoring is retired); `nb_estimator` is
    KEPT with its productivity form flagged — an NB2 rate model with
    log(RVH) as a fixed OFFSET (exposure), not ill-defined. **D6** the scan
    predicts productivity per window directly (no svc_std input); the index
    is predicted productivity relative to the median fitted route's
    predicted productivity; `screen_svc_std` machinery retired for v2.2
    (scan CODE is the phase-2b-v22 batch, not this one). **D7** the §9.10
    regime-split gate applies to the productivity fit unchanged. **D8**
    reuse unchanged: vintage map (§9.3/§9.9.2), the SAME 300-route-year /
    63-cluster panel with the 4 contemporaneous-shape drops + the
    KNOWN_BAD/DUP_RVH no-RVH drops, archived-shape catchments,
    route_short_name join. RVH is still REQUIRED — now for the DV — so
    input-side accounting (permitted §9.9.5 use: presence + RVH
    passthrough, no predictor join, no fit) CONFIRMS the DV is
    well-defined: all 304 fittable route-years have RVH>0 and boardings>0
    (min RVH 981.0, min boardings 7,691), and the 300 kept route-years / 63
    clusters are every one RVH>0 and boardings>0. **D9** same tripwire; if
    v2.2 fails, the threshold shortlist remains the output and the §9.5
    path stays open for further governed changes (e.g. a regional cluster
    base) — NO permanence hardening. Registry: `screen_estimand_v22`
    (`log(boardings/RVH)`, structural-governance role at constant tier per
    the `screen_battery_rows` precedent, avoiding the check-5 trap) and
    `screen_battery_rows_v22` (the 17-row list) added, both
    `spec-pending:01§10` until the v2.2 fit consumes them; append-only
    supersession-for-productivity notes on `screen_battery_rows_v21` and
    `screen_svc_std` (both stay VALID for the v2.1/v2.0 LEVEL artifacts). NO
    fit ran; NO coefficient computed or peeked; v2.1
    (`screen_results_v21.json`, sha `83aeb032`) and v2.0
    (`screen_results.json`, sha `b88f9b65`) stay byte-identical; PRIORS and
    the prior-order fingerprint untouched.

44. **v2.2 PRODUCTIVITY fit LANDED (2026-07-21): `ordinal_ok = FALSE` — the
    endogeneity fix WORKED but the length artifact did not (spec 01 §10;
    rule-3 log).** The phase-2b-v22 fit ran EXACTLY ONCE under the frozen §10
    pre-registration (`scripts/screen_fit_v22.py` + `scripts/screen_scan_v22.py`;
    DV = `log(boardings/RVH)`, b3 pinned at +1 and moved to the LHS, no svc_std
    input). Artifact `outputs/screen_results_v22.json` (run_id `00770f64`, sha
    `3b1d5526`, dual fresh-process byte-identical); NEW file — v2.0 (`b88f9b65`)
    and v2.1 (`83aeb032`) untouched. Universe UNCHANGED from v2.1: 300
    route-years / 63 clusters, the same 4 contemporaneous-shape drops
    (53X/57X/64X fy2017 + 529/fy2022) and 4 no-RVH drops (35/70/150 fy2017 +
    560/fy2022); every kept row RVH>0. **The productivity move did what the
    owner directed it to do: it RESCUED CRITERION 1.** The demand block now
    predicts productivity — `b1_flows` +0.256 (t 1.49, bootstrap pos_frac
    **0.9075**), `b2_zveh` +0.383 (t 2.97, pos_frac **0.9965**), both ≥ 0.841,
    PASS — where the v2.1 LEVEL fit failed (0.8115 / 0.7435). Removing the RVH
    tautology (b3 was +1.340 at t 22.5, absorbing the fundamentals' variance)
    let the fundamentals load onto productivity. **But `ordinal_ok` is still
    FALSE, and the binding reason is the LENGTH ARTIFACT, not the demand
    block.** Criterion 2 FAILS: battery min Spearman rho **0.2072** at
    `offset_variant` (vs 0.7). The §10 D2 "length artifact expected to shrink"
    hypothesis is PARTIALLY borne out but NOT enough: the offset_variant rho
    rose from **−0.486** in the v2.1 LEVEL fit (where the length loading was
    split b3+b5 = +1.340 − 0.340 = +1.00 and the ranking essentially INVERTED
    under the length pin) to **+0.207** here (b3 gone; the length loading is b5
    alone, which came back **−0.229**) — a material ~0.69 improvement, so
    pinning b5 to +1 no longer flips the ranking. But +0.207 is still far below
    the 0.7 floor, so the ranking remains length-sensitive enough to FAIL
    criterion 2, and offset_variant is still the binding worst row (reported,
    not forced — the fit answered the pre-registered question). Criterion 3
    FAILS both sub-thresholds: window-unit
    tie-churn **1.4444** at `offset_variant` (vs 0.20), host-shape **0.4000** at
    `window_10` (vs 2⁄14). The §9.10/D7 regime-split gate does NOT downgrade
    (pre-2020-only pos_frac 0.8635 / 0.9985 both pass; interaction i_flows_post
    +0.040 / i_zveh_post −0.103). Decision output: `threshold_shortlist`, 18
    `tie_with_cutoff` windows, **stable core EMPTY (0/18)** — no window survives
    the whole 17-row battery, so per §4b the honest stage-1 output is narrower
    than the shortlist and names no stable core. **`b4_wrong_sign` obligation
    (§9.1/§10 D3, this entry is the required rule-3 log):** the measured
    `l_genjobs` (b4) is again NEGATIVE (**−0.041**, t −0.29) under productivity,
    so the pre-registered `b4_wrong_sign` flag is SET in
    `screen_results_v22.json` `fit_diagnostics.b4_wrong_sign` /
    `decision_output.b4_wrong_sign` — a diagnostic (b4 is OUTSIDE the demand
    block, so it does NOT affect criterion 1), a signal that b5 (scale) may be
    absorbing attraction effects. Registry: `screen_estimand_v22` and
    `screen_battery_rows_v22` dispositions flipped `spec-pending:01§10 ->
    definitional` (the fit consumed them via `val()`), clearing the 2 check-1
    warnings; PRIORS and the prior-order fingerprint (`f0bb42f69644`) untouched.
    **Consequence for stage 1:** three estimands have now failed the tripwire on
    OC-only data; the §9.5 governed path stays open (e.g. a wider regional
    cluster base with agency FE), a SEPARATE future pre-registration, never a
    same-§10-spec re-run. The v2.2 index remains diagnostic-only;
    `config/candidates.json` stays `hand_supplied: true`.

45. **v2.3 REGIONAL-CLUSTER-BASE GOVERNED-METHOD-CHANGE PRE-REGISTERED
    (2026-07-21): a wider cluster base — OC + regional SoCal agencies with
    agency FE — written BEFORE any v2.3 fit (spec 01 §11; rule-3 log).** Owner
    directive: v2.2 (productivity, OC-only) PASSED criterion 1 — the endogeneity
    was the binding constraint on the demand SIGNAL and the productivity move
    fixed it (b1_flows pos_frac 0.9075, b2_zveh 0.9965 vs 0.841) — but FAILED
    criteria 2/3: the ranking is still LENGTH-DRIVEN and unstable
    (offset_variant rho +0.207 vs 0.7, stable core empty). The remaining binding
    constraint is RANKING STABILITY; OC's 63 clusters do not pin the
    length/fundamentals relationship stably, so fit on a wider regional cluster
    base of SoCal agencies with agency FE and score the OC windows from the
    regional fit (the recon-confirmed availability set is ~125 route-clusters,
    ~2x OC-only — NOT the several hundred originally hoped; see the
    ACQUISITION-RECON RESULT below). §9.5 basis: v2.2 ran ONCE and FAILED its §10
    pre-registration (issue 44), which under the softened §9.5 (and §10 D9,
    which explicitly reserved a wider regional base as a separate future
    pre-registration) authorizes a documented owner-approved change of METHOD —
    not a barred same-spec re-run. FROZEN decisions (D1–D8): **D1** KEEP the
    productivity DV `log(boardings/RVH)` from v2.2 (REUSE `screen_estimand_v22`,
    no new estimand entry — it is the method that rescued criterion 1;
    reverting to the LEVEL would re-inject the RVH tautology). **D2** the fit
    PANEL is OC (OCTA) + regional agencies — pre-recon candidate set {LA Metro,
    Long Beach Transit, Foothill Transit, OmniTrans, Riverside Transit Agency,
    Big Blue Bus} + OCTA — FROZEN ON ACQUISITION-AVAILABILITY FACTS ALONE (which
    agencies publish public route-level boardings AND RVH joinable to a GTFS
    shape), NEVER on fit results, exactly as v2.1's fit-panel YEAR set was
    frozen on availability (§9.9.1). **ACQUISITION-RECON RESULT (2026-07-21,
    this workflow; independent review APPROVE-WITH-FIXES).** Binding
    availability fact: only agencies publishing the RCTC/TransTrack SRTP "Route
    Statistics Table 3" format expose route-level boardings AND RVH together.
    Applying the freeze rule, `config/regional_agencies.json` is now the FROZEN
    list (no longer a PENDING stub): CONFIRMED-USABLE = OCTA (63) + Riverside
    Transit Agency (~36, mdb-98) + SunLine (~14) + Corona Cruiser (~3) + Pass
    Transit/Banning+Beaumont (~5) + PVVTA/Blythe (~4) = **~125 route-clusters**
    (~2x OC-only). EXCLUDED, route-level boardings+RVH NOT both public (major
    finding 1: the earlier "NTD route-level" attribution was WRONG — NTD is
    AGENCY-level): LA Metro (no line-level RVH — LACMTA README known gap),
    OmniTrans (route boardings missing), Long Beach Transit / Foothill Transit /
    Big Blue Bus (agency-level-only) — each kept as a records-request upgrade
    path, NOT fitted. VALIDITY CAVEAT (honest, pre-fit, changes no frozen
    decision): every confirmed regional agency is Riverside County (FIPS 06065),
    exurban/desert, distinct from dense coastal/suburban OC; agency FE absorbs
    LEVEL not SLOPE differences, so pooling is a heterogeneous-slopes risk
    analogous to the v2.1 regime problem — a RISK TO TEST via `loao` + the §9.10
    regime split, not an assumption. **D3** RHS = b1
    log1p(flows), b2 log1p(zero-veh HH), b4 log1p(WAC genjobs CNS15-18), b5
    log(length) + year FE + AGENCY FE (base OCTA; the one structural addition —
    slopes identified from within-agency variation); b3 stays GONE (DV
    denominator). Thresholds carried over UNCHANGED (0.841 / 0.7 / 0.20 / 2⁄14)
    via the SAME registry ids — a method change never moves the decision bar; NO
    new threshold entry. **D4** fit REGIONALLY (all agencies, one pooled
    productivity regression), score the OC scan windows (OCTA's agency FE used
    for OC windows); productivity index per §10 D6 (predict productivity
    directly, no svc_std). **D5** criterion 1 unchanged (demand block {b1,b2},
    each pos_frac ≥ 0.841); b4 sign a diagnostic (`b4_wrong_sign` carries,
    negative in both v2.1 −0.094 and v2.2 −0.041). **D6**
    `screen_battery_rows_v23` = `screen_battery_rows_v22` (17 rows) PLUS `loao`
    (leave-one-AGENCY-out, the regional analogue of `loyo`: min Spearman rho over
    each non-OCTA-agency-dropped refit vs the v2.3 headline OC-window ranking;
    OCTA never dropped; window-unit, feeds criteria 2 and 3 as `loyo` does) =
    **18 rows**; `gen_dummy_swap` flagged (its hand-coded OC-only special-
    generator dummy is identically zero on non-OCTA routes — stated coverage
    property, the measured WAC b4 is the regional generator signal); criterion-2
    min-rho / criterion-3 dual tie-churn UNCHANGED. **D7** the §9.10 regime-split
    gate applies to the regional productivity fit unchanged. **D8**
    PRE-COMMITTED verdict: the KEY hypothesis is whether the wider cluster base
    rescues criteria 2/3 (ranking stability) the way productivity rescued
    criterion 1 — NOT pre-judged; if v2.3 still fails, the threshold shortlist
    stays the output AND the pre-registered interpretation is that OC corridor
    RANKING is not achievable even with regional identification, so the
    shortlist stays the PERMANENT stage-1 output (`config/candidates.json`
    stays `hand_supplied: true`) — a documented outcome, NOT a permanence
    HARDENING (the §9.5 path stays open). Registry: `screen_battery_rows_v23`
    (18-row list) and `screen_regional_agencies` (config-tier, FROZEN by the
    recon to the ~125-cluster confirmed-usable panel; `config/regional_agencies.json`
    is the frozen list, no longer a stub) added, both `spec-pending:01§11` until
    the v2.3 fit consumes them; append-only
    reuse note on `screen_estimand_v22`. NO fit ran; NO regional coefficient
    computed or peeked; v2.2 (`3b1d5526`), v2.1 (`83aeb032`), v2.0 (`b88f9b65`)
    stay byte-identical; PRIORS and the prior-order fingerprint (`f0bb42f69644`)
    untouched.

46. **v2.4 GOVERNANCE PRE-COMMITMENTS (owner-ratified 2026-07-22): the
    failure-mode gate, a numeric stopping rule, the external-validity check, and
    delegation-with-two-guards — written BEFORE the v2.4 fit (spec 01 §5/§9.5/§12;
    docs/review-verification.md; rule-3 log).** PRE-COMMITMENT governance
    writing, NOT a measurement: it adds the STRUCTURE the v2.4 thresholds attach
    to, changing no frozen threshold VALUE, estimand, or committed battery id
    list. **(1) FAILURE-MODE GATE** (spec 01 §5 + registry
    `screen_gate_failure_modes`): criteria 2/3 are re-scoped to attach BY FAILURE
    MODE, not by row id, because row ids cannot stay constant across the
    window→anchor geometry change (`offset_variant`/`window_10`/`window_15` are
    meaningless in the v2.4 ANCHOR world; `min_sep` is meaningless in the WINDOW
    world; only `buffer` survives both). Three modes — catchment-width (buffer,
    both worlds), spatial-resolution (window length in window-world /
    anchor min-separation in IDENTITY units in anchor-world), specification (a
    swap or estimator variant) — each instantiated per version (v2.0
    buffer/window_len/estimator-or-swap; v2.1/v2.2 buffer/window_len/swap;
    v2.4-anchor buffer/min_sep-identity/swap). Criterion 2 = min rho over the
    three failure-mode rows; criterion 3 = max churn over them (dual-unit). The
    other battery rows become DISCLOSED DIAGNOSTICS outside the gate. Threshold
    VALUES unchanged (0.7 / 0.20 / 2⁄14); only their SUPPORT is re-scoped.
    REGISTRY NOTE (stated, not hidden): a min over three rows is noisier than
    over twenty, so the bar is EASIER in expectation — the CORRECT direction for
    this problem (the whole-battery min was dominated by universe-change and
    decision-orthogonal rows). The re-scoping is FORWARD-LOOKING (binds v2.4);
    the v2.0/v2.1/v2.2 verdicts were computed over the full battery and their
    artifacts stay byte-identical, so the per-version map is DOCUMENTARY for
    them. **(2) STOPPING RULE WITH A NUMERIC FLOOR** (spec 01 §9.5): the softened
    §9.5 always resolved to "keep going"; a terminus is added. v2.4 (the
    benefit-per-cost BCA-queue build) is the LAST stage-1 method attempt — branch
    (a) DECISION-GRADE iff failure-mode Spearman rho ≥ 0.7 [`screen_battery_rho_min`,
    NOT the 0.79/0.87 anchor-world previews] AND the item-9 check PASSES → ship
    the queue, gate 1 consumes it; branch (b) DOCUMENTED NULL (OC demand does not
    separate corridors) → ship that finding. Either way stage 1 STOPS. CLOSED
    v2.5 list (nothing else re-opens the arc): (i) new route-level RVH from a
    records request, (ii) a new agency panel clearing §11 D2, (iii) a materially
    different data source; internal refinement of an existing source does NOT
    count. A stopping rule written NOW is legitimate; one written after the next
    result is not. **(3) EXTERNAL-VALIDITY CHECK** (spec 01 §12.1): CONCEDES that
    the earlier "Harbor top ~10" bar was anchored to a preview rank already seen
    (the e016 error). Redefined — N = 8 FROM CONSUMPTION (gate-1 consumes top 5-8
    + ties, spec 00 §3), NON-TRANSFER note (preview used raw catchment, v2.4 uses
    benefit-per-cost), benchmark set honestly scoped (Bravo/Harbor + Bravo
    Westminster/17th are CLEAN arterial-ALM benchmarks; OC Streetcar is a
    CONFOUNDED rail case), pre-stated MISS SEMANTICS (a demand-strong OCTA-chosen
    ARTERIAL outside top-8 counts against the screen; an OC-Streetcar miss is a
    mode/length confound; a grant/political demand-weak low rank is a benchmark
    confound), n=3 (really 2 clean) so one clean miss is weak evidence, and a
    NAIVE POPULATION BASELINE as the discrimination control — the check PASSES
    only if the screen places the arterial benchmarks in top-8 AND with
    discrimination the population count lacks (if both pass, reported honestly as
    "consistent with a population count"). **(4) DELEGATION WITH TWO GUARDS**
    (docs/review-verification.md + `outputs/DELEGATED_CHANGES.md`): the controller
    may proceed WITHOUT owner ratification on metric-definition corrections,
    universe-invariance/identity fixes, and housekeeping, with logged
    notification — GUARD 1 (escalation tripwire: any change that moves a published
    number or flips a pass/fail returns for owner ratification with both versions),
    GUARD 2 (accumulating diff `outputs/DELEGATED_CHANGES.md`, folded into the next
    pre-registration; seeded with rule 6, rule 7, the min_sep identity correction,
    the screen-fork consolidation, the canonical pointer). Values that bind an
    UNRUN fit (thresholds, estimand, failure-mode subset, cost-model params,
    ranking measure) still require owner ratification. NO fit ran; the three
    frozen artifacts stay byte-identical (`b88f9b65` / `83aeb032` / `3b1d5526`);
    PRIORS and the prior-order fingerprint (`f0bb42f69644`) untouched.

47. **STAGE-2 SCOPING under the v2.4 stopping rule (owner-ratified 2026-07-22,
    option (ii); spec 01 §12.2, spec 07 §4.3, spec 00 §3; rule-3 log).** Closing
    the screen→candidates loop means a v2.4-promoted candidate set would STRAND
    spec 07's verdict and stage 2's welfare BCA, both computed on the
    HAND-SUPPLIED harbor/streetcar universe. Adopted resolution (the one
    consistent with issue 46's stopping rule — v2.4 = last STAGE-1 attempt, not a
    stage-2/3 re-trigger): the "no OC ALM corridor clears BCR=1" verdict is
    PERMANENTLY scoped to the corridors ACTUALLY EVALUATED; the v2.4
    benefit-per-cost queue is FORWARD-LOOKING input for FUTURE stage-2 work — NOT
    a trigger to re-run stage 2/3 and NOT auto-promoted into
    `config/candidates.json` for the current verdict. DISALLOWED STATE, stated
    explicitly: shipping a new candidate set (`hand_supplied: false`) alongside
    verdicts computed from the old hand-supplied one is incoherent and must never
    be committed — a promotion lands only in a batch that also re-runs the
    stage-2/3 verdicts that consume it. Docs only; no artifact regenerated; the
    three frozen screen artifacts and `network_sequence.json` untouched.
