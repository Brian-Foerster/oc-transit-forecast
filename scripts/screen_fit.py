"""Stage-1 screen: route-level fit (spec 01 §3.1 / panel D1-D3, D11, D14).

Fit unit: route-years -- data/derived/route_boardings.csv (47 routes x
{fy2017, fy2019, fy2020q3}) intersected with the 2026-07 GTFS weekday shapes
(the 6 discontinued routes drop; printed by name). PRIMARY estimator =
log-OLS on log(annual boardings) with cluster-robust-by-route SEs; NB2 is a
permanent robustness row fitted alongside (never a silent fallback --
registry `estimator_screen`). Rows within a route are pseudo-replication, so
ALL inference clusters by route and LOO means leave-one-ROUTE-out.

Predictors (5 + intercept + 2 year FE), every catchment quantity through the
SHARED screen_common.compute_predictors (route = full-shape window [0, L]):

    b1  log1p(LODES both-ends-in flows in catchment)
    b2  log1p(zero-vehicle workers, B08141 E002)   [E016 = e016_swap row]
    b3  log(annual revenue hours)                  [allocation control]
    b4  special-generator dummy (geometric)
    b5  log(route length mi)                       [offset_variant row]

FY2020-Q3 (March-in, 9-month YTD -- registry `screen_fy2020_clip`): handled
by the year FE alone; the explicit months_observed=9 exposure offset was NOT
adopted (the FE already absorbs the common truncation level shift, and a
partial offset would fight it), so the pre-registered drop_fy2020 row is the
honest handle. Route-years lacking a validated RVH cell (the 3 KNOWN_BAD_RVH
FY2017 rows) drop from the fit because b3 is unavailable; printed.

    python screen_fit.py     -> prints fit table, coefficients, VIFs, drops
"""
import json
import os
import sys

import numpy as np
import pandas as pd

from assumptions import val
import build_corridor as bc
import screen_common as sc

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
DER = os.path.join(HERE, "..", "data", "derived")
CFGDIR = os.path.join(HERE, "..", "config")

FYS = ("fy2017", "fy2019", "fy2020q3")

# Model-configuration toggles (each non-headline setting is a pre-registered
# sensitivity row; see screen_scan.SENSITIVITY_ROWS). Values here are the
# HEADLINE spec -- the alternatives are enumerated by the registry's
# structural entries, not silent branches.
BASE_CFG = {
    "use_rh": True,        # b3 in (drop_rh row = False)
    "use_e016": False,     # b2 = E002 (e016_swap row = True)
    "b4": True,            # generator dummy in (b4_off row = False)
    "gen_exclude": None,   # gen_leave_class_out rows = one of resort/college/medical
    "year_fe": True,       # year_fe_vs_pooled row = False
    "offset": False,       # b5 free elasticity (offset_variant row = True)
    "drop_fy2020": False,  # drop_fy2020 row = True
}

# NB2 robustness-fit optimizer scaffolding (numerical mechanics, not analytic
# constants -- CANON_DECIMALS precedent; determinism checklist item 1: fixed
# start_params/maxiter/method under pinned statsmodels==0.14.5). Starts are
# DERIVED from the log-OLS fit (lognormal moment map: intercept + s2/2,
# alpha = expm1(s2)), so no tunable literal enters; newton converges cleanly
# where bfgs stalls at the same optimum (probed 2026-07-18).
NB_MAXITER = 200
NB_METHOD = "newton"


