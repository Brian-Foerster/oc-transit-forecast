# Spec 01 — Stage 1: Direct-Demand Regression Screen

Status: panel-revised 2026-07-18 (3-lens adversarial panel; 9 blocking
findings adjudicated) · BUILD IN PROGRESS · §9 v2.1 rebuild
PRE-REGISTERED 2026-07-20 (before any new data fitted) · §5 tripwire
v2 per owner review 2026-07-20 (criterion 1 revised + ratified;
criteria 2/3 RATIFIED 2026-07-20 — criterion 2 kept LIVE at 0.7,
criterion 3 a dual window/host-shape threshold; §9.10 regime-split
gate + §9.3/§9.9 universe amendments pre-registered) · §9 v2.1 fit
LANDED + FAILED 2026-07-21 (ordinal_ok=FALSE; README known issue 42) ·
§10 v2.2 productivity-estimand GOVERNED-METHOD-CHANGE PRE-REGISTERED
2026-07-21 (owner-directed, OC-only; written before any v2.2 fit) ·
§10 v2.2 productivity fit LANDED + FAILED 2026-07-21 (ordinal_ok=FALSE;
criterion 1 RESCUED, criteria 2/3 failed on the length artifact;
README known issue 44) · §11 v2.3 REGIONAL-CLUSTER-BASE
GOVERNED-METHOD-CHANGE PRE-REGISTERED 2026-07-21 (owner-directed;
KEEP productivity DV, ADD agency FE + regional panel frozen on
acquisition-availability facts; written before any v2.3 fit) · §12 v2.4
GOVERNANCE PRE-COMMITMENTS owner-ratified 2026-07-22 (failure-mode gate
+ numeric stopping rule + external-validity check + delegation guards)
· §13 v2.4 BENEFIT-PER-COST BCA-QUEUE PRE-REGISTRATION DRAFT 2026-07-23
(NOT FROZEN — freeze requires owner ratification; discrete anchor-pair
corridors, REUSES the committed v2.2 coefficients, NO new fit; four
failure-mode rows instantiated for the anchor world)
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
max_tie_churn_frac_window, max_tie_churn_row_window,
max_tie_churn_frac_hostshape, max_tie_churn_row_hostshape (the §5 dual
threshold: window-unit rows vs screen_tie_churn_max_window,
window_10/window_15 vs screen_tie_churn_max_hostshape),
n_tie_headline, stable_core, n_stable_core}, note), `decision_output{}`
(the §5 tripwire v2,
mechanized: {ordinal_ok, criteria {sign_pos_frac (b1/b2 pos_frac,
threshold, pass), battery_rho (min_rho, threshold, pass — LIVE 0.7),
tie_churn (window {max_over_window_unit_rows, threshold, worst_row,
pass}, hostshape {max_over_window10_window15, threshold, worst_row,
pass} — DUAL threshold, both must pass)}, decision_format
'ordinal'|'threshold_shortlist', shortlist
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

**Criterion 2 — battery minimum Spearman rho (RATIFIED LIVE
2026-07-20).** The battery's minimum Spearman rho over the FROZEN
perturbation list [screen_battery_rows] — EXCLUDING the
leave-one-year-out consistency check (see demotion below) — must be
>= 0.7 [screen_battery_rho_min]. The owner KEEPS 0.7 and makes it
LIVE (the earlier "provisional" marker is removed): it is the ordinal
PRODUCT's own gate — an uncalibrated FLOOR EXPECTED TO BE SLACK
guarding whole-ORDERING stability (Spearman rho over the frozen
battery), DISTINCT from criterion 3's tie-set churn, which guards
shortlist-MEMBERSHIP stability; `ordinal_ok` governs publication of
the ordinal product specifically. Any earlier calibration story
anchoring 0.7 to an observed battery value is RETRACTED (reaffirmed,
recorded in the registry entry's history): it tuned the bar to a
measured row (e016_swap's rho 0.746) and that example fails criterion
3's own statistic anyway.

**Criterion 3 — margin-defined tie-set churn (DUAL THRESHOLD,
RATIFIED 2026-07-20).** The statistic is the maximum margin-defined
tie-set churn fraction across battery rows (§5c), replacing the hard
top-8 membership count (`screen_top8_churn_max`, superseded: rank-8 is
an arbitrary boundary; the decision object is the MARGIN-DEFINED tie
set). Because a window-length change alters the window UNIVERSE, the
two window-length rows (`window_10`/`window_15`) measure churn in a
COARSER host-shape unit (denominator 14 shapes) that a single scalar
cannot compare to the 46-window unit of the other rows; so each
comparison unit gets its OWN one-in-five cap:

- WINDOW-UNIT sub-threshold `screen_tie_churn_max_window` = 0.20
  (owner one-in-five over the 46-window tie set), applied to
  `shortlist_stability.aggregate.max_tie_churn_frac_window` — the max
  over the window-unit battery rows; for `gen_leave_class_out` the
  aggregate scans EVERY generator class (class max — the row's
  published entry is its min-Jaccard class tuple, and the two extremes
  need not coincide in one class, so per-row scanning alone could
  understate the statistic).
- HOST-SHAPE-UNIT sub-threshold `screen_tie_churn_max_hostshape` =
  0.142857 = 2/14 (one-in-five over the 14-shape set rounds to 2.8 →
  a 2-shape cap), applied to `max_tie_churn_frac_hostshape` — the max
  over `window_10`/`window_15`.

Criterion 3 passes IFF BOTH sub-thresholds pass.
`decision_output.criteria.tie_churn` carries `{window:
{max_over_window_unit_rows, threshold, worst_row, pass}, hostshape:
{max_over_window10_window15, threshold, worst_row, pass}}` — there is
NO top-level pass; `ordinal_ok` combines the two sub-passes. The
legacy hard-top-8 churn survives as a per-row DIAGNOSTIC column with
an explicit per-row UNIT field — 'window_id' for most rows,
'host_shape' for `window_10`/`window_15` (whose window sets differ
from the headline scan).

**Criterion-3 dual-threshold rationale (owner ratification 2026-07-20;
SUPERSEDES the PW batch's report-only exclusion — registry
`screen_top8_churn_max` history).** The two window-length rows are NOT
exempt from criterion 3 — the PW batch's choice to drop them from the
max is REVERTED. A length change alters the window UNIVERSE, so their
churn cannot be measured over window ids at all and is instead
measured in HOST-SHAPE units — a coarser 14-shape denominator (vs 46
windows; ONE flip reads 7.1% against 2.2%). Cross-universe membership
churn is a category mismatch, not a stability measurement, and a
single scalar threshold cannot compare the two units — so each unit
gets its own one-in-five cap (0.20 over 46 windows, 2/14 over 14
shapes) and the host-shape rows feed the parallel `hostshape`
sub-criterion above. Both rows also remain FULLY in criterion 2's
min-rho (the best-per-shape ranking comparison is unit-consistent) and
in the §5c report's per_row block; the aggregate no longer carries a
`criterion3_excluded_rows` list (`min_jaccard` stays an all-rows
REPORT aggregate — it feeds no criterion). The window-length
perturbation is the most decision-relevant in the battery and MUST
remain GATED, not decorative.

**Fail-safe rule.** ordinal_ok requires criterion 1, criterion 2, AND
both criterion-3 sub-thresholds to pass. With criteria 2/3 now LIVE
and owner-ratified, ordinal_ok is no longer "false by construction" —
it is FALSE because criteria FAIL on the measured numbers below.
Whenever any criterion fails the decision output is the THRESHOLD
SHORTLIST — all `tie_with_cutoff` windows grouped by host shape,
presented beside the measured indicators — and the ordinal index is
diagnostic-only. The rule is MECHANIZED: `screen_scan.py` writes the
artifact's `decision_output` block (§4) with the measured numbers, the
registry thresholds, per-criterion pass booleans, `decision_format`,
and the shortlist; a standing test recomputes pos_frac from the stored
replicate signs and every boolean from the stored numbers
(test_screen.py D6). Measured outcome (2026-07-20 ratification build):
ordinal_ok = FALSE — criterion 1 fails (b1_pos_frac 0.8115,
b2_pos_frac 0.7435 vs 0.841), criterion 2 fails (min rho = 0.39 < 0.7,
buffer_lo), criterion 3 fails BOTH sub-thresholds (window-unit 0.848 >
0.20 at e016_swap; host-shape 0.571 = 8/14 > 0.142857 at window_10,
with window_15 4/14 = 0.286 also over) — the screen delivers the
shortlist, not a ranking. README known issues 35 (opened) and 38
(owner review).

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

**FAILURE-MODE GATE (owner-ratified 2026-07-22 — criteria 2/3
re-scoped to attach BY FAILURE MODE, not by row id; registry
`screen_gate_failure_modes`).** The criterion-2/3 thresholds
(`screen_battery_rho_min` = 0.7, `screen_tie_churn_max_window` = 0.20,
`screen_tie_churn_max_hostshape` = 2/14) are UNCHANGED in VALUE. What
they RANGE OVER is re-scoped. The whole-battery min/max cannot survive
a geometry change across versions: `offset_variant`, `window_10`,
`window_15` are meaningless in the v2.4 ANCHOR world (no sliding
windows, no free length elasticity to pin), and `min_sep` is
meaningless in the WINDOW world — only `buffer` survives both. A
criterion whose row list changes meaning across versions cannot be a
frozen bar. So the criterion-2/3 subset is frozen BY FAILURE MODE.
Four failure modes (owner amendment 2026-07-22 added the FOURTH,
estimation-uncertainty; see its rationale below), each of which EVERY
version must instantiate with its own named row (or edge pair):

1. **catchment-width sensitivity** — the `buffer` perturbation
   (`buffer_lo`, `buffer_hi`), in BOTH worlds;
2. **spatial-resolution sensitivity** — the window-length perturbation
   (`window_10`, `window_15`, HOST-SHAPE unit) in the WINDOW world;
   the anchor min-separation perturbation in IDENTITY units
   (`min_sep`-identity, per docs/review-verification.md rule 6 — the
   anchor-lattice change is decomposed into no-longer-exists vs
   exists-but-moved, and this row scores the exists-but-moved part) in
   the ANCHOR world;
3. **specification sensitivity** — a predictor SWAP or ESTIMATOR
   variant (v2.0: `nb_estimator` or `e016_swap`; v2.1/v2.2:
   `popden_swap` / `e002_swap` / `gen_dummy_swap` / `nb_estimator`;
   v2.4-anchor: a designated swap row).
4. **estimation-uncertainty sensitivity (added 2026-07-22)** — the
   COEFFICIENT-SAMPLING perturbation. Its single row DRAWS b1/b2 from
   v2.2's EXISTING route-cluster coefficient bootstrap (§3.4 — no new
   fit; v2.4 reuses the committed v2.2 coefficients, and this row reuses
   that same bootstrap family), reranks the corridors on the v2.4
   discrete-corridor universe, and measures IDENTITY-UNIT membership
   churn at the top-8 cutoff (rule-6 identity metric per
   docs/review-verification.md: decompose no-longer-exists from
   exists-but-moved). Because a coefficient resample leaves the anchor
   LATTICE unchanged, no-longer-exists is empty and the churn is ALL
   exists-but-moved — pure ranking instability at the cutoff. Row:
   v2.4-anchor = `coeff_resample`; v2.0/v2.1/v2.2 documentary.

   **Rationale for a fourth mode (write it in).** The fit-materiality
   read showed the v2.2 coefficients SWAP 6 OF 8 shortlist members
   versus the coefficient-free (raw-catchment) ranking — so the
   coefficients are the largest single driver of membership. Their OWN
   sampling uncertainty (b1 sits at t = 1.49, a wide cluster SE) is
   therefore the perturbation MOST LIKELY to move the cutoff, and until
   this amendment it sat ENTIRELY OUTSIDE the gate — the whole-battery
   min never contained a coefficient-resample row. Homing it as a
   FOURTH mode (not folding it under specification) preserves the
   one-row-per-mode discipline: each mode contributes exactly one gated
   row, and estimation uncertainty gets its own. The alternative —
   folding it under specification — rests on the argument that
   estimation and specification uncertainty are the SAME KIND of threat
   (both perturb the fitted predictor→ranking map rather than the data
   geometry); that argument is real and recorded here, but the owner
   chooses the separate home so the load-bearing threat carries its own
   named, visible bar rather than being averaged into a swap row.

**Re-scoped criteria.** Criterion 2 = MIN Spearman rho over the FOUR
failure-mode rows (>= 0.7). Criterion 3 = MAX margin-defined tie-set
churn over them, keeping the DUAL-UNIT split of §5 where applicable:
the catchment-width, specification AND estimation-uncertainty rows are
window-unit (or the anchor-world's identity-window unit — the
estimation-uncertainty row's rule-6 churn is all exists-but-moved on a
fixed lattice, so it measures in the same identity-window unit as a
within-universe reranking) and feed `screen_tie_churn_max_window` =
0.20; the spatial-resolution row is host-shape-unit (window world) /
identity-unit (anchor world) and feeds
`screen_tie_churn_max_hostshape` = 2/14. The remaining battery
rows (`drop_fy2020`, `drop_rh` (retired for productivity), `svc_*`,
`overlap_*`, `year_fe_vs_pooled`, `loyo`, `loao`, the generator-class
rows, …) are NOT dropped — they become DISCLOSED DIAGNOSTICS reported
in `shortlist_stability` OUTSIDE the gate, so nothing is hidden; they
simply no longer set the pass/fail bar.

**Direction of the bar, stated deliberately (NOT hidden).** A min over
FOUR rows is noisier than a min over twenty, and in expectation an
EASIER bar to clear. That is the CORRECT direction for this problem:
the whole-battery min was dominated by rows that measure UNIVERSE
change (the rule-6 class) or perturbations orthogonal to the decision
(service-level, year-drop, overlap), not by the four sensitivities a
corridor ranking must actually be robust to. Scoping the gate to the
four genuine failure modes tests the right thing; that it is also
easier is a consequence, disclosed, not a reason. The threshold VALUES
are unchanged — only their SUPPORT is re-scoped.

**The fourth mode is the honest correction to that noise (added
2026-07-22).** Adding estimation-uncertainty makes the min over FOUR
rows noisier STILL than the min over three. That is stated, not hidden.
But this row differs in kind from the others: it CAN GENUINELY BIND. It
is the load-bearing threat — the coefficients drive 6 of 8 shortlist
members (above), and their sampling uncertainty is the perturbation
most able to move the cutoff. A gate whose noisiest new row is also its
most decision-relevant is MORE HONEST even though it is noisier: the
earlier three-mode gate could pass while leaving the single largest
membership driver entirely untested. The added noise buys a gate that
tests the thing most likely to break the ranking.

**Frozen-artifact invariance (binding).** This re-scoping is
FORWARD-LOOKING: it binds the v2.4 gate. It does NOT re-run and does
NOT alter the v2.0 / v2.1 / v2.2 verdicts, which were computed with
criteria 2/3 over the FULL battery and whose artifacts stay
byte-identical (b88f9b65 / 83aeb032 / 3b1d5526). The per-version
row→mode mapping in `screen_gate_failure_modes` is DOCUMENTARY for
those three (it names which rows WOULD have carried each mode); it is
NORMATIVE for v2.4. The full-battery min-rho / churn statistics remain
published in every artifact's `shortlist_stability` as diagnostics.

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
max_tie_churn_frac_window (criterion 3's window-unit sub-statistic,
the max over the window-unit rows) and max_tie_churn_frac_hostshape
(the host-shape sub-statistic, the max over window_10/window_15) — the
§5 DUAL threshold, no rows excluded — and the
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
| `screen_battery_rho_min` | 0.7 | constant | judgment (criterion 2; RATIFIED LIVE 2026-07-20 — kept at 0.7, provisional marker removed; the ordinal product's own uncalibrated floor expected to be slack; calibration story retracted) | quality-knob (consumption verified by the `screen` scan) | — |
| `screen_top8_churn_max` | 2 | constant | judgment — SUPERSEDED 2026-07-20 (criterion-3 statistic rebuilt as a DUAL THRESHOLD of margin-defined tie-set churn; successors `screen_tie_churn_max_window` / `screen_tie_churn_max_hostshape`; hard top-8 churn demoted to a unit-tagged diagnostic) | superseded | — |
| `screen_tie_churn_max_window` | 0.20 | constant | judgment (criterion 3 window-unit sub-threshold, OWNER-RATIFIED 2026-07-20; one-in-five over the 46-window tie set) | quality-knob (consumption verified by the `screen` scan) | — |
| `screen_tie_churn_max_hostshape` | 0.142857 | constant | judgment (criterion 3 host-shape-unit sub-threshold, OWNER-RATIFIED 2026-07-20; 2/14 = one-in-five over the 14-shape set → 2-shape cap; governs window_10/window_15) | quality-knob (consumption verified by the `screen` scan) | — |
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

**Vintage-consistency drops (owner adjudication 2026-07-20;
pre-registered, measured facts recorded — the fit stays unrun).** Two
drop rules follow from vintage consistency and are fixed here before
the phase-2b fit:

- **FY2017 Express drop.** Routes 53X/57X/64X HAVE FY2017 boardings
  (228,478 / 1,145,261 / 615,387) but the FY2017 archived feed carries
  NO Express shape — they do not exist as separate GTFS routes until
  FY2019. A catchment computed on a FY2019 shape for a FY2017 boardings
  year would reintroduce the exact vintage mismatch this rebuild
  removes, so the 3 FY2017 Express route-years are DROPPED (never
  matched to a FY2019 shape). Those routes still contribute their
  FY2019+ rows.
- **Shapeless-route rule (general, pre-registered).** A route-year
  whose route has NO contemporaneous shape in that fiscal year's
  archived feed is DROPPED: a catchment is uncomputable without a
  shape, and carrying it on a wrong-year shape is explicitly REJECTED
  as reintroducing the vintage mismatch. Recorded per fiscal year; the
  measured extended-panel accounting (which route-years, total) is in
  §9.9.7.

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

**STOPPING RULE WITH A NUMERIC FLOOR (owner-ratified 2026-07-22 — the
softened §9.5 governed-method path gets a TERMINUS for the stage-1
arc).** The softened §9.5 correctly refuses a false permanence promise,
but as written it always resolves to "keep going": there is no numeric
condition under which stage 1 STOPS. That is fixed here, before the
v2.4 fit exists (the legitimacy condition below). **v2.4 (the
benefit-per-cost BCA-queue build, §12) is the LAST method attempt of
the stage-1 arc.** Its result resolves to exactly one of two branches,
and EITHER branch stops stage 1:

- **(a) DECISION-GRADE queue.** v2.4 is decision-grade IFF the
  full-ranking Spearman rho on the **failure-mode subset** (the FOUR
  §5 failure-mode rows — catchment-width / spatial-resolution /
  specification / estimation-uncertainty — criterion 2 as re-scoped
  above) is >= 0.7 [screen_battery_rho_min]. (The bar is the EXISTING
  criterion-2 value 0.7, NOT the 0.79 / 0.87 anchor-world de-risk
  PREVIEW — those previews were cheap reads seen before the fit and do
  not set the bar; the §12 non-transfer note applies.) **The item-9
  external-validity check (§12.1) is SUFFICIENT-BUT-NOT-NECESSARY, NOT a
  second necessary condition (owner option b, resolved 2026-07-22 —
  supersedes the earlier "two necessary conditions" AND form).** Its
  role is:
  - an item-9 **PASS** (both clean arterial benchmarks in the top-8) is
    **CONFIRMATORY** — it strengthens branch (a) but is not required to
    reach it;
  - an item-9 **MISS** does NOT by itself veto the stage. §12.1 concedes
    that with n = 2 clean benchmarks one clean miss is WEAK evidence
    (funding / political / mode confounds), so it cannot unilaterally
    force the null. A miss instead TRIGGERS a **documented
    confound-review** under the already-frozen §12.1 miss semantics — is
    the miss a benchmark confound (grant/political/mode) or a genuine
    screen failure? — and that recorded finding decides ship-vs-null. A
    miss is NOT an automatic null.

  On (a) (failure-mode rho >= 0.7, and any item-9 miss resolved by the
  confound-review to "benchmark confound"): SHIP the benefit-per-cost
  queue; gate 1 consumes it per §4b; `config/candidates.json` may take
  `hand_supplied: false`.
- **(b) DOCUMENTED NULL.** Otherwise — failure-mode rho < 0.7, OR an
  item-9 miss that the confound-review finds to be a GENUINE screen
  failure — SHIP the finding that **OC demand does not separate
  corridors**: the threshold shortlist stays the permanent stage-1
  output and `config/candidates.json` stays `hand_supplied: true`. This
  is a real result, published as such, not a failure to be retried.

**This branching is decided NOW, before any v2.4 number exists —
including the sufficient-but-not-necessary status of item-9 and the
confound-review disposition of a miss — precisely so it cannot be
relitigated AT the miss. Whether a miss is a benchmark confound or a
screen failure is answered under the §12.1 semantics that were frozen
before the queue was ranked; the finding is recorded, not chosen after
seeing which corridors missed.**

Either way **stage 1 STOPS.** A stopping rule written NOW — before the
v2.4 numbers exist — is legitimate; one written AFTER seeing the next
result is not (it would be a stop tuned to a number already seen). That
timing is the rule's entire warrant, the same warrant every §9/§10/§11
pre-registration rests on.

**CLOSED LIST of what licenses a v2.5 (nothing else does).** Only a new
EMPIRICAL INPUT re-opens the arc, and only these three:

1. new route-level RVH from a **records request** (an OC or regional
   agency's line-level revenue hours that were not public before);
2. a **new agency panel** (an agency clearing the §11 D2 availability
   test — public route-level boardings AND RVH joinable to GTFS — that
   the recon did not land);
3. a **materially different data source** (e.g. a systemwide stop-level
   APC extract, or a non-commute demand fabric).

**Internal refinement of an existing source does NOT count** — a new
estimand on the same data, a re-vintaged predictor, a re-geometry of
the same scan, a wider bootstrap: none re-open the arc. Those are the
moves §9.5 already bars as same-data re-runs. v2.5 requires NEW
evidence, not a new way of reading the old evidence.

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

### 9.9 PANEL-EXTENSION ADDENDUM (owner directive 2026-07-20; governed design change under the softened §9.5)

**Owner directive, verbatim: "extend the panel" (2026-07-20).** The
directive was made on the power arithmetic alone — the design-stage
power check read criterion 1 as UNDERPOWERED at the committed v2.0
effect sizes (required-at-80% ~ 0.32/0.19 vs estimates 0.099/0.087,
outputs/screen_power_check.json) — and BEFORE any v2.1 fit exists.
This addendum is the governance-rule-3 record of that design change
(README known issue 39): a method change that is owner-approved,
spec-amended, and logged, exactly the governed path §9.5 reserves.
Everything §9 froze stays frozen: predictor set (§9.1), catchment
rule (§9.2), estimator/tripwire/decision rule (§9.5), battery
membership (§9.8 — the 20-row [screen_battery_rows_v21] list is
UNCHANGED by this addendum).

**9.9.1 Frozen extended year set (availability facts only).** The
extraction (scripts/extract_apc_ext.py, Legistar board-record Q4
detailed reports) landed, with passing validation, EXACTLY four new
fiscal years: **fy2020 (full year, 61 routes), fy2021 (50), fy2022
(53), fy2023 (54)** — 218 route-year rows,
data/derived/route_boardings_ext.csv. The extended year set is frozen
on those availability facts and nothing else:

- Landed set: {fy2020, fy2021, fy2022, fy2023}. NOT landed, with the
  reason on record: FY2013-FY2016 (the older Transit Division report
  format has no route-level table at all), FY2018 (both known copies
  embed the tables as raster image strips — unextractable without
  OCR), FY2024+ (the quarterly report family ends at Q4 FY2022-23;
  the successor bimonthly deck carries no route-level statistics).
  The §9.9.2 pre-2017 vintage clause is therefore MOOT — no pre-2017
  FY landed (the 2013/2015 LODES raws stay staged-only contingency,
  no derived tables built).
- The extended fit panel year set is {fy2017, fy2019, fy2020,
  fy2021, fy2022, fy2023}: **fy2020 full-year SUPERSEDES fy2020q3**
  (the committed cell is its 9-month subset; the two never co-enter
  a fit — one FY, one row per route). Availability fact: every
  committed fy2020q3-fittable route has an ext fy2020 row, so the
  supersession drops no cluster.
- Row universe, frozen as landed: fittable = boardings present AND
  validated RVH present, from route_boardings.csv (fy2017/fy2019)
  UNION route_boardings_ext.csv (the four new FYs). The single
  blank-RVH cell (route 560, fy2022, KNOWN_DUP_RVH_EXT) drops by
  that rule. NO boardings floor is applied to the new FYs — the ext
  table enters the phase-2b fit exactly as landed (the committed
  FY2017/FY2019 universe keeps its LEGACY_MIN_BOARDINGS floor; that
  asymmetry is an availability fact of the two landed tables, and
  widening the committed years' universe remains a separate governed
  edit recorded at the apc_fy17_19_20 registry entry). Pre-stating
  the no-floor rule NOW closes it as a post-fit tuning knob.

**9.9.2 Vintage map for the new rows (extends the §9.3 table; the
resolve_vintage dispatch is the single mechanical source).**

| boardings year | LODES (OD + WAC) | ACS 5-year | note |
|---|---|---|---|
| fy2020 (full) | 2019 vintage | 2015-2019 | carries the committed fy2020q3 rule: 2019 is the last pre-shock enumeration; LODES 2020 embeds the shock, not the fundamentals the screen ranks |
| fy2021 | 2021 vintage | 2017-2021 | both acquired this batch; ACS 2017-21 is the FIRST 5-yr vintage published on 2020 tracts — no tract10-to-tract20 bridge for these rows (registry acs_2021_5yr, lodes_od_2021, lodes_wac) |
| fy2022 | 2022 vintage | 2019-2023 | the committed scan-side tables (nearest acquired vintages) |
| fy2023 | 2022 vintage | 2019-2023 | DECISION, stated: LODES8 now ships 2023 (the acquisition batch's premise correction; CA od+wac 2023 raws are STAGED with sidecars) — but FY2023 rows are FROZEN on the 2022 vintage for this design: the nearest-vintage disposition as registered at lodes_2022, no 2023 derived tables built. Re-vintaging FY2023 to LODES 2023 is a governed later amendment, not a silent swap |
| pre-2017 FYs | — | — | none landed; clause moot (nearest-LODES + stated-ACS rule would have applied) |

**9.9.3 Shape-vintage policy.** UNCHANGED from §9.4: fit-side
catchments for ALL years — the original three AND the four new FYs —
remain gated on the archived-GTFS acquisition (the owner's Mobility
Database token; no archived-GTFS data-tier entries exist until it
lands). The design-stage POWER CHECK may use the current-shape
(2026-07 GTFS) stylization for every year, stated as such in its
artifact: l_len is time-invariant under it, and routes with no
2026-07 shape enter only as X-replica clusters. Consequence of the
extension, on availability facts: 9 ext routes DO have 2026-07
weekday shapes (76, 123, 177, 453, 472, 473, 480, 553, 862), so the
current-shape fit universe grows 41 -> 50; 13 union routes have
fittable rows but no current shape (the §9.4 six — 24, 82, 153, 53X,
57X, 64X — plus 87, 206, 213, 463, 701, 721, 794), so the
with-replicas design grows 47 -> 63. The §9.4 fit/scan asymmetry and
the archived-GTFS re-entry plan are unchanged.

**9.9.4 Validation protocol for route_boardings_ext.csv (all gates
standing in scripts/test_extract_apc_ext.py + the extractor).**

1. Per-row 2dp interval gate: every emitted row reproduces the
   printed Board/VSH column to 2dp (the house protocol, imported
   from extract_apc.py — same code path as the committed table).
2. Anchor cross-validation (G3): the same parser on the Legistar
   FY2017/FY2019 Q4 copies reproduces EVERY committed
   route_boardings.csv cell exactly — all boardings, all RVH,
   including the three KNOWN_BAD_RVH blanks failing 2dp identically.
3. Within-FY2020 coherence (G4): full-year boardings >= the
   committed 9-month fy2020q3 for every shared cell; the six RVH
   cells printed BELOW the 9-month YTD (150/529/53X/560/57X/64X) are
   recorded as COVID Express-suspension source revisions in the Q4
   print, both prints passing their own 2dp checks.
4. FYTD bound (G5): the two Q2 fiscal-year-to-date reports are
   cross-checks only (their annual-looking headers sit over YTD
   data — the extraction's source correction); FYTD <= annual for
   every route in both, and no route appears in a Q2 file but not
   the annual.
5. Known defect, frozen: ONE blank RVH cell (560, fy2022,
   KNOWN_DUP_RVH_EXT — the source's two sort-order tables print RVH
   variants 22,387/22,382 with boardings agreeing; neither is
   forensically preferable, so boardings kept, RVH blank; the
   KNOWN_BAD_RVH precedent).
6. Schema, uniqueness, new-FY-only labels (T8); deterministic
   byte-identical rebuild (sha256 e39f74f3...aed5c); per-FY
   provenance sidecars (URL, bytes, sha256, Legistar matter id)
   under data/raw/apc_ext/.

**9.9.5 Contamination guard (restated, extended).** The new
route-year boardings are OUTCOME data. Their EXISTENCE (which
route-years) informs this design; their VALUES are never regressed
on or joined to any predictor matrix until phase 2b. The power
check's re-run reads route_boardings_ext.csv through a guarded
loader for (i) the presence mask and (ii) the validated RVH values
ONLY (RVH is the b3 predictor passthrough, exactly the committed
table's load_rvh treatment); boardings values are dropped inside the
loader and never leave it (test_screen_power.py G1/G2, extended).
The blanket module ban in test_extract_apc_ext.py T7 carries the
single corresponding carve-out for scripts/screen_power.py — every
other predictor/fit module stays banned. The power machinery keeps
consuming ONLY the committed v2.0 variance decomposition
(screen_v20_resid_decomp); no variance is re-estimated from any new
data.

**9.9.6 Power-check re-run (this batch).** scripts/screen_power.py
gains a panel_ext block in outputs/screen_power_check.json: same
grid/S/B/seed/criterion knobs [screen_power_check], same v2.0
variance decomposition, vintage-matched X per §9.9.2 for every
route-year, extended-panel year FE (5 FE + intercept + 5 slopes),
BOTH designs (50 current-shape clusters; 63 with X-replicas — the
donor-replication stylization carried over, donors = the N
lowest-l_flows fitted routes at the fy2019 vintage), an explicit
BEFORE/AFTER required-elasticity table against the committed 3-year
numbers, and the verdict recomputed under the pre-stated registry
rule (with-replicas design vs the committed v2.0 estimates +/-
verdict_se_mult cluster SEs). The extended panel's frozen year list
is the registry constant [screen_panel_ext_fys], consumed via
val(). The baseline 3-year blocks are regenerated bit-identically
(same seed stream, drawn first); the artifact remains deterministic
(dual fresh-process byte-identity, a standing gate).

**9.9.7 Universe-key amendments + drop accounting (owner adjudication
2026-07-20; measured/availability facts recorded — the fit is NOT
recomputed here).**

- **Route-id case normalization (join-key amendment).** The fit-side
  APC↔GTFS join case-normalizes route ids, so APC 53X/57X/64X match
  the archived GTFS 53x/57x/64x. This is a post-acquisition change to
  a universe-determining key, disclosed here (governance rule 3): it
  adds the three Express routes to the recoverable set on FY2019
  shapes.
- **Contemporaneous-shape drop accounting.** Applying the §9.3
  vintage-consistency drops to the extended panel: the shapeless feed
  routes are overwhelmingly branch variants (150A/29A/42A/47A/79A) and
  suspended Express (53x/57x/64x) that carry NO boardings; the only
  boardings-carrying route-year the shapeless rule removes is
  **529/fy2022** (86,674 boardings) — route 529 does NOT appear at all
  in the fy2022 archived feed (octa_gtfs_fy2022_20211224.zip), i.e. it
  has no contemporaneous shape by absence; it re-enters with resolved
  shapes in the fy2020 and fy2023 feeds, so only its fy2022 row drops
  → **1 route-year**. Added to the **3 FY2017 Express route-years**
  (§9.3), the total contemporaneous-shape drop from the extended panel
  is **4 route-years** (3 FY2017 Express + 1 shapeless
  boardings-carrying). These are availability facts recorded now; no
  coefficient is fitted.

  **Correction (governance rule 3, 2026-07-21).** An earlier draft of
  this accounting also dropped **553/fy2023** (266,142 boardings) as
  shapeless, giving a total of 5. That was a MISCOUNT: route 553 IS
  present in the fy2023 archived feed
  (octa_gtfs_fy2023_20230210.zip, snapshot 2023-02-10) as route_ids
  553_merged_10882877 and 553_merged_10882878, each 74 trips on
  weekday service MTUWTF (Mon–Fri; calendars 20221010–20230211 and
  20230212–20230513, which bracket the snapshot), carrying shape_ids
  5535/5536/5537/5538 that ALL resolve in shapes.txt. So 553/fy2023
  has a fully-resolved contemporaneous WEEKDAY shape and, under the
  pre-registered shapeless-route rule (§9.3 — a route-year whose route
  has NO contemporaneous shape is DROPPED), must be KEPT, not dropped.
  This is also consistent with §9.9.3 (553 is among the routes that DO
  have weekday shapes). The corrected total is 4, not 5; the fit is
  unrun and the v2.0 artifact is uncontaminated, so this is a
  report-only pre-registration correction that RESTORES a valid
  266,142-boardings weekday route-year to the phase-2b fit universe.

### 9.10 Regime-split gate (pre-registered; runs in phase 2b, NOT now)

The concrete pre-committed form of "materially different slopes",
fixed here before the phase-2b fit exists (registry
`screen_regime_split`). In phase 2b the demand block is fit THREE
ways:

- **POOLED** — all 6 fit-panel FYs (`screen_panel_ext_fys`);
- **PRE-2020-ONLY** — fy2017 + fy2019;
- **FULL-PANEL WITH INTERACTION** — a post2020 × {l_flows, l_zveh_hh}
  interaction added to the pooled design.

The v2.1 artifact REPORTS the pre-2020 b1/b2 bootstrap sign-fractions
and the interaction coefficients alongside the pooled fit.

**BINDING DOWNGRADE RULE (pre-committed).** If the POOLED demand block
PASSES tripwire criterion 1 but the PRE-2020-ONLY demand block does
NOT independently pass criterion 1 (the SAME `screen_pos_frac_min` =
0.841 bar, each demand coefficient), the pooled pass is DOWNGRADED to
reported-only: `ordinal_ok` is forced false, `decision_format` =
threshold_shortlist, and a `regime_split_downgrade` flag is set. This
is ONE pre-registered gate reusing the EXACT criterion-1 statistic —
it introduces NO new threshold beyond 0.841.

**Rationale.** Year FE absorb LEVEL shifts, not SLOPE changes; LODES
2021 measures remote-work-era workplace geography. A pooled pass that
the pre-period does not corroborate cannot be distinguished from a
pooling artifact — so it must not be published as a decision-grade
ordinal ranking. The gate is a §9.5-governed pre-registration (owner
review 2026-07-20, README known issue 40); the current v2.0 artifact
does not consume it.

## 10. v2.2 productivity estimand (governed-method-change, PRE-REGISTRATION 2026-07-21, written before any fit)

**This section is a pre-registration document, written and committed
2026-07-21 BEFORE any v2.2 fit has run — before a single productivity
coefficient has been computed or peeked at. Its entire epistemic value
is that timing: the estimand, the RHS, the criteria, the thresholds,
the battery, the scan/index design, the regime-split gate and the
reused universe below are all fixed while the productivity fit's
numbers are unknown, so a later pass or fail cannot be narrated as a
choice made after seeing the result. v2.1 (screen_results_v21.json,
sha 83aeb032) and v2.0 (screen_results.json, sha b88f9b65) stay
byte-identical: this is a NEW pre-registration, not an edit to a
landed artifact.**

**Owner directive (verbatim, 2026-07-21):** *"v2.1 failed
(ordinal_ok=FALSE) and the diagnosis is the §1 ENDOGENEITY, not data
quality: b3 (RVH) sits at t=22.5 while b1 sits at t=0.80, because
service is allocated on the same fundamentals the demand block
measures, so conditioning on RVH leaves the fundamentals nothing to
explain. Pre-register a v2.2 GOVERNED-METHOD-CHANGE (spec §9.5) with a
PRODUCTIVITY estimand, OC-only (NOT a cluster-base expansion — that is
a separate future decision)."*

**§9.5 basis (governed-method-change, not a same-spec re-run).** v2.1
ran ONCE under its pre-registration and FAILED the §5 tripwire on the
measured numbers (`ordinal_ok = FALSE`, README known issue 42): fit
universe 300 route-years / 63 clusters, headline b1_flows +0.121
(t≈0.80), b3_rvh +1.340 (t≈22.5), all three criteria fail, stable core
empty, and — decisively — the rebuild fixed every v2.0 INPUT defect
(vintage-matched X, block catchments, contemporaneous archived shapes,
six recovered routes, panel tripled) and b1 still moved only 0.099 →
0.121. Data quality was never the binding constraint; the §1
endogeneity was. Under §9.5 (permanence clause softened, owner review
2026-07-20) a documented, owner-approved CHANGE OF METHOD is the
sanctioned path forward once the pre-registered spec has failed —
GOVERNED (owner-approved, spec-amended, logged), never banned. A v2.2
is therefore NOT barred by the §9.5 no-re-run rule: re-running the §9
spec unchanged is barred (same inputs, same spec ⇒ same artifact by
the determinism gate), but a new estimand pre-registered before its
fit is exactly what §9.5 reserves. This section is the
governance-rule-3 record (README known issue 43). The v2.2 fit is NOT
implemented here — this batch pre-registers it; the fit is the
phase-2b-v22 batch.

The following decisions are FROZEN by this pre-registration.

### D1 — ESTIMAND (frozen)

The dependent variable is

    log(boardings / RVH) = productivity (boardings per revenue vehicle-hour).

**Pinned-coefficient identity.** log(b/RVH) = log(b) − log(RVH), so the
productivity regression IS the v2.1 LEVEL regression with the RVH
coefficient PINNED at +1 and MOVED to the LHS:

    v2.1 level:         log(b)      = a + b1·l_flows + b2·l_zveh + b3·log(RVH) + b4·l_genjobs + b5·l_len + yearFE + e
    v2.2 productivity:  log(b) − log(RVH) = a + b1·l_flows + b2·l_zveh +   (b3≡1)   + b4·l_genjobs + b5·l_len + yearFE + e

Pinning b3 at +1 and moving log(RVH) to the DV removes, in one step,
(i) the b1/b3 collinearity between the demand block and the allocation
control, and (ii) the tautology by which b3 (RVH), fitted freely at
+1.340 / t≈22.5 on the same fundamentals service is allocated on, leaves
the demand block nothing to explain. b3 no longer competes for the
fundamentals' variance because it is no longer estimated. **This is the
whole method change** — one degree of freedom removed by pinning, one
regressor moved to the LHS. Nothing else in §3's estimator, clustering,
bootstrap, output guardrails, §3.4 uncertainty machinery or §5 tripwire
changes.

### D2 — RHS (frozen)

    b1  log1p(LODES both-ends-in flows)          [demand block]
    b2  log1p(B25044 zero-vehicle HOUSEHOLDS)     [demand block]
    b4  log1p(WAC generator jobs, CNS15-18)       [outside the block; sign a diagnostic]
    b5  log(route length mi)                       [scale term]
    + year fixed effects (base fy2017; 5 FE over screen_panel_ext_fys)

**b3 (RVH) is GONE from the RHS** — it now lives in the DV denominator.
**NO agency FE** (OC-only, 63 clusters; a cluster-base expansion with
agency FE is explicitly NOT this pre-registration — owner directive).

**Length honesty (pre-registered, not pre-judged).** In v2.1 the length
loading was split b3+b5 across the free RVH control and the scale term
(≈+0.917/log-mile in v2.0; +1.340 − 0.340 = +1.000 in v2.1). With b3
removed and pinned into the DV, the RHS length loading is **b5 alone**
(v2.1's b5_len came back −0.340). The length artifact is therefore
EXPECTED to shrink — but this is a hypothesis for the fit to test, not
a foregone conclusion: if the ranking is still length-driven the
productivity move will not have helped. We pre-register KEEPING b5 and
the length battery rows (`window_10`/`window_15` host-shape;
`offset_variant` pins b5 to +1) and letting the fit show it; we do NOT
drop b5 and do NOT pre-judge the outcome.

### D3 — CRITERION 1 (carried over, reinterpreted)

Unchanged statistic: the demand block is DEFINED as {b1_flows,
b2_zveh}, and EACH must be strictly positive in ≥ `screen_pos_frac_min`
= 0.841 of the B=2000 route-cluster bootstrap replicates (§3.4, §5
criterion 1). **Reinterpretation under productivity:** the question is
now *do the fundamentals predict PRODUCTIVITY once the RVH tautology is
removed* (not *do they predict boardings conditional on RVH*, which
v2.1 answered no because RVH absorbed the variance). b4 (l_genjobs)
stays OUTSIDE the demand block; its per-replicate sign is a diagnostic,
and the `b4_wrong_sign` flag (§9.1, set when the point estimate is
negative — it WAS negative in v2.1, −0.094) carries over with its
governance-rule-3 obligation intact.

### D4 — THRESHOLDS (carried over UNCHANGED; the anti-tuning guarantee)

The v2.2 fit consumes the EXACT ratified v2.1 threshold values, via the
SAME registry ids — no new threshold entry is created:

| criterion | registry id | value |
|---|---|---|
| 1 — demand-block bootstrap pos-frac | `screen_pos_frac_min` | 0.841 |
| 2 — battery min Spearman rho | `screen_battery_rho_min` | 0.7 |
| 3a — window-unit tie-churn cap | `screen_tie_churn_max_window` | 0.20 |
| 3b — host-shape-unit tie-churn cap | `screen_tie_churn_max_hostshape` | 2/14 |

A governed-method-change changes the METHOD, never the decision bar.
Reusing the exact thresholds — the numbers set and ratified before v2.1
ran, that v2.1 then failed — is the anti-tuning guarantee: the bar
cannot be re-tuned to a method that might clear it, because the bar is
frozen from before. No `screen_*` threshold id is added, edited, or
re-tiered by this pre-registration. A standing test asserts the v2.2
thresholds resolve to the same `val()` as v2.1 (§ Tests below).

### D5 — BATTERY (frozen: `screen_battery_rows_v22`)

    screen_battery_rows_v22 = screen_battery_rows_v21
                              MINUS { drop_rh, svc_p25, svc_p75 }

The three dropped rows are UNDEFINED under productivity, on estimand
grounds decided here before the fit:

- **`drop_rh`** — RVH is no longer a predictor that can be dropped from
  the RHS; it is the DV denominator. "Fit without RVH" IS the v2.2
  headline, so a drop-RVH perturbation is vacuous.
- **`svc_p25` / `svc_p75`** — standardized-RVH-service scoring is
  RETIRED (D6): productivity is already exposure-normalized, so there
  is no svc_std service level to shift to p25/p75. Direct productivity
  prediction replaces the standardized-service machinery.

**Exact final v22 list (17 rows, order-exact):**

    ["buffer_lo", "buffer_hi", "window_10", "window_15", "drop_fy2020",
     "e016_swap", "e002_swap", "popden_swap", "genjobs_off",
     "genjobs_leave_class_out", "gen_dummy_swap", "nb_estimator",
     "offset_variant", "overlap_lo", "overlap_hi", "year_fe_vs_pooled",
     "loyo"]

Count = **17** ( = 20 − 3 ). All other v2.1 rows are KEPT because each
remains well-defined under productivity: the buffer, window-length,
overlap, year-FE and loyo rows perturb the catchment/universe/panel
(estimand-independent); the b1/b2/b4 swap rows (`popden_swap`,
`e016_swap`, `e002_swap`, `genjobs_off`, `genjobs_leave_class_out`,
`gen_dummy_swap`) perturb RHS predictors that are unchanged; `drop_fy2020`
drops rows; `offset_variant` pins b5 (length) to +1, which is orthogonal
to the RVH move (under productivity it moves log(length) to the LHS too,
giving log(b/(RVH·length)) with b5≡1 — well-defined).

**Flag (D5 obligation — a kept row whose FORM changes, stated not
hidden):** `nb_estimator` stays in the battery but its productivity
FORM is the count-model analogue of the pinned identity: an NB2 fit of
the boardings COUNT with **log(RVH) as a FIXED offset (exposure)** —
i.e. log(E[b]) = log(RVH) + Xβ, so log(E[b]/RVH) = Xβ, the canonical
rate model — NOT a free b3. This is the productivity translation of the
v2.1 NB2 row (which regressed the count with a free log(RVH) term); it
is well-defined, not ill-defined, so the row is KEPT (per the owner
directive) with its form pre-registered here. No other v21 row is
ill-defined under productivity; nothing is silently added or dropped
beyond `drop_rh` + `svc_p25`/`svc_p75`.

`screen_battery_rows_v22` is frozen NOW, before the v2.2 fit exists,
for the identical reason the v21 list was: the battery criterion is a
MIN, so membership edits after seeing v2.2 numbers would be a tunable
bar. Row changes from here are owner-approved §9.5 spec amendments.

### D6 — SCAN / INDEX (frozen design; code is the phase-2b-v22 batch)

The scan predicts **PRODUCTIVITY per window directly** — there is NO
standardized-RVH service input to the scoring design (that is the whole
point: RVH is gone from the RHS). The published index is predicted
productivity **relative to the median fitted route's predicted
productivity** (a same-exposure normalization; productivity is already
exposure-normalized, so no service level is injected). Concretely, in
the pinned identity every window's score is Xβ (year FE cancel, no
log(RVH) term), and index = 100·exp(win_pred − base) where base = the
lower-median over fitted host routes of each route's own BEST
window productivity — the §3.2/§4 same-exposure baseline stripped of
its svc_std term. The v2.1 `screen_svc_std` standardized-service
machinery (svc_std × window length in the `b3_rvh` scoring column) is
RETIRED for v2.2. This design is pre-registered here; the scan CODE is
NOT written in this batch (it is the phase-2b-v22 fit batch).

### D7 — REGIME-SPLIT (carried over unchanged, applied to productivity)

The §9.10 regime-split gate is unchanged: the productivity demand block
is fit THREE ways — POOLED (all 6 fit-panel FYs), PRE-2020-ONLY
(fy2017+fy2019), and FULL-PANEL WITH a post2020 × {l_flows, l_zveh_hh}
interaction — and the BINDING DOWNGRADE rule (`screen_regime_split`)
applies to the productivity fit: if the pooled block PASSES criterion 1
but the pre-2020-only block does NOT independently pass the same
`screen_pos_frac_min` = 0.841 bar, the pooled pass is downgraded to
reported-only (`ordinal_ok` forced false, `decision_format` =
threshold_shortlist, `regime_split_downgrade` set). The
pre-period-corroboration downgrade and its rationale carry over verbatim;
no new threshold.

### D8 — REUSE (unchanged from v2.1)

- **Vintage map (§9.3 + §9.9.2):** each boardings year keeps its
  vintage-matched X dispatch; unchanged.
- **Universe:** the SAME 300-route-year / 63-cluster panel over
  `screen_panel_ext_fys` = {fy2017, fy2019, fy2020, fy2021, fy2022,
  fy2023}, with the 4 contemporaneous-shape drops (53X/57X/64X fy2017 +
  529/fy2022, §9.9.7) and the KNOWN_BAD_RVH / KNOWN_DUP_RVH_EXT no-RVH
  drops (35/70/150 fy2017 + 560/fy2022) unchanged. **RVH is still
  REQUIRED on every kept route-year — now as the DV denominator rather
  than the b3 predictor**, so the DV log(b/RVH) is well-defined only
  where RVH > 0. Input-side accounting confirms this on the frozen
  universe (permitted §9.9.5 use — presence + RVH passthrough only, no
  predictor join, no fit): all 304 fittable route-years have RVH > 0
  and boardings > 0 (min RVH 981.00 rev-hr, min boardings 7,691); after
  the 4 pre-registered shapeless drops the **300 kept route-years / 63
  clusters are every one RVH > 0 and boardings > 0**, so log(b/RVH) is
  finite everywhere the v2.2 fit will read it. The 4 shapeless-dropped
  rows also carry RVH > 0 (8,857 / 35,484 / 16,135 / 5,521), so the
  drop is a shape-availability fact, never an RVH-definedness one.
- **Archived-shape catchments (§9.4)** and the **route_short_name /
  case-normalized join (§9.9.7):** unchanged. Same fit/scan asymmetry
  (fit on contemporaneous archived shapes, scan on current GTFS).

### D9 — PRE-COMMITTED VERDICT (softened §9.5, no permanence hardening)

The §5 tripwire (criteria 1/2/3 + the §9.10 regime-split downgrade)
governs the v2.2 productivity output IDENTICALLY. PRE-COMMITTED: if the
v2.2 productivity fit STILL fails the tripwire, the decision output
REMAINS the threshold shortlist plus the measured-indicator table (or
the narrower stable core per §4b when churn is heavy), the ordinal
index stays diagnostic-only, and the §9.5 governed-method-change path
stays OPEN for further documented, owner-approved changes — e.g. a
wider REGIONAL cluster base (LA Metro, Long Beach, Foothill, OmniTrans,
RTA, Big Blue Bus via NTD + archived GTFS + LODES + ACS, several
hundred clusters with agency FE), which is a SEPARATE future
pre-registration, not this one. There is NO permanence hardening: a
v2.2 failure is not "the screen is impossible," it is one more
governed estimand tested and recorded. Barred, as always: re-running
THIS §10 spec unchanged hoping for a different answer, predictor
shopping beyond D2, and threshold re-tuning after seeing the v2.2
numbers.

## 11. v2.3 regional-cluster-base estimand (governed-method-change, PRE-REGISTERED 2026-07-21, written before any fit)

**This section is a pre-registration document, written and committed
2026-07-21 BEFORE any v2.3 fit has run — before a single regional
coefficient has been computed or peeked at, and before the regional
inputs have been acquired. Its entire epistemic value is that timing:
the estimand, the panel-freezing RULE, the RHS, the criteria, the
thresholds, the battery, the scan/index design, the regime-split gate
and the reused OC universe below are all fixed while the regional fit's
numbers are unknown, so a later pass or fail cannot be narrated as a
choice made after seeing the result. v2.2 (screen_results_v22.json,
sha 3b1d5526), v2.1 (screen_results_v21.json, sha 83aeb032) and v2.0
(screen_results.json, sha b88f9b65) stay byte-identical: this is a NEW
pre-registration, not an edit to a landed artifact.**

**Owner directive (2026-07-21):** *v2.2 (productivity, OC-only) PASSED
criterion 1 — the endogeneity was the binding constraint on the demand
SIGNAL and the productivity move fixed it (b1_flows pos_frac 0.9075,
b2_zveh 0.9965 vs 0.841) — but FAILED criteria 2/3: the ranking is
still LENGTH-DRIVEN and unstable (offset_variant Spearman rho +0.207 vs
0.7). The remaining binding constraint is RANKING STABILITY. OC's 63
clusters do not pin the length/fundamentals relationship stably; fit on
a WIDER CLUSTER BASE — a regional panel of Southern California transit
agencies, with agency fixed effects — and score the
OC corridor windows from the regional fit. The key hypothesis: does the
wider cluster base rescue criteria 2/3 (ranking stability) the way
productivity rescued criterion 1?*

**§9.5 basis (governed-method-change, not a same-spec re-run).** v2.2
ran ONCE under its §10 pre-registration and FAILED the §5 tripwire on
the measured numbers (`ordinal_ok = FALSE`, README known issue 44):
criterion 1 PASSED (the productivity move rescued the demand signal),
but criterion 2 failed (battery min rho 0.2072 at offset_variant vs
0.7) and criterion 3 failed both sub-thresholds (window 1.4444 /
host-shape 0.4000), with the stable core EMPTY. Three estimands — v2.0
level / v2.1 rebuilt-input level / v2.2 productivity — have now failed
the tripwire on OC-only data; the diagnosis is now RANKING STABILITY,
not the demand signal (v2.2 fixed that) and not input quality (v2.1
fixed that). §9.5 (permanence clause softened, owner review
2026-07-20; D9 of §10 explicitly reserved "a wider REGIONAL cluster
base ... a SEPARATE future pre-registration") sanctions a documented,
owner-approved CHANGE OF METHOD once the pre-registered spec has failed
— GOVERNED (owner-approved, spec-amended, logged), never banned.
Re-running §10 unchanged is barred (same inputs, same spec ⇒ same
artifact by the determinism gate); a wider-panel identification
strategy pre-registered before its fit is exactly what §9.5 reserves.
This section is the governance-rule-3 record (README known issue 45).
The v2.3 fit is NOT implemented here — this batch pre-registers it and
runs the acquisition recon; the fit is the phase-2b-v23 batch.

The following decisions are FROZEN by this pre-registration.

### D1 — ESTIMAND (frozen: KEEP productivity)

The dependent variable is UNCHANGED from v2.2:

    log(boardings / RVH) = productivity (boardings per revenue vehicle-hour).

v2.3 REUSES `screen_estimand_v22` (no new estimand entry). Productivity
is the method that RESCUED criterion 1 on OC-only data; reverting to
the boardings LEVEL would re-inject the b1/b3 collinearity and the RVH
tautology §10 D1 removed. The regional change is to the PANEL and the
fixed-effect structure (agency FE), NOT to the estimand. RVH remains
the DV denominator on every kept route-year, regional agencies
included, so log(b/RVH) is defined only where RVH > 0 — an
acquisition-side requirement stated in the manifest.

### D2 — PANEL (frozen on ACQUISITION-AVAILABILITY FACTS, not fit results)

The fit panel is OC (OCTA) PLUS regional Southern California transit
agencies. Candidate set (pre-recon hypothesis): LA Metro, Long Beach
Transit, Foothill Transit, OmniTrans, Riverside Transit Agency, Big Blue
Bus (+ OCTA). The acquisition recon (this workflow) then applied the D2
freezing rule to actual availability and FROZE the panel to exactly the
availability-qualifying subset — see the **Acquisition-recon RESULT**
note below. The candidate set is NOT the fitted set: most of the
Los Angeles / San Bernardino candidates do not publish the route-level
boardings+RVH pair and are EXCLUDED with reason.

**FREEZING RULE (pre-registered, the entire point of this section's
timing).** The FINAL agency list is frozen on ACQUISITION-AVAILABILITY
FACTS ALONE — *which agencies publish public route-level annual
boardings AND revenue hours (RVH) at a vintage that joins to a GTFS
route shape* — exactly as v2.1's fit-panel YEAR set was frozen on
availability (§9.9.1) and v2.1's battery excluded `sld_swap` on an
acquisition fact (§9.8), NEVER on fit results. An agency enters the
frozen panel IFF the acquisition scouts land, with passing validation:
(i) public route-level boardings, (ii) route-level RVH (the DV
denominator — an agency with boardings but no published RVH cannot
enter, because log(b/RVH) is undefined without it), and (iii) a GTFS
feed whose route ids join to those route-level rows. The scouts (this
same workflow, acquisition-recon phase) report per-candidate
availability into the §11 manifest below; the agency list in
`screen_regional_agencies` is finalized to EXACTLY what they land,
before any coefficient is fitted. Freezing the panel on availability —
not on which agencies happen to stabilize the ranking — is the
anti-tuning guarantee for the identification set, the panel analogue of
the frozen battery: a panel edited after seeing v2.3 numbers would be a
tunable identification strategy.

The regional-panel YEAR set is frozen on the SAME availability facts
(each agency contributes the fiscal years for which the scouts land
validated route-level boardings + RVH joinable to a contemporaneous
GTFS shape); it is recorded per-agency in the manifest and consumed
alongside the agency list. The §9.3/§9.9.2 vintage-match dispatch
(each boardings year gets its own LODES/ACS vintage) extends to every
regional agency's service area — regional LODES OD+WAC and ACS B25044
are acquired at the matching vintages, the manifest states the
geography.

**Acquisition-recon RESULT (2026-07-21, this workflow — freezes the D2
panel on availability facts; corrects the candidate set and the cluster
count per the independent review's APPROVE-WITH-FIXES).** The recon
established the BINDING availability fact: only agencies publishing the
RCTC / TransTrack SRTP "Route Statistics Table 3" format expose
route-level annual boardings AND revenue hours TOGETHER — and the
productivity DV log(boardings/RVH) requires BOTH per route-year.
Applying the D2 freezing rule to exactly what the recon landed:

CONFIRMED-USABLE frozen panel (public route-level boardings + RVH,
recon-verified; source = the RCTC/TransTrack SRTP Route Statistics
tables at rctc.org / sunline.org, OCTA via its committed APC tables):

- OCTA (Orange, base agency) — 63 routes
- Riverside Transit Agency / RTA — ~36 routes
- SunLine Transit Agency — ~14 routes
- Corona Cruiser — ~3 routes
- Pass Transit / Banning + Beaumont — ~5 routes
- PVVTA / Blythe — ~4 routes

EXCLUDED — route-level boardings + RVH NOT both public (records-request
upgrade paths, NOT in the fitted set):

- **LA Metro** — route boardings public (metro.net) but NO line-level
  RVH; the LACMTA public-data README flags line-level revenue hours as a
  known public gap. Pair broken.
- **OmniTrans** (San Bernardino) — route-level RVH published but
  route-level boardings NOT published. Pair broken.
- **Long Beach Transit**, **Foothill Transit**, **Big Blue Bus** —
  boardings and RVH are published AGENCY-level only (NTD is an
  AGENCY-level source, not route-level); no public route-level pair.

**Corrected cluster count (minor finding).** The realistic,
availability-confirmed base is **~125 route-clusters** (OCTA 63 + RTA 36
+ SunLine 14 + the small RCTC/TransTrack city operators ~12), NOT the
"several hundred" originally hoped in the owner directive. That is ~2x
the OC-only 63-cluster base — a real widening, but an order of magnitude
short of the original aspiration. The D8 hypothesis (does the wider base
rescue criteria 2/3) is therefore tested on ~125 clusters, not several
hundred.

**Validity caveat (honest, pre-fit — changes NO frozen threshold,
estimand, or battery).** Every confirmed regional agency is a Riverside
County / Coachella Valley / desert-exurban operator (RTA, SunLine,
Corona Cruiser, Pass Transit, and PVVTA/Blythe are all Riverside County,
FIPS 06065), geographically and demographically distinct from dense
coastal/suburban Orange County. The agency fixed effect (D3) absorbs
LEVEL differences between agencies, but NOT SLOPE differences: if the
productivity-fundamentals slope differs between exurban Riverside and
dense OC, pooling — even with agency FE — is a HETEROGENEOUS-SLOPES
risk, directly analogous to the v2.1 regime problem (§9.10). This is
pre-registered as a RISK TO TEST, not an assumption: the §9.10
regime-split machinery (D7) and the `loao` leave-one-agency-out battery
row (D6, in `screen_battery_rows_v23`) are the instruments that will
EXPOSE the risk if it is present. This caveat changes no frozen
decision — it is honesty about what a ~125-cluster panel drawn almost
entirely from one neighboring exurban county can and cannot establish
about dense-OC corridor ranking.

### D3 — RHS (frozen; thresholds carried over UNCHANGED)

    b1  log1p(LODES both-ends-in flows)          [demand block]
    b2  log1p(B25044 zero-vehicle HOUSEHOLDS)     [demand block]
    b4  log1p(WAC generator jobs, CNS15-18)       [outside the block; sign a diagnostic]
    b5  log(route length mi)                       [scale term]
    + year fixed effects
    + AGENCY fixed effects (new; base = OCTA)

**b3 (RVH) is GONE from the RHS** — it lives in the DV denominator
(D1, carried from §10). The ONE structural addition versus v2.2 is
**AGENCY fixed effects**: each agency gets its own intercept, so the
demand and scale slopes are identified from WITHIN-agency variation and
the fit does not confound systematic cross-agency level differences
(fare policy, network maturity, reporting convention) with the
fundamentals. Base agency = OCTA, so the OC intercept is the reference
when scoring OC windows (D4).

**Thresholds CARRIED OVER UNCHANGED** — the exact ratified v2.1/v2.2
values via the SAME registry ids, NO new threshold entry:

| criterion | registry id | value |
|---|---|---|
| 1 — demand-block bootstrap pos-frac | `screen_pos_frac_min` | 0.841 |
| 2 — battery min Spearman rho | `screen_battery_rho_min` | 0.7 |
| 3a — window-unit tie-churn cap | `screen_tie_churn_max_window` | 0.20 |
| 3b — host-shape-unit tie-churn cap | `screen_tie_churn_max_hostshape` | 2/14 |

A governed-method-change changes the METHOD (the cluster base and the
FE structure), never the decision bar. Reusing the exact thresholds —
the numbers set and ratified before v2.1 ran, that v2.0/v2.1/v2.2 then
failed — is the anti-tuning guarantee: the bar cannot be re-tuned to a
method that might clear it, because the bar is frozen from before. No
`screen_*` threshold id is added, edited, or re-tiered by this
pre-registration.

### D4 — SCORING (frozen; fit regional, score OC)

Fit REGIONALLY (all frozen-panel agencies jointly, one pooled
productivity regression with year + agency FE). Apply the fitted
demand/scale slopes to the OC corridor scan windows for the published
index, using OCTA's agency FE (the base intercept) when scoring OC
windows. The scan universe is UNCHANGED from every prior version: OC
current-GTFS weekday shapes, sliding 12.5-mi windows (§3.2). Regional
agencies ENTER THE FIT ONLY — they are cluster base for identifying the
slopes; the ranked output is OC corridor windows, exactly as the
screen's §1 role requires. The productivity index is per §10 D6:
predict productivity per window DIRECTLY (year + agency FE cancel in
the pinned identity; no svc_std service input), index =
100·exp(win_pred − base) with base = the lower-median over fitted OC
host routes of each OC route's own BEST window productivity. The
regional fit changes WHERE the slopes come from, not the OC-window
scoring arithmetic.

### D5 — CRITERION 1 (unchanged)

The demand block is DEFINED as {b1_flows, b2_zveh}, and EACH must be
strictly positive in ≥ `screen_pos_frac_min` = 0.841 of the B=2000
cluster bootstrap replicates (§3.4, §5 criterion 1; the bootstrap now
resamples the REGIONAL route-clusters). Interpretation on the regional
panel: *do the fundamentals predict productivity within agency, once
the wider cluster base pins the relationship*. b4 (l_genjobs) stays
OUTSIDE the demand block; its per-replicate sign is a diagnostic, and
the `b4_wrong_sign` flag (§9.1, set when the point estimate is
negative — it WAS negative in v2.1 −0.094 and v2.2 −0.041) carries over
with its governance-rule-3 obligation intact.

### D6 — BATTERY (frozen: `screen_battery_rows_v23`)

    screen_battery_rows_v23 = screen_battery_rows_v22 (17 rows) PLUS loao

**`loao` — leave-one-AGENCY-out — is ADDED (judged well-defined).** It
is the regional analogue of `loyo` (leave-one-year-out): the statistic
is the min Spearman rho, over each refit that DROPS one non-OCTA
agency in turn, of the OC-corridor-window ranking versus the v2.3
headline OC-window ranking. It tests whether the OC ranking depends on
any single agency's clusters — the direct stability question the wider
base is meant to answer. Well-definedness: OCTA is NEVER dropped (the
OC agency FE is required to score OC windows and OCTA is the ranking
target), so `loao` enumerates the non-OCTA agencies; the expansion
premise guarantees ≥ 1 non-OCTA agency in the frozen panel, so the row
is always non-vacuous. Its comparison UNIT is the OC window ranking —
the SAME 46-window unit as `loyo` and the other window-unit rows — so
it participates in criterion 2's min-rho and criterion 3's window-unit
tie-churn max EXACTLY as `loyo` does. Caveat (stated, not hidden, the
`loyo`/fy2017 precedent): dropping an agency that contributes few
clusters barely perturbs the fit, so `loao`'s rho is expected slack for
small-panel agencies; that is a property of the design, and the row is
still GATED, not decorative.

**Exact final v23 list (18 rows, order-exact):**

    ["buffer_lo", "buffer_hi", "window_10", "window_15", "drop_fy2020",
     "e016_swap", "e002_swap", "popden_swap", "genjobs_off",
     "genjobs_leave_class_out", "gen_dummy_swap", "nb_estimator",
     "offset_variant", "overlap_lo", "overlap_hi", "year_fe_vs_pooled",
     "loyo", "loao"]

Count = **18** ( = 17 + 1 ). All 17 v22 rows are KEPT because each
remains well-defined on the regional panel: buffer/window/overlap/
year-FE/loyo perturb the catchment/universe/panel (estimand- and
FE-independent); `drop_fy2020` drops rows across all agencies;
`offset_variant` pins b5 to +1 (orthogonal to the agency-FE addition);
the b1/b2/b4 swap rows perturb RHS predictors that are unchanged in
form; `nb_estimator` keeps its §10 D5 productivity FORM (NB2 rate model
with log(RVH) as a fixed exposure offset), now fit on the regional
panel with agency FE.

**Flag (a kept row whose regional COVERAGE is degenerate, stated not
hidden):** `gen_dummy_swap` replaces the measured WAC generator term
(b4) with the legacy binary special-generator dummy from
`config/special_generators.json`, which is a HAND-CODED OC-ONLY list —
so on non-OCTA agency routes the dummy is identically zero. The row is
still well-defined (it computes) and still tests OC-side sensitivity to
the hand-coded generator list; it does NOT test regional generators
(the measured WAC term b4, acquired region-wide, is the regional
generator signal). This is a stated coverage property of the swap, the
regional analogue of the §10 nb_estimator form-flag; no other v22 row's
coverage changes on the regional panel.

`screen_battery_rows_v23` is frozen NOW, before the v2.3 fit exists,
for the identical reason the v21/v22 lists were: the battery criterion
is a MIN, so membership edits after seeing v2.3 numbers would be a
tunable bar. Criterion-2 min-rho and criterion-3 dual tie-churn are
UNCHANGED (§5); row changes from here are owner-approved §9.5 spec
amendments.

### D7 — REGIME-SPLIT (carried over unchanged, applied to the regional productivity fit)

The §9.10 regime-split gate is unchanged: the regional productivity
demand block is fit THREE ways — POOLED (all fit-panel FYs),
PRE-2020-ONLY (the regional panel restricted to pre-2020 boardings
years), and FULL-PANEL WITH a post2020 × {l_flows, l_zveh_hh}
interaction — and the BINDING DOWNGRADE rule (`screen_regime_split`)
applies: if the pooled block PASSES criterion 1 but the pre-2020-only
block does NOT independently pass the same `screen_pos_frac_min` =
0.841 bar, the pooled pass is downgraded to reported-only (`ordinal_ok`
forced false, `decision_format` = threshold_shortlist,
`regime_split_downgrade` set). The pre-period-corroboration rationale
carries over verbatim; no new threshold.

### D8 — PRE-COMMITTED VERDICT (softened §9.5, no permanence hardening)

The §5 tripwire (criteria 1/2/3 + the §9.10 regime-split downgrade)
governs the v2.3 regional output IDENTICALLY. **The KEY hypothesis
under test is whether the wider cluster base rescues criteria 2/3
(ranking stability) the way the productivity estimand rescued criterion
1** — nothing here pre-judges whether it will. PRE-COMMITTED: if the
v2.3 regional fit STILL fails the tripwire, the decision output REMAINS
the threshold shortlist plus the measured-indicator table (or the
narrower stable core per §4b when churn is heavy), the ordinal index
stays diagnostic-only, and — the pre-registered interpretation of a
FAIL here — **OC corridor RANKING is not achievable even with regional
identification, so the threshold shortlist stays the PERMANENT stage-1
output** and `config/candidates.json` stays `hand_supplied: true`. That
is a documented outcome, NOT a permanence HARDENING of the screen: the
§9.5 governed-method-change path stays OPEN for further owner-approved
changes, and a v2.3 failure is one more governed estimand tested and
recorded, not "the screen is impossible." Barred, as always: re-running
THIS §11 spec unchanged hoping for a different answer, panel/predictor
shopping beyond D2/D3, and threshold re-tuning after seeing the v2.3
numbers.

### §11 acquisition manifest (FILLED by the recon; source attribution corrected)

Per-file provenance sidecars under `data/raw/`; raw files stay
untracked. An agency enters the frozen `screen_regional_agencies` list
IFF all three of {route-level boardings, route-level RVH, joinable GTFS
shapes} land with passing validation (D2 freezing rule). **Source
attribution corrected (major finding 1, independent review 2026-07-21):
the earlier manifest set the source to "NTD route-level ..." — WRONG.
NTD is an AGENCY-level source, not route-level.** The only public source
exposing route-level boardings AND RVH together is the RCTC/TransTrack
SRTP "Route Statistics Table 3" format; each row below carries its TRUE
per-agency availability status.

| agency | county FIPS | route-level boardings + RVH source | GTFS feed (mdb id) | status |
|---|---|---|---|---|
| OCTA (Orange) | 06059 | committed APC tables (route_boardings.csv + _ext) | committed OCTA GTFS (§9.4/§9.9.3) | LANDED — CONFIRMED-USABLE (base agency, 63 routes) |
| Riverside Transit Agency | 06065 | RCTC/TransTrack SRTP Route Statistics Table 3 (rctc.org) | mdb-98 | CONFIRMED-USABLE (~36 routes) |
| SunLine Transit Agency | 06065 | SunLine SRTP Route Statistics (sunline.org) | per feeds recon (Mobility Database) | CONFIRMED-USABLE (~14 routes) |
| Corona Cruiser | 06065 | RCTC/TransTrack SRTP Route Statistics Table 3 (rctc.org) | per feeds recon | CONFIRMED-USABLE (~3 routes) |
| Pass Transit (Banning+Beaumont) | 06065 | RCTC/TransTrack SRTP Route Statistics Table 3 (rctc.org) | per feeds recon | CONFIRMED-USABLE (~5 routes) |
| PVVTA / Blythe | 06065 | RCTC/TransTrack SRTP Route Statistics Table 3 (rctc.org) | per feeds recon | CONFIRMED-USABLE (~4 routes) |
| LA Metro | 06037 | route boardings public (metro.net) but NO line-level RVH — LACMTA public-data README flags it as a known gap; pair broken | Metro GTFS (current + archived) | EXCLUDED (route-RVH-missing); records-request upgrade path |
| OmniTrans (San Bernardino) | 06071 | route-level RVH published but route boardings NOT published; pair broken | OmniTrans GTFS | EXCLUDED (route-boardings-missing); records-request upgrade path |
| Long Beach Transit | 06037 | boardings + RVH AGENCY-level only (NTD is agency-level, not route-level) | LBT GTFS | EXCLUDED (agency-level-only); records-request upgrade path |
| Foothill Transit | 06037 | boardings + RVH AGENCY-level only (NTD is agency-level, not route-level) | Foothill GTFS | EXCLUDED (agency-level-only); records-request upgrade path |
| Big Blue Bus (Santa Monica) | 06037 | boardings + RVH AGENCY-level only (NTD is agency-level, not route-level) | BBB GTFS | EXCLUDED (agency-level-only); records-request upgrade path |

Confirmed-usable cluster estimate: OCTA 63 + RTA 36 + SunLine 14 +
Corona Cruiser 3 + Pass Transit 5 + PVVTA/Blythe 4 = **~125
route-clusters** (~2x OC-only). The excluded agencies stay named here as
EXCLUDED-with-reason and as records-request upgrade paths — they are NOT
in the fittable set.

Regional predictor sources extend the §9.6/§9.9 manifests to each
landed agency's service-area geography: LODES OD + WAC (both-ends flows
+ CNS15-18 generator jobs) and ACS B25044 zero-vehicle households (+
B01003 for `popden_swap`), acquired at the §9.3/§9.9.2 vintages
matching each agency's boardings years; TIGER block centroids for the
§9.2 catchment membership. Status columns filled by the acquisition
reports; the frozen agency list, per-agency year set, and predictor
geographies are finalized to what the scouts land, before any fit.

**What the scouts must confirm to finalize the panel (per candidate
agency):** (1) a PUBLIC route-level ANNUAL boardings series (NTD
route-level tables or the agency's own open-data portal), with the
fiscal years covered; (2) a PUBLIC route-level REVENUE-HOURS series at
the same vintage (REQUIRED — the DV denominator; an agency with
boardings but no published route-level RVH does NOT enter); (3) a GTFS
feed (current, and archived for pre-current boardings years) whose
route ids join to the route-level rows; (4) LODES + ACS coverage of the
service-area geography at the matching vintages. The agency list
`screen_regional_agencies` is then frozen to exactly the candidates
that clear (1)-(4).

## 12. v2.4 governance pre-commitments (owner-ratified 2026-07-22; written before the v2.4 fit)

**This section is a pre-commitment document, ratified and committed
2026-07-22 BEFORE the v2.4 benefit-per-cost BCA-queue build has run —
before any anchor-world corridor has been ranked. It is GOVERNANCE
STRUCTURE, not a measurement: it adds the frame the v2.4 thresholds
attach to (the failure-mode gate), the terminus for the stage-1 arc
(the numeric stopping rule), the external-validity pre-registration
below, and the stage-2 scoping — none of which changes a frozen
threshold value, estimand, or committed battery id list. The three
frozen artifacts stay byte-identical (v2.0 b88f9b65 / v2.1 83aeb032 /
v2.2 3b1d5526). The v2.4 pre-registration PROPER (estimand, RHS,
anchor-lattice scan design, index) is a SEPARATE later batch; this
section fixes only the governance that must predate it.**

The batch has five owner-ratified pre-commitments; the other four are
recorded at their canonical anchors and cross-referenced here so §12 is
the single landing page for the v2.4 governance:

- **Failure-mode gate** — §5 (**FAILURE-MODE GATE**) + registry
  `screen_gate_failure_modes`: criteria 2/3 re-scoped to range over the
  FOUR failure-mode rows (catchment-width / spatial-resolution /
  specification / estimation-uncertainty — the fourth added 2026-07-22),
  not the whole battery, threshold VALUES unchanged.
- **Stopping rule with a numeric floor** — §9.5 (**STOPPING RULE WITH
  A NUMERIC FLOOR**): v2.4 is the LAST stage-1 method attempt; branch
  (a) decision-grade iff failure-mode rho >= 0.7 (the §12.1 item-9 check
  is SUFFICIENT-BUT-NOT-NECESSARY — a PASS is confirmatory, a MISS
  triggers a documented confound-review, not an automatic null), branch
  (b) documented null; closed v2.5 list.
- **External-validity check** — §12.1 below (item-9).
- **Delegation with two guards** — docs/review-verification.md
  (**Delegation**) + outputs/DELEGATED_CHANGES.md (the accumulating
  log).
- **Stage-2 scoping** — §12.2 below, mechanized in spec 07 §4.3 and
  spec 00 §3.

### 12.1 External-validity check (item-9; pre-registered before any v2.4 run)

**Concession first (the e016 error, conceded in the text).** An earlier
framing set the external-validity bar as "Harbor lands in the top ~10."
That bar was anchored to a preview RANK ALREADY SEEN — the same class of
error as scoring on B08141 E016 (§1): a target read off the data before
the test is not an out-of-sample test. The bar is REDEFINED here so its
N, its benchmark set, and its miss semantics are all fixed before the
v2.4 queue exists.

**N FROM CONSUMPTION, not from a preview.** The gate-1 memo consumes the
TOP OF THE QUEUE (spec 00 §3: top 5-8 corridors + ties; §4b). The
external-validity N is set to the consumption ceiling: **N = 8**. The
claim under test: OCTA's own revealed arterial-ALM corridor choices
should land in the **top 8** of the v2.4 benefit-per-cost queue.

**Non-transfer note (binding).** The preview that produced the old
"~10" bar ranked corridors by RAW catchment. v2.4 ranks by
BENEFIT-PER-COST (a cost model over an anchor-lattice queue). The raw
preview rank therefore does NOT transfer to the v2.4 ordering — a
corridor's raw-catchment rank and its benefit-per-cost rank are
different objects. Stated so no one re-imports the preview number as a
prior on the v2.4 result. (This is also why §9.5's stopping rule reads
the criterion-2 value 0.7, not the 0.79/0.87 anchor-world previews.)

**Benchmark set, honestly scoped (n = 3, really 2 clean).**

- **Bravo! / Harbor (Route 543 corridor)** — an arterial rapid-transit
  choice OCTA actually made. CLEAN benchmark.
- **Bravo! Westminster / 17th** — an arterial rapid-transit choice.
  CLEAN benchmark.
- **OC Streetcar** — fixed-guideway RAIL on a short alignment, NOT an
  arterial ALM corridor. CONFOUNDED case (mode + length differ from
  what the screen ranks); carried for completeness, not as a clean
  test.

**Pre-stated miss semantics (written BEFORE any run).** Each possible
outcome is dispositioned in advance so no result can be re-narrated
after the fact:

- a **demand-strong, OCTA-chosen ARTERIAL** corridor (Harbor,
  Westminster/17th) ranking OUTSIDE top-8 counts **AGAINST** the screen;
- a **miss on OC Streetcar** is attributed to the mode/length
  **confound**, NOT scored against the screen;
- a corridor OCTA chose for **grant or political** reasons that is
  demand-weak and ranks low is a **benchmark confound**, not a screen
  failure.

**Evidentiary weight, stated (item-9 is SUFFICIENT-BUT-NOT-NECESSARY,
resolved 2026-07-22, owner option b — supersedes the earlier
"necessary condition" form).** With n = 3 (really 2 clean), ONE clean
miss is WEAK evidence — the check can corroborate or embarrass, it
cannot by itself validate, and — the symmetric point, now made
explicit — it cannot by itself VETO. Because one clean miss at n = 2 is
confounded by funding, political, and mode factors, item-9 does NOT
unilaterally force the null. Its status in the §9.5 stopping rule is
therefore:

- an item-9 **PASS** is **CONFIRMATORY** of branch (a) — it strengthens
  the decision-grade finding but is not required to reach it (branch (a)
  gates on the failure-mode-subset rho >= 0.7 alone);
- an item-9 **MISS** triggers a **documented confound-review** under the
  frozen miss semantics below (is the miss a benchmark confound or a
  genuine screen failure?), whose recorded finding decides ship-vs-null
  — NOT an automatic null.

It remains never read as independent validation, and is never
sufficient ON ITS OWN to reach branch (a) without the failure-mode
gate. This status is decided NOW, before the queue is ranked, so the
confound-vs-failure disposition of a miss cannot be relitigated after
seeing which benchmarks missed.

**Naive baseline (the discrimination control — the load-bearing part).**
Also rank the corridors by **catchment POPULATION alone** (no
coefficients, no cost model) and run the SAME benchmark against the same
N = 8. Then:

- if the naive population ranking ALSO puts the arterial benchmarks in
  the top tier, the check does NOT discriminate the screen from a
  population count, and a v2.4 pass tells you nothing the population
  count did not already say;
- **PASS CONDITION (resolved 2026-07-22, owner review; supersedes the
  contradictory dual-clause form committed in ee03fc0):** the check
  **PASSES** iff BOTH clean arterial benchmarks (Bravo/Harbor-543,
  Bravo/Westminster-17th) rank in the top-8 of the v2.4 benefit-per-cost
  queue. Decidable, falsifiable, frozen now. Either clean benchmark
  outside top-8 = item-9 **MISS**. A miss does NOT auto-route to
  stopping-rule branch (b) (that was the superseded necessary-condition
  form); it triggers the **documented confound-review** above under the
  frozen miss semantics, and only a review finding of GENUINE SCREEN
  FAILURE routes to branch (b) — a finding of BENCHMARK CONFOUND leaves
  branch (a) available on the failure-mode gate alone.
- **Discrimination vs the naive baseline is a REPORTED DIAGNOSTIC, not a
  pass condition** — demoted BEFORE any numbers exist, for a stated
  reason: with n=2 clean benchmarks and N=8, a discrimination margin
  between two rankings is UNDECIDABLE as a gate (no honest threshold on
  2 points); leaving it in the pass condition would have forced post-hoc
  resolution in the direction of shipping. MANDATORY DISCLOSURE: if the
  naive population ranking ALSO places both clean benchmarks in top-8,
  the artifact and the gate-1 memo MUST carry the label **"consistent
  with a population count"** — the external-validity evidence is then
  weak-positive, not confirmatory, and is explicitly NOT
  evidence that the screen adds signal over counting people.

The check, its N, its benchmark scoping, its miss semantics, and its
naive baseline are all frozen here; the diagnostic reports the mean clean-benchmark rank under the screen vs under the population count (displacement, sign and size); the v2.4 batch runs them and reports
the disposition, never re-defining them after seeing the queue.

### 12.2 Stage-2 scoping — the downstream gap (mechanized in spec 07 §4.3 + spec 00 §3)

Closing the screen→candidates loop (v2.4 branch (a)) would produce a
PROMOTED candidate set. But stage 2's welfare BCA and spec 07's "no OC
ALM corridor clears BCR=1" verdict were computed on the HAND-SUPPLIED
set (harbor / streetcar). A newly promoted set would STRAND them. Of the
available options, the one consistent with the item-8 stopping rule
(v2.4 = last STAGE-1 attempt, not a stage-2/3 re-trigger) is adopted:

**Option (ii), adopted.** Spec 07's "no OC ALM corridor clears BCR=1"
verdict is **PERMANENTLY scoped to the corridors ACTUALLY EVALUATED**
(hand-supplied harbor / streetcar). The v2.4 benefit-per-cost queue is
**FORWARD-LOOKING input for future stage-2 work — NOT a trigger to
re-run stage 2/3, and NOT auto-promoted into `config/candidates.json`
for the current verdict.**

**Disallowed state, stated explicitly.** Shipping a NEW candidate set
alongside verdicts computed from the OLD one is barred — a candidates.json
that says `hand_supplied: false` beside a BCR verdict computed on the
hand-supplied universe is an incoherent artifact and must never be
committed. If v2.4 branch (a) ever promotes a set, the stage-2/3 verdicts
that consume it are RE-RUN in that same batch or the promotion does not
land. This scoping is logged (governance rule 3; README known issue) and
mechanized in spec 07 §4.3 (candidate-pool standing condition) and spec
00 §3 (network-sequence row).

## 13. v2.4 benefit-per-cost BCA-queue on discrete anchor-pair corridors — PRE-REGISTRATION

**DRAFT — NOT FROZEN; freeze requires owner ratification (stopping-rule

> **REJECTED by independent review 2026-07-23 — do NOT freeze.** Two
> STRUCTURAL findings block a freeze (neither is a knob fix):
> (1) **min_sep-under-M2_fit landmine** — under the FITTED ranking the
> anchor-resolution row shows genuine (exists-but-moved) top-8 churn 6/16,
> vs ~0 under the coefficient-free measure; M2_fit specifically is unstable
> to the lattice, driven by long-corridor dominance from the length
> exposure. The spatial-resolution failure mode would fail for M2_fit.
> (2) **change-of-support** (reviewer rule-7): the v2.2 coefficients were
> fit on the OCTA ROUTE panel and are applied unchanged to fabricated
> anchor-corridors; if corridor-unit elasticities differ (b1 endogeneity-
> attenuated, b4 wrong-signed) the ranking is coefficients-on-the-wrong-
> unit, and NO failure mode can detect it (modes 1-3 hold coeffs fixed;
> mode 4 samples the same route-panel distribution). This REFRAMES the 6/8
> fit-materiality result: the coefficients MOVE the ranking, but movement
> is not improvement — it may be transfer bias. Requires an OWNER DECISION
> on the ranking measure (M2_fit vs coefficient-free M1) before any
> redesign or freeze. See known-issue 50.
timing).** This is the v2.4 pre-registration PROPER — the estimand
APPLICATION, universe, scoring, deliverable, and the concrete
instantiation of the §5 four-mode gate — that §12 deferred to "a
SEPARATE later batch". It is a DRAFT on purpose. §9.5 makes v2.4 the
LAST stage-1 method attempt, so the timing warrant that legitimizes
every prior pre-registration (the numbers are unknown when the rule is
fixed) binds here with special force: the freeze is deferred to an
EXPLICIT owner ratification so the stopping-rule clock starts on a
ratified object, not a draft. Until that ratification the values below
are PROPOSED, no v2.4 fit consumes them, and nothing here changes a
frozen threshold, the estimand, or a committed battery id list. The
three frozen artifacts stay byte-identical (v2.0 b88f9b65 / v2.1
83aeb032 / v2.2 3b1d5526).

**NO NEW FIT (binding).** v2.4 REUSES the committed v2.2 productivity
coefficients — b1_flows 0.256194, b2_zveh 0.382547, b4_genjobs
−0.041057, b5_len −0.22846 (read from `outputs/screen_results_v22.json`,
DV = log(boardings/RVH), §10) — applied to the discrete anchor-pair
corridor universe. It fits NOTHING: no re-estimation, no new estimand,
no re-vintaged predictor. Per the §9.5 CLOSED v2.5 list, applying an
existing fit to a new geometry is NOT a new empirical input and does not
re-open the arc; it is the last reading of the v2.2 evidence. The
coefficient bootstrap the estimation-uncertainty gate row consumes
(§13.4, mode 4) is v2.2's EXISTING route-cluster resample family (B =
2000, §3.4) — no new bootstrap.

**Delegated-changes fold-in (GUARD 2, docs/review-verification.md →
Delegation).** This pre-registration quotes the accumulated
`outputs/DELEGATED_CHANGES.md` log in aggregate, as required before any
new pre-registration. As of 2026-07-22 the delegated set is FIVE items:
(1) rule 6 (universe-change / perturbation-identity check), (2) rule 7
(spec-validity review), (3) the min_sep IDENTITY-UNIT metric correction
applied to the anchor de-risk read only, (4) the screen-fork
consolidation, (5) the canonical-pointer file. In aggregate: TWO
review-harness rules, ONE identity-unit metric correction on a de-risk
read (not a committed verdict), and TWO pure-housekeeping items. NONE
moved a published number or flipped a pass/fail — the three frozen
artifacts stay byte-identical and no `ordinal_ok` changed — and NONE set
a bar an unrun fit will be judged against. Guard 1 fired zero
escalations. This §13 therefore inherits an UNMOVED pipeline; the
delegated corrections it RELIES ON are rule 6 (the identity metric the
spatial-resolution and estimation-uncertainty rows use) and the min_sep
identity-unit read (§13.1/§13.4 evidence), both of which recompute no
committed statistic.

**Prior de-risk reads (context, NOT the bar).** Three cheap reads
preceded this draft (tasks: anchor cheap read, marginal-churn battery,
min_sep-under-M2_fit + fit-materiality). Their numbers are used ONLY to
justify WHICH perturbation is the strongest threat in each failure-mode
class (criterion C below). Per §9.5 / §12.1 non-transfer, a preview
NEITHER sets NOR predicts the gate statistic: the gate runs on the
fit-applied v2.4 numbers, computed after this document freezes. Where a
preview is quoted it is labelled as such.

### 13.1 UNIVERSE — discrete anchor-pair corridors

The v2.4 universe is NOT sliding windows. It is a finite set of
DISCRETE corridors, each spanning a pair of demand ANCHORS along a
single host arterial. Construction (mechanical, no "major arterial"
hand-filter — governance rule 1):

**(a) Anchors.** The anchor set is the UNION of three sources, deduped
(step c):
- **WAC employment peaks** — census-block workplace jobs (LODES WAC,
  block `C000` all-jobs totals), top-`screen_anchor_peak_pool` pool;
- **Decennial P1 population peaks** — census-block resident population
  (2020 Decennial P1), same top-`screen_anchor_peak_pool` pool;
- **Special generators** — the `config/special_generators.json` sites
  (resort / college / medical), AUTHORITATIVE (a generator is never
  thinned away in favour of a co-located emp/pop peak; co-located peaks
  fold in as extra feature tags).

**(b) Deduplication at min-separation (universe-defining, FROZEN per
rule 6).** Anchors are greedy-thinned so no two survivors sit within
`screen_anchor_min_sep` = **1.5 mi** of each other (generators kept
first, then emp, then pop; deterministic order). This constant DEFINES
the universe: at 1.5 mi the min_sep-under-M2_fit read measured **90
anchors → 187 connectable corridors** (freeway-excluded, geo-deduped;
the read's headline figures). Per rule 6 min_sep is a universe-DEFINING
knob (the anchor-world analogue of the window-length constant), FROZEN
for the delivered product — NOT a free robustness axis. It is
SIMULTANEOUSLY the spatial-resolution FAILURE-MODE row (§13.4 mode 2):
the product is delivered at 1.5 mi and the gate perturbs it in IDENTITY
units to test robustness. Freezing the value and gating its perturbation
are the same discipline the window world applies to `screen_window_mi`
(12.5 frozen; `window_10`/`window_15` gated).

**(c) Path eligibility — freeway/express exclusion (general predicate,
NOT a route blacklist).** A corridor's host path must be a surface
arterial: freeway and express alignments are excluded by a
ROAD-CLASS / GEOMETRY predicate (`screen_anchor_path_exclusion` — e.g.
GTFS route-type / stop-spacing / limited-access geometry), a general
rule that would exclude ANY freeway-running shape, not an enumerated
list of route ids. Rationale: the cheap read surfaced Route 83 (the
"5 Freeway" alignment) as five contaminant top-15 entries; a
general geometric predicate removes the whole CLASS, and the on/off
toggle is a disclosed diagnostic (§13.4), not a gated row (the read
measured near-zero ranking churn from the toggle).

**(d) Pair selection (each a named registry knob with its home).** A
candidate corridor is an anchor PAIR both of whose members lie within
`screen_anchor_membership_buffer` = **X = 0.5 mi** of a common weekday
GTFS shape (the corridor is that shape's segment between the two
projected anchor positions; one corridor per pair = the best-fit host
route by minimum summed offset), subject to a length cap
`screen_anchor_pair_dist_cap` = **Y = 15 mi**. Same-route sub-segments
overlapping ≥ 0.70 Jaccard collapse to one (deterministic). Both X and Y
are named registry knobs; both are DISCLOSED DIAGNOSTICS, not gate rows
(their HOME and rationale are in §13.7).

### 13.2 SCORING — M2_fit benefit-per-cost (M1 co-reported)

**Primary measure `M2_fit` (`screen_v24_ranking_measure.primary`).**
Benefit-per-cost. The NUMERATOR is predicted productivity carried to a
demand-like quantity by the exposure convention; the DENOMINATOR is
capital:

    M2_fit(corridor) = [ exp(b1·l_flows + b2·l_zveh + b4·l_genjobs
                             + b5·l_len) · L ]  /  capital_$M

where `l_flows / l_zveh / l_genjobs` are the log1p catchment aggregates
computed on the corridor's catchment by the SAME shared
`compute_predictors` geometry (§3.2) — LODES both-ends-in flows,
B25044 zero-vehicle households, WAC generator jobs (`gen_jobs_naics`) —
so the CATCHMENT enters the numerator through the covariates; `l_len =
log(L)`; and `exp(const) + year FE` are COMMON multipliers, rank-inert,
omitted. `exp(·)` is predicted PRODUCTIVITY (boardings/RVH, the §10
estimand); `× L` is the exposure step (§13.2 convention); the ratio to
capital is benefit-per-cost.

**Exposure / length convention (rank-relevant, FROZEN —
`screen_v24_exposure`).** Corridor length `L` (miles, anchor-to-anchor,
endogenous) enters TWICE and deliberately: as the `b5` covariate
(`l_len = log L`) AND as the exposure multiplier (`· L`) that converts
per-service productivity to a demand-like numerator. This double use is
NOT rank-inert — the fit-materiality read found the M2_fit vs M2_raw
divergence is CONCENTRATED in the length profile of the shortlist (fit
top-8 lengths 9.6–14.5 mi, clustering at the Y = 15 mi cap) — so it is
stated explicitly and FROZEN here rather than left implicit. An
alternative exposure (offset/`b5`-only, no `· L` multiplier) is a
DISCLOSED DIAGNOSTIC, not a gated row.

**Cost denominator (`screen_v24_cost_model`; owner-frozen params).**
`capital_$M` = the spec-04 `capcost.py` capital at the LOW markup band:
a TWO-PART guideway cost (fixed OCC + depot, plus per-route-km) PLUS
per-station PLUS rolling stock — stations = max(2, round(L / 1.0 mi)),
fleet = `capcost.fleet(L, 5-min peak headway)`, LOW markup 1.20. The
cost-model PARAMETERS bind an unrun fit and are OWNER-only (never
delegated, docs/review-verification.md); they are pre-registered here as
the LOW-band instantiation, with a HIGH/BASE band sweep as a disclosed
diagnostic.

**Co-reported measure `M1` (`screen_v24_ranking_measure.co_reported`).**
The COEFFICIENT-FREE demand-per-mile ranking — raw catchment demand
(jobs + population) / L, no coefficients, no cost model — is published
ALONGSIDE M2_fit for every corridor. It is a transparency co-report, not
a second gate. The fit-materiality read measured rho(M2_fit, M1) = 0.068
(near-orthogonal) — the cost model and the fitted elasticities DO drive
the answer away from raw density — so the M1-vs-M2_fit divergence is a
MANDATORY disclosed diagnostic (§13.7), flagged as a
ranking-measure-choice fragility.

### 13.3 DELIVERABLE — a ranked BCA queue (no product cutoff)

The v2.4 product is a RANKED BENEFIT-PER-COST QUEUE over the frozen
(min_sep 1.5) discrete-corridor universe — the full ~187 corridors
ranked by M2_fit, with the top **~25 named** and worked down (anchor A,
anchor B, host arterial, length, M2_fit, M1 co-report,
catchment components). There is NO cutoff for the PRODUCT: the queue is
the deliverable, a priority ordering, not a shortlist with a line. The
ONLY cutoff is the gate-1 consumption ceiling: **gate 1 consumes the
top-8** (spec 00 §3 / §4b: top 5–8 + ties), which is also the N the §5
gate churn and the §12.1 external-validity check are measured at. The
queue is written to a v2.4 artifact under the §4 deterministic-write and
output-format guardrails (no field denominated in boardings; the index
is ordinal benefit-per-cost).

### 13.4 GATE — the four §5 failure-mode rows, instantiated for v2.4

The §5 FAILURE-MODE GATE binds v2.4 (NORMATIVE, per
`screen_gate_failure_modes.row_map["v2.4-anchor"]`). Criterion 2 = MIN
Spearman rho over the FOUR rows ≥ `screen_battery_rho_min` = 0.7;
criterion 3 = MAX margin-defined tie-set churn over them, DUAL-UNIT.
Exactly ONE named row instantiates each mode (criterion C); each row's
pass condition is computable with no v2.4 results in hand (criterion B).

**Mode 1 — catchment-width — row `buffer` (`buffer_lo` / `buffer_hi`).**
Perturb the catchment buffer to its band edges. The anchor LATTICE is
unchanged (buffer changes only the catchment aggregates), so every
corridor persists — no universe change, no rule-6 decomposition needed.
Statistic: full-ranking Spearman rho of M2_fit vs the buffer-edge
ranking, and the margin-defined top-8 identity churn (window-unit).
PASS: rho ≥ 0.7 AND churn ≤ `screen_tie_churn_max_window` = 0.20.
*Criterion C (strongest catchment-width threat):* buffer is the ONLY
catchment-geometry knob that survives BOTH worlds (§5); it is the
canonical catchment-width perturbation, and the marginal-churn read
measured it as the second-largest ranking mover after min_sep
(preview rho 0.94–0.96, moderate top-8 movement) — the largest that
holds the universe fixed.

**Mode 2 — spatial-resolution — row `min_sep-identity`.** Perturb
`screen_anchor_min_sep` from the frozen 1.5 to the band edges
{1.0, 2.0} mi. Each edge REBUILDS the anchor lattice and the corridor
universe, so this is a rule-6 universe-CHANGING perturbation: match the
frozen-universe top-8 into the perturbed universe by the segment-overlap
IDENTITY matcher (bearing ≤ 25° mod 180, endpoint-to-line perp ≤ 0.6 mi,
along-overlap ≥ 0.4 of the shorter; greedy 1-1, endpoint-distance
tie-break; matched against the FULL perturbed universe). DECOMPOSE each
frozen top-8 member into NO-LONGER-EXISTS (zero seg-match candidate —
universe change, DISCLOSED, not counted against the ranking) vs
EXISTS-BUT-MOVED (a match exists but falls outside the perturbed top-8 —
genuine ranking instability, COUNTED). Statistic = MAX over the two
edges of [# exists-but-moved / # frozen-top-8 that persist]. PASS:
statistic ≤ `screen_tie_churn_max_hostshape` = 2/14 = 0.142857 (the
anchor-world identity-unit analogue of the host-shape cap) AND the
persist-set rho ≥ 0.7.
*Criterion C (strongest spatial-resolution threat):* min_sep is the
ONLY universe-defining lattice knob — the direct analogue of the
window-length row that was the most decision-relevant perturbation in
the window world (§5). The min_sep-under-M2_fit read makes it the
DEMONSTRATED landmine: under the FITTED ranking the finer edge (1.0 mi,
universe grows 187→407, NO baseline corridor destroyed so
no-longer-exists = 0) showed **5 of 8** frozen top-8 EXIST-BUT-FALL out
(e.g. Alton 14.5 mi fit#2 → 24/407; Standard/Bristol 14.3 mi fit#7 →
310/407; Main St 9.6 mi fit#8 → 11/407), pooled genuine 6/16 across both
edges. The COEFFICIENT-FREE read had found ~0 genuine churn (all
universe change) — the fitted ranking FLIPS the verdict, because
`b5_len`'s exposure×length interaction rewards long corridors and a
finer lattice manufactures MORE long-corridor candidates that displace
the frozen top-8's specific representatives. This is precisely why
min_sep is GATED here rather than "frozen and forgotten": the earlier
de-risk recommendation to freeze it as a safe constant is SUPERSEDED by
the fitted read. (Preview 5/8 ≫ 2/14 signals real risk that this row
binds; per non-transfer it does not set the gate, which runs on the
fit-applied numbers.)

**Mode 3 — specification — row `swap` (demand-numerator swap).** Swap
the FITTED demand numerator for its COEFFICIENT-FREE counterpart over
the SAME cost denominator, same universe, same exposure — i.e. rank by
M2_raw (raw catchment demand · L⁻¹-free / capital) and compare to
M2_fit. The lattice is unchanged (no rule-6 decomposition). Statistic:
full-ranking rho of M2_fit vs M2_raw and the top-8 identity churn
(window-unit). PASS: rho ≥ 0.7 AND churn ≤ 0.20.
*Criterion C (strongest specification threat):* this is the MAXIMAL
within-scoring specification change — it replaces the ENTIRE fitted
demand specification with its coefficient-free form while holding cost,
universe, and exposure fixed. A single-predictor swap (`popden_swap`
b1→density, `gen_dummy_swap` b4→binary) is a SUBSET of this change and
its divergence is bounded above by it, so those are disclosed
diagnostics, not the gated row. The fit-materiality read measured the
swap at rho 0.480 with 6 of 8 shortlist members replaced — the fit is
NOT decorative, the specification genuinely moves the answer, so this is
the binding specification threat. (Preview rho 0.48 < 0.7 again signals
real bind-risk; it does not set the gate.)

**Mode 4 — estimation-uncertainty — row `coeff_resample`.** Draw the
coefficients (b1/b2, and b4/b5) from v2.2's EXISTING route-cluster
coefficient bootstrap (B = 2000, §3.4 — no new fit, no new bootstrap),
re-rank the FROZEN corridor universe per draw, and — because a
coefficient resample leaves the lattice UNCHANGED, so every corridor
persists (rule-6 no-longer-exists is empty and the churn is ALL
exists-but-moved) — measure the margin-defined top-8 identity churn
across draws (window-unit / identity-window unit). Statistic: the
bootstrap tie-set churn at the top-8 cutoff (max(#in,#out)/8 aggregated
over draws) and the mean resampled-vs-point Spearman rho. PASS: churn ≤
0.20 AND rho ≥ 0.7.
*Criterion C (strongest estimation threat, and the LOAD-BEARING row):*
it IS the estimation uncertainty, sampled directly — no proxy. The
fit-materiality read showed the v2.2 coefficients SWAP 6 of 8 shortlist
members versus the coefficient-free ranking, so the coefficients are the
single largest membership driver; b1 sits at t = 1.49 (cluster SE 0.17),
b2 at t ≈ 2.97 — wide enough that their sampling distribution is the
perturbation MOST able to move the top-8. Until §5's 2026-07-22
amendment this threat sat ENTIRELY OUTSIDE the gate. It is homed as its
OWN mode (not folded under specification) so the load-bearing threat
carries its own visible bar (§5 rationale).

**Non-mode perturbations = DISCLOSED DIAGNOSTICS (outside the gate,
nothing hidden).** Reported in the artifact's `shortlist_stability`
block but setting NO pass/fail bar: `screen_anchor_peak_pool` 200/500
(read: near-zero churn, street-Jaccard 1.00), `screen_anchor_pair_dist_cap`
12/18 (near-zero churn), `screen_anchor_membership_buffer` variants,
the freeway-exclusion on/off toggle (near-zero churn), the cost-model
band (LOW/BASE/HIGH), the exposure-variant (offset-only), and the
M1-vs-M2_fit ranking-measure divergence (rho 0.068 — the
measure-choice fragility, MANDATORY disclosure). Each is a DIAGNOSTIC
precisely because the de-risk reads measured it as decision-orthogonal
or as a disclosed universe/measure choice, not one of the four
sensitivities a corridor ranking must be robust to (§13.7 states each
home + reason).

### 13.5 STOPPING RULE (the §9.5 numeric floor consumes this queue)

v2.4 is the LAST stage-1 method attempt (§9.5). The benefit-per-cost
queue of §13.3 is the object the stopping rule reads:
- **(a) DECISION-GRADE** iff the failure-mode-subset MIN rho (the four
  §13.4 rows) ≥ 0.7 [`screen_battery_rho_min`] — the criterion-2 value,
  NOT the 0.79/0.87 anchor-world previews. The §12.1 item-9 check is
  SUFFICIENT-BUT-NOT-NECESSARY: a PASS is confirmatory; a MISS triggers
  the documented confound-review, not an automatic null. On (a): SHIP
  the queue, gate 1 consumes the top-8 per §4b, `config/candidates.json`
  may take `hand_supplied: false` (subject to the §12.2 stage-2 re-run
  condition).
- **(b) DOCUMENTED NULL** otherwise (failure-mode rho < 0.7, or a
  confound-review finding of GENUINE screen failure): SHIP the finding
  that OC demand does not separate corridors; the threshold shortlist
  stays the permanent stage-1 output, `candidates.json` stays
  `hand_supplied: true`.

Either branch STOPS stage 1. The CLOSED v2.5 list (§9.5) is unchanged:
only a genuinely new empirical input (records-request RVH, a new agency
panel clearing §11 D2, or a materially different data source) re-opens
the arc — and applying the v2.2 fit to the anchor geometry is NOT such
an input.

### 13.6 ITEM-9 — the §12.1 external-validity check runs against this queue

The §12.1 check (frozen 2026-07-22) runs against the §13.3 queue,
UNCHANGED: N = 8 from consumption; benchmark set Bravo/Harbor (Route 543
corridor) and Bravo Westminster/17th (the two CLEAN arterial-ALM
benchmarks) plus OC Streetcar (CONFOUNDED rail case). PASS CONDITION
(resolved 2026-07-22, sufficient-not-necessary): the check PASSES iff
BOTH clean arterial benchmarks rank in the top-8 of the v2.4
benefit-per-cost queue — a PASS is CONFIRMATORY of branch (a); either
clean benchmark outside top-8 is a MISS that triggers the documented
confound-review (benchmark confound vs genuine screen failure) under the
frozen miss semantics, only a "genuine screen failure" finding routing
to branch (b). NAIVE-BASELINE diagnostic (the discrimination control):
also rank by catchment POPULATION alone against the same N = 8; if the
naive population ranking ALSO places both clean benchmarks in top-8, the
artifact and the gate-1 memo MUST carry the label "consistent with a
population count" — the external-validity evidence is then weak-positive,
not confirmatory. The discrimination margin is a REPORTED DIAGNOSTIC
(mean clean-benchmark rank under the screen vs under the population
count), not a pass condition (undecidable at n = 2).

### 13.7 Knob → home → rationale (criterion A + criterion C)

EVERY v2.4 knob has a registry entry AND an explicit home — inside a
named failure mode OR a disclosed diagnostic — with the reason stated.
Machine-readable as `screen_v24_prereg.knob_home_map`; the
v24-prereg-lock test asserts every knob is present with a home, and that
each of the four modes is instantiated by EXACTLY ONE row.

| knob (registry id) | value (DRAFT) | home | why here / strongest-in-class (criterion C) |
|---|---|---|---|
| `screen_anchor_min_sep` | 1.5 mi | **FAILURE MODE 2** (spatial-resolution, `min_sep-identity`) + universe-defining FROZEN (rule 6) | only universe-defining lattice knob; fitted read shows 5/8 top-8 exist-but-fall at the finer edge — the demonstrated landmine, strongest resolution threat |
| catchment buffer (`buffer_mi`) | 0.9 mi (existing entry) | **FAILURE MODE 1** (catchment-width, `buffer_lo`/`buffer_hi`) | only catchment-geometry knob surviving both worlds; largest universe-fixed catchment mover |
| `screen_v24_ranking_measure` | {primary M2_fit, co-report M1} | **FAILURE MODE 3** (specification, `swap` = M2_raw↔M2_fit) | maximal within-scoring demand-spec change; preview rho 0.48, 6/8 swap; single-predictor swaps are subsets |
| v2.2 coefficients (reused, `screen_results_v22.json`) | b1 .256194 / b2 .382547 / b4 −.041057 / b5 −.22846 | **FAILURE MODE 4** (estimation-uncertainty, `coeff_resample`) | THE load-bearing threat: coeffs drive 6/8 members, b1 at t=1.49; sampling uncertainty most able to move the cutoff |
| `screen_anchor_membership_buffer` (X) | 0.5 mi | DISCLOSED DIAGNOSTIC | pair-selection connect distance, not a catchment-width knob; read: not decision-moving |
| `screen_anchor_pair_dist_cap` (Y) | 15 mi | DISCLOSED DIAGNOSTIC | read measured 12/18 near-zero churn — decision-orthogonal |
| `screen_anchor_peak_pool` | 300 (emp & pop each) | DISCLOSED DIAGNOSTIC | read measured 200/500 near-zero churn, street-Jaccard 1.00 |
| `screen_anchor_path_exclusion` | freeway/express road-class geometry predicate | universe PREDICATE (definitional) + DISCLOSED DIAGNOSTIC (on/off) | general class exclusion, not a route blacklist; toggle near-zero churn |
| `screen_v24_cost_model` | spec-04 capcost LOW band (owner-frozen params) | DISCLOSED DIAGNOSTIC (band sweep) | cost params bind an unrun fit → owner-only; band LOW/BASE/HIGH swept as diagnostic |
| `screen_v24_exposure` | length L (double use: `b5` covariate + `·L` multiplier) | FROZEN rank-relevant convention + DISCLOSED DIAGNOSTIC (offset-only variant) | rank-relevant (divergence concentrated in length profile), so stated + frozen, not implicit |
| queue length (`screen_v24_prereg.deliverable`) | ~25 named; gate-1 top-8 | deliverable definitional | the queue is the product; only cutoff is the top-8 consumption ceiling |

*A min over four is only as good as the four (criterion C, stated).*
Each mode's row is the STRONGEST available threat in its class by the
de-risk previews: min_sep (5/8 fitted top-8 churn) for resolution,
buffer (largest universe-fixed mover) for width, the demand-numerator
swap (rho 0.48, 6/8) for specification, and coeff_resample (the direct
sampling of the largest membership driver) for estimation. Weaker
in-class perturbations are homed as diagnostics, not averaged into the
gated row.

### 13.8 Results-blind self-check (criterion B)

Every pass condition below is DECIDABLE by someone who has seen NO v2.4
results — it references only quantities frozen in this document (or in
the already-committed §5 / §9.5 / §12.1) plus the fit-applied ranking
the v2.4 run will produce. The check that item-9 just failed (a bar read
off a preview rank already seen, §12.1) is avoided: no pass condition
names a corridor, a rank, or a preview value.

- **Criterion 1 (sign)** — decidable: b1/b2 positive-fraction ≥ 0.841
  over v2.2's existing bootstrap; the coefficients and the bootstrap are
  frozen (v2.2 artifact), nothing v2.4-specific to see.
- **Criterion 2 (min rho ≥ 0.7)** — decidable: the FOUR rows are named
  (§13.4), each row's ranking comparison and rho are fully specified
  (perturbation, identity matcher, cutoff), the threshold 0.7 is frozen.
- **Criterion 3 (dual churn caps)** — decidable: window-unit rows
  {buffer, swap, coeff_resample} ≤ 0.20; identity-unit row {min_sep} ≤
  2/14; the metric (margin-defined tie-set / rule-6 identity churn), the
  cutoff (top-8), and both caps are frozen.
- **Stopping rule (a)/(b)** — decidable: gates on the criterion-2 value
  0.7 (NOT a preview); the sufficient-not-necessary status of item-9 and
  the confound-review disposition of a miss are fixed NOW so a miss
  cannot be relitigated after seeing which corridors missed.
- **Item-9 (§12.1)** — decidable: PASSES iff BOTH named clean benchmarks
  are in the top-8; N = 8, benchmark set, and miss semantics all frozen;
  the naive-population disclosure is a fixed rule, not a threshold.

The only quantities NOT knowable in advance are the RANKINGS themselves —
which is the point: the rules that judge them are complete before they
exist.

### 13.9 Registry, freeze checklist, and what v2.4 does NOT do

**Registry (all `spec-pending:01§13`, DRAFT — not yet ratified).** New
entries: `screen_anchor_min_sep`, `screen_anchor_membership_buffer`,
`screen_anchor_pair_dist_cap`, `screen_anchor_peak_pool`,
`screen_anchor_path_exclusion`, `screen_v24_ranking_measure`,
`screen_v24_cost_model`, `screen_v24_exposure`, and the umbrella
`screen_v24_prereg` (which carries `knob_home_map`, the design summary,
the delegated-diff fold-in flag, and the DRAFT status). `buffer_mi`,
`gen_jobs_naics`, `special_generators`, and the v2.2 coefficients are
REUSED existing entries. No `*_v24` THRESHOLD id is minted (the frozen
0.841 / 0.7 / 0.20 / 2·14⁻¹ are unchanged, §5); no prior-tier entry is
added, so the prior-order fingerprint is untouched.

**Freeze checklist (what owner ratification must do to start the
stopping-rule clock).** (1) Ratify the DRAFT values (min_sep 1.5,
X 0.5, Y 15, pool 300, the LOW cost band, the exposure convention, the
M2_fit/M1 measure pair). (2) Flip each `spec-pending:01§13` entry's
disposition to accepted-frozen. (3) Confirm the four-mode row map and
the dual churn caps as the binding v2.4 gate. Only after (1)–(3) does
v2.4 become the ratified LAST attempt whose single fit-application run
resolves branch (a)/(b).

**What v2.4 does NOT do.** It fits NOTHING (reuses v2.2 coefficients);
it adds NO networked scoring (corridors scored in isolation; transfers
remain spec 07's job); it publishes NO field denominated in boardings
(ordinal benefit-per-cost only, §4 guardrails); it does NOT auto-promote
into `config/candidates.json` for the current verdict (§12.2 — a
promotion lands only in a batch that re-runs the stage-2/3 verdicts that
consume it); and it does NOT treat the anchor geometry as a new
empirical input (§9.5 closed v2.5 list). The §1 endogeneity confession
is UNCHANGED — b3 (RVH) is on the LHS as the productivity denominator
(§10), never read as a service response, and no prediction at any
counterfactual service level is published.
