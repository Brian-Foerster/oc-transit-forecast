# Spec 01 — Stage 1: Direct-Demand Regression Screen

Status: panel-revised 2026-07-18 (3-lens adversarial panel; 9 blocking
findings adjudicated) · BUILD IN PROGRESS · §9 v2.1 rebuild
PRE-REGISTERED 2026-07-20 (before any new data fitted) · §5 tripwire
v2 per owner review 2026-07-20 (criterion 1 revised + ratified;
criteria 2/3 statistics rebuilt, values deferred pending the
shortlist-stability report)
(prototype: the 13-arterial screen, summarized in HANDOFF.md "Dropped
work"; superseded draft: 2026-07-08)

## 1. Role and non-role

Ranks every plausible corridor window in Orange County to produce the
finalist shortlist. Its numbers are ordinal screening scores with
uncertainty, never quotable ridership forecasts (spec 00 §1). The
published quantity is a normalized index (§4), never boardings.

**Endogeneity firewall (revised 2026-07-18).** Two inputs are
reclassified as *endogenous to service*, not merely "controls":

- **Revenue hours** (b3): OCTA allocates service partly on unobserved
  demand, so conditioning on it is a bad-control/collider risk that can
  bias the demand coefficients (b1, b2) that generate every ranking —
  not just b3's own interpretation. b3 stays in the model as an
  allocation control, but the protection is *mechanized*: the §5
  cross-spec battery fits with and without it (`drop_rh` row), and a
  standing test forbids any published prediction at a counterfactual
  service level.
- **ACS transit workers (B08141 E016)**: itself an outcome of
  historical service — tracts commute by transit because service
  exists. Scoring on it would mechanically penalize never-served
  arterials, the exact corridors the underservice mechanism exists to
  surface. E016 is REMOVED from the predictor set (replaced by
  zero-vehicle workers, §3.1) and retained only as a pre-registered
  swap row (`e016_swap`).

Scoring at standardized service (§3.2) is a *presentation convention*,
not an identification fix; the battery is the enforcement. The dilemma
is logged as a README known-issue entry (governance rule 3).

"What happens if we add service" belongs to stage 2 (spec 02). This
model never answers it.

## 2. Inputs

| Input | Source | Status |
|---|---|---|
| Route-level annual boardings + revenue hours, 47 routes x FY2017/FY2019/FY2020-Q3 | `data/raw/apc/*.pdf` via `scripts/extract_apc.py` → `data/derived/route_boardings.csv` (boardings + `rvh_*` columns; parse validated: boardings/RVH must reproduce the printed b/RVH column to 2 dp for every parsed row, EXCEPT the 3 forensically inconsistent FY2017 rows — routes 35/70/150, printed b/RVH irreconcilable with printed totals — whitelisted as `KNOWN_BAD_RVH` with their RVH cells blanked; those route-years drop from the fit) | on disk (S0) |
| Route shapes, headways | `data/raw/gtfs/` via `build_corridor.py` helpers (`main_shape_xy`, `route_headways`) | on disk |
| Tract centroids + land area | `data/derived/oc_tracts.csv` | on disk |
| LODES tract O-D flows | `data/derived/oc_tract_od.csv.gz` | on disk |
| ACS B08141 zero-vehicle workers (E002) + MOEs | `data/derived/oc_b08141.csv` | on disk |
| Special-generator list (~10-15 entries: resort/college/medical; name, type, lat, lon) | `config/special_generators.json` — judgment data, config-tier registry entry, append-only history per edit | to create (S2) |

Vintage exposure (registered, §5b): predictors are 2022 LODES / 2023
ACS; outcomes are FY2017-FY2020-Q3 boardings; GTFS shapes are the
2026-07 snapshot. The X-vs-y temporal mismatch is a structural
assumption of the fit (`x_vintage_mismatch`), not a footnote. Six APC
routes (24, 53X, 57X, 64X, 82, 153) were discontinued and have no 2026
shape — they cannot be fitted, the drop is survivorship-biased toward
low performers, and `screen_fit.py` prints the dropped list by name.

## 3. Method

**3.1 Fit (route level).** PRIMARY: log-OLS on log(annual boardings),
cluster-robust SEs by route (statsmodels OLS, `cov_type='cluster'`,
groups=route). At annual boardings of 1e5-1e6 the NB2 variance is
effectively alpha*mu^2 — pure multiplicative error, i.e. log-OLS
territory — and NB adds convergence fragility at n_eff≈41. NB2
(statsmodels `NegativeBinomial`, `loglike_method='nb2'`, fixed
start_params/maxiter) is a PERMANENT robustness row (`nb_estimator`):
both estimators are always fitted; the row reports Spearman rho of the
full window ranking plus top-8 set churn vs primary. There is no
silent fallback branch (structural entry `estimator_screen`).

Pool: 47 routes x {fy2017, fy2019, fy2020q3} = 132 route-years,
intersected with GTFS weekday shapes → ~41 fitted routes. Rows within
a route are pseudo-replication (cross-year log correlation ≈ 0.97;
effective n ≈ 41, not 132): ALL inference is clustered by route, and
LOO means leave-one-ROUTE-out (all its years).

    log(boardings_ry) = a + b1*log1p(LODES both-ends-in flows in catchment)
                      + b2*log1p(zero-vehicle workers in catchment)   [B08141 E002]
                      + b3*log(annual revenue hours)   [allocation control — never causal]
                      + b4*(special-generator dummy)   [geometric, §3.2]
                      + b5*log(route length mi)        [free elasticity; offset variant = sensitivity row]
                      + year fixed effects (fy2019, fy2020q3)

Zero handling (registered rule, stated in the artifact notes): b1/b2
consume catchment sums through log1p, not log — log1p(0) = 0 keeps
empty-catchment windows finite without a new floor constant, and at
catchment magnitudes (1e3-1e5) log1p is indistinguishable from log.

5 predictors + intercept + 2 year FE. b2 replaces E016 transit workers
(E016 is endogenous AND mostly noise: 39% zero tracts, median
MOE/estimate 1.26; E002 has far better signal-to-noise). b5 puts fit
and scan on a shared exposure footing — without it, coefficients
fitted on 3.3-46.9-mi whole-route catchments are incomparable with
fixed-length windows.

VIFs are a required fit diagnostic (b1/b2 are collinear catchment
aggregates). Measured collinearity is MILD — VIF max 3.8 (b1_lodes
3.81, b2_e002 3.30; artifact `fit_diagnostics.vif`) — and is NOT the
rationale for grouping. The decomposition output is GROUPED — demand
block (b1+b2) / service (b3) / generator (b4) / scale (b5) — never
per-coefficient, because the demand coefficients are individually
WEAK (cluster-robust |t| < 1: b1 ≈ 0.93, b2 ≈ 0.81 measured), so
per-coefficient attribution is noise attribution. (An earlier
revision justified grouping with "VIF>10 at n_eff≈41" — a
misstatement corrected against the measured artifact, SC batch
2026-07-19; README known issue 37.) Windows whose
b1/b2 covariates fall outside the fitted routes' covariate bounding
box get a `leverage_flag` (a conservative hull proxy — the implemented
test; the full convex-hull test is not implemented).

FY2020-Q3: kept, March included (`screen_fy2020_clip` documents the
clip; the old "Jul-Feb only if March distorts" clause is DELETED — the
on-disk PDF is a 9-month YTD total and a monthly cut is
unimplementable without a network fetch). Handling: year FE, plus an
explicit months_observed=9 exposure adjustment on the fit side only if
trivially cleaner; either way a pre-registered `drop_fy2020`
sensitivity row is MANDATORY.

**3.2 Score (window level).** Scan universe is MECHANICAL, no "major
arterial" filter (the screen exists to rank; screening everything
honors governance rule 1): every weekday GTFS route shape with
main-shape length >= the window length. Window length is FIXED at
12.5 [screen_window_mi] (the 13-arterial prototype's best-window
length; band (10, 15) with BOTH-edge sensitivity rows — a swept length
would make windows of different lengths incomparable within one scan).
Step 0.5 [screen_step_mi]; w0 = k*0.5 exactly (integer k, never
accumulated floats). Measured: 53 weekday shapes; ~612 windows at
12.5 mi (846 at 10 mi, 430 at 15 mi). Best window per host shape is
reported alongside all windows.

