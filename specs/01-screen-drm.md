# Spec 01 — Stage 1: Direct-Demand Regression Screen

Status: DRAFT for review · 2026-07-08 · not yet built (prototype: the
13-arterial screen, summarized in HANDOFF.md "Dropped work")

## 1. Role and non-role

Ranks every plausible corridor window in Orange County to produce the
finalist shortlist. Its numbers are ordinal screening scores with
uncertainty, never quotable ridership forecasts. Its service-level
coefficients are treated as *controls* (they absorb OCTA's historical
allocation of service toward demand), never as causal response estimates
— the endogeneity of service to demand makes them uninterpretable as
"what happens if we add service"; that question belongs to stage 2.

## 2. Inputs

| Input | Source | Status |
|---|---|---|
| Route-level annual boardings + revenue hours, ~45 routes x FY2017/FY2019/FY2020-Q3 | `data/raw/apc/*.pdf` (extraction code pattern exists from anchor work) | on disk |
| Route shapes, stop spacing, headways by period | `data/raw/gtfs/` via `build_corridor.py` helpers (`main_shape_xy`, `route_headways`) | on disk |
| Tract centroids + land area | `data/derived/oc_tracts.csv` | on disk |
| LODES tract O-D flows | `data/derived/oc_tract_od.csv.gz` | on disk |
| ACS transit workers x car ownership (+ MOEs) | `data/derived/oc_b08141.csv` | on disk |
| Special-generator flags (resort, colleges, medical) | hand-coded once, committed | to create |

## 3. Method

**3.1 Fit (route level).** Negative binomial (fallback: log-OLS with
robust SEs) on ~45 routes x up to 3 years:

    log E[boardings_r] = a + b1*log(LODES flows within 0.9-mi catchment)
                       + b2*log(ACS transit workers in catchment)
                       + b3*log(revenue hours)          [control, not causal]
                       + b4*(special-generator dummy)
                       + year fixed effects

Max 4-5 predictors (n is small). Catchment = 0.9-mi buffer of the route
shape, reusing `build_corridor.py` projection code. Panel years are
replication/robustness, not identification (service changes 2017-2020
are few and confounded with secular decline).

**3.2 Score (window level).** Slide a 10-15-mi window along every major
arterial GTFS shape (step 0.5 mi); compute the same predictors for the
window; apply the fitted model at a *standardized* service level (so
candidates are compared on fundamentals, not on incumbent service).
Report per window: predicted index with CI, decomposition by predictor,
and the **underservice residual** of any incumbent route (actual minus
predicted at actual service) — high-fundamentals/low-service windows are
flagged as opportunity candidates even if raw scores lag.

**3.3 Overlap handling.** Windows sharing >30% of catchment tracts are
grouped; the shortlist reports groups, not just windows, so gate 1 can't
double-count central Santa Ana demand.

## 4. Outputs

`outputs/screen_results.json` + one ranked chart:
window id, arterial, span (route-mi), score P50/P10/P90, predictor
decomposition, overlap group, underservice flag, incumbent routes.

## 5. Validation gates (must pass before first use)

Ordered by weight (review 2026-07-08: rank stability is the PRIMARY gate
— for a screen that passes ties onward, ranking robustness matters more
than point accuracy):

1. **Rank stability (primary):** LOO refits keep Spearman rho >= 0.9 on
   the full-route ranking, and the model ranks existing routes by
   observed boardings/revenue-hour sensibly (external check).
2. **LOO accuracy (secondary diagnostic):** median absolute log error
   <= 0.35 (~ +/-40% on a held-out route); report the worst 5 routes.
3. **Smoke test (demoted from gate):** reproduces the qualitative
   13-arterial prototype result — near-circular (the prototype is what
   this model supersedes), so failure prompts investigation, not
   automatic rejection.
4. **Endogeneity guard:** publish scores at standardized service; never
   publish "predicted ridership if service added" from this model.

## 6. Runtime & implementation

Fit: seconds. County scan: ~200-400 windows x seconds each — minutes
total, well inside the 1-hour budget. New scripts: `scripts/extract_apc.py`
(all-route table from the PDFs, committed as `data/derived/route_boardings.csv`),
`scripts/screen_fit.py`, `scripts/screen_scan.py`. Python/numpy/pandas +
statsmodels (new dependency — flag in requirements.txt).

## 7. Known limitations (accepted at this stage)

Cross-sectional; no network effects; catchments overlap; special
generators crudely dummied; FY2020-Q3 partially COVID-clipped (use
Jul-Feb only if March distorts). All acceptable because the output is a
shortlist, and gate 1 passes near-ties onward rather than resolving them.

## 8. Questions resolved (review 2026-07-08)

- Q1 (buffer): 0.9 mi primary (spine consistency); 0.5 mi as a
  robustness row.
- Q2 (standardized service): median OCTA local — scoring at the proposed
  rapid spec would re-inject the service endogeneity §1 removes and
  flatter corridors one intends to propose rapid on.
- Q3 (dependency): statsmodels accepted and pinned in requirements.txt;
  hand-rolled NB is a maintenance liability for a solo analyst.
