# Spec 02 — Stage 2: Incremental Pivot Logit (finalist comparison)

Status: BUILT (this repo), spec covers current state + planned upgrades ·
2026-07-08 · Method detail: README.md; internals: scripts/model.py docstring.

## 1. Role and non-role

Compares finalist corridors x service designs (speed, headway by period,
stop spacing, fold-vs-retain) with honest uncertainty, and picks what
goes to stage 3. It forecasts the response of the *existing* travel
market only; market creation (induced demand, land use, network
redesign beyond the corridor local) is out of scope by construction and
must not be silently imputed to it.

## 2. Current state (v. commit b99204a)

- Pivot: S1 = S0*e^dV/(S0*e^dV+1-S0) per market x distance bin x
  car-ownership segment x sub-rider; forecast = anchor x base-share-
  weighted ratio; N=40,000 draws, seconds per run.
- Markets: walk (LODES both-ends incl. 0-0.5-mi intra-tract bin),
  transfer (pinned tau 25-40%), visitor (pinned phi 5-15%); non-work via
  ws/kappa (+ shorter-trip tilt sensitivity).
- Service utilities: IVT from speed; arrival-strategy wait
  min(h/2, w0+lam*h); rider-position walk quadrature (K=8, no variety
  bonus); {peak, offpeak} headways blended by pkshare; ASC (new line).
- Anchor: MEASURED 7,650-9,650 (`scripts/anchor_from_apc.py`).
- Calibration: ABC vs the 543 launch (launch-equivalent kernel mu=5,938
  sigma=500, NTD back-trend 1.28678 — §4.6, landed 2026-07-11; matured
  mu=4,200 kept as a row); headline = uncapped | backtest-calibrated
  side by side.
- Current Harbor answer: uncapped 11,969 (9,956-13,998); calibrated
  11,833 (10,377-13,395); ASC posterior 0.14/0.19/0.24 (matured row:
  0.06/0.11/0.16). Average speed is now DERIVED (§4.9, landed 2026-07-11):
  the central move is within noise, the bands widened slightly, and the
  stop-spacing sensitivity rows shrank toward physical honesty.

## 3. Inputs / outputs

In: `config/<corridor>.json` (anchor + derivation note, base services,
proposed service, visitor block) + `data/derived/corridor_<name>.json`
(from `build_corridor.py`). Out: `outputs/results_<name>.json` (summary
percentiles, ~40-row sensitivity table, design sweep),
`outputs/abc_<name>.json`, charts.

## 4. Planned upgrades (approved direction, this spec authorizes)

**4.1 Multi-corridor operation.** One config per finalist; anchor
derivation per corridor from the measured route series x corridor share
(pattern: `route43_share.py`). Beach recoverable from commit e2d518e.

**4.2 Common-random-number ranking.** All finalists run with the same
`draw_params(N, seed)` draws so MC noise cancels from comparisons.
Report pairwise P(A > B) alongside per-corridor bands.

**4.3 Overlap sensitivity.** For finalist pairs sharing >30% of
catchment tracts: rerun with exclusive tract assignment (each shared
tract to its nearer corridor) as a sensitivity row on both.

**4.4 Multi-experiment ABC.** Sequenced (review 2026-07-08, so the 529
does double duty honestly):
1. **Validate first:** commit the 543-calibrated model's prediction of
   the Bravo! 529 launch outcome (Feb 2019; pre = Rt 29 FY2017/FY2019,
   post = FY2020-Q3, data on disk) BEFORE comparing — this is stage 2's
   only near-term out-of-sample test (spec 00 §5).
2. **Then calibrate jointly:** fold the 529 into the kernel; optionally
   the FY2017->FY2020 service-change panel, down-weighted. Panel kernel
   sigma is ESTIMATED, not asserted: the ridership drift of routes with
   UNCHANGED service FY2017->FY2019 measures non-service variance, and
   that sets the panel sigma (replaces the earlier round-number "3x").
Joint weight = product of per-experiment kernels; structural-error floor
sigma >= 400 per experiment REGARDLESS of experiment count
(overconfidence guard). Report per-experiment residuals and joint ESS;
if ESS < 1,000 or one experiment's residual is systematically one-sided,
that is a model-saturation finding to report, not to fix with extra
parameters. (The current single-experiment residual IS one-sided —
central 6,169 vs target 4,200 — recorded as README known issue 15; the
launch-equivalent retarget in 4.6 is the first-order response.)
**Hold out the Harbor TSP speed-up**: before its post-2024 data arrives,
commit a registered prediction of the ridership response to the measured
+7-8% speed change — BOTH the corridor total AND the 43-vs-543 route
split (the split is the more falsifiable prediction)
(`outputs/registered_prediction_tsp.json`).

