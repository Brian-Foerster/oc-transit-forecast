"""Stage-1 screen: county-wide window scan (spec 01 §3.2-3.4, §4 / panel
D4-D10, D12, D17, D19, D21).

Universe (MECHANICAL, no 'major arterial' filter -- governance rule 1):
every weekday GTFS route shape with main-shape length >= 12.5
[screen_window_mi]; windows slide at 0.5 [screen_step_mi] steps, w0 = k*step
exactly. Every window's predictors come from the SAME shared
screen_common.compute_predictors as the fit side (panel D6).

Published score (ordinal ONLY, spec 00 §1): screen_index = 100 * predicted
at standardized service / (median fitted-route prediction at standardized
service). svc_std = 1577.65 [screen_svc_std] FY2019 RVH per route-mile x
window length. NO field in the artifact is denominated in boardings; a
standing test (test_screen.py D3) enforces it.

Uncertainty: route-cluster bootstrap, B = 2000 [screen_n_boot], seeded
default_rng(7 [screen_seed]) -- resample ROUTES with replacement, refit,
rescore ALL windows jointly per replicate; tract E002 perturbed within
MOE/1.645 [moe_z] (normal, clipped at 0) inside each replicate (panel D9).
tie_with_cutoff operationalizes gate 1's tie rule from the JOINT rank
distribution.

Sensitivity block (THE stage-1 materiality convention): each pre-registered
perturbation reruns the point pipeline and reports pct = 100 * (1 - Spearman
rho of the full window ranking vs headline) with top-8 set churn in detail.
The 16 row ids match the registry's screen claims exactly
(check_assumptions.py `screen` scan).

Artifact: outputs/screen_results.json, deterministic write (sort_keys,
indent=2, LF, floats 6dp, no timestamps; run_id preimage includes the
assumptions values_hash -- sequence_network.py pattern). Dual-generation
byte-identity is a commit gate (D21). Chart: outputs/screen_ranked.png (D19).

    python screen_scan.py            -> artifact + chart + console summary
"""
import json
import math
import os
import sys

import numpy as np
import pandas as pd

from assumptions import val, band
import network_mechanics as nm          # canonical fingerprint (acyclic)
import screen_common as sc
import screen_fit as sf

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "outputs")

SCHEMA = "01-S1"
# canonical artifact float precision (sequence_network.py CANON_DECIMALS
# precedent -- readability + last-ULP drift guard, not an analytic constant)
CANON_DECIMALS = 6

DISCLAIMER = ("ordinal screening index; not a ridership forecast "
              "(spec 00 §1)")

VINTAGES = {"gtfs": "2026-07", "lodes": "2022", "acs": "2019-2023 5-yr",
            "apc": "FY2017 / FY2019 / FY2020-Q3 (9-mo YTD, March-in)"}

# registry leaves the scan consumes via val() -- declared in the artifact's
# assumptions_manifest; their values-hash enters the run_id preimage.
CONSUMED = (
    ("buffer_mi", "catchment radius (shared with stage 2 -- D13)"),
    ("screen_window_mi", "window length"),
    ("screen_step_mi", "window slide step"),
    ("screen_overlap_threshold", "overlap-grouping threshold"),
    ("screen_svc_std", "standardized service (FY2019 RVH/route-mi)"),
    ("screen_n_boot", "bootstrap replicates"),
    ("screen_seed", "bootstrap RNG seed"),
    ("screen_loo_rho", "LOO leverage-screen floor"),
    ("screen_male", "LOO MALE ceiling"),
    ("moe_z", "ACS 90% MOE -> SE conversion"),
    ("mi_lat", "mi per degree latitude"),
    ("mi_per_deg_lon", "mi per degree longitude at equator"),
    ("oc_ref_lat", "OC reference latitude"),
)

# registry ids whose band() EDGES the sensitivity block consumes (buffer_lo/
# hi, window_10/15, svc_p25/p75, overlap_lo/hi). Declared in the manifest and
# hashed into the run_id preimage alongside the val() leaves -- otherwise a
# band edit would regenerate an artifact under an unchanged run_id
# (review 2026-07-19 provenance fix).
BAND_CONSUMED = ("buffer_mi", "screen_overlap_threshold", "screen_svc_std",
                 "screen_window_mi")


