"""Stage-1 screen v2.2 PRODUCTIVITY fit engine (spec 01 §10; the once-only
governed-method-change fit).

This module is the v2.2 counterpart of screen_fit_v21.py. The ONLY method
change (spec 01 §10 D1/D2) is the ESTIMAND:

  * DEPENDENT VARIABLE = log(boardings / RVH) = productivity, NOT log(boardings).
  * b3 (log RVH) is GONE from the RHS -- log(b/RVH) = log(b) - log(RVH), so the
    productivity regression IS the v2.1 LEVEL regression with the RVH
    coefficient PINNED at +1 and MOVED to the LHS (b3 leaves the RHS entirely).

Everything else is reused UNCHANGED from the v2.1 phase-2b fit
(screen_fit_v21): the same 300-route-year / 63-cluster panel, the same
archived-shape catchments (route_short_name join, _merged_ ids), the same
vintage map, the same 4 contemporaneous-shape drops, year FE, the log-OLS
cluster-by-route primary + NB2 robustness -- but NB2 is now a RATE model
(log(E[b]) = log(RVH) + Xbeta, i.e. log(RVH) is a FIXED OFFSET), the count
analogue of the pinned identity (D5). The block-resolution vintage-matched
catchments come from screen_common_v21.compute_predictors_v21 REUSED VERBATIM.

CONSOLIDATION (item 2, 2026-07-23). The v2.1 and v2.2 fits share the entire
estimand-INDEPENDENT block-fit machinery: the fast per-shape projection, the
archived-GTFS feeds (§9.4), the boardings panel (§9.9.1), the catchment
extraction, and the OLS/VIF helpers. Those are now SINGLE-SOURCED from the
canonical v2.1 module (screen_fit_v21) by import rather than copied -- v2.2
carries ONLY its genuine estimand delta (BASE_CFG_V22, col_order_v22,
design_matrix_v22, and the NB2 RATE-model offset in fit_nb2 /
nb2_beta_fixed_alpha). The block predictor itself is one function object,
screen_common_v21.compute_predictors_v21, on BOTH the fit and scan sides of
BOTH versions (test_screen_cross_version.py XV1). This keeps every v2.2 fit
input byte-identical to what the old copied fork produced (byte-identity gate
test_screen_cross_version.py XV3 / test_screen_v22_fit.py V5-V6).

§10 D2 headline: b1 log1p(LODES both-ends flows), b2 log1p(B25044 zero-vehicle
HOUSEHOLDS), b4 log1p(WAC generator jobs CNS15-18), b5 log(length mi); + year FE
(base fy2017). NO b3 (RVH is the DV denominator). NO agency FE (OC-only).

ONCE-ONLY FIT DISCIPLINE (spec 01 §9.5/§10, binding): this fit runs EXACTLY
ONCE under the pre-registered spec. No predictor may enter beyond the §10 D2
headline + pre-registered swaps; no threshold is tuned. The DV is well-defined
only where RVH > 0 -- every fit row asserts rvh > 0 and the productivity DV
finite (§10 D8: all 300 kept route-years have RVH > 0 and boardings > 0).

    python -X utf8 scripts/screen_fit_v22.py   -> fit table, coefficients,
                                                  VIFs, dropped route-years
"""
import sys

import numpy as np