# ---------------------------------------------------------------------------
# inputs
# ---------------------------------------------------------------------------
def load_screen_inputs():
    """Tracts (mi frame), ACS E002/E016 (+ MOE-derived SEs for the D9
    bootstrap perturbation), LODES as tract-index arrays, generator sites,
    route_boardings. One load, shared by fit and scan."""
    tr = pd.read_csv(os.path.join(DER, "oc_tracts.csv"), dtype={"GEOID": str})
    tx = tr["lon"].to_numpy() * sc.MI_LON
    ty = tr["lat"].to_numpy() * sc.MI_LAT
    acs = pd.read_csv(os.path.join(DER, "oc_b08141.csv"), dtype={"GEOID": str})
    m = tr[["GEOID"]].merge(acs, on="GEOID", how="left", validate="1:1")
    assert not m["B08141_E002"].isna().any(), "tracts missing from ACS table"
    e002 = m["B08141_E002"].to_numpy(float)
    e016 = m["B08141_E016"].to_numpy(float)
    # ACS 90% MOE -> SE (same conversion as build_corridor's segment SEs)
    se_e002 = m["B08141_M002"].to_numpy(float) / val("moe_z")
    od = pd.read_csv(os.path.join(DER, "oc_tract_od.csv.gz"),
                     dtype={"h": str, "w": str})
    gidx = {g: i for i, g in enumerate(tr["GEOID"])}
    od_h = od["h"].map(gidx)
    od_w = od["w"].map(gidx)
    assert not od_h.isna().any() and not od_w.isna().any(), \
        "LODES GEOIDs missing from oc_tracts.csv"
    gens = json.load(open(os.path.join(CFGDIR, "special_generators.json"),
                          encoding="utf-8"))["generators"]
    gx = np.array([g["lon"] for g in gens]) * sc.MI_LON
    gy = np.array([g["lat"] for g in gens]) * sc.MI_LAT
    gtypes = [g["type"] for g in gens]
    rb = pd.read_csv(os.path.join(DER, "route_boardings.csv"),
                     dtype={"route": str})
    return {"tracts": tr, "tx": tx, "ty": ty,
            "e002": e002, "e016": e016, "se_e002": se_e002,
            "od_h": od_h.to_numpy(int), "od_w": od_w.to_numpy(int),
            "od_n": od["n"].to_numpy(float),
            "gx": gx, "gy": gy, "gtypes": gtypes, "rb": rb}


def _route_sort_key(r):
    return (len(r), r)


def gtfs_universe(inputs):
    """ShapeProj for EVERY GTFS route with a weekday shape (the mechanical
    scan universe before the length filter -- no 'major arterial' filter,
    governance rule 1). Sorted route iteration (determinism item 2)."""
    trips, shapes, st, wk = bc.load_gtfs()
    routes = pd.read_csv(os.path.join(HERE, "..", "data", "raw", "gtfs",
                                      "routes.txt"), dtype=str)
    projs = {}
    for rid in sorted(routes["route_id"], key=_route_sort_key):
        res, L = bc.main_shape_xy(trips, shapes, wk, rid)
        if res is None or L <= 0:
            continue
        x, y = res
        projs[rid] = sc.ShapeProj(rid, x, y,
                                  (inputs["tx"], inputs["ty"]),
                                  (inputs["gx"], inputs["gy"]),
                                  inputs["gtypes"])
    return projs


# ---------------------------------------------------------------------------
# fit table
# ---------------------------------------------------------------------------
def _gen_dummy(gen_types, exclude):
    if exclude is None:
        return 1 if gen_types else 0
    return 1 if any(t != exclude for t in gen_types) else 0