# ---------------------------------------------------------------------------
# canonical serialization (sequence_network.py write pattern)
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
# assembly: fit frame + window predictors for one (buffer, window_mi)
# ---------------------------------------------------------------------------
def assemble(inputs, projs, views, buffer_mi, window_mi, step_mi):
    """Fit frame (shared function, full-shape windows) + sliding-window
    predictors for every eligible weekday shape. Sorted route iteration;
    integer-step w0 (determinism items 2-3)."""
    fit = sf.build_fit_frame(projs, inputs, buffer_mi, views)
    wins = []
    n_eligible = 0
    for rid in sorted(projs, key=sf._route_sort_key):
        proj = projs[rid]
        if proj.L < window_mi:
            continue
        n_eligible += 1
        key = (rid, buffer_mi)
        if key not in views:
            views[key] = sc.CatchmentView(proj, buffer_mi, inputs["od_h"],
                                          inputs["od_w"], inputs["od_n"])
        view = views[key]
        for w0 in sc.window_starts(proj.L, window_mi, step_mi):
            w1 = w0 + window_mi
            p = sc.compute_predictors(view, w0, w1,
                                      {"e002": inputs["e002"],
                                       "e016": inputs["e016"]})
            p["route_id"] = rid
            p["w0"] = float(w0)
            p["w1"] = float(w1)
            p["window_id"] = f"{rid}_{w0:05.1f}"
            wins.append(p)
    W = {
        "route_id": [w["route_id"] for w in wins],
        "window_id": [w["window_id"] for w in wins],
        "w0": np.array([w["w0"] for w in wins]),
        "w1": np.array([w["w1"] for w in wins]),
        "l_lodes": np.log1p(np.array([w["lodes_both"] for w in wins])),
        "sum_e002": np.array([w["sum_e002"] for w in wins]),
        "sum_e016": np.array([w["sum_e016"] for w in wins]),
        "gen_types": [w["gen_types"] for w in wins],
        "tract_idx": [w["tract_idx"] for w in wins],
    }
    return {"fit": fit, "W": W, "n_windows": len(wins),
            "n_eligible": n_eligible, "n_weekday": len(projs),
            "buffer_mi": buffer_mi, "window_mi": window_mi}


def _window_cols(asm, cfg):
    W = asm["W"]
    return {"l_lodes": W["l_lodes"],
            "l_e002": np.log1p(W["sum_e002"]),
            "l_e016": np.log1p(W["sum_e016"]),
            "gen": np.array([sf._gen_dummy(g, cfg["gen_exclude"])
                             for g in W["gen_types"]], float)}


def _route_cols(fit, routes, cfg):
    rp = fit["route_pred"]
    return {"l_lodes": np.log1p(np.array([rp[r]["lodes_both"]
                                          for r in routes])),
            "l_e002": np.log1p(np.array([rp[r]["sum_e002"] for r in routes])),
            "l_e016": np.log1p(np.array([rp[r]["sum_e016"] for r in routes])),
            "gen": np.array([sf._gen_dummy(rp[r]["gen_types"],
                                           cfg["gen_exclude"])
                             for r in routes], float)}


