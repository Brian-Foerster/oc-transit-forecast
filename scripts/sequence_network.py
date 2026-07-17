"""
sequence_network.py -- the spec 07 network-sequencing HARNESS (work item N1b).

A greedy portfolio harness that sits ABOVE the ridership pipeline, replacing
nothing in it (spec 07 §1). Each cycle: candidate ALM lines are evaluated
against the network built so far, one is committed by the §3 selection rule,
and the loop repeats -- producing a build ORDER and a portfolio frontier as the
planning layer's primary output, while claiming nothing it cannot deliver.

This module is the harness half of the N1 skeleton; the model-side mechanics
(the `persistent` flag, `run(anchor_add=)`, the networked rebuild, and the pure
geometry / canonical serialization) are N1a -- scripts/network_mechanics.py +
the model.py / build_corridor.py extensions this imports. The harness is
READ-ONLY over the model: it never mutates a committed config or derived file
(networked rebuilds route to the gitignored run dir, spec 07 §4.2.4), so the
full pipeline reruns byte-identically (gate G7).

INTERIM OBJECTIVE (available now; the full-NPV objective is N5, gated on
R1 -> R6 -> W1). Ranking is by Delta(welfare-minutes) LEVEL -- the spec 06 B1
exact-logsum accumulators (um_infra + um_margin, person-scaled), D8-blended at
the exported per-draw ws/kappa. Delta-K is shown beside it as the spec 04
LOW | US-TYPICAL band pair (capcost.py, N2), and the welfare-per-dollar RATIO
is a DISPLAY column only -- the interim layer cannot do timing economics and
never quotes itself as BCA output. Every welfare quantity is aggregated
WITHIN-DRAW under common random numbers (spec 07 §3).

    python scripts/sequence_network.py [--cycles K] [--budget $M] [--n N]
        [--seed S] [--scenario fold|retain] [--out PATH] [--quiet]

Writes outputs/network_sequence.json -- committed, regenerable byte-identically
from committed configs + seed (gate G6: no timestamps, sorted lists, canonical
floats, run id = sha256 of the config-set + seed).
"""
import argparse
import copy
import json
import math
import os
import sys

import numpy as np
import pandas as pd

import build_corridor as bc
import capcost
import network_mechanics as nm
from assumptions import val, band
from backtest_543 import backtest_corridor
from model import Corridor, run, draw_params, pct, wpct, N
from reweight_abc import abc_weights, central_label

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
CFG = os.path.join(ROOT, "config")
DER = os.path.join(ROOT, "data", "derived")
OUT = os.path.join(ROOT, "outputs")

SEED = val("seed")
BUFFER_MI = val("buffer_mi")
MI_LAT = val("mi_lat")
MI_LON = val("mi_per_deg_lon") * math.cos(math.radians(val("oc_ref_lat")))

# spec 07 §6.2 dependency predicate threshold: a candidate DEPENDS on committed
# line H when omega(H, candidate) > this, OR co-located persistent injection, OR
# a feeder/transfer edge in the rebuilt inputs. Without the threshold the depth
# rule degenerates to a flat cycle count (spec 07 §6.2). 0.01 is the spec's
# stated value.
DEP_OMEGA = 0.01

# spec 07 §3 / G4 knife-edge tolerance, on the per-draw WIN PROBABILITY. In the
# INTERIM objective delta = 1 (welfare-minutes are a level, never discounted), so
# under a SLACK budget every candidate's CV = own + best continuation approaches
# the SAME portfolio total (the interchange argument: without timing economics,
# build order is welfare-neutral). When P(top beats runner-up on CV) lands in
# [0.5 - tol, 0.5 + tol] the order is a genuine coin-flip; the §3 interim
# directive 'ranking is by Delta-minutes LEVEL' is the deterministic tie-break
# (own Delta-wm level, robust across seeds -> gate G4 rank stability), and the
# pair is reported as P ~ 0.5, not a defect (G4). A thin P50 gap with a decisive
# P(beats) is NOT a knife-edge -- correlated CRN draws make it a stable rank.
KNIFE_EDGE_TOL = 0.05
DEPTH_CAP = val("depth_cap")            # spec 07 §6.2 (constant-tier, band 1/3)
CYCLE_GAP = val("cycle_gap")            # spec 07 §11 Q1 (constant-tier, band 4/8)
BUDGET_REF = val("network_budget")      # spec 07 §7 / Q2 (constant-tier, band lo/hi)
EQ_DAYS = sum(val("eq_days")) / 2.0     # weekday<->annual midpoint (fold_sub units)

# Interim capital-PV DISPLAY discount (spec 07 §3: capital is discounted to the
# common base year; a line committed at cycle k opens later, so its Delta-K_PV
# declines). The REAL discount rate is a BCA-wrapper property (federal BCA 2026:
# 7% real), NOT an OC-registry leaf -- the registry owns ridership-model
# quantities, the wrapper owns prices and discounting (spec 06 §2). It is a
# DISPLAY-ONLY factor here: interim ranking is by welfare-minutes LEVEL and is
# never discounted (the interim layer cannot do timing economics); only the
# Delta-K_PV column and the ratio column carry it, so the number is cited, not
# owned. N5's NPV mode consumes the wrapper's own rate.
DISPLAY_DISCOUNT = 0.07

# canonical artifact float precision (gate G6). The computation is deterministic
# given the seed, so full precision already reproduces; rounding to a fixed
# decimal count additionally guards against any last-ULP platform drift and
# keeps the committed JSON readable. Applied to every float before the dump.
CANON_DECIMALS = 6


# ---------------------------------------------------------------------------
# GTFS cache (loaded at most once -- the only slow, shared read)
# ---------------------------------------------------------------------------
class _Gtfs:
    """Lazily load the GTFS tables build_corridor needs for alignment shapes /
    fold-route geometry, and cache them so a multi-cycle run reads them once."""
    def __init__(self):
        self._t = None

    def tables(self):
        if self._t is None:
            self._t = bc.load_gtfs()      # (trips, shapes, st, wk)
        return self._t


# ---------------------------------------------------------------------------
# geometry / candidate loading
# ---------------------------------------------------------------------------
def _alignment_xy(cfg, gtfs):
    """Alignment (x, y) in the mi-scaled frame for a candidate config, from
    either an explicit corridor_waypoints polyline (streetcar's PE-ROW) or a
    GTFS corridor_route shape (harbor's 543) -- the two sources build_corridor
    already reads (spec 07 §4.2.1: 'the alignment sources exist')."""
    if cfg.get("corridor_waypoints"):
        wp = np.array(cfg["corridor_waypoints"], float)
        return wp[:, 1] * MI_LON, wp[:, 0] * MI_LAT
    trips, shapes, _st, wk = gtfs.tables()
    (x, y), _L = bc.main_shape_xy(trips, shapes, wk, cfg["corridor_route"])
    return x, y


def _tract_table():
    """OC tract centroids (mi-scaled) + total-worker mass (B08141_E001), read
    once. Returns a DataFrame with columns cx, cy, workers."""
    tr = pd.read_csv(os.path.join(DER, "oc_tracts.csv"), dtype={"GEOID": str})
    acs = pd.read_csv(os.path.join(DER, "oc_b08141.csv"), dtype={"GEOID": str})
    wmap = dict(zip(acs["GEOID"], acs["B08141_E001"].astype(float)))
    tr["workers"] = tr["GEOID"].map(wmap).fillna(0.0)
    tr["cx"] = tr["lon"].to_numpy() * MI_LON
    tr["cy"] = tr["lat"].to_numpy() * MI_LAT
    return tr


def _corridor_workers(x, y, window, tracts):
    """Corridor-tract worker points + mass for a committed line H (spec 07 §4.2:
    'boardings allocated along H proportional to corridor-tract worker mass').
    Projects every OC tract onto H's WINDOWED alignment, keeps those whose
    centroid is within the 0.9-mi buffer AND the committed window, and returns
    (pts (k,2), mass (k,)) in the mi-scaled frame. Feeds omega()'s worker_pts /
    worker_mass so the declared default is REAL, not the silent uniform fallback
    (N1a reviewer wiring note 1)."""
    line = bc.Line(np.asarray(x, float), np.asarray(y, float))
    w0, w1 = window
    off = np.empty(len(tracts)); pos = np.empty(len(tracts))
    cx = tracts["cx"].to_numpy(); cy = tracts["cy"].to_numpy()
    for i in range(len(tracts)):
        off[i], pos[i] = line.project(cx[i], cy[i])
    keep = (np.abs(off) <= BUFFER_MI) & (pos >= w0) & (pos <= w1)
    pts = np.column_stack([cx[keep], cy[keep]])
    mass = tracts["workers"].to_numpy()[keep]
    return pts, mass


