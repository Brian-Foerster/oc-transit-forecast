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
import csv
import io
import math
import os
import sys
import zipfile

import numpy as np
import pandas as pd

from assumptions import val
from build_corridor import Line
from screen_common import project_points
import screen_common_v21 as sv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
DER = os.path.join(HERE, "..", "data", "derived")
ARCHIVE = os.path.join(HERE, "..", "data", "raw", "gtfs_archive")

# committed-table years (route_boardings.csv) that survive into the extended
# panel; the four new FYs come from route_boardings_ext.csv (§9.9.1).
COMMITTED_FYS = ("fy2017", "fy2019")

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


def _route_sort_key(r):
    return (len(r), r)


def _norm(rid):
    """Case-normalized APC<->GTFS join key (spec 01 §9.9.7)."""
    return str(rid).strip().lower()


# ---------------------------------------------------------------------------
# fast per-shape projection (drop-in for ScreenDataV21.proj / ShapeProjV21)
# ---------------------------------------------------------------------------
# widest buffer any run uses is band("buffer_mi")[1] = 1.25; a block whose
# INTERNAL POINT lies outside the shape bbox expanded by MAXBUF cannot be
# within MAXBUF of any point ON the shape, so it is never in-buffer for any
# buffer <= MAXBUF and its exact offset is irrelevant. Projecting only the
# in-bbox blocks (a few thousand vs 26,734) is therefore an EXACT speedup:
# for every block that CAN enter a catchment the offset/position are the same
# vectorized project_points values ShapeProjV21 would compute.
MAXBUF = 1.30


class FastProjV22:
    """Same interface as screen_common_v21.ShapeProjV21 (route_id, line, L,
    b_off, b_pos, g_off, g_pos, g_types) -- buffer-independent -- but projects
    only blocks inside the shape bbox+MAXBUF; far blocks carry b_off = inf
    (never in catchment). compute_predictors_v21 / ScreenDataV21.view read
    only these attributes, so the result is byte-identical to the full
    projection at any buffer <= MAXBUF. IDENTICAL to screen_fit_v21.FastProjV21."""

    def __init__(self, route_id, x, y, block_xy, gen_xy, gen_types):
        self.route_id = str(route_id)
        self.line = Line(np.asarray(x, float), np.asarray(y, float))
        self.L = float(self.line.L)
        bx, by = np.asarray(block_xy[0], float), np.asarray(block_xy[1], float)
        near = ((bx >= self.line.x.min() - MAXBUF)
                & (bx <= self.line.x.max() + MAXBUF)
                & (by >= self.line.y.min() - MAXBUF)
                & (by <= self.line.y.max() + MAXBUF))
        self.b_off = np.full(len(bx), np.inf)
        self.b_pos = np.zeros(len(bx))
        if near.any():
            off, pos = project_points(self.line, bx[near], by[near])
            self.b_off[near] = off
            self.b_pos[near] = pos
        self.g_off, self.g_pos = project_points(self.line, *gen_xy)
        self.g_types = list(gen_types)


def fast_proj(data, route_id, x, y):
    """Build a FastProjV22 against a loaded ScreenDataV21's block/generator
    geometry (drop-in for data.proj)."""
    return FastProjV22(route_id, x, y, (data.bx, data.by),
                       (data.gx, data.gy), data.gtypes)


# ---------------------------------------------------------------------------
# archived GTFS feeds (§9.4) -- one contemporaneous feed per boardings year
# ---------------------------------------------------------------------------
ARCHIVE_FEEDS = {
    "fy2017": "octa_gtfs_fy2017_20170201.zip",
    "fy2019": "octa_gtfs_fy2019_20190208.zip",
    "fy2020": "octa_gtfs_fy2020_20200129.zip",
    "fy2021": "octa_gtfs_fy2021_20210217.zip",
    "fy2022": "octa_gtfs_fy2022_20211224.zip",
    "fy2023": "octa_gtfs_fy2023_20230210.zip",
}


def _read_zip_csv(zf, name):
    """Read a GTFS member as a DataFrame (utf-8-sig handles the BOM + quotes;
    dtype=str, columns stripped of stray quotes/whitespace)."""
    raw = zf.read(name).decode("utf-8-sig")
    df = pd.read_csv(io.StringIO(raw), dtype=str)
    df.columns = [c.strip().strip('"') for c in df.columns]
    return df