def _index_from_preds(win_pred, route_pred):
    """screen_index = 100 * exp(window pred - BASELINE route pred); baseline
    = the lower-median fitted route (deterministic; exact median at odd n).
    Any common additive term (year FE, a svc level shift) cancels here --
    which is exactly why the svc_p25/p75 rows are rank-inert."""
    base = np.sort(route_pred)[(len(route_pred) - 1) // 2]
    return 100.0 * np.exp(win_pred - base), float(base)


def score(asm, cfg, svc, beta=None):
    """Point pipeline for one model config: fit (unless beta given), score
    all windows + fitted routes at standardized service, return index."""
    y, X, names, groups, df = sf.design_matrix(asm["fit"]["rows"], cfg)
    if beta is None:
        beta = sf.ols_beta(y, X)
    routes = sorted(set(df["route"]), key=sf._route_sort_key)
    Xw = sf.score_design(_window_cols(asm, cfg), cfg, svc,
                         asm["window_mi"])
    Lr = np.array([asm["fit"]["route_pred"][r]["L"] for r in routes])
    Xr = sf.score_design(_route_cols(asm["fit"], routes, cfg), cfg, svc, Lr)
    win_pred = Xw @ beta
    route_pred = Xr @ beta
    if cfg["offset"]:
        win_pred = win_pred + math.log(asm["window_mi"])
        route_pred = route_pred + np.log(Lr)
    index, base = _index_from_preds(win_pred, route_pred)
    return {"beta": beta, "names": names, "y": y, "X": X, "groups": groups,
            "df": df, "routes": routes, "index": index, "win_pred": win_pred,
            "route_pred": route_pred, "base_logpred": base, "Xw": Xw,
            "Xr": Xr, "Lr": Lr}


def _ranking(index, window_ids):
    """Deterministic rank (1 = best; ties broken by window_id)."""
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
# bootstrap (headline only -- panel D9)
# ---------------------------------------------------------------------------
def bootstrap(asm, cfg, svc, inputs, n_boot, seed, quiet=False):
    """Route-cluster bootstrap with within-replicate ACS E002 MOE
    perturbation. ALL windows rescored jointly per replicate; returns
    per-window index percentiles + joint rank distribution stats."""
    head = score(asm, cfg, svc)
    routes = head["routes"]
    nR = len(routes)
    nT = len(inputs["e002"])
    W = asm["W"]
    nW = len(W["window_id"])
    b2col = head["names"].index("b2_e002" if not cfg["use_e016"]
                                else "b2_e016")
    # membership matrices for perturbed-sum recomputation
    Mw = np.zeros((nW, nT))
    for i, ti in enumerate(W["tract_idx"]):
        Mw[i, ti] = 1.0
    Mr = np.zeros((nR, nT))
    for i, r in enumerate(routes):
        Mr[i, asm["fit"]["route_pred"][r]["tract_idx"]] = 1.0
    row_route = np.array([routes.index(r) for r in head["df"]["route"]])
    route_rows = [np.flatnonzero(row_route == i) for i in range(nR)]
    y, X = head["y"], head["X"].copy()
    Xw = head["Xw"].copy()
    Xr = head["Xr"].copy()
    e002, se = inputs["e002"], inputs["se_e002"]
    rng = np.random.default_rng(seed)
    idx_mat = np.empty((n_boot, nW))
    rank_mat = np.empty((n_boot, nW), int)
    wids = W["window_id"]
    for b in range(n_boot):
        sample = rng.integers(0, nR, nR)
        z = rng.standard_normal(nT)
        e = np.clip(e002 + se * z, 0.0, None)
        re = np.log1p(Mr @ e)
        we = np.log1p(Mw @ e)
        X[:, b2col] = re[row_route]
        rows_sel = np.concatenate([route_rows[i] for i in sample])
        beta = sf.ols_beta(y[rows_sel], X[rows_sel])
        Xw[:, b2col] = we
        Xr[:, b2col] = re
        wp = Xw @ beta
        rp = Xr @ beta
        idx, _ = _index_from_preds(wp, rp)
        idx_mat[b] = idx
        order = np.argsort(-idx, kind="stable")
        rank_mat[b, order] = np.arange(1, nW + 1)
        if not quiet and (b + 1) % 500 == 0:
            print(f"  bootstrap {b + 1}/{n_boot}")
    p10, p50, p90 = np.percentile(idx_mat, [10, 50, 90], axis=0)
    rank_lo, rank_hi = np.percentile(rank_mat, [2.5, 97.5], axis=0)
    # tie_with_cutoff: the 95% joint-rank interval straddles the rank-5
    # boundary (gate 1's tie rule in bootstrap-rank form, spec 00 §3)
    tie = (rank_lo <= 5.0) & (rank_hi > 5.0)
    return {"p10": p10, "p50": p50, "p90": p90,
            "rank_lo": rank_lo, "rank_hi": rank_hi, "tie": tie,
            "head": head, "window_ids": wids}


# ---------------------------------------------------------------------------
# LOO / leave-one-year-out batteries (point fits)
# ---------------------------------------------------------------------------
def loo_battery(asm, cfg, svc, head):
    """Leave-one-ROUTE-out (all its years): out-of-sample log errors (MALE,
    P90 for the underservice flag), and the window-ranking leverage screen
    (min Spearman rho vs headline across deletions)."""
    y, X, names, groups = head["y"], head["X"], head["names"], head["groups"]
    routes = head["routes"]
    errs, route_err = [], {}
    rho_min, rho_min_route = 1.0, None
    for r in routes:
        m = groups != r
        beta = sf.ols_beta(y[m], X[m])
        e = y[~m] - X[~m] @ beta
        errs.extend(np.abs(e).tolist())
        route_err[r] = float(np.mean(np.abs(e)))
        wp = head["Xw"] @ beta
        rp = head["Xr"] @ beta
        idx, _ = _index_from_preds(wp, rp)
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


def loy_battery(asm, cfg, svc, head):
    """Leave-one-YEAR-out window-rank stability (gate battery c)."""
    out = {}
    for fy in sf.FYS:
        m = (head["df"]["fy"] != fy).to_numpy()
        beta = sf.ols_beta(head["y"][m], head["X"][m])
        wp = head["Xw"] @ beta
        rp = head["Xr"] @ beta
        idx, _ = _index_from_preds(wp, rp)
        out[fy] = _spearman(idx, head["index"])
    return out


# ---------------------------------------------------------------------------
# sensitivity block (the pre-registered battery, spec 01 §5 / D12b)
# ---------------------------------------------------------------------------
def _row(rid, label, head_idx, head_ids, var_idx, var_ids=None, note=None,
         extra=None):
    var_ids = head_ids if var_ids is None else var_ids
    if var_ids is head_ids:
        rho = _spearman(head_idx, var_idx)
        churn = _churn(_top8(head_idx, head_ids), _top8(var_idx, var_ids))
    else:
        raise ValueError("mismatched window sets need a caller-computed rho")
    detail = {"rho": rho, **churn}
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
    """window_10/window_15: window sets differ, so the ranking comparison is
    best-window-per-host-shape over the shapes eligible in BOTH scans."""
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
                       "note": "best-window-per-host-shape comparison over "
                               f"{len(common)} shapes eligible in both scans "
                               "(window sets differ across lengths); churn "
                               "ids are host shapes",
                       "n_windows_variant": var_asm["n_windows"]}}