def load_candidates(path, gtfs, tracts):
    """Read config/candidates.json and materialize each candidate: config dict,
    committed derived-file path, WINDOWED alignment, stop spacing, peak headway,
    derived capital dimensions (route_mi / stations / cars), fold route lists,
    and the omega worker-mass allocation (as line H)."""
    doc = json.load(open(path, encoding="utf-8"))
    cands = []
    for c in doc["candidates"]:
        cfg = json.load(open(os.path.join(ROOT, c["config"]), encoding="utf-8"))
        x, y = _alignment_xy(cfg, gtfs)
        full_len = nm.polyline_length(x, y)
        win = cfg.get("window_mi") or [0.0, full_len]
        w0 = 0.0 if win[0] is None else float(win[0])
        w1 = full_len if win[1] is None else float(win[1])
        # windowed shape -- the committed extent (N1a reviewer wiring note 2):
        # omega() and the feeder injection both see the truncated polyline.
        wx, wy = nm.truncate_polyline(x, y, w0, w1)
        route_mi = nm.polyline_length(wx, wy)
        sn = cfg["service_new"]
        spacing = float(sn["spacing"])
        hw = sn["headway"]
        hpk = float(hw["peak"] if isinstance(hw, dict) else hw)
        stations = int(round(route_mi / spacing)) + 1
        cars = capcost.fleet(route_mi, hpk)
        wp, wm = _corridor_workers(wx, wy, [w0, w1], tracts)
        removed = cfg.get("bca", {}).get("routes_removed", {"fold": [], "retain": []})
        cands.append({
            "id": c["id"],
            "cfg": cfg,
            "config_path": os.path.join(ROOT, c["config"]),
            "derived_path": os.path.join(DER, f"corridor_{c['id']}.json"),
            "x": wx, "y": wy, "window": [w0, w1],
            "spacing": spacing, "headway": hw, "headway_peak": hpk,
            "route_mi": route_mi, "stations": stations, "cars": cars,
            "worker_pts": wp, "worker_mass": wm,
            "folds": {s: list(removed.get(s, [])) for s in ("fold", "retain")},
        })
    return cands, bool(doc.get("hand_supplied")), doc.get("substitution_note", "")


# ---------------------------------------------------------------------------
# capital (spec 04 rate card via capcost.py, N2) + the cycle_gap PV display
# ---------------------------------------------------------------------------
def capital_bands(cand, fixed_cost_share=1.0):
    """LOW | US-TYPICAL Delta-K ($M) for a candidate (never the low number
    alone, spec 04 §3.2)."""
    return capcost.capital_bands(cand["route_mi"], cand["stations"],
                                 cand["cars"], fixed_cost_share=fixed_cost_share)


def pv_factor(cycle_index, cycle_gap=CYCLE_GAP, rate=DISPLAY_DISCOUNT):
    """Capital-PV display discount for a line committed at cycle k (0-based
    cycle_index): opens (k)*cycle_gap years later, so Delta-K_PV = Delta-K /
    (1+rate)^(k*cycle_gap). cycle 0 -> factor 1.0 (spec 07 §3). Interim DISPLAY
    only -- welfare-minutes are never discounted."""
    return 1.0 / (1.0 + rate) ** (cycle_index * cycle_gap)


# ---------------------------------------------------------------------------
# the interim objective: D8-blended welfare-minutes, per draw, within-draw
# ---------------------------------------------------------------------------
def welfare_minutes(res, scen):
    """Delta(welfare-minutes) per draw for one scenario (spec 07 §3 interim
    objective): the B1 exact-logsum accumulators um_infra + um_margin
    (equivalent-IVT min/wd, person-scaled), D8-blended at the exported per-draw
    ws/kappa. The blend factor m = ws + (1-ws)*kappa is the benefit-magnitude
    analog of the ridership ratio blend ws*r + (1-ws)*(1 + kappa*(r_nw-1)) with
    the deviation measured from 0 (a benefit) rather than 1 (a ratio); under
    D8's b_nw = b_work deferral it is a COMMON per-draw scalar, so it cancels
    EXACTLY in within-draw ranking and only sets the displayed LEVEL."""
    d = res["uncapped"][scen]
    p = res["params"]
    m = p["ws"] + (1.0 - p["ws"]) * p["kappa"]
    return m * (d["um_infra"] + d["um_margin"])


def _bands(x, weights=None):
    """[P10, P50, P90] of a per-draw array, weighted if weights given."""
    if weights is None:
        return [pct(x, q) for q in (10, 50, 90)]
    return [wpct(x, weights, q) for q in (10, 50, 90)]


# ---------------------------------------------------------------------------
# per-draw anchor chaining (spec 07 §4.2) + the dependency predicate (§6.2)
# ---------------------------------------------------------------------------
def _fold_route_geometry(routes, gtfs):
    """(x, y, weekday_boardings) for each folded route: GTFS shape + fy2019
    route boardings / eq_days (weekday units, matching the anchor). A route with
    no shape or no boardings row is skipped."""
    trips, shapes, _st, wk = gtfs.tables()
    rb = pd.read_csv(os.path.join(DER, "route_boardings.csv"), dtype={"route": str})
    bmap = dict(zip(rb["route"], rb["fy2019"]))
    out = []
    for rid in routes:
        res, _L = bc.main_shape_xy(trips, shapes, wk, str(rid))
        b = bmap.get(str(rid))
        if res is None or b is None or not np.isfinite(b):
            continue
        out.append({"x": res[0], "y": res[1],
                    "boardings": float(b) / EQ_DAYS})
    return out


def dependency(H, B, gtfs, allocation=None):
    """The spec 07 §6.2 predicate pieces for candidate B against committed line
    H: omega(H,B), the fold_sub ghost term, and the co-location flag. B DEPENDS
    on H when omega > DEP_OMEGA OR co-located OR (a feeder edge appears once H is
    injected). Returns a dict of the pieces; the caller decides injection and
    depth. omega uses H's WINDOWED shape + worker-mass allocation (wiring notes
    1 & 2)."""
    om = nm.omega(H["x"], H["y"], B["x"], B["y"], H["spacing"],
                  worker_pts=H["worker_pts"], worker_mass=H["worker_mass"],
                  buffer_mi=BUFFER_MI, B_window=B["window"], allocation=allocation)
    # fold_sub (the §4.2 'ghosts' term) removes folded routes' MEASURED boardings
    # that were inside B's anchor -- the double-count guard rests on "H's diverted
    # riders are already inside anchor_B_MEASURED wherever the routes they came
    # from cross B's buffer". A folded route contributes to that measured anchor
    # ONLY if it is part of B's own corridor composition (its corridor_route /
    # excluded_feeders -- the routes whose boardings the anchor is built from);
    # a route that merely CROSSES B enters via the transfer market (tau), not the
    # anchor, so subtracting it would over-remove riders that were never in the
    # anchor (and flip G3's sign). Screen the folded set to B's anchor routes.
    anchor_routes = set(str(r) for r in B["cfg"].get("excluded_feeders", []))
    if B["cfg"].get("corridor_route"):
        anchor_routes.add(str(B["cfg"]["corridor_route"]))
    folded_ids = [r for r in H["folds"][H["scenario"]] if str(r) in anchor_routes]
    folded = _fold_route_geometry(folded_ids, gtfs)
    fs = nm.fold_sub(folded, B["x"], B["y"], buffer_mi=BUFFER_MI,
                     B_window=B["window"]) if folded else 0.0
    return {"omega": float(om), "fold_sub": float(fs),
            "fold_sub_routes": sorted(str(r) for r in folded_ids),
            "co_located": False,                 # crossing candidates, not parallel
            "depends": bool(om > DEP_OMEGA)}