def build_fit_frame(projs, inputs, buffer_mi, views=None):
    """Route-year fit rows + per-route predictor dicts. Every catchment
    quantity via the SHARED compute_predictors on the route's full-shape
    window [0, L]. Routes without a weekday GTFS shape are dropped (printed
    by callers); route-years without boardings or without a validated RVH
    drop (b3 needs log RVH)."""
    rb = inputs["rb"]
    fitted, dropped = [], []
    for r in sorted(rb["route"], key=_route_sort_key):
        (fitted if r in projs else dropped).append(r)
    route_pred, rows, dropped_years = {}, [], []
    for r in fitted:
        proj = projs[r]
        if views is not None and (r, buffer_mi) in views:
            view = views[(r, buffer_mi)]
        else:
            view = sc.CatchmentView(proj, buffer_mi, inputs["od_h"],
                                    inputs["od_w"], inputs["od_n"])
            if views is not None:
                views[(r, buffer_mi)] = view
        p = sc.compute_predictors(view, 0.0, proj.L,
                                  {"e002": inputs["e002"],
                                   "e016": inputs["e016"]})
        p["L"] = proj.L
        route_pred[r] = p
        rrow = rb[rb["route"] == r].iloc[0]
        for fy in FYS:
            b = rrow[fy]
            rvh = rrow["rvh_" + fy]
            if pd.isna(b):
                continue
            if pd.isna(rvh):
                dropped_years.append((r, fy, "no validated RVH"))
                continue
            rows.append({"route": r, "fy": fy,
                         "log_b": float(np.log(b)),
                         "boardings": float(b),
                         "l_lodes": float(np.log1p(p["lodes_both"])),
                         "l_e002": float(np.log1p(p["sum_e002"])),
                         "l_e016": float(np.log1p(p["sum_e016"])),
                         "l_rvh": float(np.log(rvh)),
                         "gen_types": p["gen_types"],
                         "l_len": float(np.log(proj.L))})
    return {"fitted": fitted, "dropped": dropped,
            "dropped_years": dropped_years,
            "route_pred": route_pred,
            "rows": pd.DataFrame(rows)}


# ---------------------------------------------------------------------------
# design matrices
# ---------------------------------------------------------------------------
def col_order(cfg):
    names = ["const", "b1_lodes",
             "b2_e016" if cfg["use_e016"] else "b2_e002"]
    if cfg["use_rh"]:
        names.append("b3_rvh")
    if cfg["b4"]:
        names.append("b4_gen")
    if not cfg["offset"]:
        names.append("b5_len")
    if cfg["year_fe"]:
        names.append("fe_fy2019")
        if not cfg["drop_fy2020"]:
            names.append("fe_fy2020q3")
    return names


def design_matrix(rows, cfg):
    """(y, X, colnames, route labels) for the fit rows under a model config.
    offset=True moves log(length) to the LHS (elasticity pinned at 1)."""
    df = rows[rows["fy"] != "fy2020q3"] if cfg["drop_fy2020"] else rows
    y = df["log_b"].to_numpy(float)
    if cfg["offset"]:
        y = y - df["l_len"].to_numpy(float)
    gen = np.array([_gen_dummy(g, cfg["gen_exclude"])
                    for g in df["gen_types"]], float)
    colmap = {
        "const": np.ones(len(df)),
        "b1_lodes": df["l_lodes"].to_numpy(float),
        "b2_e002": df["l_e002"].to_numpy(float),
        "b2_e016": df["l_e016"].to_numpy(float),
        "b3_rvh": df["l_rvh"].to_numpy(float),
        "b4_gen": gen,
        "b5_len": df["l_len"].to_numpy(float),
        "fe_fy2019": (df["fy"] == "fy2019").to_numpy(float),
        "fe_fy2020q3": (df["fy"] == "fy2020q3").to_numpy(float),
    }
    names = col_order(cfg)
    X = np.column_stack([colmap[c] for c in names])
    return y, X, names, df["route"].to_numpy(), df


def score_design(cols, cfg, svc, lengths, fe2019=0.0):
    """Design matrix for SCORING units (windows or routes) at a common
    service level: b3 = log(svc_per_mi * length); year FE = fe2019 on the
    fy2019 column (0 for index scoring -- a common FE shifts every unit
    identically and cancels in the index). `cols` maps b1/b2/gen arrays."""
    n = len(cols["l_lodes"])
    lengths = np.broadcast_to(np.asarray(lengths, float), (n,))
    colmap = {
        "const": np.ones(n),
        "b1_lodes": cols["l_lodes"],
        "b2_e002": cols["l_e002"],
        "b2_e016": cols["l_e016"],
        "b3_rvh": np.log(svc * lengths),
        "b4_gen": cols["gen"],
        "b5_len": np.log(lengths),
        "fe_fy2019": np.full(n, float(fe2019)),
        "fe_fy2020q3": np.zeros(n),
    }
    return np.column_stack([colmap[c] for c in col_order(cfg)])