ONE shared function computes predictors on both sides:
`compute_predictors(line, w0, w1, tracts, od, acs, generators)` in
`scripts/screen_common.py`, used by `screen_fit.py` (route =
full-shape window [0, L]) and `screen_scan.py` (sliding windows).
Catchment = tract centroid |offset| <= 0.9 [buffer_mi] AND projected
position in [w0, w1] (clipped); LODES flows are BOTH-ends-in (home AND
work tract in catchment); intra-tract flows treated identically on
both sides; the special-generator dummy is derived geometrically on
both sides (any flagged generator within the buffer of the catchment
window). A standing unit test asserts Route 43's fit-side predictor
vector equals the scan-side vector for the full-length window on 43's
shape — fit/score consistency is machine-checked, not assumed.

**Standardized service.** svc_std = median over fitted routes of
FY2019 revenue hours per route-mile, times window length (registry
`screen_svc_std`, constant tier, measured basis; p25/p75 sensitivity
rows — expected rank-inert because a single additive b3 term shifts
all windows by a constant; the rows PROVE it rather than asserting
it).

**Published score (same-exposure baseline; rebased 2026-07-19, SC
batch).** screen_index = 100 * (predicted at svc_std) / (median over
fitted host routes of that route's own BEST 12.5-mi-window prediction
at svc_std — the same best-window-per-shape objects the scan already
computes, restricted to fitted routes; lower-median, deterministic).
The superseded baseline — the median fitted route's prediction AT ITS
OWN LENGTH — was a length artifact: with b3+b5 = +0.917 per log-mile
and 12.5-mi windows against an ~18-mi median fitted route, no window
could mechanically exceed ~72. The rebase is a positive scalar
multiple of the old index, so RANKS ARE UNCHANGED (a standing test
asserts the monotone rescale — test_screen.py D5; README known issue
36). Ordinal only; no field anywhere in the artifact is denominated
in boardings (§4).

**Underservice (redefined).** The old actual-minus-fitted formula was
the model's own in-sample residual — mean-zero, orthogonal to the
predictors, with the service effect already conditioned out via b3 —
and is DEAD; it measured misfit, not underservice.
underservice_gap = (predicted at STANDARDIZED service) minus (actual),
in log points; underservice_flag is set only when the gap exceeds the
leave-route-out P90 absolute log error, so model error is explicitly
netted out. The artifact carries both, plus a disclaimer that the flag
conflates unmodeled route quality with underservice — that caveat also
goes in the gate-1 memo verbatim. Predicted-at-incumbent-actual
service appears ONLY as the diagnostic input to this gap (one of the
exactly two permitted service levels, §4).

**3.3 Overlap handling.** Windows sharing > 0.30
[screen_overlap_threshold] of catchment tracts are grouped by
connected components (band (0.2, 0.4), both-edge rows). Group ids are
deterministic: the lexicographically smallest member window_id.
Grouping addresses double-counted demand, not correlated errors —
cross-window error correlation is handled by the joint bootstrap
(§3.4).

**Measured degeneracy caveat (review 2026-07-19).** On the real
universe the connected components COLLAPSE: all ~612 windows form ONE
county-wide component at the 0.30 headline threshold (still one at
the 0.2 band edge; two at 0.4 — the `overlap_lo`/`overlap_hi` rows
report this). Single-linkage transitivity chains ~96%-overlapping
adjacent windows on each shape, and the min-denominator share
(|A∩B|/min(|A|,|B|)) links parallel and crossing routes, so
`overlap_group` cannot do the deduplication job this section was
built for. The artifact therefore carries an `overlap_diagnostics`
block — best window per host shape plus per-pair overlap shares among
those best windows (same share rule, NO transitive closure) — and
gate 1 deduplicates from THAT, never from `overlap_group` (§4b step
2). Replacing the grouping with a non-chaining rule (complete-linkage
or host-shape-scoped components) is an OWNER decision, not a build
patch; logged as README known issue 34.

**3.4 Uncertainty (route-cluster bootstrap).** B = 2000
[screen_n_boot] replicates: resample ROUTES with replacement, refit,
rescore ALL windows jointly per replicate — cross-window correlation
is captured for free, so cutoff comparisons use the joint rank
distribution rather than pretending window CIs are independent. ACS
measurement error propagates inside each replicate: tract E002
perturbed within MOE/1.645 (normal, clipped at 0). Deterministic:
single `numpy.random.default_rng(7 [screen_seed])`. Per window:
screen_index p50/p10/p90, rank_ci (2.5/97.5 percentiles of rank), and
`tie_with_cutoff` = rank-5-boundary overlap from the JOINT rank
distribution — this operationalizes gate 1's tie rule (spec 00 §3,
restated there in bootstrap-rank form).

## 4. Outputs

**Artifact: `outputs/screen_results.json`** — deterministic write
(sort_keys, indent=2, LF, no timestamps, floats rounded 6 dp).