def build_anchor_add(B, network_before, gtfs, params, seed, n, allocation=None,
                     omega_scale=1.0):
    """Per-draw anchor adjustment for candidate B against every committed line H
    in the network-before (spec 07 §4.2):

        anchor_add = sum_H  omega(H,B)*margin_H(draw) - fold_sub(H,B)

    margin_H = total_H - anchor_H (H's committed-scenario per-draw MARGIN, both
    from H's own cached run under the SAME CRN -- never gross newline). Returns
    (anchor_add (n,) or None, injected_lines, excluded_fold, dep_records). The
    unconditional feeder injection is SCREENED by the dependency predicate
    (wiring note 3): H is injected only where B depends on H. omega_scale is the
    §8i / §10 G7 sensitivity multiplier (omega x {0.5, 1.5})."""
    add = np.zeros(n)
    injected, excluded, deps = [], [], []
    any_dep = False
    for H in network_before:
        dep = dependency(H, B, gtfs, allocation=allocation)
        om = dep["omega"] * omega_scale
        margin = H["margin"]                     # (n,) total_H - anchor_H
        add = add + om * margin - dep["fold_sub"]
        dep = dict(dep, omega_effective=om,
                   depends=bool(om > DEP_OMEGA or dep["co_located"]))
        deps.append({"H": H["id"], **dep})
        if dep["depends"]:
            any_dep = True
            injected.append({
                "route": f"committed_{H['id']}",
                "corridor_route": H["cfg"].get("corridor_route"),
                "corridor_waypoints": H["cfg"].get("corridor_waypoints"),
                "window_mi": H["window"],
                "headway": H["headway"]})
            excluded += H["folds"][H["scenario"]]
    if not any_dep and not np.any(add):
        return None, [], [], deps                # empty-network / inert path
    return add, injected, sorted(set(excluded)), deps


# ---------------------------------------------------------------------------
# evaluation: one corridor rebuild (if networked) + one run() under CRN
# ---------------------------------------------------------------------------
def evaluate(B, network_before, params, seed, weights, gtfs, tracts, n,
             run_dir, allocation=None, omega_scale=1.0):
    """Evaluate candidate B against the network-before under common random
    numbers. Returns a record with per-scenario welfare-minute arrays (fold and
    retain), total/newline/ratio per draw, the ABC-weighted bands, provenance
    depth inputs, and the run's raw res (so a committed line can cache its own
    margin). Empty network-before -> the committed derived FILE verbatim +
    anchor_add=None (gate G1 byte-identity by construction)."""
    add, injected, excluded, deps = build_anchor_add(
        B, network_before, gtfs, params, seed, n,
        allocation=allocation, omega_scale=omega_scale)

    if injected or excluded:
        # networked rebuild -> gitignored run dir (never the committed file)
        desc = {"candidate": B["id"],
                "injected": nm.sorted_set_list(i["route"] for i in injected),
                "excluded": nm.sorted_set_list(excluded)}
        fp = nm.network_fingerprint(desc)[:16]
        dest = bc.networked_path(B["id"], fp)
        bc.main(B["config_path"], dest=dest, injected_lines=injected,
                excluded_fold_routes=excluded)
        cor = Corridor(dest)
    else:
        cor = Corridor(B["derived_path"])

    res = run(cor, n=n, params=params, seed=seed, anchor_add=add)

    rec = {"id": B["id"], "res": res, "anchor_add": add,
           "injected": [i["route"] for i in injected], "excluded": excluded,
           "deps": deps, "depth": eval_depth(deps, network_before),
           "scenarios": {}}
    for scen in ("fold", "retain"):
        d = res["uncapped"][scen]
        wm = welfare_minutes(res, scen)
        rec["scenarios"][scen] = {
            "wm": wm,                                   # (n,) D8-blended welfare min
            "total": d["total"], "newline": d["newline"],
            "wm_uncapped": _bands(wm),
            "wm_abc": _bands(wm, weights),
            "newline_uncapped": _bands(d["newline"]),
            "newline_abc": _bands(d["newline"], weights)}
    return rec


# ---------------------------------------------------------------------------
# provenance DAG depth (spec 07 §6.2)
# ---------------------------------------------------------------------------
def eval_depth(deps, network_before):
    """depth(candidate evaluation) = 1 + max{ depth(H) : H in network-before AND
    the candidate DEPENDS on H } (max over the empty set = 0). A committed line
    inherits its evaluation's depth. Depth > DEPTH_CAP -> EXPLORATORY."""
    depth_of = {H["id"]: H["depth"] for H in network_before}
    dep_depths = [depth_of[d["H"]] for d in deps if d["depends"]]
    return 1 + (max(dep_depths) if dep_depths else 0)


# ---------------------------------------------------------------------------
# the §3 selection rule (k=2 lookahead) and its interaction-matrix audit (§5)
# ---------------------------------------------------------------------------
def cv_components(cand_id, singles, continuations, scen, feasible_ids,
                  delta=1.0):
    """CV(A) per draw (spec 07 §3, stated exactly):

        CV(A) = Delta-wm(A|N) + max( 0, max_{B != A feasible} delta*Delta-wm(B|N+A) )

    delta is the one-cycle_gap discount shift; in the INTERIM objective the
    layer cannot do timing economics, so delta = 1 (welfare-minutes are a level,
    never discounted) and cycle_gap enters only the Delta-K_PV display. The best
    single competes through its own best continuation, so there is no
    best-single-vs-best-pair ambiguity. Returns (cv (n,), own (n,), continuation
    (n,), best_B or None)."""
    own = singles[cand_id][scen]["wm"]
    best_cont = np.zeros_like(own)                  # the max(0, .) null continuation
    best_B, b_p50 = None, -np.inf
    for B, cwm in continuations.get(cand_id, {}).items():
        if B not in feasible_ids:
            continue
        c = delta * cwm[scen]["wm"]
        best_cont = np.maximum(best_cont, c)        # per-draw elementwise max
        v = pct(c, 50)                              # report the P50-best continuation
        if v > b_p50:
            b_p50, best_B = v, B
    cont = np.maximum(best_cont, 0.0)
    cv = own + cont
    return cv, own, cont, best_B


def select_winner(feasible_ids, cvs):
    """Commit argmax CV(A) subject to K_A <= R_k (spec 07 §3). A KNIFE-EDGE (gate
    G4) is diagnosed on the per-draw win probability, NOT the P50 gap: under CRN a
    thin P50 gap can still be a decisive per-draw win (correlated draws), which is
    a STABLE rank -- only P(top beats runner-up) ~ 0.5 is a true coin-flip. On a
    knife-edge the §3 interim directive 'ranking is by Delta-minutes LEVEL' is the
    deterministic tie-break (higher OWN Delta-wm, robust across seeds -> G4 rank
    stability); the pair is reported as P ~ 0.5, not a defect. Returns (winner,
    knife_edge_bool, ranked, p_top_beats_second)."""
    ranked = sorted(feasible_ids, key=lambda c: cvs[c]["cv_p50"], reverse=True)
    winner, knife, p = ranked[0], False, None
    if len(ranked) > 1:
        top, second = ranked[0], ranked[1]
        p = float(np.mean(cvs[top]["cv"] > cvs[second]["cv"]))
        if 0.5 - KNIFE_EDGE_TOL <= p <= 0.5 + KNIFE_EDGE_TOL:
            knife = True
            winner = max((top, second), key=lambda c: cvs[c]["own_p50"])
    return winner, knife, ranked, p


def interaction(a, b, singles, continuations, scen):
    """Symmetrized interaction I(A,B) at COMMON timing (delta undone, spec 07
    §5.1):

        I(A,B) = 1/2 * [ (V(B|A) - V(B)) + (V(A|B) - V(A)) ]

    where V(X|Y) = Delta-wm(X | N + Y) and V(X) = Delta-wm(X | N). In the interim
    objective both legs are already at common timing (delta = 1), so I isolates
    approximation error (S0 staleness, anchor chaining) from genuine sequencing
    value; the delta-timed sequencing component is 0 in interim and reported
    separately. Per-draw, summarized to P50 with the tau caveat attached by the
    caller (§5.4)."""
    v_b = singles[b][scen]["wm"]
    v_a = singles[a][scen]["wm"]
    v_b_given_a = continuations.get(a, {}).get(b, {}).get(scen, {}).get("wm")
    v_a_given_b = continuations.get(b, {}).get(a, {}).get(scen, {}).get("wm")
    if v_b_given_a is None or v_a_given_b is None:
        return None
    leg1 = v_b_given_a - v_b
    leg2 = v_a_given_b - v_a
    I = 0.5 * (leg1 + leg2)
    return {"pair": sorted([a, b]),
            "I_p50": pct(I, 50), "I_p10": pct(I, 10), "I_p90": pct(I, 90),
            "leg_b_given_a_p50": pct(leg1, 50),
            "leg_a_given_b_p50": pct(leg2, 50),
            "approximation_component_p50": pct(I, 50),   # common-timing => all approx
            "sequencing_component_p50": 0.0,             # delta-timed; 0 in interim
            "tau_caveat": ("tau pinning (spec 07 §8a) pins transfer volume to a "
                           "share of base boardings, so cross-line synergy in the "
                           "objective is MUTED -- this interaction estimate is a "
                           "lower bound on true complementarity; records-request "
                           "item 3 is the eventual fix")}