**4.5 Structural risk pricing (sensitivity rows, not headline changes).**
(a) Nonlinear time: damped utility bivt*t^gamma, gamma in {0.7, 0.8, 0.9}
    rows (0.7 added per review — 0.8/0.9 alone are too mild to reveal
    whether nonlinearity matters).
(b) Induced demand: optional side column "with induced demand" using a
    total-demand elasticity to the accessibility change, prior U(0.1, 0.3),
    clearly labeled, never the headline and never a gate criterion.
(c) **ASC transportability** (review 2026-07-08; README known issue 14;
    sharpened by the 2026-07-08 MODE DECISION — elevated automated light
    metro): the ABC moves essentially only the ASC, and the calibration
    experiments are BUS overlays while the forward line is a rail-class
    product — transporting the 543's premium is an assumption in the
    conservative direction, now across modes. Sensitivity band widened:
    forward ASC = calibrated ASC x premium factor, premium in
    {1.0 (current assumption), 1.5, 2.0} — the launch-equivalent central
    ~0.19 already sits at the prior midpoint (0.20); a 2.0 premium probes roughly double it.
(d) Choice-structure middle bracket: the hard max and the theta=1 logsum
    (-37%) are the two extremes; add small-theta softmax rows
    (theta in {0.1, 0.2}) — genuine idiosyncratic taste without the full
    variety bonus. Expectation: with typical inter-service utility gaps
    >= 0.3, small-theta should land within a few percent of the max —
    showing that (or failing to) is the point. Note: the existing
    walk_spread row perturbs walk distance, not choice-level taste, and
    is not a substitute.

**4.6 Calibration-target vintage.** Retarget the 543 kernel from the
matured six-year average (mu=4,200) to a launch-equivalent value:
FY2017 measured (4,615) x the 2013->2017 system back-trend (needs OCTA
FY2013 bus UPT from NTD — public data). Keep mu=4,200 as a sensitivity.
Expected direction: raises the ASC posterior and the calibrated headline,
and shrinks the one-sided residual. Until then the current target is
labeled "matured", not "launch" (README known issue 15).
(landed 2026-07-11: MU_LAUNCH=4,615×1.28678≈5,938, NTD-measured back-trend;
FY2014-ratio and matured-4,200 kept as rows — reweight_abc.py. Actuals:
calibrated blend P50 10,757→11,836, ASC posterior 0.11→0.19, ESS 8,624→15,090,
central residual +47%→+3.9%.)

**4.7 Reporting: separate the fold/retain scenarios.** The 50/50
coin-flip blend mixes an operator decision into the forecast band. Lead
with fold and retain reported separately; the blend becomes a labeled
summary line, and ONE blend convention (expected blend) is used
everywhere (currently the headline uses the coin-flip mixture and the
sensitivity table uses blend_ev — unify).

**4.8 Demand-fabric vintage row.** LODES 2022 carries post-COVID,
WFH-reshaped commute SHAPE into both the backtest (2013) and the forward
market — sharper than an "old data" caveat because the response keys on
the trip-length mix. Rebuild bins with pre-COVID LODES 2019 as a
sensitivity row; the vintage gap is also now named in the ABC sigma
rationale.

**4.9 Derived average speed (R6 — land BEFORE the 4.5 risk-pricing
batch, since it revises the stop-spacing rows those will quote).**
`speed` and `spacing` are currently independent config knobs — a
physical inconsistency: the "+21.8% at 0.5-mi spacing" row credits
shorter walks while holding 30 mph fixed, charging nothing for the
added stops. Replace exogenous speed with a TCQSM-style decomposition:

    min/mi = 60/v_cruise + (dwell + accel/decel loss)/(60 * spacing)
             [+ signal delay/mi]

*Mode decision 2026-07-08 (elevated automated light metro) splits this
in two:* the FORWARD line uses the grade-separated variant — no signal
delay, cruise prior 70-90 km/h, dwell 20-30 s (at 80 km/h / 25 s /
1.6-km spacing: ~47 km/h ≈ 29.5 mph, independently validating the
30-mph config value); the street-calibrated variant below (43/543
two-point measurement) remains for the BUS backtest/calibration
experiments, whose service definitions stay street-physical. The same
function sizes the fleet (spec 04 §3.1) and generates stage-3 build-GTFS
stop_times.

- Config: services gain a running-way package (mixed / TSP / dedicated
  -> v_cruise prior) and a dwell prior; average speed becomes DERIVED.
