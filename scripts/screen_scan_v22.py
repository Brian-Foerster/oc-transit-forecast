"""Stage-1 screen v2.2 PRODUCTIVITY scan + verdict (spec 01 §10; the
governed-method-change once-only fit culmination).

The ONLY method change vs screen_scan_v21 is the §10 D1/D2 ESTIMAND: the fit
DV is log(boardings/RVH) (productivity), b3 (RVH) is GONE from the RHS (pinned
at +1, moved to the LHS), and the scan predicts PRODUCTIVITY per window
DIRECTLY -- there is NO standardized-RVH service input to the scoring design
(the svc_std machinery is RETIRED, §10 D6). Everything else is the v2.0/v2.1
machinery carried over UNCHANGED: index definition (same-exposure rebase, now
of predicted productivity), route-cluster bootstrap, decision tripwire v2,
shortlist-stability report, output guardrails (no boardings field), the §9.10
regime-split gate, and the frozen thresholds (screen_pos_frac_min /
screen_battery_rho_min / tie-churn caps -- reused UNCHANGED per §10 D4, read
via val(), never a source literal).

SCAN side stays on CURRENT (2026-07) GTFS (§9.4 asymmetry). Window predictors
come from the SAME screen_common_v21.compute_predictors_v21 (REUSED VERBATIM)
as the fit side, at the "scan" vintage (LODES 2022 / ACS 2023).

Battery: the FROZEN 17-row v2.2 battery screen_battery_rows_v22 =
screen_battery_rows_v21 MINUS {drop_rh, svc_p25, svc_p75} (the three rows
undefined under productivity, §10 D5). nb_estimator's productivity FORM is the
NB2 RATE model (log(RVH) fixed offset), the count analogue of the pinned
identity.

BOOTSTRAP NOTE (carried over from v2.1, stated). The §3.4 route-cluster
bootstrap is carried over. The §3.4 WITHIN-REPLICATE ACS-MOE perturbation is
NOT applied: screen_common_v21 carries no ACS MOE (input-availability fact, not
a tuning choice; it removes one noise source, so criterion 1 is marginally MORE
lenient -- stated, artifact `bootstrap`).

Artifact: outputs/screen_results_v22.json (NEW file -- does NOT overwrite the
v2.0 screen_results.json nor the v2.1 screen_results_v21.json). Chart:
outputs/screen_ranked_v22.png. Deterministic write (sort_keys, indent=2, LF,
floats 6dp, no timestamps; dual fresh-process byte-identity is a gate).

    python -X utf8 scripts/screen_scan_v22.py
"""
import json
import math
import os
import sys

import numpy as np
import pandas as pd

from assumptions import val, band
import build_corridor as bc
import network_mechanics as nm          # canonical fingerprint (acyclic)
import screen_common_v21 as sv
import screen_fit_v22 as sf

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "outputs")

SCHEMA = "01-S1-v22"
CANON_DECIMALS = 6
DISCLAIMER = ("ordinal screening index; not a ridership forecast "
              "(spec 00 §1)")
VINTAGES = {"gtfs_scan": "2026-07", "gtfs_fit": "archived contemporaneous "
            "feeds fy2017-fy2023 (§9.4)", "lodes_scan": "2022",
            "acs_scan": "2019-2023 5-yr",
            "apc": "FY2017/FY2019 + ext FY2020/FY2021/FY2022/FY2023 (§9.9)"}
POST2020 = ("fy2020", "fy2021", "fy2022", "fy2023")

CONSUMED = (
    ("buffer_mi", "catchment radius (shared with stage 2)"),
    ("screen_window_mi", "window length"),
    ("screen_step_mi", "window slide step"),
    ("screen_overlap_threshold", "overlap-grouping threshold"),
    ("screen_n_boot", "bootstrap replicates"),
    ("screen_seed", "bootstrap RNG seed"),
    ("screen_loo_rho", "LOO leverage-screen floor"),
    ("screen_male", "LOO MALE ceiling"),
    ("screen_pos_frac_min", "tripwire criterion 1: min demand-coef bootstrap "
                            "positive-sign fraction"),
    ("screen_battery_rho_min", "tripwire criterion 2: battery min Spearman rho"),
    ("screen_tie_churn_max_window", "criterion 3 window-unit sub-threshold"),
    ("screen_tie_churn_max_hostshape", "criterion 3 host-shape sub-threshold"),
    ("screen_battery_rows_v22", "FROZEN v2.2 17-row battery"),
    ("screen_estimand_v22", "v2.2 productivity dependent variable log(b/RVH)"),
    ("screen_panel_ext_fys", "extended 6-FY fit panel"),
    ("screen_regime_split", "§9.10 regime-split downgrade gate"),
    ("gen_jobs_naics", "b4 generator-jobs NAICS columns"),
    ("mi_lat", "mi per degree latitude"),
    ("mi_per_deg_lon", "mi per degree longitude at equator"),
    ("oc_ref_lat", "OC reference latitude"),
)
BAND_CONSUMED = ("buffer_mi", "screen_overlap_threshold", "screen_window_mi")