Top level: `run_id` (sha256 of an explicit preimage including the
assumptions values_hash — `sequence_network.py` pattern; the preimage
also hashes the `config/special_generators.json` list and the band()
edges the sensitivity rows consume, so a config or band edit mints a
new run), `schema` '01-S1', `seed`, `n_boot`, universe rule + counts
(shapes, windows), data vintages (gtfs/lodes/acs/apc), `disclaimer`
("ordinal screening index; not a ridership forecast (spec 00 §1)"),
`assumptions_manifest` {consumed ids + values, band edges,
values_hash}, `windows[]`, `overlap_diagnostics{}` (n_groups +
degeneracy note + best window per host shape + per-pair overlap
shares, §3.3 caveat — this also delivers the §3.2 best-window-per-
host-shape report), `fit_diagnostics{}`, `sensitivity[]`,
`shortlist_stability{}` (the §5c report: per_row [id, unit,
n_tie_row, tie_in/tie_out vs the margin-defined headline tie set,
jaccard, tie_churn_frac, hard_top8_churn diagnostic with unit field;
by_class for gen_leave_class_out], aggregate {min_jaccard, worst_row,
max_tie_churn_frac, max_tie_churn_row, criterion3_excluded_rows (the
§5 unit fix: the churn max scans window-unit rows only),
n_tie_headline, stable_core, n_stable_core}, note), `decision_output{}`
(the §5 tripwire v2,
mechanized: {ordinal_ok, criteria {sign_pos_frac (b1/b2 pos_frac,
threshold, pass), battery_rho (min_rho, provisional threshold, pass),
tie_churn (max_tie_churn_frac, threshold null, pass null — pending
owner)}, decision_format 'ordinal'|'threshold_shortlist', shortlist
[all tie_with_cutoff windows grouped by host shape with
screen_index_p50 + underservice_flag], diagnostics {min_abs_t_demand,
b4_pos_frac}, replicate_signs {b1/b2/b4 '+'/'-' strings, replicate
order}}).

Per window: `window_id` (route_id + w0, deterministic), `route_id`,
`w0`, `w1`, `window_mi`, `screen_index_p50/p10/p90`, `rank`,
`rank_ci`, `tie_with_cutoff`, `decomposition` (grouped: demand /
service / generator / scale), `overlap_group`, `underservice_gap`,
`underservice_flag`, `leverage_flag`, `incumbent_routes`. The
window_id + route_id + [w0, w1] triple is sufficient for the §4b
promotion step to materialize a corridor config mechanically.

`fit_diagnostics`: coefficients with cluster-robust SEs, VIFs, grouped
decomposition shares, LOO-route rho and MALE (worst-5 routes named),
dropped-route list, dfbetas for special-generator-flagged routes,
Harbor-area window scores with and without b4, leave-one-year-out
rank stability. b3 is reported here labeled "allocation control — not
a service response (spec 02 owns that question)".

`sensitivity[]`: {id, label, pct, detail} rows where **pct = 100 * (1
− Spearman rho of the full window ranking vs headline)** and detail
carries top-8 set churn. This is THE stage-1 materiality convention
(there is no ridership headline to move) — documented here and in
`check_assumptions.py`. Baseline and variant rankings in these rows
are POINT-fit rankings (the pipeline rerun without the bootstrap);
the published per-window `rank` field is bootstrap-p50-based and can
differ near ties — stated in the artifact notes. Row ids: `buffer_lo`, `buffer_hi`,
`window_10`, `window_15`, `drop_fy2020`, `drop_rh`, `e016_swap`,
`b4_off`, `gen_leave_class_out`, `nb_estimator`, `svc_p25`, `svc_p75`,
`offset_variant`, `overlap_lo`, `overlap_hi`, `year_fe_vs_pooled`.

**Output-format guardrails (binding, mechanized).** (a) NO field in
`screen_results.json` is denominated in boardings; scores exist only
as screen_index. (b) Predictions at exactly TWO service levels appear
anywhere in the pipeline: standardized (svc_std) and
incumbent-actual (diagnostic for the underservice gap only) — never
any counterfactual service level. (c) Standing tests assert both (a)
and (b); the endogeneity guard is machine-checked, not aspirational.

**Chart: `outputs/screen_ranked.png`** — top ~25 windows, index P50
with P10-P90 whiskers, overlap-group coloring (falls back to
host-shape coloring while the grouping is degenerate — one component
makes group coloring vacuous, §3.3), axis label "ordinal screening
index (median fitted route's best same-length window = 100) — not a
ridership forecast". House
matplotlib conventions (make_charts.py `screen` mode or a standalone
helper in screen_scan.py).

## 4b. Gate-1 promotion protocol (owner-mediated, never automatic)

The screen cannot produce what `config/candidates.json` requires (a
full spec-02 corridor config, a committed
`data/derived/corridor_<id>.json`, an honestly-determined spec 04 §3.3
crossings count), so promotion is necessarily a human step. The
protocol:

1. **Screen artifact** (`screen_results.json`) →
2. **Gate-1 memo** applying the spec 00 §3 formula: top 5-8 windows
   (deduplicated via `overlap_diagnostics` — best window per host
   shape, then per-pair overlap shares among those; NEVER via
   `overlap_group`, whose connected components are measured-degenerate,
   §3.3) + every `tie_with_cutoff` window + every `underservice_flag`
   window, with the §3.2 underservice caveat quoted and
   leverage-flagged windows annotated. **Tripwire binding (SC batch
   2026-07-19):** while `decision_output.ordinal_ok` is false, the memo
   consumes `decision_output.shortlist` plus the measured indicator
   columns (rank_ci, tie_with_cutoff, underservice_flag,
   leverage_flag), NEVER a top-N by rank — the ordinal index is
   diagnostic-only until the §5 tripwire passes;
   `decision_output.decision_format` states which mode applies.
   **Stability binding (owner review 2026-07-20):** additionally, if
   the `shortlist_stability` aggregate shows heavy tie-set churn, the
   memo MUST state that the honest stage-1 output is NARROWER than the
   shortlist, and name the stable core if one exists —
   `shortlist_stability.aggregate.stable_core`, the windows present in
   the tie set under EVERY battery row (empty core ⇒ the memo says so
   plainly: no window survives the whole battery);
3. **Owner authors** per-finalist corridor configs and crossings
   counts under the spec 04 §3.3 category discipline (per-crossing
   geometry, not defaults);
4. **`config/candidates.json` updated** with `hand_supplied: false`
   and per-candidate provenance `{screen_run_id, screen_index_p50,
   overlap_group}`.

The screen refreshes the candidate POOL between real programmatic
commitments; it does NOT re-score counterfactual networks — network
interaction is the sequencing harness's job via `anchor_add` (spec 07
§4.3, amended to match). Final gate authority stays with the project
owner (spec 00 §3).

## 5. Validation gates (must pass before first use)

**DECISION TRIPWIRE v2 (owner review 2026-07-20 of the SC-batch
pre-registration; criterion 1 revised AND ratified, criteria 2/3
statistics rebuilt with values deferred).** The screen emits a
decision-grade ORDINAL ranking only if ALL criteria pass:

**Criterion 1 — signed bootstrap fraction (RATIFIED 2026-07-20).**
For EACH demand-block coefficient, the fraction of the B=2000
route-cluster bootstrap replicates (§3.4) in which the coefficient is
STRICTLY POSITIVE must be >= 0.841 [screen_pos_frac_min]. The demand
block is DEFINED as {b1_lodes, b2_e002}. b4 is OUTSIDE it, per the
artifact's own grouped decomposition (demand b1+b2 / service b3 /
generator b4 / scale b5): b4's wrong-sign risk is priced by the
`b4_off` battery row, and v2.1 replaces the hand-coded dummy with
measured WAC generator jobs (§9.1); b4's per-replicate sign IS still
reported, as a diagnostic (`decision_output.diagnostics.b4_pos_frac`).
Basis: 0.841 = Phi(1), the one-sided translation of |t| >= 1 with the
sign requirement added; t = 1 is the threshold at which a regressor
improves adjusted R-squared and out-of-sample prediction error — the
decision-theoretic minimum for carrying a variable at all. The
bootstrap-fraction form replaces the analytic cluster-SE t
(`screen_t_min`, superseded) because cluster-robust SEs are
downward-biased at ~41 clusters and that bias runs toward PASS; the
analytic |t| values stay in the artifact as reported diagnostics.
Implementation: per-replicate b1/b2/b4 signs are recorded in the
EXISTING headline bootstrap (no new compute) and published as
`decision_output.replicate_signs`; the pos_frac values recompute from
those strings (test D6).