def sensitivity_block(inputs, projs, views, asm, head, svc, tract_sets,
                      groups_head, quiet=False):
    rows = []
    hidx, hids = head["index"], asm["W"]["window_id"]
    step = val("screen_step_mi")
    win = val("screen_window_mi")

    def say(rid):
        if not quiet:
            print(f"  sensitivity row {rid}")

    # buffer band edges (D13 -- shared buffer_mi entry, both edges)
    for rid, buf in (("buffer_lo", band("buffer_mi")[0]),
                     ("buffer_hi", band("buffer_mi")[1])):
        say(rid)
        a = assemble(inputs, projs, views, buf, win, step)
        v = score(a, sf.BASE_CFG, svc)
        assert a["W"]["window_id"] == hids
        rows.append(_row(rid, f"catchment buffer {buf} mi", hidx, hids,
                         v["index"]))
    # window length band edges (best-per-shape comparison)
    for rid, wlen in (("window_10", band("screen_window_mi")[0]),
                      ("window_15", band("screen_window_mi")[1])):
        say(rid)
        a = assemble(inputs, projs, views, val("buffer_mi"), wlen, step)
        v = score(a, sf.BASE_CFG, svc)
        rows.append(_length_row(rid, f"window length {wlen} mi", head, asm,
                                v, a))
    # model-config perturbations on the headline assembly
    cfg_rows = (
        ("drop_fy2020", "drop FY2020-Q3 rows", {"drop_fy2020": True}),
        ("drop_rh", "fit without revenue hours (D14 firewall)",
         {"use_rh": False}),
        ("e016_swap", "E016 transit workers back in for E002",
         {"use_e016": True}),
        ("b4_off", "drop the special-generator dummy", {"b4": False}),
        ("offset_variant", "log(length) offset (b5 pinned to 1)",
         {"offset": True}),
        ("year_fe_vs_pooled", "pooled fit (no year FE)", {"year_fe": False}),
    )
    for rid, label, over in cfg_rows:
        say(rid)
        v = score(asm, dict(sf.BASE_CFG, **over), svc)
        rows.append(_row(rid, label, hidx, hids, v["index"]))
    # gen_leave_class_out: one row, per-class detail, pct = worst class
    say("gen_leave_class_out")
    classes = sorted({t for g in asm["W"]["gen_types"] for t in g}
                     | {t for r in head["routes"] for t in
                        asm["fit"]["route_pred"][r]["gen_types"]})
    by_class, rho_min = {}, 1.0
    for cls in classes:
        v = score(asm, dict(sf.BASE_CFG, gen_exclude=cls), svc)
        rho = _spearman(hidx, v["index"])
        by_class[cls] = {"rho": rho,
                         **_churn(_top8(hidx, hids), _top8(v["index"], hids))}
        rho_min = min(rho_min, rho)
    rows.append({"id": "gen_leave_class_out",
                 "label": "leave one generator class out (worst of "
                          f"{'/'.join(classes)})",
                 "pct": 100.0 * (1.0 - rho_min),
                 "detail": {"rho": rho_min, "by_class": by_class}})
    # NB2 estimator row (always fitted -- estimator_screen)
    say("nb_estimator")
    beta_ols = head["beta"]
    nb_beta, nb_alpha, nb_conv = sf.fit_nb2(
        head["df"]["boardings"].to_numpy(), head["y"], head["X"], beta_ols)
    v = score(asm, sf.BASE_CFG, svc, beta=nb_beta)
    r = _row("nb_estimator", "NB2 robustness estimator", hidx, hids,
             v["index"],
             extra={"alpha": float(nb_alpha), "converged": bool(nb_conv)})
    rows.append(r)
    # svc p25/p75 (rank-inert by construction; the rows PROVE it)
    for rid, s in (("svc_p25", band("screen_svc_std")[0]),
                   ("svc_p75", band("screen_svc_std")[1])):
        say(rid)
        v = score(asm, sf.BASE_CFG, s)
        rows.append(_row(rid, f"standardized service at {s} RVH/route-mi",
                         hidx, hids, v["index"],
                         note="a single additive b3 term shifts every "
                              "window and the baseline route identically, "
                              "so the index is invariant by construction"))
    # overlap threshold band edges: ranking unchanged; regrouping reported
    thr_h = val("screen_overlap_threshold")
    n_head = len(set(groups_head.values()))
    for rid, thr in (("overlap_lo", band("screen_overlap_threshold")[0]),
                     ("overlap_hi", band("screen_overlap_threshold")[1])):
        say(rid)
        g = sc.overlap_groups(hids, tract_sets, thr)
        top8 = _top8(hidx, hids)
        changed = sorted(w for w in top8 if g[w] != groups_head[w])
        rows.append({"id": rid,
                     "label": f"overlap-grouping threshold {thr}",
                     "pct": 0.0,
                     "detail": {"rho": 1.0,
                                "note": "grouping only -- window scores and "
                                        "ranking are unchanged by "
                                        "construction; pct is 0 and the "
                                        "regrouping effect is reported here",
                                "n_groups": len(set(g.values())),
                                "n_groups_headline": n_head,
                                "top8_regrouped": changed}})
    order = ["buffer_lo", "buffer_hi", "window_10", "window_15",
             "drop_fy2020", "drop_rh", "e016_swap", "b4_off",
             "gen_leave_class_out", "nb_estimator", "svc_p25", "svc_p75",
             "offset_variant", "overlap_lo", "overlap_hi",
             "year_fe_vs_pooled"]
    rows.sort(key=lambda r: order.index(r["id"]))
    return rows, {"alpha": float(nb_alpha), "converged": bool(nb_conv)}