# ---------------------------------------------------------------------------
# canonical serialization (gate G6)
# ---------------------------------------------------------------------------
def _canon(o):
    """Recursively canonicalize for a byte-identical dump: floats rounded to
    CANON_DECIMALS, numpy scalars/arrays -> python, sets -> sorted lists."""
    if isinstance(o, dict):
        return {k: _canon(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_canon(v) for v in o]
    if isinstance(o, set):
        return [_canon(v) for v in sorted(o)]
    if isinstance(o, (np.floating, float)):
        return round(float(o), CANON_DECIMALS)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, np.ndarray):
        return _canon(o.tolist())
    return o


def write_artifact(path, artifact):
    """Write the primary artifact G6-deterministically: canonical floats, sorted
    keys, no timestamps, LF newlines. Byte-identical on rerun from the same
    seed + configs."""
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(_canon(artifact), f, sort_keys=True, indent=2)
        f.write("\n")


# ---------------------------------------------------------------------------
# the cycle loop
# ---------------------------------------------------------------------------
_WEIGHT_CACHE = {}


def _cycle_weights(n, seed, clbl):
    """The shared OC posterior weights (spec 07 §6.1): the 543_launch_s500 ABC
    weights, a function of (params, seed) via the harbor backtest and IDENTICAL
    across corridors under CRN -- so computed ONCE per (n, seed) and reused. The
    weights are applied by label to EVERY candidate's per-draw objective (the
    §1 amendment: they are properties of the shared posterior). Returns
    (params, weights, ess)."""
    key = (n, seed, clbl)
    if key not in _WEIGHT_CACHE:
        params = draw_params(n, seed)
        pred = run(backtest_corridor(), n=n, params=params,
                   seed=seed)["uncapped"]["retain"]["newline"]
        from reweight_abc import get_kernels
        kern = next(k for k in get_kernels() if k[0] == clbl)
        w = abc_weights(pred, [kern])[clbl]
        _WEIGHT_CACHE[key] = (params, w, float(1.0 / np.sum(w ** 2)))
    return _WEIGHT_CACHE[key]


def sequence(cands, hand_supplied, subst_note, seed=SEED, n=N, max_cycles=None,
             budget=None, scenario="fold", quiet=False, gtfs=None, tracts=None):
    """Run the greedy sequencing loop and return the primary-artifact dict.
    budget is a cumulative program budget ($M, US-TYPICAL band, spec 07 §7/Q2);
    None -> slack (level ranking, spec 07 §3). scenario is the operator fold/
    retain decision fixed at commitment (spec 06 un-blending); both scenarios
    are always reported."""
    gtfs = gtfs or _Gtfs()
    tracts = _tract_table() if tracts is None else tracts
    run_dir = bc.RUN_DIR

    # spec 07 §6.1 shared OC posterior: the 543_launch_s500 ABC weights, computed
    # once per (n, seed) and applied by label to EVERY candidate's per-draw
    # objective (the §1 amendment). ESS reported for every ABC-weighted statistic.
    clbl = central_label()                       # 543_launch_s500
    params, weights, ess = _cycle_weights(n, seed, clbl)
    ess_min = val("ess_min")

    committed = []                               # the growing network (chain)
    cycle_records = []
    remaining = {c["id"]: c for c in cands}
    stop = None

    ncyc = max_cycles if max_cycles is not None else len(cands)
    for k in range(ncyc):
        if not remaining:
            stop = {"reason": "candidate_exhaustion", "cycle": k}
            break

        network_before = [dict(H) for H in committed]
        net_ids = [H["id"] for H in committed]

        # --- singles: Delta-wm(A | N_k) for every remaining candidate ----------
        singles = {}
        for cid, C in remaining.items():
            C = dict(C, scenario=scenario)
            rec = evaluate(C, network_before, params, seed, weights, gtfs,
                           tracts, n, run_dir)
            rec["depth"] = eval_depth(rec["deps"], network_before)
            singles[cid] = {"rec": rec,
                            "fold": rec["scenarios"]["fold"],
                            "retain": rec["scenarios"]["retain"]}

        # --- directional continuations: Delta-wm(B | N_k + A) ------------------
        # commit A hypothetically, evaluate every B != A against N_k + A. These
        # are BOTH the CV lookahead and the interaction-matrix legs (common
        # timing), so they are computed once and shared.
        continuations = {}
        for aid, A in remaining.items():
            A_c = dict(A, scenario=scenario)
            A_committed = _as_committed(A_c, singles[aid]["rec"], params,
                                        scenario, network_before)
            net_plus_a = network_before + [A_committed]
            continuations[aid] = {}
            for bid, B in remaining.items():
                if bid == aid:
                    continue
                B_c = dict(B, scenario=scenario)
                rb = evaluate(B_c, net_plus_a, params, seed, weights, gtfs,
                              tracts, n, run_dir)
                rb["depth"] = eval_depth(rb["deps"], net_plus_a)
                continuations[aid][bid] = {
                    "fold": rb["scenarios"]["fold"],
                    "retain": rb["scenarios"]["retain"], "rec": rb}

        # --- feasibility (budget) + CV -----------------------------------------
        remaining_budget = (None if budget is None
                            else budget - sum(H["capital_ut"] for H in committed))
        feasible = {}
        for cid, C in remaining.items():
            cap = capital_bands(C)["US_TYPICAL"]
            feas = remaining_budget is None or cap <= remaining_budget + 1e-6
            feasible[cid] = feas
        feasible_ids = [cid for cid, f in feasible.items() if f]

        if not feasible_ids:
            marg = _economic_margin(remaining, singles, scenario)
            stop = {"reason": "budget_exhaustion", "cycle": k,
                    "remaining_budget_ut": remaining_budget,
                    "economic_margin_note": marg}
            break

        cvs = {}
        for cid in feasible_ids:
            cv, own, cont, bestB = cv_components(
                cid, singles_for(singles), continuations_for(continuations),
                scenario, feasible_ids)
            cvs[cid] = {"cv": cv, "own": own, "cont": cont, "best_B": bestB,
                        "cv_p50": pct(cv, 50), "own_p50": pct(own, 50),
                        "cont_p50": pct(cont, 50)}

        winner, knife_edge, ranked, p_top = select_winner(feasible_ids, cvs)

        # spec 07 §3 pair-justified commitment: if the winner's OWN Delta-wm < 0
        # it is committed only because its continuation B* justifies it.
        pair_justified = cvs[winner]["own_p50"] < 0.0
        best_B = cvs[winner]["best_B"]

        # --- interaction matrix (audit; §5.1/§5.4) -----------------------------
        imatrix = []
        ids = list(remaining)
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                I = interaction(ids[i], ids[j], singles_for(singles),
                                continuations_for(continuations), scenario)
                if I is not None:
                    imatrix.append(I)

        # --- pairwise P(beats) on the CV arrays --------------------------------
        pbeats = {}
        for cid in feasible_ids:
            for oid in feasible_ids:
                if cid < oid:
                    p = float(np.mean(cvs[cid]["cv"] > cvs[oid]["cv"]))
                    pbeats[f"{cid}>{oid}"] = p

        # --- commit the winner -------------------------------------------------
        W = dict(remaining[winner], scenario=scenario)
        W_committed = _as_committed(W, singles[winner]["rec"], params, scenario,
                                    network_before)
        W_committed["depth"] = singles[winner]["rec"]["depth"]
        capW = capital_bands(W)

        # --- bounded swap pass (runner-up-only, §5.2) --------------------------
        swaps = _swap_pass(committed, winner, feasible_ids, cvs, scenario)

        cyc = _cycle_record(k, network_before, committed, remaining, singles,
                            continuations, cvs, winner, pair_justified, best_B,
                            imatrix, pbeats, capW, W_committed, swaps, scenario,
                            feasible, budget, remaining_budget, knife_edge)
        cycle_records.append(cyc)
        if not quiet:
            _print_cycle(cyc, singles, cvs, winner)

        committed.append(W_committed)
        del remaining[winner]

    if stop is None:
        stop = {"reason": "candidate_exhaustion", "cycle": len(committed)}
    stop = _finalize_stop(stop, committed, cycle_records, budget, scenario)

    return _assemble_artifact(cands, hand_supplied, subst_note, seed, n,
                              scenario, budget, clbl, ess, ess_min,
                              committed, cycle_records, stop, gtfs, tracts)