class ArchivedFeed:
    """One archived OCTA feed: weekday services + short_name->longest-weekday
    shape (mi frame). Mirrors build_corridor.main_shape_xy (monday==1 service,
    longest shape) generalized to the case-normalized route_short_name join,
    so the fy2023 '<short>_merged_<id>' route_ids and the express 53x/57x/64x
    all resolve. Longest-shape heuristic is the documented v2.0 behavior.
    IDENTICAL to screen_fit_v21.ArchivedFeed (fit universe unchanged, §10 D8)."""

    def __init__(self, path):
        zf = zipfile.ZipFile(path)
        routes = _read_zip_csv(zf, "routes.txt")
        trips = _read_zip_csv(zf, "trips.txt")
        cal = _read_zip_csv(zf, "calendar.txt")
        shapes = _read_zip_csv(zf, "shapes.txt")
        zf.close()
        wk = set(cal[cal["monday"] == "1"]["service_id"])
        # route_id -> case-normalized short_name
        rid_short = {r["route_id"]: _norm(r["route_short_name"])
                     for _, r in routes.iterrows()}
        # weekday trips only, tagged with their short_name
        t = trips[trips["service_id"].isin(wk)].copy()
        t["short"] = t["route_id"].map(rid_short)
        # shape geometry (sorted), precomputed length in mi frame
        shapes = shapes.copy()
        shapes["seq"] = shapes["shape_pt_sequence"].astype(int)
        self._shape_xy = {}
        for sid, g in shapes.groupby("shape_id"):
            g = g.sort_values("seq")
            x = g["shape_pt_lon"].to_numpy(float) * sv.MI_LON
            y = g["shape_pt_lat"].to_numpy(float) * sv.MI_LAT
            self._shape_xy[sid] = (x, y,
                                   float(np.sum(np.hypot(np.diff(x),
                                                         np.diff(y)))))
        # short_name -> list of weekday shape_ids
        self._short_shapes = {}
        for _, r in t.iterrows():
            sid = r.get("shape_id")
            if pd.isna(sid) or sid == "" or sid not in self._shape_xy:
                continue
            self._short_shapes.setdefault(r["short"], set()).add(sid)

    def main_shape(self, apc_route):
        """Longest weekday shape for the APC route (matched by case-normalized
        route_short_name). Returns ((x, y), L) or (None, -1) when the route has
        NO contemporaneous weekday shape in this feed (the §9.3 shapeless-route
        drop applies)."""
        key = _norm(apc_route)
        sids = self._short_shapes.get(key)
        if not sids:
            return None, -1.0
        best, bl = None, -1.0
        for sid in sids:
            x, y, L = self._shape_xy[sid]
            if L > bl:
                best, bl = (x, y), L
        return best, bl


