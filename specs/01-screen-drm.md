# Spec 01 — Stage 1: Direct-Demand Regression Screen

Status: panel-revised 2026-07-18 (3-lens adversarial panel; 9 blocking
findings adjudicated) · BUILD IN PROGRESS
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
aggregates). The decomposition output is GROUPED — demand block
(b1+b2) / service (b3) / generator (b4) / scale (b5) — never
per-coefficient: with VIF>10 at n_eff≈41, per-coefficient attribution
is arbitrary and can flip sign under one-route deletion. Windows whose
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

**Published score.** screen_index = 100 * (predicted at svc_std) /
(median fitted-route prediction at svc_std). Ordinal only; no field
anywhere in the artifact is denominated in boardings (§4).

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
host-shape report), `fit_diagnostics{}`, `sensitivity[]`.

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
index (median fitted route = 100) — not a ridership forecast". House
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
   leverage-flagged windows annotated;
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

**PRIMARY — rank-stability battery** (panel 2026-07-18: for a screen
that passes ties onward, ranking robustness under *specification
choices* matters most; single-observation deletion barely moves a
41-route fit and is nearly toothless as a primary gate):

(a) bootstrap rank confidence sets for the top-10 windows (§3.4);
(b) cross-spec Spearman rho + top-8 set churn across the
    pre-registered perturbations: buffer 0.5/1.25, window 10/15,
    drop_fy2020, drop-RH, drop-generator (b4_off), E016-swap, NB
    estimator, svc p25/p75, offset-variant;
(c) leave-one-YEAR-out rank stability.

The gate report enumerates every shortlist (top-8) membership change
across the battery explicitly — windows that enter or exit are named
and dispositioned in the gate-1 memo, never averaged away.

**Demoted / secondary:**

- LOO-route Spearman rho >= 0.9 [screen_loo_rho] — retained as a
  *leverage screen* only (LOO = leave-one-ROUTE-out, all years of the
  held-out route removed; leave-row-out would leak route identity
  through the other years and pass trivially).
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