# ---------------------------------------------------------------------------
# artifact assembly
# ---------------------------------------------------------------------------
def _incumbents(asm, views, projs, buffer_mi, threshold, inputs):
    """Per-window incumbent routes: every weekday GTFS route whose full-shape
    catchment shares > threshold of the WINDOW's tracts (host included by
    construction). Uses the registered overlap threshold."""
    full_sets = {}
    for rid in sorted(projs, key=sf._route_sort_key):
        key = (rid, buffer_mi)
        if key not in views:
            views[key] = sc.CatchmentView(projs[rid], buffer_mi,
                                          inputs["od_h"], inputs["od_w"],
                                          inputs["od_n"])
        p = sc.compute_predictors(views[key], 0.0, projs[rid].L, {})
        full_sets[rid] = set(p["tract_idx"].tolist())
    out = []
    for ti in asm["W"]["tract_idx"]:
        wset = set(ti.tolist())
        if not wset:
            out.append([])
            continue
        inc = [r for r in sorted(full_sets, key=sf._route_sort_key)
               if len(full_sets[r] & wset) / len(wset) > threshold]
        out.append(inc)
    return out


def _underservice(head, asm, inputs, svc, loo_p90):
    """Host-route underservice gap (log points): predicted at STANDARDIZED
    service (fy2019 FE, svc_std x route length) minus actual FY2019
    boardings, per fitted host route; flagged beyond the LOO P90 abs error
    (panel D7). Windows on unfitted hosts carry null."""
    rb = inputs["rb"].set_index("route")
    cfg = sf.BASE_CFG
    routes = head["routes"]
    Xr19 = sf.score_design(_route_cols(asm["fit"], routes, cfg), cfg, svc,
                           head["Lr"], fe2019=1.0)
    pred19 = Xr19 @ head["beta"]
    gap, flag = {}, {}
    for i, r in enumerate(routes):
        b19 = rb.at[r, "fy2019"] if r in rb.index else np.nan
        if pd.isna(b19):
            continue
        g = float(pred19[i] - np.log(float(b19)))
        gap[r] = g
        flag[r] = bool(g > loo_p90)
    return gap, flag