# ---------------------------------------------------------------------------
# per-CNS block arrays (genjobs_leave_class_out needs per-NAICS-sector sums;
# ScreenDataV21 only carries the CNS15-18 total, so the fit layer loads the
# sector columns itself -- keeps screen_common_v21 frozen under its no-fit hold)
# ---------------------------------------------------------------------------
def load_cns_by_block(data, vintages):
    """{vintage: {CNS col: per-block array aligned to data.geoids}}."""
    naics = val("gen_jobs_naics")
    gidx = {g: i for i, g in enumerate(data.geoids)}
    out = {}
    for v in vintages:
        cols = {c: np.zeros(len(data.geoids)) for c in naics}
        with open(os.path.join(DER, f"oc_block_wac_{v}.csv"),
                  encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                i = gidx[r["GEOID20"]]
                for c in naics:
                    cols[c][i] = float(r[c]) if r[c] not in ("", ".") else 0.0
        out[v] = cols
    return out


# ---------------------------------------------------------------------------
# boardings panel (route_boardings.csv committed years UNION the ext table)
# ---------------------------------------------------------------------------
def load_panel():
    """Long-format fit panel rows {route, fy, boardings, rvh} for the frozen
    6-FY set screen_panel_ext_fys, from route_boardings.csv (fy2017/fy2019)
    UNION route_boardings_ext.csv (fy2020/fy2021/fy2022/fy2023). fy2020q3 is
    SUPERSEDED and never enters. fittable requires boardings present AND
    validated RVH present; non-fittable rows are returned tagged so the caller
    prints them (the 3 KNOWN_BAD_RVH fy2017 rows, the 560/fy2022
    KNOWN_DUP_RVH_EXT blank). IDENTICAL to screen_fit_v21.load_panel (§10 D8:
    same universe -- RVH is still REQUIRED on every kept row, now as the DV
    denominator rather than the b3 predictor)."""
    fys_ext = tuple(val("screen_panel_ext_fys"))
    rows, unfittable = [], []
    rb = pd.read_csv(os.path.join(DER, "route_boardings.csv"),
                     dtype={"route": str})
    for _, rr in rb.iterrows():
        for fy in COMMITTED_FYS:
            b, rvh = rr[fy], rr["rvh_" + fy]
            if pd.isna(b):
                continue
            if pd.isna(rvh):
                unfittable.append((str(rr["route"]), fy, "no validated RVH"))
                continue
            rows.append({"route": str(rr["route"]), "fy": fy,
                         "boardings": float(b), "rvh": float(rvh)})
    re_ = pd.read_csv(os.path.join(DER, "route_boardings_ext.csv"),
                      dtype={"route": str})
    bad = sorted(set(re_["fy"]) - set(fys_ext))
    if bad:
        raise ValueError(f"route_boardings_ext.csv carries FY labels outside "
                         f"the frozen §9.9.1 set: {bad}")
    for _, rr in re_.iterrows():
        fy = str(rr["fy"])
        if pd.isna(rr["boardings"]):
            continue
        if pd.isna(rr["rvh"]):
            unfittable.append((str(rr["route"]), fy, "no validated RVH"))
            continue
        rows.append({"route": str(rr["route"]), "fy": fy,
                     "boardings": float(rr["boardings"]),
                     "rvh": float(rr["rvh"])})
    return rows, unfittable


# ---------------------------------------------------------------------------
# fit-side predictor extraction (archived-shape catchments, vintage-matched X)
# ---------------------------------------------------------------------------
def build_fit_projs(data, quiet=False):
    """The EXPENSIVE step, done ONCE: a FastProjV22 per fittable (route, fy) on
    that FY's contemporaneous archived shape (buffer-independent, so the whole
    battery -- including buffer_lo/buffer_hi -- reuses it). Returns
    {proj_cache: {(route, fy): FastProjV22 | None}, dropped_shapeless: [...],
     dropped_norvh: [...], feeds: {fy: ArchivedFeed}}. None = the route has no
     contemporaneous weekday shape in that FY's feed (§9.3 shapeless drop).
     IDENTICAL to screen_fit_v21.build_fit_projs."""
    panel, unfittable = load_panel()
    feeds = {fy: ArchivedFeed(os.path.join(ARCHIVE, fn))
             for fy, fn in ARCHIVE_FEEDS.items()}
    proj_cache, dropped_shapeless, seen = {}, [], set()
    for rec in panel:
        r, fy = rec["route"], rec["fy"]
        key = (r, fy)
        if key in seen:
            continue
        seen.add(key)
        res, L = feeds[fy].main_shape(r)
        if res is None:
            proj_cache[key] = None
            dropped_shapeless.append((r, fy))
        else:
            proj_cache[key] = fast_proj(data, f"{r}@{fy}", res[0], res[1])
    return {"proj_cache": proj_cache, "dropped_shapeless": dropped_shapeless,
            "dropped_norvh": unfittable, "feeds": feeds}


def build_fit_rows(data, cns_by_block, buffer_mi, projs=None, quiet=False):
    """One raw-sum row per FITTABLE route-year whose route has a contemporaneous
    archived-feed weekday shape. Each row's catchment is built on that FY's
    archived shape at that FY's vintage (§9.3/§9.9.2). `projs` is a
    build_fit_projs() result (built once and reused across buffer variants);
    when None it is built here. Returns {rows: DataFrame,
    dropped_shapeless: [...], dropped_norvh: [...], feeds: {fy: ArchivedFeed}}.
    Shapeless route-years drop (§9.3): the pre-registered set is 3 FY2017
    Express + 529/fy2022 = 4. IDENTICAL to screen_fit_v21.build_fit_rows (fit
    universe unchanged, §10 D8)."""
    if projs is None:
        projs = build_fit_projs(data, quiet=quiet)
    proj_cache = projs["proj_cache"]
    panel, _unfittable = load_panel()
    rows = []
    for rec in panel:
        r, fy = rec["route"], rec["fy"]
        proj = proj_cache.get((r, fy))
        if proj is None:
            continue
        p = sv.compute_predictors_v21(data, proj, 0.0, proj.L, fy,
                                      rvh=rec["rvh"], buffer_mi=buffer_mi)
        vin = p["vintage"]
        bidx = p["block_idx"]
        cns = {c: float(cns_by_block[vin["wac"]][c][bidx].sum())
               for c in val("gen_jobs_naics")}
        rows.append({
            "route": r, "fy": fy,
            "boardings": rec["boardings"], "rvh": rec["rvh"],
            "log_b": math.log(rec["boardings"]),
            "L": proj.L,
            "flows": p["flows"], "zveh": p["zveh_hh"],
            "e002": p["e002"], "e016": p["e016"], "popden": p["popden"],
            "genjobs": p["genjobs"], "gen_dummy": p["gen_dummy"],
            **{f"cns_{c}": cns[c] for c in cns},
        })
    df = pd.DataFrame(rows).sort_values(
        ["route", "fy"], key=lambda s: (s.map(_route_sort_key)
                                        if s.name == "route" else s)
    ).reset_index(drop=True)
    return {"rows": df, "dropped_shapeless": projs["dropped_shapeless"],
            "dropped_norvh": projs["dropped_norvh"], "feeds": projs["feeds"]}


# ---------------------------------------------------------------------------
# design matrices (§10 D1/D2: PRODUCTIVITY DV, b3 gone from the RHS)
# ---------------------------------------------------------------------------
def _fys_in(cfg):
    """Fit-panel FY set for a config (base year first)."""
    fys = list(val("screen_panel_ext_fys"))
    if cfg["panel"] == "pre2020":
        fys = [f for f in fys if f in ("fy2017", "fy2019")]
    if cfg["drop_fy2020"]:
        fys = [f for f in fys if f != "fy2020"]
    return fys


def _b1name(cfg):
    return "b1_popden" if cfg["b1"] == "popden" else "b1_flows"


def _b2name(cfg):
    return {"zveh": "b2_zveh", "e002": "b2_e002",
            "e016": "b2_e016"}[cfg["b2"]]


def _b4name(cfg):
    return "b4_gendummy" if cfg["b4"] == "dummy" else "b4_genjobs"


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


def _col_b1(df, cfg):
    return np.log1p(df["popden"].to_numpy(float) if cfg["b1"] == "popden"
                    else df["flows"].to_numpy(float))


def _col_b2(df, cfg):
    return np.log1p(df[{"zveh": "zveh", "e002": "e002",
                        "e016": "e016"}[cfg["b2"]]].to_numpy(float))


def _col_b4(df, cfg):
    if cfg["b4"] == "dummy":
        return df["gen_dummy"].to_numpy(float)
    gj = df["genjobs"].to_numpy(float)
    if cfg["b4_ex_cns"] is not None:
        gj = gj - df["cns_" + cfg["b4_ex_cns"]].to_numpy(float)
    return np.log1p(np.clip(gj, 0.0, None))


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


def ols_beta(y, X):
    """Deterministic least-squares point fit (min-norm on degenerate
    resamples) -- used by variants, LOO and the bootstrap."""
    return np.linalg.lstsq(X, y, rcond=None)[0]


def fit_primary(y, X, names, groups):
    """log-OLS with cluster-robust-by-route SEs (spec 01 §3.1)."""
    import statsmodels.api as sm
    res = sm.OLS(y, X).fit(cov_type="cluster",
                           cov_kwds={"groups": pd.Categorical(groups).codes})
    return {"params": np.asarray(res.params),
            "se_cluster": np.asarray(res.bse), "names": names,
            "n": int(res.nobs), "res": res}


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


def vifs(X, names):
    """VIF per non-intercept column (required diagnostic)."""
    out = {}
    for j, name in enumerate(names):
        if name == "const":
            continue
        others = [k for k in range(X.shape[1]) if k != j]
        beta = ols_beta(X[:, j], X[:, others])
        resid = X[:, j] - X[:, others] @ beta
        v = X[:, j] - X[:, j].mean()
        ss_tot = float(v @ v)
        r2 = 1.0 - float(resid @ resid) / ss_tot if ss_tot > 0 else 0.0
        out[name] = float(1.0 / max(1.0 - r2, 1e-12))
    return out


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
