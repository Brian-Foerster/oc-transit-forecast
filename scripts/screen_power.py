"""DESIGN-STAGE power check for tripwire criterion 1 under the v2.1 rebuild
(spec 01 §9; owner review 2026-07-20, item 3). Runs BEFORE the v2.1 fit,
which stays unrun.

QUESTION. What true demand elasticities would b1 (log1p LODES flows) and b2
(log1p B25044 zero-vehicle households) need for criterion 1 -- the
route-cluster bootstrap strictly-positive sign fraction >= 0.841
[screen_pos_frac_min] -- to pass with 80% probability at ~41 (current-shape)
and ~47 (re-entrant) route clusters?

CONTAMINATION GUARD (binding; standing tests test_screen_power.py G1/G2).
This module may use (a) v2.1 predictor matrices built INPUT-SIDE via
screen_common_v21, never joined to boardings; (b) the COMMITTED v2.0 fit's
residual variance decomposition, pinned in the registry
(screen_v20_resid_decomp -- extracted once by the v2.0 module, consumed
here via val()); (c) synthetic log-boardings generated from INJECTED true
coefficients. It NEVER regresses real boardings on v2.1 predictors: no
estimator in this file ever sees a real outcome value. load_rvh() reads
data/derived/route_boardings.csv ONLY for the fittable route-year mask and
the validated RVH values (b3 is a v2.1 predictor); boardings values are
dropped inside that function and never leave it.

RECIPE (owner item 3):
  (a) v2.1 fit-side predictor matrix for the 41 current-shape routes x
      vintages (full-shape windows, §9.3 dispatch); MEASURE the
      within-route across-year variation of each predictor -- this doubles
      as §9.3's LOYO condition and resolves LOYO membership in the frozen
      v2.1 battery (screen_battery_rows_v21) on an input-side fact.
  (b) the 6 re-entering routes (24/82/153/53X/57X/64X) are simulated as
      X-replicas of the 6 LOWEST-l_flows fitted routes (fy2019 vintage,
      input-side ranking; independent route effects) -- a stated
      stylization honoring the survivorship fact that the discontinued
      routes were low performers; it adds clusters WITHOUT adding covariate
      support, so the 47-cluster gain is a precision gain only.
      Sensitivity: power reported at 41 AND 47 clusters.
  (c) synthetic log-boardings y = X @ beta_true + u_route + eps, with
      Var(u_route) = sig2_route and Var(eps) = sig2_resid matched to the
      committed v2.0 fit's cluster decomposition (registry
      screen_v20_resid_decomp; extraction documented there). Year FE
      columns are IN the design; their true values (and every non-demand
      coefficient's) are set to 0 WLOG -- OLS estimator error
      beta_hat - beta_true = (X'X)^-1 X'u is invariant to beta_true, so
      power depends on beta_true ONLY through the gridded coefficient
      itself (exact, not approximate; also why the marginal designs are
      exact at any value of the other coefficient).
  (d) beta_true grid over [0, 0.8] step 0.05 [screen_power_check], joint
      (b1 = b2 = g) and marginal (per-coefficient; exact by the invariance
      above) designs; S = 200 simulated datasets per grid point (common
      random numbers across grid points -- the bootstrap noise deltas are
      computed once per sim and reused, an EXACT algebraic reduction, not
      an approximation); per dataset the EXACT criterion-1 statistic:
      route-cluster bootstrap refit, strictly-positive sign fraction,
      B = 500, with a small-B check at one grid point vs B = 2000
      (tolerance stated in the registry dict; TESTED by W3).
  (e) power curves, required-elasticity-at-80%-power, in-repo reference
      comparison (no invented citations), and the verdict field with the
      arithmetic visible.

STATED STYLIZATIONS (honest list, artifact `stylizations`):
  - fit-side shapes are the CURRENT (2026-07) GTFS for all years; the real
    v2.1 fit uses archived per-year shapes (§9.4), so l_len is
    time-invariant here and the re-entrant routes' true geometry is absent;
  - the within-replicate ACS-MOE perturbation of the real criterion-1
    bootstrap is OMITTED (no B25044 MOE is wired input-side yet); omitting
    a noise source makes simulated power OPTIMISTIC, so the required
    elasticities are a FLOOR;
  - bootstrap refits solve the resampled normal equations (Gram-sum form,
    exactly the resampled-row OLS when nonsingular; min-norm lstsq
    fallback on the normal equations for degenerate resamples).

PANEL EXTENSION (spec 01 §9.9; owner directive 2026-07-20 "extend the
panel"). The artifact carries a panel_ext block: the same question
re-asked on the EXTENDED design -- route x FY presence from
route_boardings.csv UNION route_boardings_ext.csv (presence + validated
RVH ONLY, guarded loader load_rvh_ext; the §9.9.5 guard extension --
boardings values are dropped inside the loader and never leave it),
vintage-matched X per §9.9.2 (fy2020 -> 2019 tables; fy2021 -> 2021;
fy2022/fy2023 -> 2022 LODES / 2019-23 ACS, fy2023 frozen on 2022 by the
stated decision), extended-panel year FE, same grid/S/B/seed knobs
[screen_power_check] and the SAME committed v2.0 variance decomposition
[screen_v20_resid_decomp] -- no variance is re-estimated from any new
data. Designs: ext_current_shape (every union route with a 2026-07
weekday shape) and ext_with_replicas (+ one X-replica cluster per
no-shape union route with fittable rows -- the donor stylization carried
over, donors = the N lowest-l_flows fitted routes at the fy2019
vintage). The block reports BEFORE/AFTER required elasticities against
the committed 3-year numbers and the verdict recomputed under the
pre-stated registry rule (ext_with_replicas standing in for the
47-cluster design, §9.9.6). The baseline 3-year blocks are regenerated
bit-identically (same seed stream, drawn first). The frozen extended
year list is the registry constant [screen_panel_ext_fys].

Artifact: outputs/screen_power_check.json -- deterministic write
(sort_keys, indent=2, LF, floats 6dp, no timestamps; seeded default_rng;
dual fresh-process byte-identity is a commit gate). Chart:
outputs/screen_power_check.png.

    python -X utf8 scripts/screen_power.py
"""
import json
import math
import os
import sys