- Calibration from data on disk: Routes 43 (11.4 mph @ 0.25-mi) and 543
  (~12.8 mph @ 1.0-mi) share the street and signals — two equations
  identify the per-stop penalty and the effective no-stop street speed
  (~13-13.5 mph pre-TSP). GTFS stop_times provide segment-level checks;
  the 2024 TSP study's delay reduction informs the TSP package prior.
- Realism surfacing: 30 mph @ 1-mi spacing implies high-30s cruise —
  dedicated lanes + TSP; infeasible sweep cells become visible instead
  of silently priced. The design sweep's speed axis becomes a
  running-way-treatment axis.
- Exogenous-speed spec retained as a sensitivity toggle (governance).
- Expected effect: the 0.5-mi spacing row shrinks materially (walk gain
  minus newly-charged speed penalty); long-trip cells flip sign.
- Stage-3 tie-in: the SAME function generates the build-GTFS stop_times
  (station-pair trip times), satisfying spec 03's no-drift requirement.
  Full pair-level skims stay a stage-3 concern (stage 2's distance bins
  would average them away); optional cheap stage-2 refinement: weight
  bin-center IVTs by the corridor speed profile measured from Route 43
  GTFS stop_times.
- Known issue to log when landed: dwell depends on loading, so a small
  ridership->speed feedback is deliberately ignored at this stage.

(landed 2026-07-11: grade-separated variant on Harbor's service_new,
A_COMFORT=1.0 m/s^2 constant (loss_s = v_cruise_mps / A_COMFORT); central
80 km/h / 25 s / 1.0-mi -> 30.09 mph, validating the old 30-mph config value
(kept as the exogenous fallback + governance toggle exogenous_speed=1). Two
priors v_cruise (70-90 km/h) / dwell (20-30 s) appended LAST (rng append-last
discipline). Street variant calibrated IN CODE from the two measured OCTA
points 43 (11.4 mph @ 0.25-mi) / 543 (12.8 mph @ 1.0-mi): p_stop=0.192 min
(11.5 s), v_street=13.35 mph (~13-13.5 pre-TSP); reproduces both points to
float precision, prices hypothetical bus designs only (measured base services
keep their config scalars). Streetcar stays exogenous (at-grade, measured,
built line). Actuals: uncapped blend P50 11,969 unchanged (P10/P90
9,963/13,995 -> 9,956/13,998, slightly wider); calibrated P50 11,836 -> 11,833;
0.5-mi spacing row +23.6% -> +16.9%, 1.5-mi row -22.3% -> -20.2%; the
exogenous-speed row reproduces the pre-R6 headline; ABC weights/ESS/posterior
and outputs/backtest_543.json byte-identical (backtest untouched, only the
forward forecast moves) -- model.py grade_sep_min_per_mile / calibrate_street.)

### 4.9b Jerk-limited kinematics (landed 2026-07-11)

The grade-separated per-stop loss is refined from R6's trapezoid (instant
jerk) to the realistic jerk-limited S-curve. Real passenger service ramps
acceleration at a finite jerk j; each speed change of magnitude v costs a
phase time

    t_phase(v) = v/a + a/j     (a saturates: v >= a^2/j; else 2*sqrt(v/j)),

the extra a/j over the trapezoid v/a being the two jerk ramps. A jerk-limited
phase is antisymmetric about its midpoint, so it covers exactly v*t_phase/2 --
hence a full accel+decel (no cruise) covers v*t_phase, and cruise is REACHABLE
between stops iff v*t_phase(v) <= d (d = stop spacing in m). When reachable the
run is d/v + t_phase (pure-cruise time plus one full phase-time of excess:
accel and decel each waste t_phase/2). Constants A_COMFORT = 1.0 m/s^2
(unchanged) and J_COMFORT = 0.75 m/s^3 -- passenger-comfort standards band
sustained jerk at ~0.5-1.0 (EN 13452 family); 0.75 central, band edges are
rows. Optional accel/jerk keys on the derived_speed block override them (the
row mechanism; a future street-running-rail variant could use them too).

The reachability cap is the materially new realism at TIGHT spacings: when d
is too short to attain v the train peaks at v_p < v where a bare accel+decel
just fills d, v_p^2/a + v_p*a/j = d, i.e.

    v_p = ( -a^2/j + sqrt(a^4/j^2 + 4*a*d) ) / 2,