def make_chart(artifact, path):
    """outputs/screen_ranked.png (panel D19): top ~25 windows, P50 with
    P10-P90 whiskers, overlap-group coloring, ordinal axis label. House
    matplotlib conventions (make_charts.py palette)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    SURFACE = "#fcfcfb"; INK = "#0b0b0b"; INK2 = "#52514e"
    GRID = "#e1e0d9"; MUTED = "#898781"
    PALETTE = ["#2a78d6", "#e34948", "#1b8a6b", "#b0771f", "#7b5cd6",
               "#c74e9b", "#4a8fa8", "#898781"]
    plt.rcParams["font.family"] = ["Segoe UI", "DejaVu Sans", "sans-serif"]
    wins = sorted(artifact["windows"], key=lambda w: w["rank"])[:25]
    groups = []
    for w in wins:
        if w["overlap_group"] not in groups:
            groups.append(w["overlap_group"])
    if len(groups) > 1:
        def ckey(w):
            return w["overlap_group"]
        color_line = "colored by overlap group (spec 01 §4)"
    else:
        # single county-wide component (see overlap_diagnostics): group
        # coloring is vacuous, so color by host shape instead
        def ckey(w):
            return w["route_id"]
        groups = []
        for w in wins:
            if w["route_id"] not in groups:
                groups.append(w["route_id"])
        color_line = ("colored by host shape -- overlap grouping is "
                      "degenerate, one county-wide component "
                      "(overlap_diagnostics)")
    gcol = {g: PALETTE[i % len(PALETTE)] for i, g in enumerate(groups)}
    fig, ax = plt.subplots(figsize=(10.6, 8.2), dpi=200)
    fig.patch.set_facecolor(SURFACE); ax.set_facecolor(SURFACE)
    fig.subplots_adjust(left=0.30, right=0.97, top=0.90, bottom=0.08)
    ys = np.arange(len(wins))[::-1]
    for y0, w in zip(ys, wins):
        c = gcol[ckey(w)]
        ax.plot([w["screen_index_p10"], w["screen_index_p90"]], [y0, y0],
                color=c, lw=2.2, alpha=0.55, solid_capstyle="round",
                zorder=2)
        ax.plot(w["screen_index_p50"], y0, "o", color=c, ms=6, zorder=3)
        tag = " ●tie" if w["tie_with_cutoff"] else ""
        tag += " ▲under" if w["underservice_flag"] else ""
        ax.annotate(tag, (w["screen_index_p90"], y0), textcoords="offset points",
                    xytext=(6, -3), fontsize=7, color=INK2)
    labels = [f"#{w['rank']}  rt {w['route_id']}  "
              f"{w['w0']:.1f}-{w['w1']:.1f} mi" for w in wins]
    ax.set_yticks(ys); ax.set_yticklabels(labels, fontsize=8, color=INK)
    ax.set_xlabel("ordinal screening index (median fitted route = 100) — "
                  "not a ridership forecast", fontsize=9, color=INK)
    ax.axvline(100, color=MUTED, lw=0.8, ls="--", zorder=1)
    ax.grid(axis="x", color=GRID, lw=0.7); ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.set_title("Stage-1 DRM screen — top 25 windows, P50 with P10-P90 "
                 f"whiskers,\n{color_line}",
                 fontsize=11, color=INK, loc="left")
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)


def build_artifact(n_boot=None, quiet=False):
    """The full scan pipeline -> artifact dict (deterministic; no I/O writes
    here so tests can double-run in process)."""
    seed = val("screen_seed")
    n_boot = val("screen_n_boot") if n_boot is None else int(n_boot)
    svc = val("screen_svc_std")
    win = val("screen_window_mi")
    step = val("screen_step_mi")
    buf = val("buffer_mi")
    thr = val("screen_overlap_threshold")

    inputs = sf.load_screen_inputs()
    projs = sf.gtfs_universe(inputs)
    views = {}
    asm = assemble(inputs, projs, views, buf, win, step)
    if not quiet:
        print(f"universe: {asm['n_weekday']} weekday shapes, "
              f"{asm['n_eligible']} >= {win} mi, {asm['n_windows']} windows")
        print(f"dropped routes (no 2026-07 weekday shape): "
              f"{', '.join(asm['fit']['dropped'])}")
        for r, fy, why in asm["fit"]["dropped_years"]:
            print(f"  dropped route-year {r} {fy}: {why}")

    head = score(asm, sf.BASE_CFG, svc)
    y, X, names, groups = head["y"], head["X"], head["names"], head["groups"]
    pri = sf.fit_primary(y, X, names, groups)
    loo = loo_battery(asm, sf.BASE_CFG, svc, head)
    loy = loy_battery(asm, sf.BASE_CFG, svc, head)
    boot = bootstrap(asm, sf.BASE_CFG, svc, inputs, n_boot, seed,
                     quiet=quiet)

    wids = asm["W"]["window_id"]
    tract_sets = {w: set(ti.tolist())
                  for w, ti in zip(wids, asm["W"]["tract_idx"])}
    groups_head = sc.overlap_groups(wids, tract_sets, thr)
    sens, nb_info = sensitivity_block(inputs, projs, views, asm, head, svc,
                                      tract_sets, groups_head, quiet=quiet)
    incumbents = _incumbents(asm, views, projs, buf, thr, inputs)
    gap, flag = _underservice(head, asm, inputs, svc, loo["p90_abs_err"])

    # per-window records
    rank, order = _ranking(boot["p50"], wids)
    wcols = _window_cols(asm, sf.BASE_CFG)
    # leverage: outside the fitted covariate bounding box on b1/b2
    lo1, hi1 = head["X"][:, 1].min(), head["X"][:, 1].max()
    lo2, hi2 = head["X"][:, 2].min(), head["X"][:, 2].max()
    lev = ((wcols["l_lodes"] < lo1) | (wcols["l_lodes"] > hi1)
           | (wcols["l_e002"] < lo2) | (wcols["l_e002"] > hi2))
    # grouped decomposition vs the baseline (lower-median) route
    beta = dict(zip(names, head["beta"]))
    rcols = _route_cols(asm["fit"], head["routes"], sf.BASE_CFG)
    base_i = int(np.argsort(head["route_pred"], kind="stable")[
        (len(head["routes"]) - 1) // 2])
    windows = []
    for i, wid in enumerate(wids):
        rid = asm["W"]["route_id"][i]
        demand = (beta["b1_lodes"] * (wcols["l_lodes"][i]
                                      - rcols["l_lodes"][base_i])
                  + beta["b2_e002"] * (wcols["l_e002"][i]
                                       - rcols["l_e002"][base_i]))
        service = beta["b3_rvh"] * (math.log(svc * win)
                                    - math.log(svc * head["Lr"][base_i]))
        generator = beta["b4_gen"] * (wcols["gen"][i] - rcols["gen"][base_i])
        scale = beta["b5_len"] * (math.log(win)
                                  - math.log(head["Lr"][base_i]))
        windows.append({
            "window_id": wid, "route_id": rid,
            "w0": asm["W"]["w0"][i], "w1": asm["W"]["w1"][i],
            "window_mi": win,
            "screen_index_p50": boot["p50"][i],
            "screen_index_p10": boot["p10"][i],
            "screen_index_p90": boot["p90"][i],
            "rank": int(rank[i]),
            "rank_ci": [boot["rank_lo"][i], boot["rank_hi"][i]],
            "tie_with_cutoff": bool(boot["tie"][i]),
            "decomposition": {"demand": demand, "service": service,
                              "generator": generator, "scale": scale},
            "overlap_group": groups_head[wid],
            "underservice_gap": gap.get(rid),
            "underservice_flag": flag.get(rid, False),
            "leverage_flag": bool(lev[i]),
            "incumbent_routes": incumbents[i],
        })
    windows.sort(key=lambda w: (sf._route_sort_key(w["route_id"]), w["w0"]))

    # overlap diagnostics (review 2026-07-19): the §3.3 connected components
    # are MEASURED-DEGENERATE on the real universe -- single-linkage
    # transitivity over ~96%-overlapping adjacent windows plus the
    # min-denominator share chains parallel and crossing routes into one
    # county-wide component at the headline threshold (n_groups below; the
    # overlap_lo/overlap_hi sensitivity rows report the band edges). This
    # block carries what gate 1 uses INSTEAD of overlap_group: best window
    # per host shape (spec 01 §3.2 D5) + per-pair shares among those best
    # windows with NO transitive closure.
    n_groups = len(set(groups_head.values()))
    best = {}
    for i, rid in enumerate(asm["W"]["route_id"]):
        if rid not in best or rank[i] < rank[best[rid]]:
            best[rid] = i
    best_rows = sorted(({"route_id": r, "window_id": wids[i],
                         "rank": int(rank[i]),
                         "screen_index_p50": boot["p50"][i]}
                        for r, i in best.items()),
                       key=lambda b: b["rank"])
    pairs = sc.pairwise_shares([b["window_id"] for b in best_rows],
                               tract_sets, thr)
    overlap_diag = {
        "n_windows": len(wids),
        "n_groups": n_groups,
        "single_component": bool(n_groups == 1),
        "note": "connected-component grouping (spec 01 §3.3) is degenerate "
                "at county scale: single-linkage transitivity chains "
                "adjacent and parallel windows into (near-)one component, "
                "so overlap_group CANNOT deduplicate the gate-1 shortlist. "
                "Gate 1 uses best_window_per_shape + the per-pair shares "
                "below (same share rule, NO transitive closure) instead; a "
                "non-chaining regrouping is an owner/spec decision "
                "(README known issue 34)",
        "best_window_per_shape": best_rows,
        "pairwise_share_gt_threshold": [
            {"a": a, "b": b, "share": s} for a, b, s in pairs],
    }

    # Harbor-area with/without-b4 diagnostic (panel D15)
    v_b4off = score(asm, dict(sf.BASE_CFG, b4=False), svc)
    harbor = [{"window_id": wids[i],
               "index_headline": head["index"][i],
               "index_b4_off": v_b4off["index"][i]}
              for i in range(len(wids)) if asm["W"]["route_id"][i] == "43"]
    harbor.sort(key=lambda h: -h["index_headline"])

    flagged_routes = sorted(
        (r for r in head["routes"]
         if asm["fit"]["route_pred"][r]["gen_types"]), key=sf._route_sort_key)
    fit_diag = {
        "estimator": "log-OLS on log(annual boardings), cluster-robust SEs "
                     "by route; NB2 always fitted alongside (nb_estimator "
                     "row) -- no silent fallback (estimator_screen)",
        "coefficients": {n_: {"est": float(b), "se_cluster": float(s)}
                         for n_, b, s in zip(names, pri["params"],
                                             pri["se_cluster"])},
        "b3_label": "allocation control -- not a service response (spec 02 "
                    "owns that question)",
        "vif": sf.vifs(X, names),
        "n_routes": len(head["routes"]),
        "n_route_years": int(len(y)),
        "rows_by_fy": {k: int(v) for k, v in
                       head["df"].groupby("fy").size().items()},
        "dropped_routes": asm["fit"]["dropped"],
        "dropped_route_years": [f"{r} {fy}: {why}" for r, fy, why in
                                asm["fit"]["dropped_years"]],
        "fy2020_handling": "year FE only; the months_observed=9 exposure "
                           "offset was not adopted (the FE absorbs the "
                           "common truncation; drop_fy2020 row is the "
                           "honest handle)",
        "loo_route": {"rho_min": loo["rho_min"],
                      "rho_min_route": loo["rho_min_route"],
                      "rho_floor": val("screen_loo_rho"),
                      "male": loo["male"],
                      "male_ceiling": val("screen_male"),
                      "p90_abs_log_err": loo["p90_abs_err"],
                      "worst5": loo["worst5"]},
        "leave_one_year_out_rho": loy,
        "dfbetas_b4_flagged_routes": sf.gen_dfbetas(
            y, X, names, groups, flagged_routes),
        "harbor_windows_b4": harbor,
        "nb2": nb_info,
        "grouped_decomposition_note": "per-window decomposition is GROUPED "
                                      "(demand b1+b2 / service b3 / "
                                      "generator b4 / scale b5) vs the "
                                      "baseline route -- per-coefficient "
                                      "attribution is arbitrary at these "
                                      "VIFs (spec 01 §3.1)",
        "service_levels": ["standardized (svc_std x length; all published "
                           "scores)",
                           "incumbent-actual (diagnostic: LOO errors + "
                           "underservice gap only)"],
    }

    consumed = [{"id": cid, "role": role, "value": val(cid)}
                for cid, role in CONSUMED]
    consumed.sort(key=lambda c: c["id"])
    bands = {bid: list(band(bid)) for bid in sorted(BAND_CONSUMED)}
    values_hash = nm.network_fingerprint(
        {"consumed": {c["id"]: c["value"] for c in consumed},
         "bands": bands})
    # judgment config consumed outside val()/band(): the generator list
    # (b4). Hashed into the run_id preimage so a list edit mints a new run.
    with open(os.path.join(HERE, "..", "config", "special_generators.json"),
              encoding="utf-8") as f:
        gens_cfg = json.load(f)["generators"]
    universe = {"rule": "all weekday GTFS route shapes with main-shape "
                        "length >= window length; no functional-class "
                        "filter (governance rule 1)",
                "n_weekday_shapes": asm["n_weekday"],
                "n_eligible_shapes": asm["n_eligible"],
                "n_windows": asm["n_windows"],
                "window_mi": win, "step_mi": step}
    run_id = nm.network_fingerprint({
        "schema": SCHEMA, "seed": seed, "n_boot": n_boot,
        "universe": universe, "vintages": VINTAGES,
        "special_generators": gens_cfg,
        "assumptions_values_hash": values_hash})

    artifact = {
        "run_id": run_id, "schema": SCHEMA, "seed": seed, "n_boot": n_boot,
        "universe": universe, "vintages": VINTAGES,
        "disclaimer": DISCLAIMER,
        "assumptions_manifest": {
            "consumed": consumed, "bands": bands,
            "values_hash": values_hash,
            "note": "every registry leaf the screen consumes via val(), "
                    "plus the band() edges the sensitivity rows consume; "
                    "values_hash covers both and enters the run_id preimage "
                    "(sequence_network.py pattern); the run_id preimage "
                    "additionally hashes config/special_generators.json"},
        "windows": windows,
        "overlap_diagnostics": overlap_diag,
        "fit_diagnostics": fit_diag,
        "sensitivity": sens,
        "notes": {
            "index": "screen_index = 100 * exp(window log-prediction at "
                     "standardized service - baseline fitted-route "
                     "log-prediction); baseline = lower-median fitted route "
                     "(deterministic; exact median at odd route count)",
            "zero_handling": "b1/b2 consume catchment sums through log1p "
                             "(log1p(0)=0; indistinguishable from log at "
                             "catchment magnitudes)",
            "tie_with_cutoff": "95% joint bootstrap rank interval straddles "
                               "the rank-5 boundary (gate 1 tie rule in "
                               "bootstrap-rank form, spec 00 §3)",
            "overlap_share": "|A∩B| / min(|A|,|B|) over catchment tract "
                             "sets; strict > threshold; connected "
                             "components; group id = lexicographically "
                             "smallest member window_id",
            "incumbent_routes": "weekday GTFS routes whose full-shape "
                                "catchment shares > screen_overlap_threshold "
                                "of the window's tracts (host included by "
                                "construction)",
            "underservice": "host-route gap: predicted at STANDARDIZED "
                            "service (fy2019 FE) minus actual FY2019, log "
                            "points; flagged beyond the leave-route-out P90 "
                            "absolute log error. CAVEAT (gate-1 memo "
                            "verbatim): the flag conflates unmodeled route "
                            "quality with underservice. Null for unfitted "
                            "host shapes",
            "leverage_flag": "window b1/b2 outside the fitted routes' "
                             "covariate bounding box (out-of-support "
                             "prediction)",
            "sensitivity_pct": "pct = 100 * (1 - Spearman rho of the full "
                               "window ranking vs headline) -- THE stage-1 "
                               "materiality convention (rank churn; no "
                               "ridership headline exists). Baseline and "
                               "variant rankings are POINT-fit rankings; "
                               "the published per-window rank field is "
                               "bootstrap-p50-based and can differ near "
                               "ties",
        },
    }
    return artifact


def main(argv):
    import time
    t0 = time.time()
    artifact = build_artifact()
    out = os.path.join(OUT, "screen_results.json")
    write_artifact(out, artifact)
    print(f"-> {out}  (run_id {artifact['run_id'][:16]})")
    png = os.path.join(OUT, "screen_ranked.png")
    make_chart(artifact, png)
    print(f"-> {png}")
    top = sorted(artifact["windows"], key=lambda w: w["rank"])[:10]
    print("\ntop 10 windows (ordinal index; NOT ridership):")
    for w in top:
        print(f"  #{w['rank']:2d} {w['window_id']:12s} rt {w['route_id']:4s} "
              f"{w['w0']:5.1f}-{w['w1']:5.1f}  p50 {w['screen_index_p50']:7.1f} "
              f"rank_ci [{w['rank_ci'][0]:.0f}, {w['rank_ci'][1]:.0f}] "
              f"grp {w['overlap_group']} "
              f"{'TIE' if w['tie_with_cutoff'] else ''}"
              f"{' UNDER' if w['underservice_flag'] else ''}"
              f"{' LEV' if w['leverage_flag'] else ''}")
    n_under = sum(1 for w in artifact["windows"] if w["underservice_flag"])
    n_tie = sum(1 for w in artifact["windows"] if w["tie_with_cutoff"])
    print(f"\nunderservice-flagged windows: {n_under}; "
          f"tie_with_cutoff: {n_tie}")
    print("\nsensitivity (pct = 100*(1-Spearman rho) vs headline):")
    for r in artifact["sensitivity"]:
        print(f"  {r['id']:20s} {r['pct']:8.3f}  {r['label']}")
    d = artifact["fit_diagnostics"]
    print(f"\nLOO leverage screen: rho_min {d['loo_route']['rho_min']:.4f} "
          f"(floor {d['loo_route']['rho_floor']}) route "
          f"{d['loo_route']['rho_min_route']}; MALE "
          f"{d['loo_route']['male']:.4f} (ceiling {d['loo_route']['male_ceiling']})")
    print(f"runtime {time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