# ---- small helpers the loop leans on --------------------------------------
def singles_for(singles):
    """{id: {scen: {'wm':..}}} view for cv_components / interaction."""
    return {cid: {"fold": s["fold"], "retain": s["retain"]}
            for cid, s in singles.items()}


def continuations_for(continuations):
    return {aid: {bid: {"fold": d["fold"], "retain": d["retain"]}
                  for bid, d in bs.items()}
            for aid, bs in continuations.items()}


def _as_committed(C, rec, params, scenario, network_before):
    """Turn a candidate + its evaluation into a committed-line dict the chain
    carries: id, cfg, geometry, scenario, per-draw MARGIN (total-anchor of the
    committed scenario, for downstream anchor chaining), folds, capital, depth."""
    d = rec["res"]["uncapped"][scenario]
    margin = d["total"] - rec["res"]["anchor"]       # (n,) per-draw MARGIN
    caps = capital_bands(C)
    return {"id": C["id"], "cfg": C["cfg"], "config_path": C["config_path"],
            "derived_path": C["derived_path"],
            "x": C["x"], "y": C["y"], "window": C["window"],
            "spacing": C["spacing"], "headway": C["headway"],
            "worker_pts": C["worker_pts"], "worker_mass": C["worker_mass"],
            "folds": C["folds"], "scenario": scenario,
            "margin": margin,
            # the committed line's OWN per-draw welfare minutes as evaluated
            # against the network it FACED (for the within-draw frontier sum)
            "margin_wm": rec["scenarios"][scenario]["wm"],
            "capital_ut": caps["US_TYPICAL"], "capital_low": caps["LOW"],
            "route_mi": C["route_mi"], "stations": C["stations"],
            "cars": C["cars"],
            "depth": rec.get("depth", 1)}


def _economic_margin(remaining, singles, scenario):
    """The economic margin at which the screen emptied (spec 07 §7: never
    'candidates ran out')."""
    best = max(remaining, key=lambda c: pct(singles[c][scenario]["wm"], 50))
    return {"best_uncommitted": best,
            "best_uncommitted_wm_p50": pct(singles[best][scenario]["wm"], 50),
            "note": "budget bound before this candidate could be committed; its "
                    "welfare-minutes margin is the shadow economic value the "
                    "budget left on the table (spec 07 §7)"}


def _swap_pass(committed, winner, feasible_ids, cvs, scenario):
    """Bounded swap/removal moves, runner-up-only (spec 07 §5.2): after the
    commitment, test replacing each HYPOTHETICAL committed line with the cycle's
    runner-up. Built lines (network_asbuilt) are never swapped -- sunk. With 2
    candidates the suffix is trivial (the runner-up IS the only alternative), so
    the pass records the runner-up and the CV gap it would have to beat; a full
    suffix re-evaluation is the multi-candidate path (spec 07 §9)."""
    runner_up = None
    ranked = sorted(feasible_ids, key=lambda c: cvs[c]["cv_p50"], reverse=True)
    if len(ranked) > 1:
        runner_up = ranked[1]
    return {"runner_up": runner_up,
            "runner_up_cv_p50": (cvs[runner_up]["cv_p50"] if runner_up else None),
            "winner_cv_p50": cvs[winner]["cv_p50"],
            "hypothetical_positions_tested": [H["id"] for H in committed],
            "note": ("runner-up-only bounded swap (spec 07 §5.2); no committed "
                     "HYPOTHETICAL line was displaced -- with 2 candidates the "
                     "swap suffix is trivial (the runner-up is the sole "
                     "alternative). Built (asbuilt) lines are never swapped.")}


# ---------------------------------------------------------------------------
# record / artifact assembly
# ---------------------------------------------------------------------------
def _cand_result_block(cid, singles, continuations, cvs, scenario):
    s = singles[cid]
    rec = s["rec"]
    block = {"id": cid, "depth": rec["depth"],
             "depth_label": _depth_label(rec["depth"]),
             "injected_committed_lines": sorted(rec["injected"]),
             "excluded_fold_routes": sorted(rec["excluded"]),
             "dependencies": [dict(d) for d in rec["deps"]],
             "fold": {"wm_uncapped": s["fold"]["wm_uncapped"],
                      "wm_abc": s["fold"]["wm_abc"],
                      "newline_uncapped": s["fold"]["newline_uncapped"],
                      "newline_abc": s["fold"]["newline_abc"]},
             "retain": {"wm_uncapped": s["retain"]["wm_uncapped"],
                        "wm_abc": s["retain"]["wm_abc"],
                        "newline_uncapped": s["retain"]["newline_uncapped"],
                        "newline_abc": s["retain"]["newline_abc"]}}
    if cid in cvs:
        c = cvs[cid]
        block["cv"] = {"cv_p50": c["cv_p50"], "own_dNPV_p50": c["own_p50"],
                       "continuation_p50": c["cont_p50"], "best_continuation": c["best_B"],
                       "timing_split_note": ("interim: delta = 1 (welfare-minutes "
                                             "are a level, never discounted); the "
                                             "one-cycle_gap deferral shows only in "
                                             "the Delta-K_PV display")}
    return block


def _depth_label(depth):
    return "exploratory" if depth > DEPTH_CAP else "decision-grade"


def _cycle_record(k, network_before, committed, remaining, singles,
                  continuations, cvs, winner, pair_justified, best_B, imatrix,
                  pbeats, capW, W_committed, swaps, scenario, feasible, budget,
                  remaining_budget, knife_edge=False):
    cands_block = [_cand_result_block(cid, singles, continuations, cvs, scenario)
                   for cid in sorted(remaining)]
    return {
        "cycle": k,
        "network_before": [{"id": H["id"], "scenario": H["scenario"],
                            "provenance": "hypothetical", "depth": H["depth"]}
                           for H in network_before],
        "candidate_results": cands_block,
        "feasibility": {cid: bool(feasible[cid]) for cid in sorted(feasible)},
        "remaining_budget_ut": remaining_budget,
        "interaction_matrix": imatrix,
        "archetype_gap": _archetype_placeholder(),
        "swap_results": swaps,
        "pairwise_p_beats": pbeats,
        "commitment": {
            "line": winner, "scenario": scenario,
            "pair_justified": bool(pair_justified),
            "pair_justification": ({
                "continuation": best_B,
                "note": ("winner's own Delta-wm < 0; committed only because its "
                         "continuation justifies it (spec 07 §3). The §7 marginal "
                         "stop does NOT fire on it; the next cycle's swap pass "
                         "must reconsider it if no continuation worth >= "
                         "delta*Delta-wm(B*|N+A) is committed.")}
                if pair_justified else None),
            "capital_delta_K": {"LOW": capW["LOW"], "US_TYPICAL": capW["US_TYPICAL"]},
            "capital_delta_K_pv": {
                "LOW": capW["LOW"] * pv_factor(k),
                "US_TYPICAL": capW["US_TYPICAL"] * pv_factor(k),
                "pv_factor": pv_factor(k), "cycle_gap": CYCLE_GAP,
                "discount_note": ("Delta-K_PV display only (spec 07 §3); interim "
                                  "welfare is never discounted. rate 7% real, "
                                  "BCA-wrapper property, cited not owned")},
            "welfare_per_dollar_ratio_DISPLAY_ONLY": _ratio_display(
                cvs[winner]["own_p50"], capW, k),
            "knife_edge": bool(knife_edge),
            "knife_edge_note": ("CVs within the knife-edge tolerance (slack "
                                "budget, delta=1: build order welfare-neutral); "
                                "committed by the §3 interim LEVEL tie-break (own "
                                "Delta-wm). See pairwise_p_beats ~ 0.5 (gate G4)."
                                if knife_edge else None),
            "depth": W_committed["depth"], "depth_label": _depth_label(W_committed["depth"]),
            "rationale": _rationale(winner, cvs, pair_justified, best_B, knife_edge)},
    }