from assumptions import val
import screen_common_v21 as sv
# Estimand-INDEPENDENT block-fit machinery, single-sourced from the canonical
# v2.1 module (see the CONSOLIDATION note above). FastProjV22 is kept as an
# alias so the v2.2 module still exposes the historical name, though nothing
# references it externally. The names re-exported here are what screen_scan_v22
# reads off `sf` (fast_proj, build_fit_projs, build_fit_rows, load_cns_by_block,
# ols_beta, fit_primary, vifs, _route_sort_key, _b1name/_b2name/_b4name) plus
# the helpers design_matrix_v22 / col_order_v22 use (_fys_in, _col_b1/2/4).
from screen_fit_v21 import (                                       # noqa: E402
    _route_sort_key, fast_proj, FastProjV21 as FastProjV22,
    build_fit_projs, build_fit_rows, load_cns_by_block,
    ols_beta, fit_primary, vifs,
    _fys_in, _b1name, _b2name, _b4name, _col_b1, _col_b2, _col_b4,
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# NB2 optimizer scaffolding (mirrors screen_fit_v21 -- fixed start/maxiter/method
# under pinned statsmodels==0.14.5; starts derived from the log-OLS fit).
NB_MAXITER = 200
NB_METHOD = "newton"

# §10 D2 headline model config. Battery rows override individual keys. NOTE the
# v2.1 "use_rh" key is GONE -- RVH is no longer an RHS predictor (D2), it is the
# DV denominator, so there is nothing to toggle.
BASE_CFG_V22 = {
    "b1": "flows",         # popden_swap -> "popden"
    "b2": "zveh",          # e002_swap -> "e002"; e016_swap -> "e016"
    "b4": "genjobs",       # gen_dummy_swap -> "dummy"; genjobs_off -> None
    "b4_ex_cns": None,     # genjobs_leave_class_out -> one of gen_jobs_naics
    "offset": False,       # offset_variant -> True (b5 pinned to 1; log len -> LHS)
    "year_fe": True,       # year_fe_vs_pooled -> False
    "drop_fy2020": False,  # drop_fy2020 -> True
    "panel": "full",       # regime split: "pre2020" (fy2017+fy2019)
    "interaction": False,  # regime split: post2020 x {b1, b2}
}


# ---------------------------------------------------------------------------
# design matrices (§10 D1/D2: PRODUCTIVITY DV, b3 gone from the RHS). The
# estimand-independent column helpers (_fys_in, _b1name/_b2name/_b4name,
# _col_b1/_col_b2/_col_b4) are imported from screen_fit_v21; only the RHS column
# ORDER (no b3_rvh) and the DV transform differ.
# ---------------------------------------------------------------------------
def col_order_v22(cfg):
    """§10 D2 RHS column order. b3_rvh is GONE (RVH is the DV denominator);
    everything else is the v2.1 column order verbatim."""
    fys = _fys_in(cfg)
    names = ["const", _b1name(cfg), _b2name(cfg)]
    if cfg["b4"] is not None:
        names.append(_b4name(cfg))
    if not cfg["offset"]:
        names.append("b5_len")
    if cfg["interaction"]:
        names += ["i_flows_post", "i_zveh_post"]
    if cfg["year_fe"]:
        names += [f"fe_{fy}" for fy in fys[1:]]
    return names, fys


def design_matrix_v22(rows, cfg):
    """(y, X, names, route labels, df) for the fit rows under a model config.

    §10 D1/D2 PRODUCTIVITY estimand: y = log(boardings) - log(RVH) =
    log(boardings/RVH). b3 (log RVH) is PINNED at +1 and moved to the LHS -- it
    is NOT a RHS column. offset=True additionally moves log(length) to the LHS
    (b5 pinned to 1), giving log(b/(RVH*length)) (D5 offset_variant). RVH > 0 is
    asserted on every fit row so the DV is finite (§10 D8)."""
    fys = _fys_in(cfg)[0:]
    df = rows[rows["fy"].isin(_fys_in(cfg))].reset_index(drop=True)
    rvh = df["rvh"].to_numpy(float)
    assert np.all(rvh > 0.0), (
        "productivity DV log(b/RVH) requires RVH > 0 on every fit row "
        f"(min rvh {rvh.min()!r})")
    # PRODUCTIVITY DV: log(b/RVH) = log(b) - log(RVH). b3 pinned at +1, LHS.
    y = df["log_b"].to_numpy(float) - np.log(rvh)
    llen = np.log(df["L"].to_numpy(float))
    if cfg["offset"]:
        y = y - llen
    assert np.all(np.isfinite(y)), "non-finite productivity DV"
    post = df["fy"].isin(("fy2020", "fy2021", "fy2022",
                          "fy2023")).to_numpy(float)
    b1 = _col_b1(df, cfg)
    b2 = _col_b2(df, cfg)
    colmap = {
        "const": np.ones(len(df)),
        _b1name(cfg): b1,
        _b2name(cfg): b2,
        _b4name(cfg): _col_b4(df, cfg),
        "b5_len": llen,
        "i_flows_post": b1 * post,
        "i_zveh_post": b2 * post,
    }
    for fy in fys[1:]:
        colmap[f"fe_{fy}"] = (df["fy"] == fy).to_numpy(float)
    names, _ = col_order_v22(cfg)
    X = np.column_stack([colmap[c] for c in names])
    return y, X, names, df["route"].to_numpy(), df


def fit_nb2(boardings, y, X, start_beta, log_rvh_offset):
    """NB2 RATE-model robustness fit (spec 01 §10 D5): the productivity analogue
    of the v2.1 NB2 row. Fits the boardings COUNT with log(RVH) as a FIXED
    OFFSET (exposure) -- log(E[b]) = log(RVH) + Xbeta, so log(E[b]/RVH) = Xbeta,
    the canonical rate model -- NOT a free b3. Fixed start/maxiter/method;
    lognormal-moment-map starts from the productivity log-OLS fit (`y` is the
    productivity DV; s2 is its residual variance around Xbeta). Returns
    (params, alpha, converged)."""
    import warnings
    from statsmodels.discrete.discrete_model import NegativeBinomial
    resid = y - X @ np.asarray(start_beta, float)
    s2 = float(resid @ resid) / max(len(y) - X.shape[1], 1)
    start = np.asarray(start_beta, float).copy()
    start[0] += s2 / 2.0
    start = np.append(start, np.expm1(s2))
    mod = NegativeBinomial(np.asarray(boardings, float), X,
                           loglike_method="nb2",
                           offset=np.asarray(log_rvh_offset, float))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        res = mod.fit(start_params=start, maxiter=NB_MAXITER,
                      method=NB_METHOD, disp=0)
    return (np.asarray(res.params[:-1]), float(res.params[-1]),
            bool(res.mle_retvals.get("converged", False)))


def nb2_beta_fixed_alpha(counts, X, alpha, beta0, log_rvh_offset,
                         maxiter=40, tol=1e-10):
    """NB2 beta refit at FIXED alpha via Fisher scoring (the stated
    stability-block approximation), RATE-model form: mu = exp(offset + Xbeta)
    with offset = log(RVH) (spec 01 §10 D5)."""
    r = 1.0 / float(alpha)
    beta = np.asarray(beta0, float).copy()
    counts = np.asarray(counts, float)
    off = np.asarray(log_rvh_offset, float)
    for _ in range(maxiter):
        mu = np.exp(np.clip(off + X @ beta, -50.0, 50.0))
        s = (counts - mu) * (r / (r + mu))
        w = mu * r / (r + mu)
        step = np.linalg.lstsq(X.T @ (X * w[:, None]), X.T @ s, rcond=None)[0]
        if not np.all(np.isfinite(step)):
            break
        beta = beta + step
        if float(np.max(np.abs(step))) < tol:
            break
    return beta


def resid_decomposition(rows):
    """v2.2 route-effect / residual variance decomposition of the headline
    PRODUCTIVITY fit (method of moments on the log-OLS residuals grouped by
    route) -- a REPORTED diagnostic."""
    y, X, _, groups, _ = design_matrix_v22(rows, BASE_CFG_V22)
    resid = y - X @ ols_beta(y, X)
    routes = sorted(set(groups), key=_route_sort_key)
    ebars, inv_n, ss_within, dof_within = [], [], 0.0, 0
    for r in routes:
        e = resid[groups == r]
        ebars.append(float(e.mean()))
        inv_n.append(1.0 / len(e))
        ss_within += float(((e - e.mean()) ** 2).sum())
        dof_within += len(e) - 1
    ebars = np.asarray(ebars)
    sig2_resid = ss_within / max(dof_within, 1)
    var_b = float(((ebars - ebars.mean()) ** 2).sum()) / max(len(ebars) - 1, 1)
    sig2_route = max(var_b - sig2_resid * float(np.mean(inv_n)), 0.0)
    return {"sig2_route": sig2_route, "sig2_resid": sig2_resid,
            "n_routes": len(routes), "n_route_years": int(len(y))}


# ---------------------------------------------------------------------------
# printer (fit table + drops)
# ---------------------------------------------------------------------------
def main():
    buf = val("buffer_mi")
    estimand = val("screen_estimand_v22")
    assert estimand == "log(boardings/RVH)", estimand
    data = sv.load_data_v21(acs_vintages=("2017", "2019", "2021", "2023"),
                            lodes_vintages=("2017", "2019", "2021", "2022"))
    cns = load_cns_by_block(data, ("2017", "2019", "2021", "2022"))
    fit = build_fit_rows(data, cns, buf)
    rows = fit["rows"]
    assert np.all(rows["rvh"].to_numpy(float) > 0.0), "RVH>0 required (DV)"
    n_routes = rows["route"].nunique()
    print(f"v2.2 PRODUCTIVITY fit -- DV = {estimand}")
    print(f"fit universe: {len(rows)} route-years, "
          f"{n_routes} distinct routes (clusters)")
    print(f"rows by fy: {rows.groupby('fy').size().to_dict()}")
    print("dropped (no contemporaneous archived shape -- §9.3 shapeless "
          f"rule): {fit['dropped_shapeless']}")
    print("dropped (no validated RVH): "
          f"{[(r, fy) for r, fy, _ in fit['dropped_norvh']]}")
    y, X, names, groups, df = design_matrix_v22(rows, BASE_CFG_V22)
    pri = fit_primary(y, X, names, groups)
    print(f"\nPRIMARY log-OLS on log(b/RVH) (cluster-robust by route; "
          f"N={pri['n']}):")
    for n_, b, s in zip(names, pri["params"], pri["se_cluster"]):
        print(f"  {n_:14s} {b:+9.4f}  (se {s:.4f})  t {b / s:+6.2f}")
    print("\nVIFs:", {k: round(v, 2) for k, v in vifs(X, names).items()})
    print("\nv2.2 residual decomposition:", resid_decomposition(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