def ols_beta(y, X):
    """Deterministic least-squares point fit (minimum-norm on degenerate
    resamples -- used by variants, LOO and the bootstrap; the statsmodels
    primary fit below owns the published SEs)."""
    return np.linalg.lstsq(X, y, rcond=None)[0]


# ---------------------------------------------------------------------------
# estimators + diagnostics
# ---------------------------------------------------------------------------
def fit_primary(y, X, names, groups):
    """log-OLS with cluster-robust-by-route SEs (spec 01 §3.1 D1)."""
    import statsmodels.api as sm
    res = sm.OLS(y, X).fit(cov_type="cluster",
                           cov_kwds={"groups": pd.Categorical(groups).codes})
    return {"params": np.asarray(res.params),
            "se_cluster": np.asarray(res.bse),
            "names": names, "n": int(res.nobs), "res": res}


def fit_nb2(boardings, y, X, start_beta):
    """NB2 robustness fit on the count scale: fixed start_params/maxiter/
    method (determinism item 1); starts derived from the log-OLS point fit
    via the lognormal moment map. Returns (params, alpha, converged)."""
    import warnings
    from statsmodels.discrete.discrete_model import NegativeBinomial
    resid = y - X @ np.asarray(start_beta, float)
    s2 = float(resid @ resid) / max(len(y) - X.shape[1], 1)
    start = np.asarray(start_beta, float).copy()
    start[0] += s2 / 2.0                       # E[b] = exp(mu + s2/2)
    start = np.append(start, np.expm1(s2))     # NB2 alpha ~ Var/mu^2
    mod = NegativeBinomial(np.asarray(boardings, float), X,
                           loglike_method="nb2")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        res = mod.fit(start_params=start, maxiter=NB_MAXITER,
                      method=NB_METHOD, disp=0)
    return (np.asarray(res.params[:-1]), float(res.params[-1]),
            bool(res.mle_retvals.get("converged", False)))


def nb2_beta_fixed_alpha(counts, X, alpha, beta0, maxiter=40, tol=1e-10):
    """NB2 beta refit at FIXED alpha via Fisher scoring (log link).

    The shortlist-stability block's nb_estimator bootstrap refits NB2 in
    every replicate; profiling alpha per replicate via statsmodels (~210
    ms/fit measured, x2000 replicates) is outside that block's runtime
    budget, so per-replicate refits hold alpha at the HEADLINE NB2
    estimate and Fisher-score beta only. STATED APPROXIMATION (spec 01
    §5): a standing test (test_screen.py D7) asserts this routine
    reproduces the statsmodels NB2 beta at the headline alpha (at the
    joint MLE, the fixed-alpha beta optimum IS the joint beta optimum).
    Deterministic: fixed start, iteration cap, tolerance; degenerate
    resamples take the minimum-norm lstsq step; non-finite steps stop the
    iteration at the last finite beta."""
    r = 1.0 / float(alpha)
    beta = np.asarray(beta0, float).copy()
    counts = np.asarray(counts, float)
    for _ in range(maxiter):
        mu = np.exp(np.clip(X @ beta, -50.0, 50.0))
        s = (counts - mu) * (r / (r + mu))       # score contribution
        w = mu * r / (r + mu)                    # Fisher weights
        step = np.linalg.lstsq(X.T @ (X * w[:, None]), X.T @ s,
                               rcond=None)[0]
        if not np.all(np.isfinite(step)):
            break
        beta = beta + step
        if float(np.max(np.abs(step))) < tol:
            break
    return beta