def _ratio_display(wm_p50, capW, k):
    """Welfare-minutes per $M Delta-K_PV, both cost bands -- DISPLAY ONLY, labeled
    INTERIM (spec 07 §3: the interim layer cannot do timing economics and the
    ratio is decision-relevant only when the budget binds, §7)."""
    f = pv_factor(k)
    return {"LOW": wm_p50 / (capW["LOW"] * f),
            "US_TYPICAL": wm_p50 / (capW["US_TYPICAL"] * f),
            "units": "welfare-min per $M Delta-K_PV",
            "label": "INTERIM / DISPLAY ONLY -- never quoted as BCA output"}


def _rationale(winner, cvs, pair_justified, best_B, knife_edge=False):
    c = cvs[winner]
    if pair_justified:
        return (f"{winner} committed on its pair with {best_B} (own Delta-wm "
                f"P50 {c['own_p50']:,.0f} < 0; CV P50 {c['cv_p50']:,.0f}).")
    if knife_edge:
        return (f"{winner} = §3 interim LEVEL tie-break at a CV knife-edge (own "
                f"Delta-wm P50 {c['own_p50']:,.0f}; CV P50 {c['cv_p50']:,.0f} "
                f"within tolerance of the runner-up).")
    return (f"{winner} = argmax CV (own Delta-wm P50 {c['own_p50']:,.0f} + "
            f"continuation {c['cont_p50']:,.0f} = CV {c['cv_p50']:,.0f}).")


def _archetype_placeholder():
    """spec 07 §5.3 / §11 Q3: archetypes are OWNER-DESIGNED complete networks
    with declared build orders (trunk+feeders, crossing pair, mini-grid), N3.
    They are SKIPPED here -- N1b prints this gap-section placeholder with the
    reason so no reader mistakes the greedy result for the modified-greedy
    safeguard being complete."""
    return {"status": "skipped",
            "reason": ("archetypes are owner-designed complete networks with "
                       "declared internal build orders (spec 07 §5.3 / §11 Q3); "
                       "the harness must not generate them (a generator "
                       "reintroduces the combinatorial problem this spec declines "
                       "to solve). N3 supplies config/archetypes/*.json + the "
                       "matched-capital gap series; until then the safeguard "
                       "comparison line carries greedy vs best-single only."),
            "work_item": "N3"}


def _finalize_stop(stop, committed, cycle_records, budget, scenario):
    """Attach the §7 stopping-record economics: the interim mode stops on the
    budget knob or candidate exhaustion, WITH the economic margin printed. The
    BCR < 1 rule is N5's NPV mode -- noted, not applied here."""
    stop = dict(stop)
    stop["mode"] = "interim (welfare-minutes level ranking)"
    stop["bcr_rule_note"] = ("the BCR < 1 marginal stop is N5's NPV mode; the "
                             "interim layer stops on budget exhaustion or "
                             "candidate exhaustion and reports the economic "
                             "margin at which it emptied (spec 07 §7).")
    if committed:
        last = cycle_records[-1]["commitment"]
        stop["last_commitment"] = {
            "line": last["line"],
            "cv_p50": _last_cv(cycle_records),
            "capital_delta_K": last["capital_delta_K"]}
        stop["shadow_price_note"] = (
            "under a binding budget the marginal committed line's welfare margin "
            "is the shadow-price cutoff (spec 07 §7); it exceeds the null "
            "continuation, so the hurdle was not merely 0.")
    return stop


def _last_cv(cycle_records):
    r = cycle_records[-1]
    w = r["commitment"]["line"]
    for b in r["candidate_results"]:
        if b["id"] == w and "cv" in b:
            return b["cv"]["cv_p50"]
    return None


def _safeguard(committed, cycle_records, scenario):
    """spec 07 §2/§7 safeguard comparison line: max{greedy portfolio, best
    single feasible candidate, best feasible archetype} -- the modified-greedy
    knapsack fix, zero extra evaluations. Archetype = skipped (N3)."""
    # best single = the single line with the highest standalone Delta-wm P50 in
    # cycle 0 (the whole feasible universe seen against the empty network).
    c0 = cycle_records[0]
    best_single, best_single_wm = None, -np.inf
    for b in c0["candidate_results"]:
        v = b[scenario]["wm_uncapped"][1]
        if v > best_single_wm:
            best_single_wm, best_single = v, b["id"]
    greedy_ids = [H["id"] for H in committed]
    return {"greedy_portfolio": greedy_ids,
            "best_single_feasible": {"line": best_single,
                                     "wm_p50": best_single_wm},
            "best_feasible_archetype": {"status": "skipped", "work_item": "N3"},
            "note": ("safeguard = max{greedy portfolio, best single feasible, "
                     "best feasible archetype}; the archetype leg lands with N3.")}


def _frontier(committed, seed, n, scenario, weights):
    """Cumulative-capital-PV vs cumulative-objective frontier, aggregated
    WITHIN-DRAW (spec 07 §3/§7): sum the committed lines' per-draw welfare
    minutes INSIDE each draw, THEN take percentiles -- never sums of per-line
    percentiles (shared parameter draws correlate every line's forecast).
    Depth-shaded, both cost bands. The sigma_struct per-line independent-error
    row is a NAMED spec-pending N4 row (the within-draw sum carries the
    correlated parameter component but not the per-line idiosyncratic structural
    error)."""
    pts = []
    cum_low = cum_ut = 0.0
    cum_wm = None
    for k, H in enumerate(committed):
        # H's own per-draw welfare minutes (committed scenario), against the
        # network it was committed AGAINST -- carried on the committed dict.
        wm = H["margin_wm"]
        cum_wm = wm if cum_wm is None else cum_wm + wm     # WITHIN-DRAW sum
        cum_low += H["capital_low"] * pv_factor(k)
        cum_ut += H["capital_ut"] * pv_factor(k)
        pts.append({
            "step": k, "line": H["id"], "scenario": H["scenario"],
            "depth": H["depth"], "depth_label": _depth_label(H["depth"]),
            "capital_LOW": H["capital_low"], "capital_US_TYPICAL": H["capital_ut"],
            "pv_factor": pv_factor(k),
            "cum_capital_pv_LOW": cum_low, "cum_capital_pv_US_TYPICAL": cum_ut,
            "cum_wm_uncapped": [pct(cum_wm, q) for q in (10, 50, 90)],
            "cum_wm_abc": [wpct(cum_wm, weights, q) for q in (10, 50, 90)]})
    return {"points": pts,
            "aggregation": "within-draw (spec 07 §3): sum lines per draw, then "
                           "percentiles",
            "sigma_struct_row": {"status": "spec-pending", "work_item": "N4",
                                 "note": ("per-line idiosyncratic structural "
                                          "error (sigma_struct, spec 07 §8g); the "
                                          "within-draw sum carries only the "
                                          "correlated parameter component, so the "
                                          "portfolio bands are otherwise too "
                                          "narrow. Named here, landed at N4.")},
            "flyvbjerg_annotation": ("portfolio optimism is worse than "
                                     "single-project optimism -- forecast errors "
                                     "are correlated across the model's lines "
                                     "(spec 05 §4.3; within-draw aggregation makes "
                                     "this arithmetic, not rhetoric).")}


def _sensitivity_block():
    """spec 07 §10 G7: every knob this harness introduces ships with its row in
    the primary artifact's sensitivity block IN THE SAME COMMIT. The N1b-scope
    rows are COMPUTED (values filled by run_sensitivity); the rows this interim
    layer cannot yet produce are NAMED as spec-pending N4/N5. This function
    returns the row SPECS; run_sensitivity fills the deltas."""
    return {
        "computed_n1b": [
            {"id": "cycle_gap_lo", "knob": "cycle_gap", "value": band("cycle_gap")[0],
             "display": "Delta-K_PV (interim: welfare not discounted)"},
            {"id": "cycle_gap_hi", "knob": "cycle_gap", "value": band("cycle_gap")[1],
             "display": "Delta-K_PV (interim: welfare not discounted)"},
            {"id": "budget_lo", "knob": "network_budget", "value": band("network_budget")[0]},
            {"id": "budget_hi", "knob": "network_budget", "value": band("network_budget")[1]},
            {"id": "omega_0.5", "knob": "omega_scale", "value": 0.5},
            {"id": "omega_1.5", "knob": "omega_scale", "value": 1.5},
            {"id": "omega_uniform", "knob": "omega_allocation", "value": "uniform"},
            {"id": "depth_cap_1", "knob": "depth_cap", "value": band("depth_cap")[0]},
            {"id": "depth_cap_3", "knob": "depth_cap", "value": band("depth_cap")[1]},
        ],
        "named_spec_pending": [
            {"id": "k3_order_diff", "knob": "k=3 deep pass", "work_item": "N1/optional",
             "note": "order-difference diagnostic over the top-3 candidates (spec 07 §5.1)"},
            {"id": "offpeak_to_midday", "knob": "feeder_headway_map",
             "work_item": "N4", "note": "peak-mapped feeder-headway variant (spec 07 §4.2.1)"},
            {"id": "sigma_struct", "knob": "sigma_struct", "work_item": "N4",
             "note": "per-line independent structural error on portfolio bands (§8g)"},
            {"id": "fixed_cost_share", "knob": "fixed_cost_share", "work_item": "N4",
             "note": "shared OCC+depot for lines 2..k, rows {1, 0.5, 0} (§8j)"},
            {"id": "ratio_greedy_order", "knob": "ratio-vs-level ordering",
             "work_item": "N5", "note": "capital-efficiency-ratio ordering comparison (§3/§7)"},
            {"id": "premium_bracket", "knob": "ASC premium {1,1.5,2}", "work_item": "N5",
             "note": "R2 premium-bracket rows on every stop decision (§6.1)"},
        ]}