and the run is 2*t_phase(v_p). At the design point (80 km/h, a=1.0, j=0.75,
1.0-mi, 25 s dwell) cruise is reachable (523 m < 1609 m), t_phase 23.56 s,
t_run 95.98 s -> 29.76 mph (R6's trapezoid gave 30.09; the jerk correction is
~1%). At 0.25-mi (402 m) cruise is UNreachable: v_p 19.40 m/s (~70 km/h),
avg ~13.5 mph including dwell -- the sweep/spacing rows at 0.25-0.5 mi are now
physical rather than silently assuming a speed the train cannot reach.

j->inf recovers R6's trapezoid EXACTLY in its domain of validity (reachable
spacings, to float precision -- the 1.0-mi "trapezoid kinematics (R6)" row
reproduces the pre-JK central 12,055.96 to ~1e-8). Note the j->inf limit still
CAPS via v_p (with a/j->0, v_p = sqrt(a*d)) at short spacings where the raw R6
trapezoid never did -- that was the gap -- so the "trapezoid kinematics" row is
defined as j->inf WITH the reachability cap retained.

The STREET (bus) variant is EXEMPT: it is calibrated from two measured
end-to-end OCTA speeds (43/543), which already embed real-world jerk in their
two calibration points, so imposing an S-curve on top would double-count.

Actuals (uncapped blend P50 11,969 -> 11,949; central tornado 12,056 ->
12,036, the ~20-boarding/~0.17% jerk charge; bands 9,956/13,998 ->
9,938/13,971): jerk 0.5/1.0 rows -0.08%/+0.04% (well under +-1%), accel 1.3
+0.60%, trapezoid (R6) +0.17%; the 0.5-mi spacing row eases +16.9% -> +16.7%
(jerk charges the tighter grid's extra stops), 1.5-mi -20.2% -> -20.1%. ABC
weights/ESS/posterior and outputs/backtest_543.json byte-identical (backtest
uses config scalars, untouched; only service_new's derived speed moved) --
model.py s_curve_phase_time / stop_run_time / grade_sep_min_per_mile.

Known limitation (logged): the running way is still uniform -- grade profile,
curves, and civil speed restrictions are ignored (a real alignment would
impose local speed caps below cruise). One step past R6's dwell-loading
feedback note; both are stage-3 (STOPS) concerns.

## 5. Validation gates (standing; must hold after any change)

- Regression toggles reproduce prior behavior: smooth_k=0, scalar
  headways, no_bin0, fixed central point (documented values).
- Backtest central within the measured observed band for each
  calibration experiment; joint ABC ESS >= 1,000/40,000; seed-drift on
  calibrated P50 <= 2%.
- Design-sweep continuity: max adjacent-cell step <= 8%.
- `scripts/check_assumptions.py` green (spec 08 §5): schema, row coverage,
  no orphans, prior-order fingerprint, materiality, pointer resolution, and
  citation sync — 0 failures (spec-pending dispositions are counted
  warnings). This gate is where rule 2 (below) is now enforced.
- **Rule 2 (every structural knob is exposed) is enforced through the
  assumptions registry, which is the authoritative mechanization.** Each
  asserted quantity is a `scripts/assumptions.py` entry and each structural
  choice claims a one-at-a-time sensitivity row keyed by a stable id (per
  artifact); `check_assumptions.py` check 2/3 fail if a claimed row is
  missing or a present row is unclaimed, so a knob cannot be added without
  its row and its registry entry in the same commit. This bullet no longer
  restates the numeric rule — the registry's row-coverage semantics are the
  single source (e.g. the pedestrian walk speed 3.0 [walk_mph] and the
  service jerk limit 0.75 [j_comfort] are registry-owned, and their
  band-edge rows generate from the entry, not from hand-typed labels).

## 6. Runtime

Per corridor: model+ABC+charts < 10 min. 8 finalists x 2-3 designs well
inside the 1-hour stage budget.

## 7. Known limitations (accepted; priced where possible)

Frozen market composition (bounded by 4.5b); linear-in-time utility
(bounded by 4.5a); ASC/slope confounding (attacked by 4.4); tau/phi
pinned by assumption until the records request lands; one-transfer
access only; LA County flows excluded; weekday only.

## 8. Questions resolved (review 2026-07-08)

- Q1 (panel weighting): sigma estimated from the ridership drift of
  routes with UNCHANGED service (non-service variance), replacing the
  round-number 3x — folded into §4.4.
- Q2 (TSP prediction): publish both the corridor total AND the 43-vs-543
  split; the split is the more falsifiable, more diagnostic prediction.
- Q3 (gamma bracket): widened to {0.7, 0.8, 0.9} — folded into §4.5a.