def resid_decomposition(y=None, X=None, groups=None):
    """Route-effect / residual variance decomposition of the COMMITTED v2.0
    headline fit (log-OLS, BASE_CFG) -- the variance-matching source for
    the DESIGN-STAGE power check (spec 01 §9, owner item 3 2026-07-20).
    The registry entry `screen_v20_resid_decomp` pins the measured values;
    scripts/screen_power.py consumes THOSE via val() and never touches
    boardings itself (contamination guard: the v2.1 fit stays unrun; this
    decomposition re-derives the already-committed, already-public v2.0
    fit only). Standing test: test_screen_power.py W2 asserts the registry
    values equal this recompute.

    Extraction (method of moments on the OLS residuals e_ry, grouped by
    route r with n_r fitted years):
      sig2_resid = pooled within-route variance
                 = sum_r sum_y (e_ry - ebar_r)^2 / sum_r (n_r - 1)
      sig2_route = between-route variance of ebar_r minus the within
                   contamination of the route means:
                   var_b(ebar_r) - sig2_resid * mean_r(1/n_r), floored at
                   0, with var_b = sum_r (ebar_r - mean)^2 / (R - 1)."""
    if y is None:
        inputs = load_screen_inputs()
        projs = gtfs_universe(inputs)
        fit = build_fit_frame(projs, inputs, val("buffer_mi"))
        y, X, _, groups, _ = design_matrix(fit["rows"], BASE_CFG)
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


def vifs(X, names):
    """VIF per non-intercept column (required diagnostic, panel D3)."""
    out = {}
    for j, name in enumerate(names):
        if name == "const":
            continue
        others = [k for k in range(X.shape[1]) if k != j]
        beta = ols_beta(X[:, j], X[:, others])
        resid = X[:, j] - X[:, others] @ beta
        ss_res = float(resid @ resid)
        v = X[:, j] - X[:, j].mean()
        ss_tot = float(v @ v)
        r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
        out[name] = float(1.0 / max(1.0 - r2, 1e-12))
    return out


def gen_dfbetas(y, X, names, routes, flagged_routes):
    """Max |dfbeta| on the b4 coefficient over each generator-flagged route's
    rows (plain-OLS influence -- a leverage diagnostic, panel D15)."""
    import statsmodels.api as sm
    from statsmodels.stats.outliers_influence import OLSInfluence
    if "b4_gen" not in names:
        return {}
    res = sm.OLS(y, X).fit()
    dfb = OLSInfluence(res).dfbetas
    j = names.index("b4_gen")
    out = {}
    for r in flagged_routes:
        rows = np.flatnonzero(routes == r)
        if len(rows):
            out[r] = float(np.max(np.abs(dfb[rows, j])))
    return out


# ---------------------------------------------------------------------------
# printer
# ---------------------------------------------------------------------------
def main():
    inputs = load_screen_inputs()
    projs = gtfs_universe(inputs)
    fit = build_fit_frame(projs, inputs, val("buffer_mi"))
    print(f"fit universe: {len(fit['fitted'])} routes with weekday GTFS "
          f"shapes; DROPPED (no 2026-07 shape -- discontinued, survivorship-"
          f"biased low performers): {', '.join(fit['dropped'])}")
    for r, fy, why in fit["dropped_years"]:
        print(f"  dropped route-year {r} {fy}: {why}")
    rows = fit["rows"]
    print(f"fit rows: {len(rows)} route-years "
          f"({rows.groupby('fy').size().to_dict()})")
    y, X, names, groups, _ = design_matrix(rows, BASE_CFG)
    pri = fit_primary(y, X, names, groups)
    print("\nPRIMARY log-OLS (cluster-robust by route):")
    for n_, b, s in zip(names, pri["params"], pri["se_cluster"]):
        print(f"  {n_:12s} {b:+8.4f}  (se {s:.4f})")
    print("  b3_rvh is an allocation control -- not a service response "
          "(spec 02 owns that question)")
    print("\nVIFs:", {k: round(v, 2) for k, v in vifs(X, names).items()})
    beta = ols_beta(y, X)
    _, _, _, _, df = design_matrix(rows, BASE_CFG)
    nb_params, alpha, conv = fit_nb2(df["boardings"].to_numpy(), y, X, beta)
    print(f"\nNB2 robustness fit converged={conv} (alpha {alpha:.5f})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
