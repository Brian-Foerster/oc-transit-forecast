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
- Calibration: ABC vs the 543 launch (kernel mu=4,200 sigma=500);
  headline = uncapped | backtest-calibrated side by side.
- Current Harbor answer: uncapped 11,969 (9,963-13,995); calibrated
  10,757 (9,098-12,336); ASC posterior 0.06/0.11/0.16.

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

**4.4 Multi-experiment ABC.** Add the Bravo! 529 launch (Feb 2019;
pre = Rt 29 FY2017/FY2019, post = FY2020-Q3, data on disk) as a second
kernel; optionally the FY2017->FY2020 service-change panel as a third,
down-weighted (weight per spec 00 §5). Joint weight = product of
per-experiment kernels; structural-error floor sigma >= 400 per
experiment REGARDLESS of experiment count (overconfidence guard).
Report per-experiment residuals and joint ESS; if ESS < 1,000 or one
experiment's residual is systematically one-sided, that is a
model-saturation finding to report, not to fix with extra parameters.
**Hold out the Harbor TSP speed-up**: before its post-2024 data arrives,
commit a registered prediction of the 43/543 ridership response to the
measured +7-8% speed change (`outputs/registered_prediction_tsp.json`).

**4.5 Structural risk pricing (sensitivity rows, not headline changes).**
(a) Nonlinear time: damped utility bivt*t^gamma, gamma in {0.8, 0.9} rows.
(b) Induced demand: optional side column "with induced demand" using a
    total-demand elasticity to the accessibility change, prior U(0.1, 0.3),
    clearly labeled, never the headline (per governance).

## 5. Validation gates (standing; must hold after any change)

- Regression toggles reproduce prior behavior: smooth_k=0, scalar
  headways, no_bin0, fixed central point (documented values).
- Backtest central within the measured observed band for each
  calibration experiment; joint ABC ESS >= 1,000/40,000; seed-drift on
  calibrated P50 <= 2%.
- Design-sweep continuity: max adjacent-cell step <= 8%.
- Every new structural choice gets a sensitivity row the same commit.

## 6. Runtime

Per corridor: model+ABC+charts < 10 min. 8 finalists x 2-3 designs well
inside the 1-hour stage budget.

## 7. Known limitations (accepted; priced where possible)

Frozen market composition (bounded by 4.5b); linear-in-time utility
(bounded by 4.5a); ASC/slope confounding (attacked by 4.4); tau/phi
pinned by assumption until the records request lands; one-transfer
access only; LA County flows excluded; weekday only.

## 8. Open questions for review

- Q1: 4.4 weighting of the service-change panel — suggest each panel
  observation gets sigma 3x the launch experiments'; acceptable?
- Q2: Registered TSP prediction — publish P10/P50/P90 of boardings
  response, or also a route-split (43 vs 543) prediction?
- Q3: gamma values for the nonlinear-time rows — {0.8, 0.9} or a wider
  bracket?