import numpy as np
import pandas as pd

from assumptions import val
import build_corridor as bc
import network_mechanics as nm          # canonical fingerprint (acyclic)
import screen_common_v21 as sv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "outputs")
DER = os.path.join(HERE, "..", "data", "derived")

SCHEMA = "01-P2"
CANON_DECIMALS = 6
FYS = ("fy2017", "fy2019", "fy2020q3")
NAMES = ("const", "b1_flows", "b2_zveh", "b3_rvh", "b4_genjobs", "b5_len",
         "fe_fy2019", "fe_fy2020q3")
SLOPES = NAMES[:6]                 # const + the 5 §9.1 slopes (FE appended)
# the 6 discontinued APC routes that re-enter the v2.1 fit (spec 01 §9.4)
REENTRANT = ("24", "82", "153", "53X", "57X", "64X")
# §9.9.1 committed-table years that survive into the extended panel
# (fy2020q3 is SUPERSEDED by the ext full-year fy2020 and never co-enters)
COMMITTED_EXT_FYS = ("fy2017", "fy2019")

DISCLAIMER = ("design-stage power simulation on SYNTHETIC outcomes; not a "
              "fit, not a forecast, and no statement about measured "
              "coefficients (spec 01 §9 pre-registration hold)")


def _sort_key(r):
    return (len(r), r)