**Criterion 2 — battery minimum Spearman rho (statistic ratified;
VALUE provisional).** The battery's minimum Spearman rho over the
FROZEN perturbation list [screen_battery_rows] — EXCLUDING the
leave-one-year-out consistency check (see demotion below) — must be
>= 0.7 [screen_battery_rho_min]. The 0.7 value is PROVISIONAL: the
owner sets it after reading the shortlist-stability report (§5c).
Any earlier calibration story anchoring 0.7 to an observed battery
value is RETRACTED (recorded in the registry entry's history): it
tuned the bar to a measured row (e016_swap's rho 0.746) and that
example fails criterion 3's own statistic anyway.

**Criterion 3 — margin-defined tie-set churn (statistic REBUILT;
value pending owner).** The statistic is the maximum tie-set churn
fraction across battery rows —
`shortlist_stability.aggregate.max_tie_churn_frac` (§5c); for
`gen_leave_class_out` the aggregate scans EVERY generator class
(class max — the row's published entry is its min-Jaccard class
tuple, and the two extremes need not coincide in one class, so
per-row scanning alone could understate the statistic) — replacing
the hard top-8 membership count (`screen_top8_churn_max`, superseded:
rank-8 is an arbitrary boundary; the decision object is the
MARGIN-DEFINED tie set). NO threshold value exists yet:
`decision_output.criteria.tie_churn` carries threshold null and pass
null until the owner sets the value after the shortlist-stability
report. The legacy hard-top-8 churn survives as a per-row DIAGNOSTIC
column with an explicit per-row UNIT field — 'window_id' for most
rows, 'host_shape' for `window_10`/`window_15` (whose window sets
differ from the headline scan).

**Criterion-3 unit fix (owner item 2026-07-20; implemented, pending
owner ratification with the threshold values — registry
`screen_top8_churn_max` history).** The two window-length rows
(`window_10`/`window_15`) are DROPPED from criterion 3's max: a
length change alters the window UNIVERSE, so those rows' churn cannot
be measured over window ids at all and is instead measured in
HOST-SHAPE units — a 3.3x-coarser lossy proxy (denominator 14 vs 46
at the review build: ONE flip reads 7.1% against 2.2%). Cross-universe
membership churn is a category mismatch, not a stability measurement,
and a single scalar threshold cannot compare the two units. The rows
remain FULLY in criterion 2's min-rho (the best-per-shape ranking
comparison is unit-consistent) and in the §5c report's per_row block;
the aggregate names them in `criterion3_excluded_rows`, and
`min_jaccard` stays an all-rows REPORT aggregate (it feeds no
criterion).

**Fail-safe rule.** ordinal_ok requires ALL criteria to pass; an
UNSET threshold cannot pass. ordinal_ok is therefore FALSE BY
CONSTRUCTION until the owner sets criteria 2/3 — the intended
direction: while thresholds are open, the screen can only deliver the
shortlist, never a ranking. Otherwise (any criterion failing) the
decision output is the THRESHOLD SHORTLIST — all `tie_with_cutoff`
windows grouped by host shape, presented beside the measured
indicators — and the ordinal index is diagnostic-only. The rule is
MECHANIZED: `screen_scan.py` writes the artifact's `decision_output`
block (§4) with the measured numbers, the registry thresholds,
per-criterion pass booleans, `decision_format`, and the shortlist; a
standing test recomputes pos_frac from the stored replicate signs and
every boolean from the stored numbers (test_screen.py D6). Measured
outcome at the 2026-07-20 review build: ordinal_ok = FALSE —
criterion 1 fails (b1_pos_frac 0.8115, b2_pos_frac 0.7435 vs 0.841),
criterion 2 fails at its provisional value (min rho = 0.39,
buffer_lo), criterion 3 is unset (measured statistic 0.848,
e016_swap) — the screen delivers the shortlist, not a ranking.
README known issues 35 (opened) and 38 (owner review).

**FROZEN BATTERY (owner review 2026-07-20).** The battery is the
exact row list in [screen_battery_rows] (registry entry; the 16
sensitivity ids of §4, LOYO excluded as a consistency check). Adding
or dropping a row is an OWNER-APPROVED SPEC AMENDMENT, never a build
patch, because the battery criterion is a MIN: adding a row can only
lower it, and deleting a row can only raise it — an unfrozen list is
a tunable bar. A standing test asserts the artifact's battery rows ==
the registry list exactly, order included (test D2). This v2.0
16-row battery remains the PUBLISHED current-artifact report; the
owner's criterion-2/3 threshold values attach to the CLOSED v2.1
battery [screen_battery_rows_v21] for the phase-2b verdict (§9.8,
frozen 2026-07-20 on acquisition facts only).

**§5c Shortlist-stability report (owner review 2026-07-20; the
statistics behind criteria 2/3's pending values).** For EVERY battery
row, the artifact's `shortlist_stability` block reruns that row's OWN
route-cluster bootstrap (same B; per-row seed rule: every row
re-derives `default_rng(screen_seed)` — common random numbers, so the
route resamples and ACS z-draws are identical across rows and tie-set
differences are attributable to the perturbation, never the draw; the
z vector is drawn even where unwired, e.g. e016_swap has no E016 MOE,
purely to keep the CRN stream aligned) and computes its
`tie_with_cutoff` set. Per row: n_tie_row, tie_in/tie_out
(replacements vs the MARGIN-DEFINED headline tie set — never hard
rank-8), Jaccard overlap, tie_churn_frac = max(#in, #out)/|headline
tie set|, and the legacy hard-top-8 churn as a unit-tagged diagnostic.
The `nb_estimator` row's per-replicate NB2 refit holds alpha at the
headline NB2 estimate and Fisher-scores beta
(`screen_fit.nb2_beta_fixed_alpha` — a stated approximation, pinned
to the statsmodels fit by test D7; profiling alpha per replicate is
outside the block's runtime budget). The aggregate carries
min_jaccard (all rows — a report figure, feeding no criterion),
max_tie_churn_frac (criterion 3's statistic — WINDOW-UNIT rows only
per the §5 unit fix, the excluded length rows named in
`criterion3_excluded_rows`), and the
STABLE CORE: headline tie windows present in the tie set under every
battery row (host-shape membership for the window-length rows; every
generator class for gen_leave_class_out) — the §4b memo consumes it
when churn is heavy.

*Epistemics note (owner item 2026-07-20).* The SB reviewer's
byte-match reproduction of this artifact is recorded as
IMPLEMENTATION verification — it demonstrates the absence of a coding
slip, and nothing more. It does NOT validate the route-cluster
bootstrap as the right uncertainty model for the tie sets: reviewer
and author execute the same spec, the same seed rule, and the same
replicate family, so agreement between them cannot speak to whether
that family is the right one (README known issue 38).

**PRIMARY — rank-stability battery** (panel 2026-07-18: for a screen
that passes ties onward, ranking robustness under *specification
choices* matters most; single-observation deletion barely moves a
41-route fit and is nearly toothless as a primary gate):

(a) bootstrap rank confidence sets for the top-10 windows (§3.4);
(b) cross-spec Spearman rho + top-8 set churn across the
    pre-registered perturbations: buffer 0.5/1.25, window 10/15,
    drop_fy2020, drop-RH, drop-generator (b4_off), E016-swap, NB
    estimator, svc p25/p75, offset-variant.

Leave-one-YEAR-out rank stability — battery item (c) until the SC
batch — is DEMOTED to a *consistency check (mechanically near-1 with
time-invariant X)*: under a single time-invariant X snapshot, dropping
a year perturbs the coefficients only through the y side, so its
~0.99 rho is a property of the design, not evidence. It is reported
in `fit_diagnostics.leave_one_year_out` under that label and is
excluded from tripwire criterion (ii).

The gate report enumerates every shortlist (top-8) membership change
across the battery explicitly — windows that enter or exit are named
and dispositioned in the gate-1 memo, never averaged away.

**Demoted / secondary:**

- LOO-route Spearman rho >= 0.9 [screen_loo_rho] — retained as a
  *leverage screen* only (LOO = leave-one-ROUTE-out, all years of the
  held-out route removed; leave-row-out would leak route identity
  through the other years and pass trivially). Note also (SC batch
  2026-07-19): leave-route-out ACCURACY is dominated by b3 —
  regressing log boardings on log revenue hours is near-tautological
  at the route level — and b3 is held constant at scoring, so a
  passing LOO gate is approximately ZERO evidence about the ranking;
  it remains a leverage screen only.
- LOO median absolute log error <= 0.35 [screen_male] — secondary
  diagnostic (~±40% on a held-out route); worst 5 routes named.
- 13-arterial prototype reproduction — smoke test, near-circular (the
  prototype is what this model supersedes); failure prompts
  investigation, not rejection.

**Standing:** `check_assumptions.py` GREEN (governance rule 6) joins
this section as a standing gate; the `screen` artifact scan (§5b)
covers the sensitivity block.

*LOO dual-use note:* the existing-route productivity cross-section
appears in spec 00 §5 as "Stage-1 fit + LOO validation" — a same-data
dual use, tolerated on the mechanical ground that each holdout route
is fully excluded from its own refit (mirrors the 543 cross-stage
note). *Upgrade path:* the pending records request (items 1a/1b:
FY2014-16 and post-FY2021 route-level boardings) would extend the
panel and partially de-confound the FY2020 COVID clip; a systemwide
stop-level APC extract (widened item 2) would upgrade catchment
validation.

## 5b. Registry integration (spec 08)

Every screen knob is a `scripts/assumptions.py` entry consumed via
`val()`; no bare literals in screen code. All screen sensitivity ids
are oc-registry-owned — the screen has no engine, so NO engine-owned
exemption set applies to the `screen` artifact scan (unlike
wrapper/network, where the Q7 tie-break applies).
`check_assumptions.py` gains a `screen` artifact scan (backtest
pattern): it loads the `sensitivity` block ONLY — never the ~612
window rows — and checks 2/3/5 coverage for screen-claiming entries.

| id | value | tier | basis | band / disposition | screen rows |
|---|---|---|---|---|---|
| `buffer_mi` | 0.9 | constant (existing; ONE entry, two consumers — corr_share precedent) | definitional → judgment (append-only history transition; ref 'spec01 Q1 + external challenge 2026-07-17') | (0.5, 1.25) | `buffer_lo`, `buffer_hi` (stage-2 rebuilt-variant rows queued) |
| `screen_window_mi` | 12.5 | constant | judgment (prototype precedent) | (10, 15) | `window_10`, `window_15` |
| `screen_step_mi` | 0.5 | constant | judgment | quality-knob, no row | — |
| `screen_svc_std` | measured at build | constant | measured (median FY2019 RVH/route-mi of fitted routes) | p25/p75 probes | `svc_p25`, `svc_p75` |
| `screen_n_boot` | 2000 | constant | judgment | quality-knob | — |
| `screen_seed` | 7 | constant | definitional | quality-knob | — |
| `estimator_screen` | log-OLS primary / NB2 always-fitted | structural | judgment | row always fits BOTH | `nb_estimator` |
| `screen_overlap_threshold` | 0.30 | constant | judgment | (0.2, 0.4) | `overlap_lo`, `overlap_hi` |
| `screen_fy2020_clip` | March-in (9-mo YTD) | structural | judgment (monthly cut unimplementable from on-disk PDF) | drop row mandatory | `drop_fy2020` |
| `special_generators` | config/special_generators.json | config | judgment (append-only history per edit) | upgrade: measured magnitudes | `b4_off`, `gen_leave_class_out` |
| `apc_fy17_19_20` | PDF extraction vintage | data | measured | upgrade = records request items 1a/1b | — (caveat) |
| `x_vintage_mismatch` | 2022 LODES / 2023 ACS X vs FY2017-20 y | structural | judgment | — | `drop_fy2020` (shared), `year_fe_vs_pooled` |
| `screen_loo_rho` | 0.9 | constant | judgment | quality-knob | — |
| `screen_male` | 0.35 | constant | judgment | quality-knob | — |
| `screen_t_min` | 1.0 | constant | judgment — SUPERSEDED 2026-07-20 (criterion 1 revised to the signed bootstrap fraction; analytic \|t\| demoted to a diagnostic) | superseded, points forward to `screen_pos_frac_min` | — |
| `screen_pos_frac_min` | 0.841 | constant | judgment (revised criterion 1, OWNER-RATIFIED 2026-07-20; 0.841 = Phi(1), the one-sided \|t\|>=1 translation with the sign requirement) | quality-knob (consumption verified by the `screen` scan) | — |
| `screen_battery_rho_min` | 0.7 | constant | judgment (criterion 2; statistic ratified, VALUE PROVISIONAL pending owner post-report 2026-07-20; calibration story retracted) | quality-knob (consumption verified by the `screen` scan) | — |
| `screen_top8_churn_max` | 2 | constant | judgment — SUPERSEDED 2026-07-20 (criterion-3 statistic rebuilt as margin-defined tie-set churn; hard top-8 churn demoted to a unit-tagged diagnostic; successor threshold entry pending the owner's post-report value) | superseded | — |
| `screen_battery_rows` | 16 frozen row ids | constant (structural-governance role) | definitional (owner battery freeze 2026-07-20; the battery is a MIN — row changes are owner-approved spec amendments) | definitional (consumption verified by the `screen` scan; test D2 asserts artifact == registry list) | — |

The predictor-set perturbation rows are claimed by two structural
entries created at S2: the endogenous-controls choice (rows `drop_rh`,
`e016_swap` — the D14 firewall's enforcement) and the scale-term
choice (row `offset_variant`); exact ids land with the entries (row
coverage is the binding requirement). Screen-scoped caveats are
appended to the existing `lodes_2022` / `acs_2023` / `gtfs_2026_07`
provenance; the gtfs entry additionally notes the 6 discontinued APC
routes (survivorship disposition). README known-issue entries
(governance rule 3) are created for: the standardized-service
endogeneity dilemma, the buffer challenge/unification, the smoke-test
near-circularity, generator hand-coding, and the index-normalization
choice — and wired as `logged` pointers on the corresponding entries.
Registry entries and the scan amendment land in the same branch as the
screen scripts (A3/W1/N4 pattern). PRIORS are untouched — every screen
entry is constant/config/structural/data tier; the prior order
fingerprint must not change.

## 6. Build, runtime & determinism

Fit: seconds. Scan: 53 weekday shapes; ~612 windows at 12.5 mi —
minutes single-machine, well inside the 1-hour budget, PROVIDED the
structure is: import `Line`/`project` from `build_corridor.py` (and
nothing else — NEVER call `build_corridor.main()`, whose feeder scan
would cost hours across the universe); per-shape precompute of
(offset, position) for all 614 tracts; per-window work is a boolean
mask + grouped LODES sums.

Scripts: `scripts/screen_common.py` (shared `compute_predictors`),
`scripts/screen_fit.py`, `scripts/screen_scan.py`;
`scripts/extract_apc.py` extended to full-row parse (boardings + RVH,
validated against the printed b/RVH column to 2 dp for every row,
exit nonzero on failure; FY2020-Q3 layout drift handled explicitly).

**Determinism checklist (gate — dual-generation byte-identity of
`screen_results.json` is a commit gate):**

1. statsmodels==0.14.5 pinned in requirements.txt; fixed
   start_params/maxiter for the NB row.
2. Sorted route_id iteration everywhere.
3. Integer-step windows (w0 = k*0.5, never accumulated floats).
4. Deterministic overlap-group ids (lexicographically smallest member
   window_id) and sorted member lists; no `set()` iteration in output
   paths.
5. Single seeded `default_rng(val('screen_seed'))`.
6. Canonical json write: `open(path, 'w', encoding='utf-8',
   newline='\n')`; `json.dump(canon, f, sort_keys=True, indent=2)`;
   trailing newline; floats rounded 6 dp; no timestamps.
7. `encoding='utf-8'` on every `open()`.

**Tests.** Committed synthetic fixture (3-5 tracts, 2 toy shapes)
exercises `compute_predictors`, window mechanics, and overlap grouping
WITHOUT `data/raw`; integration tests are data-gated (skip cleanly
when `data/raw` is absent — house Q6 pattern). Standing tests:
fit==scan predictor identity (Route 43), no-boardings-field,
two-service-levels-only, artifact schema, determinism (double-run
in-process byte-identity).

## 7. Known limitations (accepted, stated plainly)

- **No network effects.** Cross-sectional; windows are scored in
  isolation. The screen cannot see transfers, feeder restructuring, or
  interaction with committed lines.
- **No counterfactual service scoring.** The model cannot say what a
  window would carry under any proposed service — b3 is an allocation
  control fitted on endogenous data. Standardized-service scoring is a
  comparison convention only.
- **Survivorship.** The 6 discontinued APC routes (24, 53X, 57X, 64X,
  82, 153) — systematically low performers — cannot be fitted, so the
  model never sees fundamentals-poor failures; the underservice logic
  is correspondingly flattered.
- **Vintage mismatch.** 2022 LODES / 2023 ACS predictors regressed on
  FY2017-FY2020 boardings: post-COVID, WFH-reshaped commute geography
  explaining pre-COVID ridership (`x_vintage_mismatch`; 2026-07 GTFS
  alignments also differ from the service that generated the
  boardings).
- Catchments of fitted routes overlap (parallel arterials); residual
  spatial correlation is only partially absorbed by route clustering.
- Special generators are judgment-flagged dummies with a binary cliff
  at the buffer edge; dfbetas and with/without-b4 diagnostics are
  reported, not a fix.
- `main_shape_xy` longest-shape heuristic mismeasures branched
  routes' catchments on the fit side.
- FY2020-Q3 includes March 2020 (COVID onset); the drop_fy2020 row is
  the honest handle, not a monthly cut.

All acceptable because the output is a shortlist and gate 1 passes
near-ties onward rather than resolving them.

## 8. Questions resolved

Review 2026-07-08 (as amended by the panel):

- Q1 (buffer): 0.9 [buffer_mi] primary — now ONE registry entry with
  two consumers (screen + stage 2), band (0.5, 1.25), BOTH-edge screen
  rows. The original one-sided "0.5 robustness row" and the entry's
  old rowless quality-knob disposition are superseded by the D13
  append-only history transition.
- Q2 (standardized service): retained in principle; operationalized as
  svc_std = median fitted-route FY2019 RVH per route-mile x window
  length (`screen_svc_std`), with p25/p75 rows proving rank-inertness.
  Scoring at the proposed rapid spec stays rejected (would re-inject
  the endogeneity §1 firewalls and flatter corridors one intends to
  propose rapid on).
- Q3 (dependency): statsmodels accepted, pinned ==0.14.5 in
  requirements.txt.

Panel 2026-07-18 (3-lens adversarial; 9 blocking findings — adjudicated
resolutions, briefly):

- Q4 (underservice residual = model's own residual): redefined against
  standardized-service predictions, flagged beyond LOO P90 error (§3.2).
- Q5 (endogenous controls bias ranking coefficients): E016 removed,
  E002 in; firewall mechanized via battery + standing tests (§1, §5).
- Q6 (pseudo-replication, ~sqrt(3) overtight intervals): cluster-by-
  route inference, leave-route-out LOO, route-cluster bootstrap (§3.1,
  §3.4).
- Q7 (scan universe undefined; counts misstated): mechanical universe,
  measured counts (§3.2, §6).
- Q8 (length/scale confound): fixed 12.5-mi window + b5 scale term
  with offset-variant row (§3.1, §3.2).
- Q9 (revenue hours not on disk): extract_apc.py full-row parse with
  2-dp b/RVH validation (§2, §6).
- Q10 (fit/score predictor identity unguaranteed): shared
  compute_predictors + Route 43 identity test (§3.2).
- Q11 (no registry integration): §5b, in the same branch as the code.
- Q12 (buffer_mi collision with landed disposition): unified entry,
  history transition, check-7 citations throughout (§5b).

## 9. v2.1 rebuild — PRE-REGISTRATION (amendment 2026-07-20; written BEFORE any new data is fitted)

**This section is a pre-registration document. It is committed
2026-07-20, before any v2.1 input has been fitted — before most of it
has even been downloaded. That timing is the section's entire
epistemic value: the predictor set, catchment rule, fit-data vintages,
fit universe, and decision rule below are fixed while the rebuilt
fit's numbers are unknown, so a later pass or fail cannot be narrated
as a choice made after seeing the results.**

Context. The §5 tripwire measured ordinal_ok = FALSE at landing
(README known issues 35–37): min demand-block |t| = 0.81 (b2), min
battery rho = 0.39 (buffer_lo), top-8 churn 8. The external critique's
trace attributes this in part to v2.0 input mechanics — one
time-invariant 2022/2023 X cross-section explaining three boardings
years, a saturated hand-coded generator dummy, tract-resolution
catchments, and a fit universe missing the six discontinued routes.
v2.1 rebuilds those inputs and NOTHING else: §3's estimator,
clustering, bootstrap, index definition and output guardrails, §3.4's
uncertainty machinery, and §5's tripwire all govern the rebuilt fit
unchanged, at unchanged df discipline.

### 9.1 Pre-registered PRIMARY predictor set

5 slopes + intercept + 2 year FE, exactly as §3.1:

- **b1** log1p(LODES both-ends-in flows, VINTAGE-MATCHED (9.3),
  block-buffer catchment (9.2))
- **b2** log1p(ACS B25044 zero-vehicle HOUSEHOLDS in catchment) —
  replaces B08141 E002 zero-vehicle workers as the headline
  car-access predictor
- **b3** log(annual revenue hours) — allocation control, UNCHANGED;
  the §1 endogeneity firewall and the `drop_rh` row carry over intact
- **b4** log1p(generator jobs: LODES WAC jobs in NAICS
  education + health care + accommodation/arts-entertainment within
  the catchment) — a measured, continuous magnitude REPLACING the
  saturated hand-coded binary generator dummy
- **b5** log(length mi) — unchanged

Pre-registered SWAP rows (sensitivity battery only, NEVER headline):

| swap row | replaces | with |
|---|---|---|
| `popden_swap` | b1 | log1p(B01003 population / ALAND density in catchment) |
| `e016_swap` | b2 | legacy B08141 E016 transit workers (carried over from §5b) |
| `e002_swap` | b2 | legacy B08141 E002 zero-vehicle workers (the v2.0 headline) |
| `sld_swap` | b1+b2 demand block | EPA SLD D-index aggregate — ONLY IF the SLD is acquired; the row drops silently from the battery otherwise |
| `gen_dummy_swap` | b4 | legacy binary special-generator dummy (config/special_generators.json) |

No other predictor may enter the rebuilt fit — see the 9.5
no-shopping rule.

**Pre-registered wrong-sign handling for b4 (owner item 4b,
2026-07-20; fixed before any v2.1 input is fitted).** If the rebuilt
fit's `l_genjobs` coefficient comes back NEGATIVE, that does NOT trip
the demand-block criterion — b4 is outside the block by construction
(§5 criterion 1) — but it MUST raise a logged diagnostic, never a
silent pass: the v2.1 artifact carries a `b4_wrong_sign` flag field
in its fit diagnostics (set when the point estimate is negative),
and setting that flag OBLIGATES a README known-issue entry
(governance rule 3) before the artifact is consumed by any gate
memo. Rationale: a negative measured-generator term is a signal that
b3 (allocation control) and/or b5 (scale) are absorbing attraction
effects — a specification symptom the owner must see, not a
tolerable sign to wave through.

### 9.2 Catchment v2.1: block resolution

Membership rule: a census BLOCK is in the catchment iff its centroid's
|offset| <= 0.9 [buffer_mi] AND its projected position lies in
[w0, w1] (clipped to the window) — the §3.2 rule verbatim, applied at
block rather than tract resolution. Blocks are small enough relative
to a 0.9-mi buffer that the centroid test approximates full
buffer-polygon intersection; that approximation is a stated property
of the rule, not a hidden one, and no polygon-intersection variant is
pre-registered. The `buffer_mi` entry keeps its single §5b identity,
band (0.5, 1.25), and the SAME `buffer_lo`/`buffer_hi` rescan rows.

### 9.3 Fit data v2.1: vintage-matched X

Each boardings year receives its own predictor vintage:

| boardings year | LODES (OD + WAC) | ACS 5-year |
|---|---|---|
| FY2017 | 2017 vintage | 2013–2017 |
| FY2019 | 2019 vintage | 2015–2019 |
| FY2020-Q3 | 2019 vintage | 2015–2019 |

Route-years therefore stop collapsing onto one cross-section: X varies
within route across years, and the year FE stop absorbing pure vintage
drift. CONDITION (pre-registered): leave-one-YEAR-out rank stability
returns to the §5 battery — reversing the SC-batch demotion — IF AND
ONLY IF the fitted X actually varies by year, verified mechanically
(the fit prints per-predictor within-route across-year variance; if a
source cannot be acquired at the matching vintage and X remains
effectively time-invariant, the check keeps its demoted
consistency-check label and stays excluded from tripwire
criterion (ii)).

**Condition RESOLVED (owner items 2/3, 2026-07-20 — input-side, this
batch, not deferred to post-fit).** The design-stage power check
(`scripts/screen_power.py`, artifact
`outputs/screen_power_check.json` `x_variation`) measured the
within-route across-year variation of the §9.1 predictors on the
41-route current-shape universe under this section's vintage
dispatch: every vintage-matched predictor (l_flows, l_zveh_hh,
l_genjobs) varies within route for share 1.0 of fitted routes
(median within-route std 0.011 / 0.039 / 0.022 respectively; l_rvh
varies through measured annual RVH, share 1.0). X actually varies by
year, so LOYO RETURNS to the v2.1 battery — row `loyo` in the frozen
[screen_battery_rows_v21] list (§9.8), statistic = min Spearman rho
over the three year-dropped refits vs the v2.1 headline ranking.
Stated caveats: the fy2017 drop leaves a single-vintage X pair
(fy2019/fy2020q3 share tables), and l_len is time-invariant in the
measurement only because it used current shapes for all years (the
archived §9.4 shapes will move it).

### 9.4 Fit-side universe: archived GTFS (explicit asymmetry)

FIT side: contemporaneous archived GTFS shapes (transitfeeds.com /
mobilitydatabase.org snapshots matching each boardings year), so the
six discontinued routes — 24, 82, 153, 53X, 57X, 64X — RE-ENTER the
fit and the §2/§7 survivorship drop is removed; the model finally sees
the fundamentals-poor failures. SCAN side: stays on CURRENT (2026-07)
GTFS — candidates must be buildable today. This asymmetry is
deliberate and stated: the fit learns from the historical network
including its failures; the scan ranks only windows that exist on
today's geometry. The shared `compute_predictors` discipline (§3.2)
is unchanged on both sides; the Route 43 fit==scan identity test is
evaluated on the snapshot pair the two sides actually share
(43's archived shape vs its current shape is itself a printed
diagnostic, not an assumed identity).

### 9.5 Decision rule (pre-committed; permanence clause softened per owner review 2026-07-20)

The §5 tripwire v2 — `screen_pos_frac_min` (criterion 1, ratified) /
`screen_battery_rho_min` (criterion 2, value provisional) / the
tie-churn statistic (criterion 3, value pending owner) — governs the
rebuilt output IDENTICALLY: same criteria, same registry thresholds
as ratified/set by the owner, same mechanized `decision_output` and
`shortlist_stability` blocks. PRE-COMMITTED interpretation: if the
rebuilt demand block STILL fails the tripwire, the screen's decision
output REMAINS the threshold shortlist plus the measured-indicator
table (rank_ci, tie_with_cutoff, underservice_flag, leverage_flag) —
or the NARROWER stable core per §4b when the stability report shows
heavy tie-set churn — UNTIL a documented, owner-approved change of
method (governance rule 3: a README known-issue log entry is
required). The FROZEN OBJECT is this §9 rebuild spec itself:
re-running the same spec hoping for a different answer is barred
(same inputs, same spec ⇒ same artifact by the determinism gate), no
post-hoc predictor shopping beyond the 9.1 pre-registered swaps, and
no threshold re-tuning after seeing the rebuilt numbers. Method
changes are GOVERNED — owner-approved, spec-amended, and logged —
not banned. (The prior wording — "no v2.2, permanent, no re-tuning
ever" — promised more than governance can honestly deliver and was
softened by the owner review 2026-07-20; README known issue 38.)

### 9.6 Acquisition manifest

Status column to be filled by the acquisition reports (per-file
provenance sidecars under `data/raw/`; raw files stay untracked).

| # | Source | Vintage | Geography | Feeds | Status |
|---|---|---|---|---|---|
| 1 | LODES OD (lehd.ces.census.gov, LODES7) | 2017, 2019 | CA blocks (2010 geography), OC subset | b1 vintage-matched both-ends flows | pending |
| 2 | LODES WAC (lehd.ces.census.gov, LODES7) | 2017, 2019 | CA blocks (2010), OC subset | b4 generator jobs (NAICS edu + health + accomm/arts) | pending |
| 3 | ACS B25044 zero-vehicle households (census.gov summary files / api) | 2013–17, 2015–19 | OC tracts/block groups (finest published) | b2 | pending |
| 4 | ACS B01003 population + ALAND | 2013–17, 2015–19 | OC tracts | `popden_swap` row | pending |
| 5 | TIGER block centroids + ALAND (census.gov) | 2010 blocks (LODES7-matching) | OC blocks | 9.2 catchment membership | pending |
| 6 | Archived OCTA GTFS (transitfeeds.com / mobilitydatabase.org) | ~FY2017, ~FY2019 snapshots | OCTA network | 9.4 fit-side shapes incl. discontinued routes | pending |
| 7 | EPA Smart Location Database (conditional) | latest | OC block groups | `sld_swap` row only | conditional — row drops if not acquired |
| 8 | CDE enrollment / NHTS context (cde.ca.gov, nhts) | latest | OC | logged context / b4 cross-check ONLY — never a predictor (9.7) | optional |

### 9.7 What v2.1 does NOT do

One paragraph, binding: v2.1 adds NO networked scoring — windows are
still scored in isolation, and transfers/feeder interaction remain the
sequencing harness's job (spec 07); it builds NO non-commute demand
model — CDE enrollment and NHTS trip-purpose data enter only insofar
as the b4 generator-jobs term proxies non-commute attraction, or as
logged context in the fit diagnostics, never as predictors; and the §1
endogeneity confession is UNCHANGED — vintage-matched X does not
identify fundamentals separately from service history, b3 remains an
allocation control that is never read causally, and no prediction at
any counterfactual service level is published. Registry entries for
the new knobs (vintage-match structure, generator-jobs NAICS set,
block-catchment transition, archived-GTFS data vintages, swap-row
structural claims) land with the build branch per the §5b / A3 / W1 /
N4 pattern — a later consolidation pass owns `scripts/assumptions.py`.

### 9.8 Frozen v2.1 battery (owner item 2, 2026-07-20 — closed pre-fit)

The CLOSED battery for the §9.5 phase-2b verdict is the 20-row list
in the registry entry [screen_battery_rows_v21], FROZEN NOW — before
any v2.1 input is fitted — on ACQUISITION FACTS ONLY. The owner's
criterion-2/3 threshold values attach to THIS list; the v2.0 16-row
battery ([screen_battery_rows]) remains the published
current-artifact report. Composition:

- the 14 v2.0 window-unit rows carried over: `buffer_lo`,
  `buffer_hi`, `drop_fy2020`, `drop_rh`, `e016_swap`, `nb_estimator`,
  `svc_p25`, `svc_p75`, `offset_variant`, `overlap_lo`, `overlap_hi`,
  `year_fe_vs_pooled`, and the two GENERATOR rows REDEFINED against
  §9.1's continuous WAC term — `b4_off` → `genjobs_off` (drop
  `l_genjobs`), `gen_leave_class_out` → `genjobs_leave_class_out`
  (drop ONE NAICS sector from the CNS15-18 sum; class-max
  aggregation carried over from §5c);
- PLUS the §9.1 swaps `popden_swap`, `e002_swap`, `gen_dummy_swap`;
- PLUS `window_10`/`window_15`, CRITERION-2-ONLY and flagged as such
  (the §5 criterion-3 unit fix excludes their host-shape-unit churn
  from the tie-churn max);
- MINUS `sld_swap` — EXCLUDED because the EPA SLD was NOT acquired
  in phase 1; §9.1 made the row conditional on acquisition and the
  exclusion is decided on that acquisition fact, never on fit
  results;
- PLUS `loyo` — leave-one-year-out rank stability RETURNS per the
  §9.3 condition, resolved in this batch on the measured input-side
  X-variance (see §9.3; min Spearman rho over the three year-dropped
  refits vs the v2.1 headline ranking).

Freezing before the rebuilt fit exists is the entire point: the
battery criterion is a MIN, so membership edits after seeing v2.1
numbers would be a tunable bar. Row changes from here are
owner-approved spec amendments (§5 freeze discipline, unchanged).