# ---------------------------------------------------------------------------
# sensitivity rows the harness CAN compute now (cheap re-derivations)
# ---------------------------------------------------------------------------
def run_sensitivity(base_artifact, cands, hand_supplied, subst_note, seed, n,
                    scenario, gtfs, tracts):
    """Fill the N1b-scope sensitivity deltas (spec 07 §10 G7). cycle_gap and
    budget rows re-run the CHEAP loop pieces (they change display / feasibility,
    not the model runs); omega and depth-cap rows re-run the loop under the
    swept knob. Every row is a % delta of the committed-order objective (the
    cumulative welfare-minutes P50 of the final portfolio)."""
    spec = _sensitivity_block()
    base_obj = _committed_order_objective(base_artifact)
    rows = []
    for r in spec["computed_n1b"]:
        val_obj, note, display = _sens_value(
            r, cands, hand_supplied, subst_note, seed, n, scenario, gtfs, tracts,
            base_artifact)
        pctd = None if base_obj in (0, None) or val_obj is None else \
            100.0 * (val_obj - base_obj) / base_obj
        row = {**r, "objective_p50": val_obj, "pct": pctd, "note": note}
        if display is not None:
            row["display"] = display
        rows.append(row)
    return {"base_objective_p50": base_obj,
            "base_objective_note": "committed-order cumulative welfare-minutes "
                                    "P50 (final portfolio, within-draw)",
            "computed_n1b": rows,
            "named_spec_pending": spec["named_spec_pending"]}


def _committed_order_objective(artifact):
    pts = artifact["frontier"]["points"]
    return pts[-1]["cum_wm_uncapped"][1] if pts else None


def _sens_value(row, cands, hand_supplied, subst_note, seed, n, scenario, gtfs,
                tracts, base_artifact):
    """Objective under one swept knob. cycle_gap / budget change only display /
    feasibility, so they re-read the base runs; omega_scale / omega_allocation /
    depth_cap re-run the loop (the model runs differ)."""
    knob = row["knob"]
    pts = base_artifact["frontier"]["points"]
    base_obj = pts[-1]["cum_wm_uncapped"][1] if pts else None
    if knob == "cycle_gap":
        # cycle_gap does not move welfare-minutes (interim: level, not
        # discounted) -- the objective is INVARIANT; the CONCRETE effect is on
        # the Delta-K_PV DISPLAY, so recompute the portfolio's cumulative
        # Delta-K_PV at the swept cycle_gap from the per-line capital + step.
        cg = row["value"]
        cum_low = sum(p["capital_LOW"] * pv_factor(p["step"], cycle_gap=cg)
                      for p in pts)
        cum_ut = sum(p["capital_US_TYPICAL"] * pv_factor(p["step"], cycle_gap=cg)
                     for p in pts)
        return base_obj, ("cycle_gap is Delta-K_PV display only; welfare "
                          "objective invariant (interim: level, not discounted)"), \
            {"cycle_gap_yr": cg, "cum_capital_pv_LOW": cum_low,
             "cum_capital_pv_US_TYPICAL": cum_ut}
    if knob == "network_budget":
        art = sequence(cands, hand_supplied, subst_note, seed=seed, n=n,
                       budget=row["value"], scenario=scenario, quiet=True,
                       gtfs=gtfs, tracts=tracts)
        committed = [p["line"] for p in art["frontier"]["points"]]
        return _committed_order_objective(art), \
            f"portfolio re-selected under budget {row['value']} $M", \
            {"committed": committed, "stop": art["stopping_record"]["reason"]}
    if knob == "omega_scale":
        art = sequence_swept(cands, hand_supplied, subst_note, seed, n, scenario,
                             gtfs, tracts, omega_scale=row["value"])
        return _committed_order_objective(art), \
            f"omega x {row['value']} (anchor-margin apportionment, §8i)", None
    if knob == "omega_allocation":
        art = sequence_swept(cands, hand_supplied, subst_note, seed, n, scenario,
                             gtfs, tracts, allocation="uniform")
        return _committed_order_objective(art), \
            "omega uniform-along-line allocation (§8i variant)", None
    if knob == "depth_cap":
        # depth cap changes only the exploratory LABEL, not the objective; record
        # WHICH lines flip to exploratory at the swept cap.
        cap = row["value"]
        expl = [p["line"] for p in pts if p["depth"] > cap]
        return base_obj, (f"depth_cap {cap} relabels the exploratory tail; "
                          "objective invariant"), \
            {"cap": cap, "exploratory_lines": expl,
             "n_exploratory": len(expl)}
    return None, "n/a", None


def sequence_swept(cands, hand_supplied, subst_note, seed, n, scenario, gtfs,
                   tracts, omega_scale=1.0, allocation=None):
    """A minimal re-run of the greedy loop under a swept ANCHOR knob (omega scale
    / allocation, spec 07 §8i / §10 G7), returning just enough artifact
    (frontier-only) to read the committed-order objective. sequence() cannot
    thread these knobs without bloating its signature, so this re-runs the
    minimal singles + continuations + commit greedy under the knob."""
    committed = []
    clbl = central_label()
    params, weights, _ess = _cycle_weights(n, seed, clbl)
    remaining = {c["id"]: c for c in cands}
    for k in range(len(cands)):
        if not remaining:
            break
        network_before = [dict(H) for H in committed]
        singles = {}
        for cid, C in remaining.items():
            C = dict(C, scenario=scenario)
            rec = evaluate(C, network_before, params, seed, weights, gtfs, tracts,
                           n, bc.RUN_DIR, allocation=allocation,
                           omega_scale=omega_scale)
            rec["depth"] = eval_depth(rec["deps"], network_before)
            singles[cid] = {"rec": rec, "fold": rec["scenarios"]["fold"],
                            "retain": rec["scenarios"]["retain"]}
        continuations = {}
        for aid, A in remaining.items():
            A_c = dict(A, scenario=scenario)
            A_committed = _as_committed(A_c, singles[aid]["rec"], params,
                                        scenario, network_before)
            net_plus_a = network_before + [A_committed]
            continuations[aid] = {}
            for bid, B in remaining.items():
                if bid == aid:
                    continue
                rb = evaluate(dict(B, scenario=scenario), net_plus_a, params,
                              seed, weights, gtfs, tracts, n, bc.RUN_DIR,
                              allocation=allocation, omega_scale=omega_scale)
                continuations[aid][bid] = {"fold": rb["scenarios"]["fold"],
                                           "retain": rb["scenarios"]["retain"],
                                           "rec": rb}
        feasible_ids = list(remaining)
        cvs = {}
        for cid in feasible_ids:
            cv, own, cont, bestB = cv_components(cid, singles_for(singles),
                                                 continuations_for(continuations),
                                                 scenario, feasible_ids)
            cvs[cid] = {"cv": cv, "cv_p50": pct(cv, 50), "own_p50": pct(own, 50)}
        winner, _knife, _ranked, _p = select_winner(feasible_ids, cvs)
        W = dict(remaining[winner], scenario=scenario)
        W_committed = _as_committed(W, singles[winner]["rec"], params, scenario,
                                    network_before)
        W_committed["depth"] = singles[winner]["rec"]["depth"]
        W_committed["margin_wm"] = singles[winner]["rec"]["scenarios"][scenario]["wm"]
        committed.append(W_committed)
        del remaining[winner]
    return {"frontier": _frontier(committed, seed, n, scenario, weights)}