# ---------------------------------------------------------------------------
# canonical serialization (screen_scan.py write pattern)
# ---------------------------------------------------------------------------
def _canon(o):
    if isinstance(o, dict):
        return {k: _canon(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_canon(v) for v in o]
    if isinstance(o, (np.floating, float)):
        return round(float(o), CANON_DECIMALS)
    if isinstance(o, (np.bool_, bool)):
        return bool(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, np.ndarray):
        return _canon(o.tolist())
    return o


def write_artifact(path, artifact):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(_canon(artifact), f, sort_keys=True, indent=2)
        f.write("\n")


# ---------------------------------------------------------------------------
# inputs (BOARDINGS-FREE beyond the documented mask)
# ---------------------------------------------------------------------------
def load_rvh():
    """Fittable route-years + validated RVH (the b3 v2.1 predictor
    passthrough). Reads data/derived/route_boardings.csv for (i) the
    fittable mask -- boardings present AND validated RVH present, the same
    row universe the committed v2.0 fit uses -- and (ii) the rvh_* values.
    Boardings VALUES are consulted only for presence (notna) and are
    dropped here; the returned frame carries route/fy/rvh ONLY (standing
    test G2)."""
    rb = pd.read_csv(os.path.join(DER, "route_boardings.csv"),
                     dtype={"route": str})
    rows = []
    for _, rr in rb.iterrows():
        for fy in FYS:
            if pd.notna(rr[fy]) and pd.notna(rr["rvh_" + fy]):
                rows.append({"route": str(rr["route"]), "fy": fy,
                             "rvh": float(rr["rvh_" + fy])})
    df = pd.DataFrame(rows, columns=["route", "fy", "rvh"])
    return df.sort_values(["route", "fy"],
                          key=lambda s: (s.map(_sort_key)
                                         if s.name == "route" else s)
                          ).reset_index(drop=True)


def load_rvh_ext():
    """EXTENDED-panel fittable route-years + validated RVH (spec 01 §9.9;
    the §9.9.5 GUARDED LOADER -- presence + RVH only). Committed table:
    the fy2017/fy2019 cells exactly as load_rvh reads them; fy2020q3 is
    SUPERSEDED by the ext full-year fy2020 and never enters the extended
    panel (§9.9.1). Ext table (data/derived/route_boardings_ext.csv, long
    format): the frozen new FYs [screen_panel_ext_fys]; boardings values
    are consulted for presence (notna) ONLY and dropped here; the single
    blank-RVH cell (560, fy2022, KNOWN_DUP_RVH_EXT) drops by the same
    fittable rule the committed panel uses. Returns route/fy/rvh ONLY
    (standing test G2e)."""
    fys_ext = tuple(val("screen_panel_ext_fys"))
    rb = pd.read_csv(os.path.join(DER, "route_boardings.csv"),
                     dtype={"route": str})
    rows = []
    for _, rr in rb.iterrows():
        for fy in COMMITTED_EXT_FYS:
            if pd.notna(rr[fy]) and pd.notna(rr["rvh_" + fy]):
                rows.append({"route": str(rr["route"]), "fy": fy,
                             "rvh": float(rr["rvh_" + fy])})
    re_ = pd.read_csv(os.path.join(DER, "route_boardings_ext.csv"),
                      dtype={"route": str})
    bad = sorted(set(re_["fy"]) - set(fys_ext))
    if bad:
        raise ValueError(f"route_boardings_ext.csv carries FY labels "
                         f"outside the frozen §9.9.1 set: {bad} -- "
                         "extending the year set is a governed spec "
                         "amendment, not a data-file side effect")
    for _, rr in re_.iterrows():
        if pd.notna(rr["boardings"]) and pd.notna(rr["rvh"]):
            rows.append({"route": str(rr["route"]), "fy": str(rr["fy"]),
                         "rvh": float(rr["rvh"])})
    df = pd.DataFrame(rows, columns=["route", "fy", "rvh"])
    return df.sort_values(["route", "fy"],
                          key=lambda s: (s.map(_sort_key)
                                         if s.name == "route" else s)
                          ).reset_index(drop=True)


def fit_universe(data, routes):
    """ShapeProjV21 for every requested route with a current weekday GTFS
    shape (the 41-route current-shape fit universe; sorted iteration)."""
    trips, shapes, st, wk = bc.load_gtfs()
    projs = {}
    for rid in sorted(set(routes), key=_sort_key):
        res, L = bc.main_shape_xy(trips, shapes, wk, rid)
        if res is None or L <= 0:
            continue
        x, y = res
        projs[rid] = data.proj(rid, x, y)
    return projs


# ---------------------------------------------------------------------------
# (a) v2.1 fit-side predictors + the within-route across-year X variation
# ---------------------------------------------------------------------------
def route_vintage_predictors(data, projs, fys=FYS):
    """{route: {fy: predictor dict}} -- the §9.1 vector on the full-shape
    window [0, L] per §9.3/§9.9.2 vintage dispatch (input-side; no RVH
    needed)."""
    out = {}
    for rid in sorted(projs, key=_sort_key):
        proj = projs[rid]
        out[rid] = {fy: sv.compute_predictors_v21(data, proj, 0.0, proj.L,
                                                  fy)
                    for fy in fys}
    return out


def measure_x_variation(preds, rvh, fys=FYS):
    """Within-route across-year variation per §9.1 predictor -- §9.3's LOYO
    condition, measured mechanically. Vintage-matched predictors (l_flows,
    l_zveh_hh, l_genjobs) vary iff the 2017 tables differ from the 2019
    tables on the route's catchment; l_rvh varies through the measured
    annual RVH; l_len is time-invariant HERE by the current-shape
    stylization (archived per-year shapes would move it, §9.4).

    LOYO resolution rule (stated): leave-one-year-out returns to the v2.1
    battery IFF every vintage-matched predictor shows nonzero within-route
    across-year variance for a MAJORITY (> 0.5 share) of fitted routes."""
    keys = ("l_flows", "l_zveh_hh", "l_genjobs", "l_len")
    stats = {}

    def _stat(stds, varying):
        stds = np.array(stds)
        return {
            "n_routes": int(len(stds)),
            # 'varying' is the EXACT max-min > 0 test (np.std of identical
            # values returns a last-ulp ~4e-16 from the mean arithmetic,
            # which must not read as real variation)
            "share_routes_varying": float(np.mean(varying)),
            "mean_within_std": float(stds.mean()),
            "median_within_std": float(np.median(stds)),
            "max_within_std": float(stds.max()),
        }

    for k in keys:
        stds, varying = [], []
        for rid, byfy in preds.items():
            v = np.array([byfy[fy][k] for fy in fys])
            stds.append(float(v.std()))          # population std over fys
            varying.append(bool(v.max() - v.min() > 0.0))
        stats[k] = _stat(stds, varying)
    # l_rvh from the fittable table (routes with >= 2 fitted years)
    stds, varying = [], []
    for rid, g in rvh.groupby("route"):
        if len(g) >= 2:
            v = np.log(g["rvh"].to_numpy())
            stds.append(float(v.std()))
            varying.append(bool(v.max() - v.min() > 0.0))
    stats["l_rvh"] = _stat(stds, varying)
    vm = ("l_flows", "l_zveh_hh", "l_genjobs")
    loyo_in = all(stats[k]["share_routes_varying"] > 0.5 for k in vm)
    return stats, {
        "rule": "LOYO returns to the v2.1 battery IFF every vintage-"
                "matched predictor (l_flows, l_zveh_hh, l_genjobs) has "
                "nonzero within-route across-year variance for > 0.5 of "
                "fitted routes (spec 01 §9.3 condition, operationalized "
                "input-side)",
        "shares": {k: stats[k]["share_routes_varying"] for k in vm},
        "loyo_in_battery": bool(loyo_in),
        "note": "resolved in THIS design-stage batch on the measured "
                "input-side fact (owner item 2); recorded in the registry "
                "entry screen_battery_rows_v21. l_len is time-invariant "
                "here only by the current-shape stylization",
    }


# ---------------------------------------------------------------------------
# design matrices (synthetic-outcome world; no y anywhere)
# ---------------------------------------------------------------------------
def build_design(preds, rvh, extra=None, panel_fys=FYS, names=NAMES):
    """Row-per-fittable-route-year design matrix on the §9.1 columns +
    year FE for panel_fys[1:] (base year = panel_fys[0]). `extra` maps
    simulated cluster ids -> donor route ids (the with-replicas variant);
    simulated clusters replicate the donor's rows under a NEW cluster
    label. Returns X, cluster labels, row fys."""
    fittable = {(r, fy): rv for r, fy, rv in
                rvh.itertuples(index=False, name=None)}
    rows, clusters, fys = [], [], []

    def add_route(cluster, rid):
        for fy in panel_fys:
            if (rid, fy) not in fittable:
                continue
            p = preds[rid][fy]
            rows.append([1.0, p["l_flows"], p["l_zveh_hh"],
                         math.log(fittable[(rid, fy)]), p["l_genjobs"],
                         p["l_len"]]
                        + [1.0 if fy == f else 0.0 for f in panel_fys[1:]])
            clusters.append(cluster)
            fys.append(fy)

    for rid in sorted(preds, key=_sort_key):
        add_route(rid, rid)
    if extra:
        for sim_id in sorted(extra, key=_sort_key):
            add_route("sim" + sim_id, extra[sim_id])
    return {"X": np.array(rows), "clusters": np.array(clusters),
            "fys": fys, "names": list(names),
            "route_list": sorted(set(clusters), key=_sort_key)}


def pick_donors(preds, missing=REENTRANT):
    """Donor routes for the no-current-shape clusters: the N fitted routes
    with the LOWEST fy2019-vintage l_flows (input-side ranking;
    deterministic tie-break by route id), N = len(missing). Returns
    {missing_id: donor_id} with the missing ids in sorted order mapped to
    donors in ascending-flows order."""
    ranked = sorted(preds, key=lambda r: (preds[r]["fy2019"]["l_flows"],
                                          _sort_key(r)))
    donors = ranked[:len(missing)]
    return {rid: donors[i]
            for i, rid in enumerate(sorted(missing, key=_sort_key))}


# ---------------------------------------------------------------------------
# (c)/(d) simulation: exact criterion-1 bootstrap deltas
# ---------------------------------------------------------------------------
def simulate_deltas(design, sig2_route, sig2_resid, n_sims, n_boot, rng):
    """For each simulated dataset s and bootstrap replicate b, the OLS
    estimator NOISE delta_j[s, b] = (X'X)_c^-1 (X'u)_c on the resampled
    clusters, for j in {b1, b2}. beta_hat = beta_true + delta EXACTLY
    (OLS linearity), so one (S, B) noise array serves every grid point
    (common random numbers across the grid -- an exact reduction).

    Per replicate the resampled normal equations are solved via per-route
    Gram sums -- identical to refitting OLS on the concatenated resampled
    rows whenever X'X is nonsingular; degenerate resamples fall back to
    min-norm lstsq on the normal equations (documented stylization)."""
    X, clusters = design["X"], design["clusters"]
    routes = design["route_list"]
    nR, k = len(routes), X.shape[1]
    ridx = {r: i for i, r in enumerate(routes)}
    row_route = np.array([ridx[c] for c in clusters])
    Xr = [X[row_route == i] for i in range(nR)]
    grams = np.stack([x.T @ x for x in Xr])          # (nR, k, k)
    j1, j2 = design["names"].index("b1_flows"), design["names"].index(
        "b2_zveh")
    sd_r, sd_e = math.sqrt(sig2_route), math.sqrt(sig2_resid)
    D1 = np.empty((n_sims, n_boot))
    D2 = np.empty((n_sims, n_boot))
    gflat = grams.reshape(nR, k * k)
    for s in range(n_sims):
        u = (sd_r * rng.standard_normal(nR))[row_route] \
            + sd_e * rng.standard_normal(len(X))
        mu = np.stack([Xr[i].T @ u[row_route == i] for i in range(nR)])
        draws = rng.integers(0, nR, (n_boot, nR))
        counts = np.zeros((n_boot, nR))
        for b in range(n_boot):
            counts[b] = np.bincount(draws[b], minlength=nR)
        XtX = (counts @ gflat).reshape(n_boot, k, k)
        Xtu = counts @ mu
        try:
            delta = np.linalg.solve(XtX, Xtu[..., None])[..., 0]
        except np.linalg.LinAlgError:                # degenerate resample
            delta = np.stack([np.linalg.lstsq(XtX[b], Xtu[b], rcond=None)[0]
                              for b in range(n_boot)])
        D1[s] = delta[:, j1]
        D2[s] = delta[:, j2]
    return D1, D2


def power_curves(D1, D2, grid, pf_min, n_boot):
    """P(pass criterion 1) vs beta_true: marginal per coefficient (exact at
    any value of the other coefficient) + joint at b1 = b2 = g. pass for a
    sim = strictly-positive sign fraction over the first n_boot replicates
    >= pf_min."""
    d1, d2 = D1[:, :n_boot], D2[:, :n_boot]
    p1, p2, pj = [], [], []
    for g in grid:
        f1 = (g + d1 > 0.0).mean(axis=1)
        f2 = (g + d2 > 0.0).mean(axis=1)
        pass1, pass2 = f1 >= pf_min, f2 >= pf_min
        p1.append(float(pass1.mean()))
        p2.append(float(pass2.mean()))
        pj.append(float((pass1 & pass2).mean()))
    return {"b1": p1, "b2": p2, "joint": pj}


def required_at(grid, power, target):
    """Smallest grid crossing of `target`, linearly interpolated; None when
    the curve never reaches it."""
    for i, p in enumerate(power):
        if p >= target:
            if i == 0:
                return float(grid[0])
            g0, g1 = grid[i - 1], grid[i]
            p0, p1 = power[i - 1], power[i]
            if p1 == p0:
                return float(g1)
            return float(g0 + (target - p0) * (g1 - g0) / (p1 - p0))
    return None


# ---------------------------------------------------------------------------
# artifact assembly
# ---------------------------------------------------------------------------
def build_power_artifact(n_sims=None, quiet=False):
    cfg = dict(val("screen_power_check"))
    dec = dict(val("screen_v20_resid_decomp"))
    pf_min = float(val("screen_pos_frac_min"))
    fys_ext = tuple(val("screen_panel_ext_fys"))
    names_ext = tuple(SLOPES) + tuple("fe_" + fy for fy in fys_ext[1:])
    if n_sims is not None:
        cfg["n_sims"] = int(n_sims)              # test override (D-run)
    grid = [round(i * cfg["beta_grid_step"], 6) for i in
            range(int(round(cfg["beta_grid_max"] / cfg["beta_grid_step"]))
                  + 1)]

    if not quiet:
        print("loading v2.1 input-side data (2017/2019/2021/2022 LODES, "
              "2017/2019/2021/2023 ACS vintages)...")
    data = sv.load_data_v21(acs_vintages=("2017", "2019", "2021", "2023"),
                            lodes_vintages=("2017", "2019", "2021", "2022"))
    rvh = load_rvh()
    rvh_ext = load_rvh_ext()
    union_routes = sorted(set(rvh["route"]) | set(rvh_ext["route"]),
                          key=_sort_key)
    projs_all = fit_universe(data, union_routes)
    # baseline (committed 3-year) universe -- IDENTICAL to the pre-§9.9
    # run: committed-table routes with a current shape
    projs = {r: projs_all[r]
             for r in sorted(set(rvh["route"]) & set(projs_all),
                             key=_sort_key)}
    dropped = sorted(set(rvh["route"]) - set(projs), key=_sort_key)
    rvh = rvh[rvh["route"].isin(projs)].reset_index(drop=True)
    if not quiet:
        print(f"fit universe: {len(projs)} current-shape routes "
              f"({len(rvh)} fittable route-years); no current shape: "
              f"{', '.join(dropped)}")
    preds = route_vintage_predictors(data, projs)
    xvar, loyo = measure_x_variation(preds, rvh)

    donors = pick_donors(preds)
    d41 = build_design(preds, rvh)
    d47 = build_design(preds, rvh, extra=donors)
    if not quiet:
        print(f"designs: {len(d41['route_list'])} clusters / "
              f"{len(d41['X'])} rows; {len(d47['route_list'])} clusters / "
              f"{len(d47['X'])} rows; donors {donors}")

    # §9.9 extended panel: union presence, extended year FE, §9.9.2 vintages
    missing_ext = sorted(set(rvh_ext["route"]) - set(projs_all),
                         key=_sort_key)
    rvh_ext_f = rvh_ext[rvh_ext["route"].isin(projs_all)] \
        .reset_index(drop=True)
    projs_ext = {r: projs_all[r]
                 for r in sorted(set(rvh_ext_f["route"]), key=_sort_key)}
    preds_ext = route_vintage_predictors(data, projs_ext, fys=fys_ext)
    xvar_ext, _loyo_ext_unused = measure_x_variation(preds_ext, rvh_ext_f,
                                                     fys=fys_ext)
    donors_ext = pick_donors(preds_ext, missing=missing_ext)
    d_ext_cs = build_design(preds_ext, rvh_ext_f, panel_fys=fys_ext,
                            names=names_ext)
    d_ext_wr = build_design(preds_ext, rvh_ext_f, extra=donors_ext,
                            panel_fys=fys_ext, names=names_ext)
    if not quiet:
        print(f"panel_ext: {len(projs_ext)} current-shape routes / "
              f"{len(d_ext_cs['X'])} rows; with replicas "
              f"{len(d_ext_wr['route_list'])} clusters / "
              f"{len(d_ext_wr['X'])} rows; no-shape replicas "
              f"{', '.join(missing_ext)}")

    rng = np.random.default_rng(cfg["seed"])
    results, curves = {}, {}
    for label, design in (("clusters_41", d41), ("clusters_47", d47),
                          ("ext_current_shape", d_ext_cs),
                          ("ext_with_replicas", d_ext_wr)):
        if not quiet:
            print(f"simulating {label} (S={cfg['n_sims']}, "
                  f"B={cfg['n_boot_check']} drawn, {cfg['n_boot']} used)...")
        D1, D2 = simulate_deltas(design, dec["sig2_route"],
                                 dec["sig2_resid"], cfg["n_sims"],
                                 cfg["n_boot_check"], rng)
        pw = power_curves(D1, D2, grid, pf_min, cfg["n_boot"])
        req = {k: required_at(grid, pw[k], cfg["power_target"])
               for k in ("b1", "b2", "joint")}
        # small-B check at ONE grid point: B=500 vs the full B=2000 draw
        gchk = float(cfg["check_beta"])
        pw_chk_500 = power_curves(D1, D2, [gchk], pf_min, cfg["n_boot"])
        pw_chk_2000 = power_curves(D1, D2, [gchk], pf_min,
                                   cfg["n_boot_check"])
        diffs = {k: abs(pw_chk_500[k][0] - pw_chk_2000[k][0])
                 for k in ("b1", "b2", "joint")}
        curves[label] = pw
        results[label] = {
            "n_clusters": len(design["route_list"]),
            "n_rows": int(len(design["X"])),
            "power": pw,
            "required_at_power_target": req,
            "boot_sd_b1": float(D1[:, :cfg["n_boot"]].std()),
            "boot_sd_b2": float(D2[:, :cfg["n_boot"]].std()),
            "small_b_check": {
                "beta_true": gchk,
                "power_b500": {k: pw_chk_500[k][0] for k in pw_chk_500},
                "power_b2000": {k: pw_chk_2000[k][0] for k in pw_chk_2000},
                "abs_diff": diffs,
                "tolerance": cfg["tol_small_b"],
                "pass": bool(max(diffs.values()) <= cfg["tol_small_b"]),
                "note": "the B=2000 replicates are a superset draw of the "
                        "B=500 replicates (nested common random numbers); "
                        "the stated small-B correction is: none applied -- "
                        "the check bounds the sign-fraction Monte Carlo "
                        "error's effect on power at one grid point instead",
            },
        }

    # verdict (rule pre-stated in the registry provenance): compare the
    # with-replicas marginal required elasticities against the committed
    # v2.0 point estimates +/- verdict_se_mult cluster SEs -- the only
    # committed fit evidence in the repo. v2.0 b1/b2 are the
    # E002-generation analogues, read from the PUBLIC screen artifact
    # (guard clause b). Applied twice: to the 47-cluster 3-year design
    # (the committed baseline verdict) and to ext_with_replicas (the
    # §9.9.6 recomputation -- same rule, the extended design standing in
    # for the 47-cluster one).
    sr_path = os.path.join(OUT, "screen_results.json")
    with open(sr_path, encoding="utf-8") as f:
        coef = json.load(f)["fit_diagnostics"]["coefficients"]
    v20 = {"b1": coef["b1_lodes"], "b2": coef["b2_e002"]}
    order = {"adequately-powered": 0, "marginal": 1, "underpowered": 2}

    def apply_verdict_rule(design_label):
        terms, worst = {}, "adequately-powered"
        for k in ("b1", "b2"):
            req = results[design_label]["required_at_power_target"][k]
            est = v20[k]["est"]
            hi = est + cfg["verdict_se_mult"] * v20[k]["se_cluster"]
            if req is None:
                v = "underpowered"
            elif req <= est:
                v = "adequately-powered"
            elif req <= hi:
                v = "marginal"
            else:
                v = "underpowered"
            terms[k] = {
                "required_at_80pct": req,
                "design": design_label,
                "v20_committed_est": est,
                "v20_cluster_se": v20[k]["se_cluster"],
                "upper_ref_est_plus_2se": hi,
                "call": v,
                "arithmetic": ("required "
                               + (f"{req:.4f}" if req is not None
                                  else "never reached on [0, 0.8]")
                               + f" vs est {est:.6f} / est+"
                               f"{cfg['verdict_se_mult']:.0f}se {hi:.6f}"),
            }
            if order[v] > order[worst]:
                worst = v
        return terms, worst

    verdict_terms, worst = apply_verdict_rule("clusters_47")
    verdict_terms_ext, worst_ext = apply_verdict_rule("ext_with_replicas")

    consumed = [{"id": cid, "value": val(cid)} for cid in
                ("screen_power_check", "screen_v20_resid_decomp",
                 "screen_pos_frac_min", "buffer_mi", "gen_jobs_naics",
                 "screen_panel_ext_fys")]
    values_hash = nm.network_fingerprint(
        {c["id"]: c["value"] for c in consumed})
    run_id = nm.network_fingerprint({
        "schema": SCHEMA, "values_hash": values_hash,
        "universe": {"n_routes": len(projs), "n_rows_41": len(d41["X"]),
                     "n_rows_47": len(d47["X"]),
                     "n_routes_ext": len(projs_ext),
                     "n_rows_ext_cs": len(d_ext_cs["X"]),
                     "n_rows_ext_wr": len(d_ext_wr["X"])}})

    artifact = {
        "run_id": run_id, "schema": SCHEMA,
        "seed": cfg["seed"], "n_sims": cfg["n_sims"],
        "n_boot": cfg["n_boot"], "n_boot_check": cfg["n_boot_check"],
        "disclaimer": DISCLAIMER,
        "assumptions_manifest": {"consumed": consumed,
                                 "values_hash": values_hash},
        "criterion": {
            "statistic": "per-coefficient route-cluster bootstrap "
                         "strictly-positive sign fraction (the EXACT "
                         "criterion-1 statistic, spec 01 §5)",
            "pos_frac_min": pf_min,
            "power_target": cfg["power_target"],
        },
        "beta_grid": grid,
        "x_variation": xvar,
        "loyo_resolution": loyo,
        "variance_matching": {
            **dec,
            "source": "registry screen_v20_resid_decomp -- method-of-"
                      "moments decomposition of the COMMITTED v2.0 "
                      "headline log-OLS residuals by route "
                      "(screen_fit.resid_decomposition; pinned by "
                      "test_screen_power.py W2)",
        },
        "designs": {k: results[k] for k in ("clusters_41", "clusters_47")},
        "reentrant_stylization": {
            "donors": donors,
            "note": "re-entering routes are X-replicas of the 6 lowest-"
                    "l_flows fitted routes (fy2019 vintage, input-side "
                    "ranking) with independent route effects -- adds "
                    "clusters, not covariate support; real archived "
                    "shapes (§9.4) would differ",
        },
        "panel_ext": {
            "directive": "owner directive 2026-07-20: 'extend the panel' "
                         "(spec 01 §9.9 -- pre-fit, made on the committed "
                         "3-year power arithmetic; governed design change "
                         "under the softened §9.5, README known issue 39)",
            "frozen_year_set": list(fys_ext),
            "new_fys": sorted(set(fys_ext) - set(COMMITTED_EXT_FYS)),
            "fy2020q3_superseded": "fy2020 full-year replaces the "
                                   "committed 9-month fy2020q3 cell (one "
                                   "FY, one row per route; §9.9.1 -- "
                                   "every fy2020q3-fittable route has an "
                                   "ext fy2020 row, so no cluster drops)",
            "vintage_map": {fy: sv.resolve_vintage(fy) for fy in fys_ext},
            "row_source": "route x FY PRESENCE from route_boardings.csv "
                          "UNION route_boardings_ext.csv + validated RVH "
                          "(the b3 passthrough); boardings values never "
                          "leave the guarded loaders (standing tests "
                          "G1/G2/G2e); fittable = boardings present AND "
                          "validated RVH present -- the 560/fy2022 "
                          "KNOWN_DUP_RVH_EXT blank drops by that rule; "
                          "NO boardings floor on the new FYs (§9.9.1)",
            "x_variation": xvar_ext,
            "x_variation_note": "INFORMATIONAL on the extended panel "
                                "(6 vintage labels, 50 routes); battery "
                                "membership incl. loyo stays FROZEN on "
                                "the committed 3-year resolution "
                                "(screen_battery_rows_v21, §9.8)",
            "designs": {k: results[k] for k in
                        ("ext_current_shape", "ext_with_replicas")},
            "replica_stylization": {
                "replicas": missing_ext,
                "donors": donors_ext,
                "note": "no-current-shape union routes enter as X-replicas "
                        "of the lowest-l_flows fitted routes (fy2019 "
                        "vintage, input-side ranking); each replica "
                        "duplicates the DONOR's fittable route-years "
                        "across the extended panel under a new cluster "
                        "label (donor presence pattern, not the missing "
                        "route's -- the committed mechanics carried "
                        "over), so the cluster-count gain is a precision "
                        "gain without covariate support",
            },
            "before_after": {
                "required_at_80pct": {
                    k: {"before_clusters_41":
                        results["clusters_41"]
                        ["required_at_power_target"][k],
                        "after_ext_current_shape":
                        results["ext_current_shape"]
                        ["required_at_power_target"][k],
                        "before_clusters_47":
                        results["clusters_47"]
                        ["required_at_power_target"][k],
                        "after_ext_with_replicas":
                        results["ext_with_replicas"]
                        ["required_at_power_target"][k]}
                    for k in ("b1", "b2", "joint")},
                "note": "BEFORE = the committed 3-year-panel designs, "
                        "regenerated in-run on the identical seed stream "
                        "(drawn first); AFTER = the §9.9 extended panel",
            },
            "verdict": {
                "rule": "the pre-stated registry rule "
                        "(screen_power_check) recomputed on the extended "
                        "design: compare the WITH-REPLICAS marginal "
                        "required-at-80% elasticities (§9.9.6 -- the "
                        "extended analogue of the 47-cluster design) "
                        "against the committed v2.0 point estimates: "
                        "adequately-powered if required <= est; marginal "
                        "if <= est + verdict_se_mult * cluster SE; else "
                        "underpowered; overall = worst coefficient",
                "terms": verdict_terms_ext,
                "overall": worst_ext,
            },
            "stylizations": [
                "all baseline stylizations apply (current shapes for all "
                "years; no ACS-MOE perturbation -- power OPTIMISTIC, "
                "required elasticities a FLOOR; Gram-sum refits; common "
                "random numbers)",
                "fy2023 X frozen on LODES 2022 (§9.9.2 stated decision; "
                "LODES8 2023 raws staged, no derived tables)",
                "13 donor-replicated clusters (vs 6 in the baseline "
                "design) -- a heavier replication load, stated",
            ],
        },
        "stylizations": [
            "current-shape geometry for all years (archived per-year "
            "shapes pending; l_len time-invariant here)",
            "no within-replicate ACS-MOE perturbation (no B25044 MOE "
            "wired input-side) -- power is OPTIMISTIC, required "
            "elasticities are a FLOOR",
            "Gram-sum bootstrap refits (== resampled-row OLS when "
            "nonsingular; min-norm lstsq fallback)",
            "common random numbers across grid points (exact reduction: "
            "OLS noise is invariant to beta_true)",
        ],
        "literature_comparison": {
            "in_repo_reference_points": {
                "v20_committed_b1_lodes": v20["b1"],
                "v20_committed_b2_e002": v20["b2"],
                "spec02_induced_demand_elasticity_prior": [0.1, 0.3],
            },
            "note": "the repo cites NO direct-demand-model literature "
                    "elasticity ranges for catchment covariates; the only "
                    "in-repo elasticity band is spec 02 §4.5b's induced-"
                    "demand U(0.1, 0.3) prior -- a DIFFERENT quantity "
                    "(total-demand response to an accessibility change), "
                    "listed for scale only. Literature comparison beyond "
                    "these in-repo reference points is owner judgment "
                    "(no invented citations)",
        },
        "verdict": {
            "rule": "compare the 47-cluster marginal required-at-80% "
                    "elasticities against the committed v2.0 point "
                    "estimates: adequately-powered if required <= est; "
                    "marginal if <= est + verdict_se_mult * cluster SE; "
                    "else underpowered; overall = worst coefficient "
                    "(pre-stated judgment rule, registry "
                    "screen_power_check)",
            "terms": verdict_terms,
            "overall": worst,
        },
        "no_contamination": "v2.1 predictor matrices built input-side "
                            "only; outcomes are synthetic (injected "
                            "beta_true); the v2.1 fit stays unrun; no "
                            "real boardings value enters this module "
                            "(standing tests test_screen_power.py G1/G2)",
    }
    return artifact


# ---------------------------------------------------------------------------
# chart
# ---------------------------------------------------------------------------
def make_chart(artifact, path):
    """2x2 grid: BEFORE (committed 3-year panel, top) over AFTER (the §9.9
    extended panel, bottom), columns aligned so each committed design sits
    above the extended design it maps to in the verdict (clusters_41 ->
    ext_current_shape; clusters_47 -> ext_with_replicas)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    SURFACE = "#fcfcfb"; INK = "#0b0b0b"; INK2 = "#52514e"
    GRID = "#e1e0d9"; MUTED = "#898781"
    plt.rcParams["font.family"] = ["Segoe UI", "DejaVu Sans", "sans-serif"]
    grid = artifact["beta_grid"]
    fig, axes = plt.subplots(2, 2, figsize=(11.4, 8.4), dpi=200,
                             sharey=True, sharex=True)
    fig.patch.set_facecolor(SURFACE)
    styles = {"b1": ("#2a78d6", "b1 (LODES flows)"),
              "b2": ("#e34948", "b2 (zero-veh HH)"),
              "joint": ("#1b8a6b", "joint (b1=b2)")}
    v20 = artifact["literature_comparison"]["in_repo_reference_points"]
    # (row, col) -> (design container, design label, banner)
    cells = {
        (0, 0): (artifact["designs"], "clusters_41", "BEFORE"),
        (0, 1): (artifact["designs"], "clusters_47", "BEFORE"),
        (1, 0): (artifact["panel_ext"]["designs"], "ext_current_shape",
                 "AFTER"),
        (1, 1): (artifact["panel_ext"]["designs"], "ext_with_replicas",
                 "AFTER"),
    }
    for (r, c), (container, label, banner) in cells.items():
        ax = axes[r][c]
        ax.set_facecolor(SURFACE)
        d = container[label]
        for k, (col, lab) in styles.items():
            ax.plot(grid, d["power"][k], color=col, lw=2.0, label=lab)
        ax.axhline(artifact["criterion"]["power_target"], color=MUTED,
                   lw=0.9, ls="--")
        for k in ("b1", "b2"):
            rq = d["required_at_power_target"][k]
            if rq is not None:
                ax.axvline(rq, color=styles[k][0], lw=0.8, ls=":",
                           alpha=0.7)
        ax.axvline(v20["v20_committed_b1_lodes"]["est"], color="#2a78d6",
                   lw=0.8, alpha=0.35)
        ax.axvline(v20["v20_committed_b2_e002"]["est"], color="#e34948",
                   lw=0.8, alpha=0.35)
        ax.set_title(f"{banner}  {d['n_clusters']} route clusters / "
                     f"{d['n_rows']} rows", fontsize=10, color=INK,
                     loc="left")
        if r == 1:
            ax.set_xlabel("true elasticity beta_true", fontsize=9,
                          color=INK)
        ax.grid(color=GRID, lw=0.7); ax.set_axisbelow(True)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
    axes[0][0].set_ylabel("P(pass criterion 1)", fontsize=9, color=INK)
    axes[1][0].set_ylabel("P(pass criterion 1)", fontsize=9, color=INK)
    axes[0][0].legend(fontsize=8, frameon=False, loc="lower right")
    axes[0][0].text(0.0, 1.16, "current-shape family (41 -> 50)",
                    transform=axes[0][0].transAxes, fontsize=9,
                    color=INK2, ha="left")
    axes[0][1].text(0.0, 1.16, "with-replicas family (47 -> 63)",
                    transform=axes[0][1].transAxes, fontsize=9,
                    color=INK2, ha="left")
    fig.suptitle("Design-stage power, panel extension (spec 01 §9.9): "
                 "criterion-1 bootstrap sign fraction >= 0.841 on synthetic "
                 "outcomes.\nTOP = committed 3-year panel; BOTTOM = extended "
                 "panel. Faint verticals = committed v2.0 estimates; dotted "
                 "= required at 80% power.",
                 fontsize=10, color=INK2, x=0.02, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)


def main(argv):
    import time
    t0 = time.time()
    artifact = build_power_artifact()
    out = os.path.join(OUT, "screen_power_check.json")
    write_artifact(out, artifact)
    print(f"-> {out}  (run_id {artifact['run_id'][:16]})")
    png = os.path.join(OUT, "screen_power_check.png")
    make_chart(artifact, png)
    print(f"-> {png}")
    print("\nx variation (within-route across-year std):")
    for k, s in artifact["x_variation"].items():
        print(f"  {k:10s} share varying {s['share_routes_varying']:.3f}  "
              f"mean std {s['mean_within_std']:.4f}  median "
              f"{s['median_within_std']:.4f}")
    lo = artifact["loyo_resolution"]
    print(f"LOYO resolution: in_battery={lo['loyo_in_battery']} "
          f"(shares {lo['shares']})")
    for label, d in artifact["designs"].items():
        r = d["required_at_power_target"]
        print(f"\n{label}: boot sd b1 {d['boot_sd_b1']:.4f} / b2 "
              f"{d['boot_sd_b2']:.4f}; required at 80%: "
              f"b1 {r['b1']} b2 {r['b2']} joint {r['joint']}; "
              f"small-B check pass {d['small_b_check']['pass']} "
              f"(max diff {max(d['small_b_check']['abs_diff'].values()):.4f})")
    v = artifact["verdict"]
    print(f"\nverdict: {v['overall']}")
    for k, t in v["terms"].items():
        print(f"  {k}: {t['arithmetic']} -> {t['call']}")
    print(f"runtime {time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