# ---------------------------------------------------------------------------
# canonical serialization (screen_scan.py write pattern)
# ---------------------------------------------------------------------------
def _canon(o):
    if isinstance(o, dict):
        return {k: _canon(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_canon(v) for v in o]
    if isinstance(o, set):
        return [_canon(v) for v in sorted(o)]
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


def _spearman(a, b):
    from scipy.stats import spearmanr
    return float(spearmanr(np.asarray(a), np.asarray(b)).correlation)


# ---------------------------------------------------------------------------
# scan universe (current GTFS, block resolution, scan vintage)
# ---------------------------------------------------------------------------
def current_universe(data):
    """{route_id: ShapeProjV21} for every current-GTFS weekday route shape
    (sorted iteration; the mechanical scan universe before the length
    filter). IDENTICAL to screen_scan_v21.current_universe."""
    trips, shapes, st, wk = bc.load_gtfs()
    routes = pd.read_csv(os.path.join(HERE, "..", "data", "raw", "gtfs",
                                      "routes.txt"), dtype=str)
    projs = {}
    for rid in sorted(routes["route_id"], key=sf._route_sort_key):
        res, L = bc.main_shape_xy(trips, shapes, wk, rid)
        if res is None or L <= 0:
            continue
        projs[rid] = sf.fast_proj(data, rid, res[0], res[1])
    return projs


def assemble_scan(data, cns2022, projs, buffer_mi, window_mi, step_mi):
    """Sliding-window raw predictor sums for every eligible current shape, at
    the scan vintage (block resolution). Sorted route iteration; integer-step
    w0. IDENTICAL to screen_scan_v21.assemble_scan (window raw sums are
    estimand-independent)."""
    naics = val("gen_jobs_naics")
    wins = []
    n_eligible = 0
    for rid in sorted(projs, key=sf._route_sort_key):
        proj = projs[rid]
        if proj.L < window_mi:
            continue
        n_eligible += 1
        for w0 in sv.window_starts(proj.L, window_mi, step_mi):
            w1 = w0 + window_mi
            p = sv.compute_predictors_v21(data, proj, w0, w1, "scan",
                                          buffer_mi=buffer_mi)
            bidx = p["block_idx"]
            cns = {c: float(cns2022[c][bidx].sum()) for c in naics}
            wins.append({"route_id": rid, "w0": float(w0), "w1": float(w1),
                         "window_id": f"{rid}_{w0:05.1f}",
                         "flows": p["flows"], "zveh": p["zveh_hh"],
                         "e002": p["e002"], "e016": p["e016"],
                         "popden": p["popden"], "genjobs": p["genjobs"],
                         "gen_dummy": p["gen_dummy"],
                         "block_idx": bidx,
                         **{f"cns_{c}": cns[c] for c in cns}})
    W = {k: ([w[k] for w in wins] if k in ("route_id", "window_id",
                                           "block_idx")
             else np.array([w[k] for w in wins], float))
         for k in ("route_id", "window_id", "w0", "w1", "flows", "zveh",
                   "e002", "e016", "popden", "genjobs", "gen_dummy",
                   "block_idx", *[f"cns_{c}" for c in naics])}
    return {"W": W, "n_windows": len(wins), "n_eligible": n_eligible,
            "n_weekday": len(projs), "buffer_mi": buffer_mi,
            "window_mi": window_mi, "projs": projs}


# ---------------------------------------------------------------------------
# scoring design (windows / routes; §10 D6: predict PRODUCTIVITY directly, NO
# standardized-service input -- there is NO b3_rvh scoring column)
# ---------------------------------------------------------------------------
def _b4_col(raw, cfg):
    """b4 predictor array for a raw-sum bundle (window or route)."""
    if cfg["b4"] == "dummy":
        return raw["gen_dummy"]
    gj = raw["genjobs"].astype(float)
    if cfg["b4_ex_cns"] is not None:
        gj = gj - raw["cns_" + cfg["b4_ex_cns"]]
    return np.log1p(np.clip(gj, 0.0, None))


def _score_cols(raw, cfg):
    b1 = np.log1p(raw["popden"] if cfg["b1"] == "popden" else raw["flows"])
    b2 = np.log1p(raw[{"zveh": "zveh", "e002": "e002",
                       "e016": "e016"}[cfg["b2"]]])
    return {"b1": b1, "b2": b2, "b4": _b4_col(raw, cfg)}


def score_design_v22(cols, cfg, lengths, fe_year=None):
    """Design matrix for SCORING units (§10 D6). Predicts PRODUCTIVITY
    directly: there is NO b3_rvh column and NO svc_std input. Year FE all 0 (a
    common FE cancels in the index) unless fe_year names one (the underservice
    diagnostic at fy2019). Interaction columns never score windows (regime-split
    is a fit-only diagnostic)."""
    n = len(cols["b1"])
    lengths = np.broadcast_to(np.asarray(lengths, float), (n,))
    names, fys = sf.col_order_v22(cfg)
    colmap = {
        "const": np.ones(n),
        sf._b1name(cfg): cols["b1"],
        sf._b2name(cfg): cols["b2"],
        sf._b4name(cfg): cols["b4"],
        "b5_len": np.log(lengths),
    }
    for fy in fys[1:]:
        colmap[f"fe_{fy}"] = (np.full(n, 1.0) if fy == fe_year
                              else np.zeros(n))
    return np.column_stack([colmap[c] for c in names])


def _host_groups(W, routes):
    """Window-index arrays per FITTED host route with current windows (sorted
    route order). Each group's max prediction is that route's own best window;
    the median over these is the same-exposure baseline."""
    fitted = set(routes)
    groups = {}
    for i, r in enumerate(W["route_id"]):
        if r in fitted:
            groups.setdefault(r, []).append(i)
    return [np.asarray(groups[r], int)
            for r in sorted(groups, key=sf._route_sort_key)]


def _index_from_preds(win_pred, host_groups):
    """screen_index = 100*exp(win_pred - baseline); baseline = lower-median
    over fitted host routes of each route's own BEST window prediction
    (deterministic). win_pred is predicted PRODUCTIVITY (§10 D6). Any common
    additive term (a shared FE) cancels."""
    best = np.array([win_pred[g].max() for g in host_groups])
    base = np.sort(best)[(len(best) - 1) // 2]
    return 100.0 * np.exp(win_pred - base), float(base)


def score(fit_rows, asm, cfg, beta=None):
    """Point pipeline for one config: fit (unless beta given), score all
    current windows -- predicting PRODUCTIVITY directly (§10 D6, NO svc input)
    -- return index + fit artifacts."""
    y, X, names, groups, df = sf.design_matrix_v22(fit_rows, cfg)
    if beta is None:
        beta = sf.ols_beta(y, X)
    routes = sorted(set(df["route"]), key=sf._route_sort_key)
    wcols = _score_cols(asm["W"], cfg)
    Xw = score_design_v22(wcols, cfg, asm["window_mi"])
    win_pred = Xw @ beta
    if cfg["offset"]:
        win_pred = win_pred + math.log(asm["window_mi"])
    hg = _host_groups(asm["W"], routes)
    index, base = _index_from_preds(win_pred, hg)
    return {"beta": beta, "names": names, "y": y, "X": X, "groups": groups,
            "df": df, "routes": routes, "index": index, "win_pred": win_pred,
            "Xw": Xw, "host_groups": hg, "base_logpred": base}


def _ranking(index, window_ids):
    order = sorted(range(len(index)), key=lambda i: (-index[i],
                                                     window_ids[i]))
    rank = np.empty(len(index), int)
    for pos, i in enumerate(order):
        rank[i] = pos + 1
    return rank, order


def _top8(index, window_ids):
    _, order = _ranking(index, window_ids)
    return [window_ids[i] for i in order[:8]]


def _churn(head_ids, var_ids):
    return {"entered": sorted(set(var_ids) - set(head_ids)),
            "exited": sorted(set(head_ids) - set(var_ids))}


# ---------------------------------------------------------------------------
# route-resample bootstrap machinery (NO ACS-MOE perturbation -- see module
# docstring). Precomputes per-route row groups once; each replicate resamples
# routes, refits OLS, rescores all windows jointly.
# ---------------------------------------------------------------------------
def _boot_setup(head):
    routes = head["routes"]
    nR = len(routes)
    row_route = np.array([routes.index(r) for r in head["df"]["route"]])
    route_rows = [np.flatnonzero(row_route == i) for i in range(nR)]
    return routes, nR, route_rows


def bootstrap(fit_rows, asm, cfg, n_boot, seed, quiet=False):
    """Headline route-cluster bootstrap: p10/p50/p90 index, joint rank
    distribution, tie_with_cutoff, and the per-replicate b1/b2/b4 signs behind
    criterion 1 (b4 sign a diagnostic). Deterministic single default_rng."""
    head = score(fit_rows, asm, cfg)
    routes, nR, route_rows = _boot_setup(head)
    y, X = head["y"], head["X"]
    Xw = head["Xw"]
    nW = len(asm["W"]["window_id"])
    off = math.log(asm["window_mi"]) if cfg["offset"] else 0.0
    sign_cols = {"b1": head["names"].index(sf._b1name(cfg)),
                 "b2": head["names"].index(sf._b2name(cfg)),
                 "b4": (head["names"].index(sf._b4name(cfg))
                        if cfg["b4"] is not None else None)}
    signs = {k: [] for k in sign_cols}
    rng = np.random.default_rng(seed)
    idx_mat = np.empty((n_boot, nW))
    rank_mat = np.empty((n_boot, nW), int)
    for b in range(n_boot):
        sample = rng.integers(0, nR, nR)
        rows_sel = np.concatenate([route_rows[i] for i in sample])
        beta = sf.ols_beta(y[rows_sel], X[rows_sel])
        for k, j in sign_cols.items():
            if j is not None:
                signs[k].append("+" if beta[j] > 0.0 else "-")
        idx, _ = _index_from_preds(Xw @ beta + off, head["host_groups"])
        idx_mat[b] = idx
        order = np.argsort(-idx, kind="stable")
        rank_mat[b, order] = np.arange(1, nW + 1)
        if not quiet and (b + 1) % 500 == 0:
            print(f"  bootstrap {b + 1}/{n_boot}")
    p10, p50, p90 = np.percentile(idx_mat, [10, 50, 90], axis=0)
    rank_lo, rank_hi = np.percentile(rank_mat, [2.5, 97.5], axis=0)
    tie = (rank_lo <= 5.0) & (rank_hi > 5.0)
    return {"p10": p10, "p50": p50, "p90": p90, "rank_lo": rank_lo,
            "rank_hi": rank_hi, "tie": tie, "head": head,
            "window_ids": asm["W"]["window_id"],
            "signs": {k: "".join(v) for k, v in signs.items()
                      if sign_cols[k] is not None}}


def sign_fracs_only(fit_rows, cfg, n_boot, seed):
    """b1/b2 (and interaction) bootstrap positive-sign fractions for a FIT-ONLY
    config (regime-split pre-2020 / interaction) -- no window scoring needed."""
    y, X, names, groups, df = sf.design_matrix_v22(fit_rows, cfg)
    routes = sorted(set(df["route"]), key=sf._route_sort_key)
    nR = len(routes)
    row_route = np.array([routes.index(r) for r in df["route"]])
    route_rows = [np.flatnonzero(row_route == i) for i in range(nR)]
    cols = {"b1": names.index(sf._b1name(cfg)),
            "b2": names.index(sf._b2name(cfg))}
    if cfg["interaction"]:
        cols["i_flows_post"] = names.index("i_flows_post")
        cols["i_zveh_post"] = names.index("i_zveh_post")
    signs = {k: 0 for k in cols}
    rng = np.random.default_rng(seed)
    for _ in range(n_boot):
        sample = rng.integers(0, nR, nR)
        rows_sel = np.concatenate([route_rows[i] for i in sample])
        beta = sf.ols_beta(y[rows_sel], X[rows_sel])
        for k, j in cols.items():
            if beta[j] > 0.0:
                signs[k] += 1
    return {k: signs[k] / n_boot for k in cols}, nR, int(len(y))


def row_tie_bootstrap(fit_rows, asm, cfg, n_boot, seed, nb_alpha=None,
                      drop_fy=None):
    """One battery row's OWN route-cluster bootstrap -> its tie_with_cutoff
    set (CRN per-row seed rule: every row re-derives default_rng(seed)).
    drop_fy (loyo) drops that FY's rows before fitting. nb_alpha (nb_estimator)
    holds NB2 alpha fixed and Fisher-scores beta per replicate as the RATE
    model (log(RVH) fixed offset, §10 D5)."""
    rows = fit_rows[fit_rows["fy"] != drop_fy] if drop_fy else fit_rows
    head = score(rows, asm, cfg)
    routes, nR, route_rows = _boot_setup(head)
    y, X = head["y"], head["X"]
    Xw = head["Xw"]
    nW = len(asm["W"]["window_id"])
    off = math.log(asm["window_mi"]) if cfg["offset"] else 0.0
    counts = head["df"]["boardings"].to_numpy(float)
    nb_off = np.log(head["df"]["rvh"].to_numpy(float))    # rate-model exposure
    k_par = X.shape[1]
    rng = np.random.default_rng(seed)
    rank_mat = np.empty((n_boot, nW), int)
    for b in range(n_boot):
        sample = rng.integers(0, nR, nR)
        rows_sel = np.concatenate([route_rows[i] for i in sample])
        beta = sf.ols_beta(y[rows_sel], X[rows_sel])
        if nb_alpha is not None:
            resid = y[rows_sel] - X[rows_sel] @ beta
            s2 = float(resid @ resid) / max(len(rows_sel) - k_par, 1)
            start = beta.copy()
            start[0] += s2 / 2.0
            beta = sf.nb2_beta_fixed_alpha(counts[rows_sel], X[rows_sel],
                                           nb_alpha, start, nb_off[rows_sel])
        idx, _ = _index_from_preds(Xw @ beta + off, head["host_groups"])
        order = np.argsort(-idx, kind="stable")
        rank_mat[b, order] = np.arange(1, nW + 1)
    rank_lo, rank_hi = np.percentile(rank_mat, [2.5, 97.5], axis=0)
    tie = (rank_lo <= 5.0) & (rank_hi > 5.0)
    idxs = np.flatnonzero(tie)
    return {"tie_ids": [asm["W"]["window_id"][i] for i in idxs],
            "tie_hosts": sorted({asm["W"]["route_id"][i] for i in idxs},
                                key=sf._route_sort_key)}


def tie_churn_stats(head_set, row_set):
    head_set, row_set = set(head_set), set(row_set)
    union = head_set | row_set
    tie_in = sorted(row_set - head_set)
    tie_out = sorted(head_set - row_set)
    return {"tie_in": tie_in, "tie_out": tie_out,
            "n_tie_in": len(tie_in), "n_tie_out": len(tie_out),
            "jaccard": (1.0 if not union
                        else len(head_set & row_set) / len(union)),
            "tie_churn_frac": (max(len(tie_in), len(tie_out))
                               / max(1, len(head_set)))}


# ---------------------------------------------------------------------------
# LOO / leave-one-year-out (point fits)
# ---------------------------------------------------------------------------
def loo_battery(fit_rows, asm, head):
    """Leave-one-ROUTE-out: OOS productivity-DV log errors (MALE, P90 for the
    underservice flag) + the window-ranking leverage screen (min Spearman rho
    vs headline)."""
    y, X = head["y"], head["X"]
    groups = head["groups"]
    routes = head["routes"]
    errs, route_err = [], {}
    rho_min, rho_min_route = 1.0, None
    for r in routes:
        m = groups != r
        beta = sf.ols_beta(y[m], X[m])
        e = y[~m] - X[~m] @ beta
        errs.extend(np.abs(e).tolist())
        route_err[r] = float(np.mean(np.abs(e)))
        idx, _ = _index_from_preds(head["Xw"] @ beta, head["host_groups"])
        rho = _spearman(idx, head["index"])
        if rho < rho_min:
            rho_min, rho_min_route = rho, r
    errs = np.array(errs)
    worst5 = sorted(route_err, key=lambda r: -route_err[r])[:5]
    return {"male": float(np.median(errs)),
            "p90_abs_err": float(np.percentile(errs, 90)),
            "worst5": [{"route": r, "mean_abs_log_err": route_err[r]}
                       for r in worst5],
            "rho_min": rho_min, "rho_min_route": rho_min_route}


def loyo_rhos(fit_rows, asm, head):
    """Leave-one-YEAR-out over the 6 fit-panel FYs (the §9.3/§9.8 restored
    battery row). Returns {fy: rho} and the worst (min-rho) fy. Productivity
    DV; NO svc input (§10 D6)."""
    out = {}
    for fy in val("screen_panel_ext_fys"):
        rows = fit_rows[fit_rows["fy"] != fy]
        if rows["route"].nunique() < 3 or len(rows) <= head["X"].shape[1]:
            continue
        v = score(rows, asm, sf.BASE_CFG_V22)
        out[fy] = _spearman(v["index"], head["index"])
    worst_fy = min(out, key=lambda k: out[k])
    return out, worst_fy, out[worst_fy]


# ---------------------------------------------------------------------------
# sensitivity battery (frozen 17-row v2.2 list) + per-row stability contexts
# ---------------------------------------------------------------------------
def _row(rid, label, head_idx, head_ids, var_idx, note=None, extra=None):
    rho = _spearman(head_idx, var_idx)
    detail = {"rho": rho, **_churn(_top8(head_idx, head_ids),
                                   _top8(var_idx, head_ids))}
    if note:
        detail["note"] = note
    if extra:
        detail.update(extra)
    return {"id": rid, "label": label, "pct": 100.0 * (1.0 - rho),
            "detail": detail}


def _best_per_shape(index, route_ids):
    best = {}
    for i, r in enumerate(route_ids):
        if r not in best or index[i] > index[best[r]]:
            best[r] = i
    return best


def _length_row(rid, label, head, head_asm, var, var_asm):
    """window_10/window_15: window sets differ, so compared best-window-per-
    host-shape over shapes eligible in BOTH scans (host-shape unit)."""
    bh = _best_per_shape(head["index"], head_asm["W"]["route_id"])
    bv = _best_per_shape(var["index"], var_asm["W"]["route_id"])
    common = sorted(set(bh) & set(bv), key=sf._route_sort_key)
    hv = [head["index"][bh[r]] for r in common]
    vv = [var["index"][bv[r]] for r in common]
    rho = _spearman(hv, vv)
    top8h = [r for _, r in sorted(zip(hv, common),
                                  key=lambda t: (-t[0], t[1]))[:8]]
    top8v = [r for _, r in sorted(zip(vv, common),
                                  key=lambda t: (-t[0], t[1]))[:8]]
    return {"id": rid, "label": label, "pct": 100.0 * (1.0 - rho),
            "detail": {"rho": rho, **_churn(top8h, top8v),
                       "note": "best-window-per-host-shape over "
                               f"{len(common)} shapes eligible in both scans; "
                               "churn ids are host shapes",
                       "n_windows_variant": var_asm["n_windows"]}}


def sensitivity_block(data, cns2022, cns_fit, fit, fit_projs, asm, head,
                      tract_sets, groups_head, buffer_mi, window_mi, step_mi,
                      quiet=False):
    """Every frozen v2.2 battery row's rho + churn, plus the per-row stability
    contexts (each row's OWN tie-set bootstrap reruns from these). Returns
    (rows_in_registry_order, nb_info, ctxs). The FROZEN 17-row v2.2 battery
    (screen_battery_rows_v22) drops drop_rh / svc_p25 / svc_p75 (undefined under
    productivity, §10 D5)."""
    fit_rows = fit["rows"]
    rows, ctxs = [], {}
    hidx, hids = head["index"], asm["W"]["window_id"]

    def say(rid):
        if not quiet:
            print(f"  sensitivity row {rid}")

    naics = val("gen_jobs_naics")
    # buffer band edges: rebuild BOTH fit (archived) and scan (current)
    for rid, buf in (("buffer_lo", band("buffer_mi")[0]),
                     ("buffer_hi", band("buffer_mi")[1])):
        say(rid)
        f2 = sf.build_fit_rows(data, cns_fit, buf, projs=fit_projs,
                               quiet=True)
        a2 = assemble_scan(data, cns2022, asm["projs"], buf, window_mi,
                           step_mi)
        v = score(f2["rows"], a2, sf.BASE_CFG_V22)
        assert a2["W"]["window_id"] == hids
        rows.append(_row(rid, f"catchment buffer {buf} mi", hidx, hids,
                         v["index"]))
        ctxs[rid] = {"fit_rows": f2["rows"], "asm": a2,
                     "cfg": sf.BASE_CFG_V22, "unit": "window_id"}
    # window length band edges (fit is full-shape, unaffected; only scan
    # window length changes) -- host-shape unit
    for rid, wlen in (("window_10", band("screen_window_mi")[0]),
                      ("window_15", band("screen_window_mi")[1])):
        say(rid)
        a2 = assemble_scan(data, cns2022, asm["projs"], buffer_mi, wlen,
                           step_mi)
        v = score(fit_rows, a2, sf.BASE_CFG_V22)
        rows.append(_length_row(rid, f"window length {wlen} mi", head, asm,
                                v, a2))
        ctxs[rid] = {"fit_rows": fit_rows, "asm": a2, "cfg": sf.BASE_CFG_V22,
                     "unit": "host_shape"}
    # model-config perturbations on the headline assembly (drop_rh REMOVED --
    # RVH is the DV denominator, not an RHS predictor to drop, §10 D5)
    cfg_rows = (
        ("drop_fy2020", "drop FY2020 rows", {"drop_fy2020": True}),
        ("e016_swap", "b2 = B08141 E016 transit workers", {"b2": "e016"}),
        ("e002_swap", "b2 = B08141 E002 zero-veh workers (v2.0 headline)",
         {"b2": "e002"}),
        ("popden_swap", "b1 = log1p(B01003 pop / ALAND density)",
         {"b1": "popden"}),
        ("genjobs_off", "drop the b4 generator-jobs term", {"b4": None}),
        ("gen_dummy_swap", "b4 = legacy binary special-generator dummy",
         {"b4": "dummy"}),
        ("offset_variant", "log(length) offset (b5 pinned to 1; "
         "log(b/(RVH*length)))", {"offset": True}),
        ("year_fe_vs_pooled", "pooled fit (no year FE)", {"year_fe": False}),
    )
    for rid, label, over in cfg_rows:
        say(rid)
        cfg_v = dict(sf.BASE_CFG_V22, **over)
        v = score(fit_rows, asm, cfg_v)
        rows.append(_row(rid, label, hidx, hids, v["index"]))
        ctxs[rid] = {"fit_rows": fit_rows, "asm": asm, "cfg": cfg_v,
                     "unit": "window_id"}
    # genjobs_leave_class_out: one row, per-NAICS-sector detail, pct = worst
    say("genjobs_leave_class_out")
    by_class, rho_min = {}, 1.0
    for cns in naics:
        v = score(fit_rows, asm, dict(sf.BASE_CFG_V22, b4_ex_cns=cns))
        rho = _spearman(hidx, v["index"])
        by_class[cns] = {"rho": rho, **_churn(_top8(hidx, hids),
                                              _top8(v["index"], hids))}
        rho_min = min(rho_min, rho)
    rows.append({"id": "genjobs_leave_class_out",
                 "label": "drop one NAICS sector from the CNS15-18 b4 sum "
                          f"(worst of {'/'.join(naics)})",
                 "pct": 100.0 * (1.0 - rho_min),
                 "detail": {"rho": rho_min, "by_class": by_class}})
    ctxs["genjobs_leave_class_out"] = {
        "fit_rows": fit_rows, "asm": asm, "unit": "window_id",
        "by_class": {cns: dict(sf.BASE_CFG_V22, b4_ex_cns=cns)
                     for cns in naics}}
    # NB2 RATE-model estimator row (always fitted; log(RVH) fixed offset, §10 D5)
    say("nb_estimator")
    nb_off = np.log(head["df"]["rvh"].to_numpy(float))
    nb_beta, nb_alpha, nb_conv = sf.fit_nb2(
        head["df"]["boardings"].to_numpy(), head["y"], head["X"],
        head["beta"], nb_off)
    v = score(fit_rows, asm, sf.BASE_CFG_V22, beta=nb_beta)
    rows.append(_row("nb_estimator", "NB2 rate-model robustness estimator "
                     "(log(RVH) fixed offset)", hidx, hids,
                     v["index"], extra={"alpha": float(nb_alpha),
                                        "converged": bool(nb_conv)}))
    ctxs["nb_estimator"] = {"fit_rows": fit_rows, "asm": asm,
                            "cfg": sf.BASE_CFG_V22,
                            "unit": "window_id", "nb_alpha": float(nb_alpha)}
    # overlap threshold band edges: ranking unchanged; regrouping reported
    n_head = len(set(groups_head.values()))
    for rid, thr in (("overlap_lo", band("screen_overlap_threshold")[0]),
                     ("overlap_hi", band("screen_overlap_threshold")[1])):
        say(rid)
        g = _overlap_groups(hids, tract_sets, thr)
        top8 = _top8(hidx, hids)
        changed = sorted(w for w in top8 if g[w] != groups_head[w])
        rows.append({"id": rid, "label": f"overlap-grouping threshold {thr}",
                     "pct": 0.0,
                     "detail": {"rho": 1.0,
                                "note": "grouping only -- scores/ranking "
                                        "unchanged by construction",
                                "n_groups": len(set(g.values())),
                                "n_groups_headline": n_head,
                                "top8_regrouped": changed}})
        ctxs[rid] = {"fit_rows": fit_rows, "asm": asm, "cfg": sf.BASE_CFG_V22,
                     "unit": "window_id"}
    # loyo: leave-one-year-out over the 6-FY panel; rho = min over year-drops
    say("loyo")
    loyo_by_fy, worst_fy, loyo_rho = loyo_rhos(fit_rows, asm, head)
    rows.append({"id": "loyo",
                 "label": "leave-one-year-out rank stability (min rho over "
                          "the 6-FY panel year-drops)",
                 "pct": 100.0 * (1.0 - loyo_rho),
                 "detail": {"rho": loyo_rho, "by_fy": loyo_by_fy,
                            "worst_fy": worst_fy, "entered": [], "exited": [],
                            "note": "restored to the battery (§9.3/§9.8) "
                                    "because vintage-matched X varies within "
                                    "route across years; leave-one-year-out "
                                    "over the extended 6-FY panel"}})
    ctxs["loyo"] = {"fit_rows": fit_rows, "asm": asm, "cfg": sf.BASE_CFG_V22,
                    "unit": "window_id", "drop_fy": worst_fy}
    # freeze row order to the registry list (test asserts artifact == list)
    order = val("screen_battery_rows_v22")
    rows.sort(key=lambda r: order.index(r["id"]))
    return rows, {"alpha": float(nb_alpha), "converged": bool(nb_conv)}, ctxs


def _row_churn(r):
    """Legacy hard-top-8 churn diagnostic (unit-tagged)."""
    d = r["detail"]
    if "by_class" in d:
        return max(max(len(v["entered"]), len(v["exited"]))
                   for v in d["by_class"].values())
    if "entered" in d:
        return max(len(d["entered"]), len(d["exited"]))
    return 0


def shortlist_stability(ctxs, sens, head_ties, head_tie_hosts, n_boot, seed,
                        quiet=False):
    """Every frozen v2.2 battery row's OWN tie_with_cutoff set vs the
    margin-defined headline tie set (CRN per-row seed rule). Criterion-3 DUAL
    statistics: max_tie_churn_frac_window over WINDOW-UNIT rows,
    max_tie_churn_frac_hostshape over window_10/window_15. min_jaccard an
    all-rows report. Plus the stable core."""
    rows_order = val("screen_battery_rows_v22")
    sens_by_id = {r["id"]: r for r in sens}
    head_set_w, head_set_h = set(head_ties), set(head_tie_hosts)
    per_row, core = [], set(head_ties)

    def run_one(ctx, cfg):
        return row_tie_bootstrap(ctx["fit_rows"], ctx["asm"], cfg,
                                 n_boot, seed, nb_alpha=ctx.get("nb_alpha"),
                                 drop_fy=ctx.get("drop_fy"))

    for rid in rows_order:
        if not quiet:
            print(f"  stability row {rid}")
        ctx = ctxs[rid]
        unit = ctx["unit"]
        head_set = head_set_h if unit == "host_shape" else head_set_w
        legacy = {"value": _row_churn(sens_by_id[rid]),
                  "unit": "host_shape" if rid in ("window_10", "window_15")
                          else "window_id"}
        if "by_class" in ctx:
            by_class, worst = {}, None
            for cns, cfg in sorted(ctx["by_class"].items()):
                res = run_one(ctx, cfg)
                st = tie_churn_stats(head_set, set(res["tie_ids"]))
                by_class[cns] = {"n_tie_row": len(res["tie_ids"]), **st}
                core &= set(res["tie_ids"])
                if worst is None or st["jaccard"] < worst[1]["jaccard"]:
                    worst = (cns, st, len(res["tie_ids"]))
            entry = {"id": rid, "unit": unit, "n_tie_row": worst[2],
                     "n_tie_headline": len(head_set), **worst[1],
                     "worst_class": worst[0], "by_class": by_class,
                     "hard_top8_churn": legacy}
        else:
            res = run_one(ctx, ctx["cfg"])
            row_set = (set(res["tie_hosts"]) if unit == "host_shape"
                       else set(res["tie_ids"]))
            st = tie_churn_stats(head_set, row_set)
            if unit == "host_shape":
                hosts = set(res["tie_hosts"])
                core = {w for w in core if w.rsplit("_", 1)[0] in hosts}
            else:
                core &= set(res["tie_ids"])
            entry = {"id": rid, "unit": unit, "n_tie_row": len(res["tie_ids"]),
                     "n_tie_headline": len(head_set), **st,
                     "hard_top8_churn": legacy}
        if "drop_fy" in ctx:
            entry["note"] = ("tie-set from the worst-year-dropped model "
                             f"(fy {ctx['drop_fy']}); loyo's published rho is "
                             "the min over the 6 year-drops")
        per_row.append(entry)

    def _jac(r):
        bc_ = r.get("by_class")
        return (min(v["jaccard"] for v in bc_.values()) if bc_
                else r["jaccard"])

    def _frac(r):
        bc_ = r.get("by_class")
        return (max(v["tie_churn_frac"] for v in bc_.values()) if bc_
                else r["tie_churn_frac"])

    window_rows = [r for r in per_row if r["unit"] == "window_id"]
    hostshape_rows = [r for r in per_row if r["unit"] == "host_shape"]
    min_jac = min(_jac(r) for r in per_row)
    worst_row = next(r["id"] for r in per_row if _jac(r) == min_jac)
    max_frac_w = max(_frac(r) for r in window_rows)
    max_frac_w_row = next(r["id"] for r in window_rows
                          if _frac(r) == max_frac_w)
    max_frac_h = max(_frac(r) for r in hostshape_rows)
    max_frac_h_row = next(r["id"] for r in hostshape_rows
                          if _frac(r) == max_frac_h)
    return {
        "per_row": per_row,
        "aggregate": {
            "min_jaccard": min_jac, "worst_row": worst_row,
            "max_tie_churn_frac_window": max_frac_w,
            "max_tie_churn_row_window": max_frac_w_row,
            "max_tie_churn_frac_hostshape": max_frac_h,
            "max_tie_churn_row_hostshape": max_frac_h_row,
            "n_tie_headline": len(head_set_w),
            "stable_core": sorted(core), "n_stable_core": len(core)},
        "note": "per frozen v2.2 battery row (screen_battery_rows_v22, 17 "
                "rows): the row's OWN route-cluster bootstrap tie_with_cutoff "
                "set vs the MARGIN-DEFINED headline tie set. CRITERION 3 = DUAL "
                "THRESHOLD: max_tie_churn_frac_window over the WINDOW-UNIT "
                "rows (cap screen_tie_churn_max_window) and "
                "max_tie_churn_frac_hostshape over window_10/window_15 (cap "
                "screen_tie_churn_max_hostshape); both must pass. min_jaccard "
                "is an all-rows report. NO ACS-MOE perturbation (see the "
                "bootstrap note); per-row CRN seed rule (default_rng(seed) per "
                "row). stable_core = headline tie windows in the tie set "
                "under EVERY row (host-shape membership for the window-length "
                "rows; every NAICS sector for genjobs_leave_class_out; the "
                "worst-year-dropped model for loyo)",
    }


# ---------------------------------------------------------------------------
# overlap helpers (block tract_sets -> connected components / pairwise shares)
# ---------------------------------------------------------------------------
def _overlap_groups(window_ids, sets, threshold):
    ids = sorted(window_ids)
    n = len(ids)
    parent = list(range(n))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            lo, hi = (ra, rb) if ra < rb else (rb, ra)
            parent[hi] = lo
    S = [sets[i] for i in ids]
    sz = [len(s) for s in S]
    for a in range(n):
        if sz[a] == 0:
            continue
        for b in range(a + 1, n):
            if sz[b] == 0:
                continue
            inter = len(S[a] & S[b])
            if inter and inter / min(sz[a], sz[b]) > threshold:
                union(a, b)
    return {ids[a]: ids[find(a)] for a in range(n)}


def _pairwise_shares(window_ids, sets, threshold):
    ids = sorted(window_ids)
    out = []
    for a in range(len(ids)):
        sa = sets[ids[a]]
        if not sa:
            continue
        for b in range(a + 1, len(ids)):
            sb = sets[ids[b]]
            if not sb:
                continue
            inter = len(sa & sb)
            if inter and inter / min(len(sa), len(sb)) > threshold:
                out.append((ids[a], ids[b], inter / min(len(sa), len(sb))))
    return out


# ---------------------------------------------------------------------------
# regime-split gate (§9.10 / §10 D7)
# ---------------------------------------------------------------------------
def regime_split(fit_rows, n_boot, seed, pf_thr):
    """Three-way demand-block PRODUCTIVITY fit: POOLED (headline, all 6 FYs) /
    PRE-2020-ONLY (fy2017+fy2019) / FULL-PANEL-WITH-INTERACTION (post2020 x
    {b1, b2}). Reports the pre-2020 b1/b2 bootstrap sign fractions and the
    interaction coefficients. BINDING DOWNGRADE: pooled PASSES criterion 1 but
    pre-2020 does NOT independently pass -> downgrade (regime_split_downgrade)."""
    pre_cfg = dict(sf.BASE_CFG_V22, panel="pre2020")
    int_cfg = dict(sf.BASE_CFG_V22, interaction=True)
    pre_pf, pre_nR, pre_n = sign_fracs_only(fit_rows, pre_cfg, n_boot, seed)
    # interaction point fit (coefficients + cluster SEs)
    y, X, names, groups, df = sf.design_matrix_v22(fit_rows, int_cfg)
    pri = sf.fit_primary(y, X, names, groups)
    coef = {n_: {"est": float(b), "se_cluster": float(s)}
            for n_, b, s in zip(names, pri["params"], pri["se_cluster"])}
    pre_pass = (pre_pf["b1"] >= pf_thr) and (pre_pf["b2"] >= pf_thr)
    return {"pre_pass": pre_pass, "pre_pf": pre_pf, "pre_nR": pre_nR,
            "pre_n": pre_n, "interaction_coef": coef, "names": names}


# ---------------------------------------------------------------------------
# decision output v2 (tripwire v2 + regime-split downgrade) -- UNCHANGED from
# v2.1: it operates on sens rows / signs / stability / regime / windows and is
# estimand-agnostic.
# ---------------------------------------------------------------------------
def decision_block(pri, names, sens, windows, signs, n_boot, stability,
                   regime, b4_wrong_sign):
    pf_thr = float(val("screen_pos_frac_min"))
    rho_thr = float(val("screen_battery_rho_min"))
    tw_thr = float(val("screen_tie_churn_max_window"))
    th_thr = float(val("screen_tie_churn_max_hostshape"))
    b1_pf = signs["b1"].count("+") / n_boot
    b2_pf = signs["b2"].count("+") / n_boot
    b4_pf = (signs["b4"].count("+") / n_boot) if "b4" in signs else None
    min_t = min(abs(b) / s for n, b, s in
                zip(names, pri["params"], pri["se_cluster"])
                if n.startswith(("b1_", "b2_")))
    min_rho, rho_row = None, None
    for r in sens:
        rho = r["detail"]["rho"]
        if min_rho is None or rho < min_rho:
            min_rho, rho_row = rho, r["id"]
    agg = stability["aggregate"]
    max_w = float(agg["max_tie_churn_frac_window"])
    max_h = float(agg["max_tie_churn_frac_hostshape"])
    tie_window = {"max_over_window_unit_rows": max_w, "threshold": tw_thr,
                  "worst_row": agg["max_tie_churn_row_window"],
                  "pass": bool(max_w <= tw_thr)}
    tie_hostshape = {"max_over_window10_window15": max_h, "threshold": th_thr,
                     "worst_row": agg["max_tie_churn_row_hostshape"],
                     "pass": bool(max_h <= th_thr)}
    criteria = {
        "sign_pos_frac": {"b1_pos_frac": float(b1_pf),
                          "b2_pos_frac": float(b2_pf), "threshold": pf_thr,
                          "pass": bool(min(b1_pf, b2_pf) >= pf_thr)},
        "battery_rho": {"min_rho": float(min_rho), "worst_row_id": rho_row,
                        "threshold": rho_thr,
                        "pass": bool(min_rho >= rho_thr)},
        "tie_churn": {"window": tie_window, "hostshape": tie_hostshape},
    }
    crit1 = criteria["sign_pos_frac"]["pass"]
    crit3 = tie_window["pass"] and tie_hostshape["pass"]
    # §9.10/D7 binding downgrade: pooled passes crit 1 but pre-2020 does not
    downgrade = bool(crit1 and not regime["pre_pass"])
    regime_block = {
        "pooled_crit1_pass": bool(crit1),
        "pre2020_pf": {"b1_pos_frac": regime["pre_pf"]["b1"],
                       "b2_pos_frac": regime["pre_pf"]["b2"],
                       "threshold": pf_thr,
                       "n_clusters": regime["pre_nR"], "n": regime["pre_n"],
                       "pass": bool(regime["pre_pass"])},
        "interaction_coefficients": {
            "i_flows_post": regime["interaction_coef"]["i_flows_post"],
            "i_zveh_post": regime["interaction_coef"]["i_zveh_post"]},
        "regime_split_downgrade": downgrade,
        "note": "§9.10/§10 D7 pre-registered gate (screen_regime_split): "
                "pooled / pre-2020-only (fy2017+fy2019) / full-panel-with-"
                "post2020-interaction, on the PRODUCTIVITY DV. BINDING "
                "DOWNGRADE: pooled PASSES criterion 1 but pre-2020 does NOT "
                "independently pass the SAME screen_pos_frac_min bar "
                "-> ordinal_ok forced false, decision_format "
                "threshold_shortlist. Reuses the exact criterion-1 statistic; "
                "no new threshold",
    }
    ok = bool(crit1 and criteria["battery_rho"]["pass"] and crit3
              and not downgrade)
    ties = sorted((w for w in windows if w["tie_with_cutoff"]),
                  key=lambda w: (sf._route_sort_key(w["route_id"]),
                                 w["rank"]))
    shortlist = [{"route_id": w["route_id"], "window_id": w["window_id"],
                  "screen_index_p50": w["screen_index_p50"],
                  "underservice_flag": w["underservice_flag"]}
                 for w in ties]
    return {
        "ordinal_ok": ok, "criteria": criteria,
        "decision_format": "ordinal" if ok else "threshold_shortlist",
        "regime_split": regime_block,
        "b4_wrong_sign": bool(b4_wrong_sign),
        "shortlist": shortlist,
        "diagnostics": {"min_abs_t_demand": float(min_t),
                        "b4_pos_frac": b4_pf,
                        "note": "analytic cluster-robust min |t| over the "
                                "demand block is a DIAGNOSTIC (cluster SEs "
                                "downward-biased at few clusters). b4 "
                                "(l_genjobs) sits OUTSIDE the demand block; "
                                "its per-replicate sign fraction and the "
                                "b4_wrong_sign flag are diagnostics (§9.1/D3)"},
        "replicate_signs": {**signs,
                            "note": "per-replicate signs from the headline "
                                    "route-cluster bootstrap ('+' iff strictly "
                                    "positive; length n_boot); pos_frac "
                                    "recomputes from these"},
        "note": "decision tripwire v2 on the v2.2 PRODUCTIVITY fit (spec 01 "
                "§5/§10). ordinal_ok requires criterion 1 (each demand coef "
                "b1/b2 bootstrap positive-sign fraction >= screen_pos_frac_min "
                "on the PRODUCTIVITY DV), criterion 2 (battery min Spearman rho "
                ">= screen_battery_rho_min over all 17 frozen rows), criterion "
                "3 (DUAL: window-unit AND host-shape tie-churn both <= their "
                "caps), AND no §9.10 regime_split_downgrade. While ordinal_ok "
                "is false the gate-1 memo consumes the threshold shortlist "
                "plus measured indicators, never a top-N by rank; if "
                "shortlist_stability shows heavy churn the honest output is "
                "the NARROWER stable core (spec 01 §4b)",
    }


# ---------------------------------------------------------------------------
# per-window records + diagnostics
# ---------------------------------------------------------------------------
def _incumbents(data, asm, buffer_mi, threshold):
    """Per-window incumbent routes: every current weekday route whose full-shape
    catchment shares > threshold of the WINDOW's blocks (host included).
    IDENTICAL to screen_scan_v21._incumbents (geometry only)."""
    full_sets = {}
    for rid in sorted(asm["projs"], key=sf._route_sort_key):
        proj = asm["projs"][rid]
        p = sv.compute_predictors_v21(data, proj, 0.0, proj.L, "scan",
                                      buffer_mi=buffer_mi)
        full_sets[rid] = set(p["block_idx"].tolist())
    out = []
    for bi in asm["W"]["block_idx"]:
        wset = set(bi.tolist())
        if not wset:
            out.append([])
            continue
        out.append([r for r in sorted(full_sets, key=sf._route_sort_key)
                    if len(full_sets[r] & wset) / len(wset) > threshold])
    return out


def _underservice(fit_rows, data, asm, head, loo_p90):
    """Host-route underservice gap (log points): predicted PRODUCTIVITY
    (fy2019 FE, current route length) minus ACTUAL fy2019 productivity
    log(fy2019 boardings / fy2019 RVH), per fitted host route WITH a current
    shape and an fy2019 panel row; flagged beyond the LOO P90 abs error.
    Diagnostic-only (§3.2 caveat). §10 D6: NO svc input -- predicts
    productivity directly."""
    d19 = fit_rows[fit_rows["fy"] == "fy2019"]
    fy19 = {r: (float(b), float(rvh)) for r, b, rvh in
            zip(d19["route"], d19["boardings"], d19["rvh"])}
    cfg = sf.BASE_CFG_V22
    gap, flag = {}, {}
    for r in head["routes"]:
        if r not in asm["projs"] or r not in fy19:
            continue
        proj = asm["projs"][r]
        p = sv.compute_predictors_v21(data, proj, 0.0, proj.L, "scan",
                                      buffer_mi=asm["buffer_mi"])
        cns = {c: float(asm_cns_full(asm, p, c)) for c in val("gen_jobs_naics")}
        raw = {"flows": np.array([p["flows"]]), "zveh": np.array([p["zveh_hh"]]),
               "e002": np.array([p["e002"]]), "e016": np.array([p["e016"]]),
               "popden": np.array([p["popden"]]),
               "genjobs": np.array([p["genjobs"]]),
               "gen_dummy": np.array([float(p["gen_dummy"])]),
               **{f"cns_{c}": np.array([cns[c]]) for c in cns}}
        cols = _score_cols(raw, cfg)
        X = score_design_v22(cols, cfg, [proj.L], fe_year="fy2019")
        pred = float((X @ head["beta"])[0]) + (math.log(proj.L)
                                               if cfg["offset"] else 0.0)
        b19, rvh19 = fy19[r]
        actual = math.log(b19 / rvh19)          # actual fy2019 productivity
        g = pred - actual
        gap[r] = g
        flag[r] = bool(g > loo_p90)
    return gap, flag


def asm_cns_full(asm, p, c):
    """Per-CNS sum for a full-shape route catchment (recomputed from the scan
    per-block CNS arrays via the window block index)."""
    return asm["_cns2022"][c][p["block_idx"]].sum()


# ---------------------------------------------------------------------------
# chart
# ---------------------------------------------------------------------------
def make_chart(artifact, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    SURFACE = "#fcfcfb"; INK = "#0b0b0b"; INK2 = "#52514e"
    GRID = "#e1e0d9"; MUTED = "#898781"
    PALETTE = ["#2a78d6", "#e34948", "#1b8a6b", "#b0771f", "#7b5cd6",
               "#c74e9b", "#4a8fa8", "#898781"]
    plt.rcParams["font.family"] = ["Segoe UI", "DejaVu Sans", "sans-serif"]
    wins = sorted(artifact["windows"], key=lambda w: w["rank"])[:25]
    hosts = []
    for w in wins:
        if w["route_id"] not in hosts:
            hosts.append(w["route_id"])
    gcol = {g: PALETTE[i % len(PALETTE)] for i, g in enumerate(hosts)}
    fig, ax = plt.subplots(figsize=(10.6, 8.2), dpi=200)
    fig.patch.set_facecolor(SURFACE); ax.set_facecolor(SURFACE)
    fig.subplots_adjust(left=0.30, right=0.97, top=0.90, bottom=0.08)
    ys = np.arange(len(wins))[::-1]
    for y0, w in zip(ys, wins):
        c = gcol[w["route_id"]]
        ax.plot([w["screen_index_p10"], w["screen_index_p90"]], [y0, y0],
                color=c, lw=2.2, alpha=0.55, solid_capstyle="round", zorder=2)
        ax.plot(w["screen_index_p50"], y0, "o", color=c, ms=6, zorder=3)
        tag = " tie" if w["tie_with_cutoff"] else ""
        tag += " under" if w["underservice_flag"] else ""
        ax.annotate(tag, (w["screen_index_p90"], y0),
                    textcoords="offset points", xytext=(6, -3), fontsize=7,
                    color=INK2)
    labels = [f"#{w['rank']}  rt {w['route_id']}  "
              f"{w['w0']:.1f}-{w['w1']:.1f} mi" for w in wins]
    ax.set_yticks(ys); ax.set_yticklabels(labels, fontsize=8, color=INK)
    ax.set_xlabel("ordinal screening index (median fitted route's best-window "
                  "PRODUCTIVITY = 100) — not a ridership forecast",
                  fontsize=9, color=INK)
    ax.axvline(100, color=MUTED, lw=0.8, ls="--", zorder=1)
    ax.grid(axis="x", color=GRID, lw=0.7); ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.set_title("Stage-1 DRM screen v2.2 (productivity, DV = log(b/RVH)) — "
                 "top 25 windows,\nP50 with P10-P90 whiskers, colored by host "
                 f"shape (ordinal_ok "
                 f"{artifact['decision_output']['ordinal_ok']})",
                 fontsize=11, color=INK, loc="left")
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)


# ---------------------------------------------------------------------------
# artifact assembly
# ---------------------------------------------------------------------------
def build_artifact(n_boot=None, quiet=False):
    seed = val("screen_seed")
    n_boot = val("screen_n_boot") if n_boot is None else int(n_boot)
    estimand = val("screen_estimand_v22")
    assert estimand == "log(boardings/RVH)", estimand
    win = val("screen_window_mi")
    step = val("screen_step_mi")
    buf = val("buffer_mi")
    thr = val("screen_overlap_threshold")

    data = sv.load_data_v21(acs_vintages=("2017", "2019", "2021", "2023"),
                            lodes_vintages=("2017", "2019", "2021", "2022"))
    cns_fit = sf.load_cns_by_block(data, ("2017", "2019", "2021", "2022"))
    cns2022 = cns_fit["2022"]
    fit_projs = sf.build_fit_projs(data, quiet=quiet)   # expensive step, once
    fit = sf.build_fit_rows(data, cns_fit, buf, projs=fit_projs, quiet=quiet)
    fit_rows = fit["rows"]
    assert np.all(fit_rows["rvh"].to_numpy(float) > 0.0), \
        "productivity DV requires RVH > 0 on every fit row (§10 D8)"
    projs = current_universe(data)
    asm = assemble_scan(data, cns2022, projs, buf, win, step)
    asm["_cns2022"] = cns2022
    if not quiet:
        print(f"v2.2 PRODUCTIVITY fit -- DV = {estimand}")
        print(f"fit: {len(fit_rows)} route-years, "
              f"{fit_rows['route'].nunique()} clusters; "
              f"scan: {asm['n_weekday']} weekday shapes, "
              f"{asm['n_eligible']} >= {win} mi, {asm['n_windows']} windows")

    head = score(fit_rows, asm, sf.BASE_CFG_V22)
    y, X, names, groups = head["y"], head["X"], head["names"], head["groups"]
    pri = sf.fit_primary(y, X, names, groups)
    b4_est = float(pri["params"][names.index("b4_genjobs")])
    b4_wrong_sign = b4_est < 0.0
    loo = loo_battery(fit_rows, asm, head)
    boot = bootstrap(fit_rows, asm, sf.BASE_CFG_V22, n_boot, seed, quiet=quiet)

    wids = asm["W"]["window_id"]
    tract_sets = {w: set(bi.tolist())
                  for w, bi in zip(wids, asm["W"]["block_idx"])}
    groups_head = _overlap_groups(wids, tract_sets, thr)
    if not quiet:
        print("sensitivity battery (17 frozen rows)...")
    sens, nb_info, ctxs = sensitivity_block(
        data, cns2022, cns_fit, fit, fit_projs, asm, head, tract_sets,
        groups_head, buf, win, step, quiet=quiet)
    head_tie_ids = [wids[i] for i in np.flatnonzero(boot["tie"])]
    head_tie_hosts = sorted({asm["W"]["route_id"][i]
                             for i in np.flatnonzero(boot["tie"])},
                            key=sf._route_sort_key)
    if not quiet:
        print("shortlist stability (per-row tie bootstraps)...")
    stability = shortlist_stability(ctxs, sens, head_tie_ids, head_tie_hosts,
                                    n_boot, seed, quiet=quiet)
    if not quiet:
        print("regime-split gate (§9.10/D7)...")
    regime = regime_split(fit_rows, n_boot, seed, val("screen_pos_frac_min"))
    incumbents = _incumbents(data, asm, buf, thr)
    gap, flag = _underservice(fit_rows, data, asm, head, loo["p90_abs_err"])

    rank, order = _ranking(boot["p50"], wids)
    wcols = _score_cols(asm["W"], sf.BASE_CFG_V22)
    lo1, hi1 = head["X"][:, 1].min(), head["X"][:, 1].max()
    lo2, hi2 = head["X"][:, 2].min(), head["X"][:, 2].max()
    lev = ((wcols["b1"] < lo1) | (wcols["b1"] > hi1)
           | (wcols["b2"] < lo2) | (wcols["b2"] > hi2))
    beta = dict(zip(names, head["beta"]))
    # reference route for the grouped decomposition (lower-median fitted host
    # route by its own best-window prediction)
    best_pred = np.array([head["win_pred"][g].max()
                          for g in head["host_groups"]])
    base_host = int(np.argsort(best_pred, kind="stable")[
        (len(best_pred) - 1) // 2])
    hg = head["host_groups"]
    ref_i = int(hg[base_host][np.argmax(head["win_pred"][hg[base_host]])])
    windows = []
    for i, wid in enumerate(wids):
        rid = asm["W"]["route_id"][i]
        demand = (beta["b1_flows"] * (wcols["b1"][i] - wcols["b1"][ref_i])
                  + beta["b2_zveh"] * (wcols["b2"][i] - wcols["b2"][ref_i]))
        generator = (beta.get("b4_genjobs", 0.0)
                     * (wcols["b4"][i] - wcols["b4"][ref_i]))
        windows.append({
            "window_id": wid, "route_id": rid,
            "w0": asm["W"]["w0"][i], "w1": asm["W"]["w1"][i], "window_mi": win,
            "screen_index_p50": boot["p50"][i],
            "screen_index_p10": boot["p10"][i],
            "screen_index_p90": boot["p90"][i],
            "rank": int(rank[i]),
            "rank_ci": [boot["rank_lo"][i], boot["rank_hi"][i]],
            "tie_with_cutoff": bool(boot["tie"][i]),
            "decomposition": {"demand": demand, "generator": generator,
                              "note": "grouped vs the lower-median fitted host "
                                      "route's best window; scale (b5) cancels "
                                      "at equal window length; productivity is "
                                      "exposure-normalized so no service term"},
            "overlap_group": groups_head[wid],
            "underservice_gap": gap.get(rid),
            "underservice_flag": flag.get(rid, False),
            "leverage_flag": bool(lev[i]),
            "incumbent_routes": incumbents[i]})
    windows.sort(key=lambda w: (sf._route_sort_key(w["route_id"]), w["w0"]))

    decision = decision_block(pri, names, sens, windows, boot["signs"],
                              n_boot, stability, regime, b4_wrong_sign)

    n_groups = len(set(groups_head.values()))
    best = {}
    for i, rid in enumerate(asm["W"]["route_id"]):
        if rid not in best or rank[i] < rank[best[rid]]:
            best[rid] = i
    best_rows = sorted(({"route_id": r, "window_id": wids[i],
                         "rank": int(rank[i]),
                         "screen_index_p50": boot["p50"][i]}
                        for r, i in best.items()), key=lambda b: b["rank"])
    pairs = _pairwise_shares([b["window_id"] for b in best_rows], tract_sets,
                             thr)
    overlap_diag = {
        "n_windows": len(wids), "n_groups": n_groups,
        "single_component": bool(n_groups == 1),
        "note": "connected-component grouping (§3.3) is degenerate at county "
                "scale; gate 1 uses best_window_per_shape + per-pair shares "
                "below (no transitive closure)",
        "best_window_per_shape": best_rows,
        "pairwise_share_gt_threshold": [{"a": a, "b": b, "share": s}
                                        for a, b, s in pairs]}

    flagged_routes = sorted(
        set(fit_rows[fit_rows["gen_dummy"] == 1]["route"]),
        key=sf._route_sort_key)
    fit_diag = {
        "estimand": estimand,
        "estimator": "log-OLS on log(boardings/RVH) [productivity, §10 D1], "
                     "cluster-robust SEs by route; NB2 RATE model (log(RVH) "
                     "fixed offset) always fitted (nb_estimator row)",
        "coefficients": {n_: {"est": float(b), "se_cluster": float(s)}
                         for n_, b, s in zip(names, pri["params"],
                                             pri["se_cluster"])},
        "b4_wrong_sign": {"flag": bool(b4_wrong_sign), "b4_genjobs_est": b4_est,
                          "note": "§9.1/§10 D3 pre-registered handling: a "
                                  "negative l_genjobs does NOT trip the "
                                  "demand-block criterion (b4 is outside the "
                                  "block) but raises this logged diagnostic -- "
                                  "a signal that b5 (scale) may be absorbing "
                                  "attraction effects; setting it OBLIGATES a "
                                  "README known-issue entry before any gate "
                                  "memo consumes the artifact"},
        "vif": sf.vifs(X, names),
        "n_routes": len(head["routes"]),
        "n_route_years": int(len(y)),
        "rows_by_fy": {k: int(v) for k, v in
                       head["df"].groupby("fy").size().items()},
        "dropped_route_years_shapeless": [f"{r} {fy}" for r, fy in
                                          fit["dropped_shapeless"]],
        "dropped_route_years_no_rvh": [f"{r} {fy}: {why}" for r, fy, why in
                                       fit["dropped_norvh"]],
        "fit_side_shapes": "contemporaneous archived GTFS per boardings year "
                           "(§9.4); scan side on current 2026-07 GTFS",
        "v22_resid_decomposition": sf.resid_decomposition(fit_rows),
        "loo_route": {"rho_min": loo["rho_min"],
                      "rho_min_route": loo["rho_min_route"],
                      "rho_floor": val("screen_loo_rho"), "male": loo["male"],
                      "male_ceiling": val("screen_male"),
                      "p90_abs_log_err": loo["p90_abs_err"],
                      "worst5": loo["worst5"]},
        "nb2": nb_info,
        "flagged_generator_routes": flagged_routes,
        "estimand_note": "DV = log(boardings/RVH) = productivity (§10 D1/D2). "
                         "b3 (RVH) is PINNED at +1 and moved to the LHS -- it "
                         "is NOT an RHS coefficient. NO standardized-service "
                         "scoring (svc_std RETIRED, §10 D6): the scan predicts "
                         "productivity directly; the index is same-exposure-"
                         "normalized predicted productivity (ordinal only). NO "
                         "field is denominated in boardings",
        "grouped_decomposition_note": "per-window decomposition is GROUPED "
                                      "(demand b1+b2 / generator b4) vs the "
                                      "lower-median fitted host route's best "
                                      "window; demand coefficients are "
                                      "individually weak so per-coefficient "
                                      "attribution is noise attribution "
                                      "(spec 01 §3.1)"}

    consumed = [{"id": cid, "role": role, "value": val(cid)}
                for cid, role in CONSUMED]
    consumed.sort(key=lambda c: c["id"])
    bands = {bid: list(band(bid)) for bid in sorted(BAND_CONSUMED)}
    values_hash = nm.network_fingerprint(
        {"consumed": {c["id"]: c["value"] for c in consumed}, "bands": bands})
    with open(os.path.join(HERE, "..", "config", "special_generators.json"),
              encoding="utf-8") as f:
        gens_cfg = json.load(f)["generators"]
    manifest_consumed = sorted(fit["feeds"].keys())
    universe = {"scan_rule": "all current-GTFS weekday route shapes with "
                             "main-shape length >= window length; no "
                             "functional-class filter",
                "n_weekday_shapes": asm["n_weekday"],
                "n_eligible_shapes": asm["n_eligible"],
                "n_windows": asm["n_windows"], "window_mi": win, "step_mi": step,
                "fit_n_route_years": int(len(y)),
                "fit_n_clusters": len(head["routes"]),
                "archived_feeds_consumed": manifest_consumed}
    run_id = nm.network_fingerprint({
        "schema": SCHEMA, "seed": seed, "n_boot": n_boot, "universe": universe,
        "vintages": VINTAGES, "estimand": estimand,
        "special_generators": gens_cfg,
        "archived_manifest": {fy: ARCHIVE_FEEDS_SHA(fy) for fy in
                              manifest_consumed},
        "assumptions_values_hash": values_hash})

    artifact = {
        "run_id": run_id, "schema": SCHEMA, "seed": seed, "n_boot": n_boot,
        "estimand": estimand,
        "universe": universe, "vintages": VINTAGES, "disclaimer": DISCLAIMER,
        "bootstrap": {
            "method": "route-cluster resample with replacement, refit, "
                      "rescore all windows jointly (spec 01 §3.4)",
            "acs_moe_perturbation": False,
            "acs_moe_note": "the §3.4 within-replicate ACS-MOE perturbation is "
                            "NOT applied: screen_common_v21 carries no ACS MOE "
                            "(input-availability fact, not a tuning choice; it "
                            "removes one noise source, so criterion 1 is "
                            "marginally MORE lenient -- stated)"},
        "assumptions_manifest": {"consumed": consumed, "bands": bands,
                                 "values_hash": values_hash},
        "windows": windows, "overlap_diagnostics": overlap_diag,
        "fit_diagnostics": fit_diag, "sensitivity": sens,
        "shortlist_stability": stability, "decision_output": decision,
        "notes": {
            "index": "screen_index = 100 * exp(predicted PRODUCTIVITY - "
                     "baseline); baseline = lower-median over fitted host "
                     "routes of each route's own BEST window predicted "
                     "productivity (same-exposure normalization; productivity "
                     "is already exposure-normalized so NO service level "
                     "injected; ordinal only) [§10 D6]",
            "estimand": "DV = log(boardings/RVH); b3 (RVH) pinned at +1 and "
                        "moved to the LHS (§10 D1/D2)",
            "zero_handling": "b1/b2/b4 consume catchment sums through log1p",
            "tie_with_cutoff": "95% joint bootstrap rank interval straddles the "
                               "rank-5 boundary (gate-1 tie rule)",
            "fit_scan_asymmetry": "fit side uses contemporaneous archived GTFS "
                                  "shapes per boardings year (§9.4, "
                                  "discontinued routes re-enter); scan side on "
                                  "current 2026-07 GTFS (candidates must be "
                                  "buildable today)",
            "sensitivity_pct": "pct = 100 * (1 - Spearman rho of the full "
                               "window ranking vs headline)"}}
    return artifact


# archived-feed sha lookup for the run_id preimage (consumed manifest)
_MANIFEST = None


def ARCHIVE_FEEDS_SHA(fy):
    global _MANIFEST
    if _MANIFEST is None:
        m = pd.read_csv(os.path.join(HERE, "..", "data", "derived",
                                     "gtfs_archive_manifest.csv"), dtype=str)
        _MANIFEST = {r["fy"]: r["sha256"] for _, r in m.iterrows()}
    return _MANIFEST[fy]


def main(argv):
    import time
    t0 = time.time()
    artifact = build_artifact()
    out = os.path.join(OUT, "screen_results_v22.json")
    write_artifact(out, artifact)
    print(f"-> {out}  (run_id {artifact['run_id'][:16]})")
    png = os.path.join(OUT, "screen_ranked_v22.png")
    make_chart(artifact, png)
    print(f"-> {png}")
    d = artifact["fit_diagnostics"]
    co = d["coefficients"]
    print(f"\nestimand {d['estimand']}; fit N {d['n_route_years']} route-years "
          f"/ {d['n_routes']} clusters; rows_by_fy {d['rows_by_fy']}")
    print("dropped shapeless:", d["dropped_route_years_shapeless"])
    print("dropped no-RVH:", d["dropped_route_years_no_rvh"])
    for k in ("b1_flows", "b2_zveh", "b4_genjobs", "b5_len"):
        print(f"  {k:12s} {co[k]['est']:+.4f} (se {co[k]['se_cluster']:.4f}) "
              f"VIF {d['vif'][k]:.2f}")
    do = artifact["decision_output"]
    c = do["criteria"]
    sp, br, tc = c["sign_pos_frac"], c["battery_rho"], c["tie_churn"]
    rs = do["regime_split"]
    print(f"\nCRITERION 1: b1_pos_frac {sp['b1_pos_frac']:.4f} / b2_pos_frac "
          f"{sp['b2_pos_frac']:.4f} vs {sp['threshold']} -> "
          f"{'PASS' if sp['pass'] else 'FAIL'}")
    print(f"CRITERION 2: min rho {br['min_rho']:.4f} ({br['worst_row_id']}) "
          f"vs {br['threshold']} -> {'PASS' if br['pass'] else 'FAIL'}")
    print(f"CRITERION 3: window {tc['window']['max_over_window_unit_rows']:.4f} "
          f"({tc['window']['worst_row']}) vs {tc['window']['threshold']} -> "
          f"{'PASS' if tc['window']['pass'] else 'FAIL'}; hostshape "
          f"{tc['hostshape']['max_over_window10_window15']:.4f} "
          f"({tc['hostshape']['worst_row']}) vs "
          f"{tc['hostshape']['threshold']:.6f} -> "
          f"{'PASS' if tc['hostshape']['pass'] else 'FAIL'}")
    print(f"REGIME SPLIT: pre2020 b1_pf {rs['pre2020_pf']['b1_pos_frac']:.4f} / "
          f"b2_pf {rs['pre2020_pf']['b2_pos_frac']:.4f} "
          f"(pass {rs['pre2020_pf']['pass']}); interaction i_flows_post "
          f"{rs['interaction_coefficients']['i_flows_post']['est']:+.4f} / "
          f"i_zveh_post "
          f"{rs['interaction_coefficients']['i_zveh_post']['est']:+.4f}; "
          f"downgrade {rs['regime_split_downgrade']}")
    print(f"b4_wrong_sign: {do['b4_wrong_sign']}")
    print(f"\nVERDICT: ordinal_ok {do['ordinal_ok']}, decision_format "
          f"{do['decision_format']}; shortlist {len(do['shortlist'])} "
          f"windows; stable_core "
          f"{artifact['shortlist_stability']['aggregate']['n_stable_core']}/"
          f"{artifact['shortlist_stability']['aggregate']['n_tie_headline']}")
    print(f"runtime {time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