def _assemble_artifact(cands, hand_supplied, subst_note, seed, n, scenario,
                       budget, clbl, ess, ess_min, committed, cycle_records,
                       stop, gtfs, tracts):
    # each committed line already carries its own per-draw welfare minutes
    # (margin_wm, set at commitment against the network it faced) for the
    # within-draw frontier sum.
    _params, weights, _ess = _cycle_weights(n, seed, clbl)

    run_id = nm.network_fingerprint({
        "candidates": nm.sorted_set_list(c["id"] for c in cands),
        "asbuilt": json.load(open(os.path.join(CFG, "network_asbuilt.json"),
                                  encoding="utf-8")).get("lines", []),
        "seed": seed, "n": n, "scenario": scenario, "budget": budget})

    artifact = {
        "schema": "spec 07 §7 network-sequence primary artifact (interim objective)",
        "run_id": run_id,
        "objective": {"mode": "interim",
                      "metric": "Delta(welfare-minutes) LEVEL, within-draw",
                      "note": ("INTERIM (spec 07 §3): the full-NPV objective is "
                               "N5, gated on R1 -> R6 -> W1. Delta-K shown as the "
                               "spec 04 LOW | US-TYPICAL band; welfare-per-dollar "
                               "ratio is a display column only.")},
        "seed": seed, "n": n, "scenario": scenario, "budget_ut": budget,
        "kernel_set": {"central_label": clbl, "ess": ess,
                       "ess_min": ess_min,
                       "ess_saturated": bool(ess < ess_min),
                       "note": ("spec 07 §6.1: all candidates ranked under the "
                                "SHARED OC posterior (the 543_launch_s500 ABC "
                                "weights), uncapped alongside; identical across "
                                "corridors under CRN, so computed once per cycle. "
                                "ESS reported for every ABC-weighted statistic "
                                "(spec 02 §4.4 ESS<1000 saturation rule).")},
        "candidate_universe": {
            "ids": nm.sorted_set_list(c["id"] for c in cands),
            "hand_supplied": hand_supplied, "substitution_note": subst_note},
        "cycles": cycle_records,
        "frontier": _frontier(committed, seed, n, scenario, weights),
        "stopping_record": stop,
        "safeguard_comparison": _safeguard(committed, cycle_records, scenario),
        "provenance_report": _provenance_report(committed, cycle_records),
        "sensitivity": None,     # filled by run_sensitivity in main()
        "amendments_note": ("spec 07 §1/§6.1: this run applies the degrade-to-"
                            "uncapped amendment (ABC weights are properties of "
                            "the shared posterior, applicable to any corridor "
                            "under the same draws). The amendment itself rides "
                            "N6; this artifact is its operational record."),
        "governance_note": ("in-run commitments are RECOMMENDATIONS (spec 07 §1); "
                            "spec 00 §3 gate discipline applies at each REAL "
                            "programmatic commitment. Each line's forecast of "
                            "record remains its own stage-3 STOPS run."),
    }
    return artifact


def _provenance_report(committed, cycle_records):
    return {"depth_rule": ("depth(measured)=0; depth(eval)=1+max{depth(H): H "
                           "hypothetical in network-before AND candidate depends "
                           "on H}; committed line inherits eval depth; cap "
                           f"{DEPTH_CAP} -> EXPLORATORY, excluded from gate memos "
                           "(spec 07 §6.2)."),
            "dependency_predicate": (f"depends = omega>{DEP_OMEGA} OR co-located "
                                     "persistent injection OR feeder/transfer edge "
                                     "in the rebuilt inputs."),
            "lines": [{"id": H["id"], "provenance": "hypothetical",
                       "depth": H["depth"], "depth_label": _depth_label(H["depth"]),
                       "scenario": H["scenario"]} for H in committed],
            "operating_mode": ("a planning tool re-run between real build cycles "
                               "as lines open and forecasts become measurements; "
                               "provenance depth resets from the updated "
                               "network_asbuilt each re-run (spec 07 §6.2)."),
            "flyvbjerg": ("network optimism > single-project optimism (correlated "
                          "errors); the depth cap is the control (spec 07 §6.2).")}


# ---------------------------------------------------------------------------
# console print
# ---------------------------------------------------------------------------
def _print_cycle(cyc, singles, cvs, winner):
    k = cyc["cycle"]
    print(f"\n=== cycle {k}: network-before "
          f"{[H['id'] for H in cyc['network_before']] or 'EMPTY'} ===")
    for b in cyc["candidate_results"]:
        cid = b["id"]
        wm = b["fold"]["wm_uncapped"]
        cv = b.get("cv", {})
        print(f"  {cid:12s} fold Delta-wm P10/50/90 {wm[0]:>10,.0f} "
              f"{wm[1]:>10,.0f} {wm[2]:>10,.0f}  depth {b['depth']} "
              f"({b['depth_label']})"
              + (f"  CV_p50 {cv['cv_p50']:>10,.0f}" if cv else ""))
    c = cyc["commitment"]
    print(f"  -> COMMIT {c['line']} [{c['scenario']}]  "
          f"Delta-K {c['capital_delta_K']['LOW']:.0f}|"
          f"{c['capital_delta_K']['US_TYPICAL']:.0f} $M"
          + ("  (PAIR-JUSTIFIED)" if c["pair_justified"] else ""))
    for I in cyc["interaction_matrix"]:
        print(f"     I{I['pair']} P50 {I['I_p50']:+,.0f} welfare-min "
              f"(tau-muted, §8a)")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main(argv=None):
    ap = argparse.ArgumentParser(description="spec 07 network-sequencing harness (N1b)")
    ap.add_argument("--cycles", type=int, default=None)
    ap.add_argument("--budget", type=float, default=None, help="cumulative program budget $M (US-TYPICAL)")
    ap.add_argument("--n", type=int, default=N)
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--scenario", choices=("fold", "retain"), default="fold")
    ap.add_argument("--out", default=os.path.join(OUT, "network_sequence.json"))
    ap.add_argument("--no-sensitivity", action="store_true",
                    help="skip the G7 sensitivity block (faster; artifact incomplete)")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args(argv)

    gtfs = _Gtfs()
    tracts = _tract_table()
    cands, hand_supplied, subst = load_candidates(
        os.path.join(CFG, "candidates.json"), gtfs, tracts)

    print(f"spec 07 N1b sequencing: {len(cands)} candidates "
          f"{[c['id'] for c in cands]}, seed {a.seed}, n {a.n}, "
          f"scenario {a.scenario}"
          + (f", budget {a.budget} $M" if a.budget else " (slack budget)"))

    artifact = sequence(cands, hand_supplied, subst, seed=a.seed, n=a.n,
                        max_cycles=a.cycles, budget=a.budget,
                        scenario=a.scenario, quiet=a.quiet, gtfs=gtfs,
                        tracts=tracts)
    if not a.no_sensitivity:
        artifact["sensitivity"] = run_sensitivity(
            artifact, cands, hand_supplied, subst, a.seed, a.n, a.scenario,
            gtfs, tracts)
    else:
        artifact["sensitivity"] = {"status": "skipped (--no-sensitivity)"}

    write_artifact(a.out, artifact)
    print(f"\n-> {a.out}  (run_id {artifact['run_id'][:16]})")
    _print_summary(artifact)
    return 0


def _print_summary(artifact):
    print("\n--- portfolio frontier (within-draw) ---")
    for p in artifact["frontier"]["points"]:
        print(f"  step {p['step']}: +{p['line']:12s} cum Delta-K_PV "
              f"{p['cum_capital_pv_LOW']:.0f}|{p['cum_capital_pv_US_TYPICAL']:.0f} "
              f"$M  cum welfare-min P50 {p['cum_wm_uncapped'][1]:,.0f} "
              f"(depth {p['depth']})")
    sg = artifact["safeguard_comparison"]
    print(f"safeguard: greedy {sg['greedy_portfolio']} | best-single "
          f"{sg['best_single_feasible']['line']} | archetype "
          f"{sg['best_feasible_archetype']['status']}")
    st = artifact["stopping_record"]
    print(f"stop: {st['reason']} ({st['mode']})")


if __name__ == "__main__":
    sys.exit(main())
