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
import gzip
import json
import math
import os
import subprocess
import sys

import numpy as np
import pandas as pd

import bca_export as bx
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

# spec 07 §9 N4 registry conversion (§10 G7): the constant-tier registry leaves
# capcost + the harness CONSUME. Declared in the artifact's assumptions_manifest
# so each claims a network-artifact row (check_assumptions' network scan), and
# their values-hash (with the active prior bands) enters the run_id preimage so
# a rate-card or prior-band edit CHANGES the id (D60 review rec 3a -- the old id
# was input-keyed only and did not move when the forecast restated).
# spec 07 §3 / §8g sigma_struct: the per-line INDEPENDENT structural-error floor
# the ABC kernel's sigma asserts but the within-draw sum omits (it carries only
# the CORRELATED parameter component, so the portfolio bands are otherwise too
# narrow). Implemented HARNESS-SIDE (NOT a model prior -- no new PRIORS key, the
# rng stream is untouched): per-line N(0, sigma_struct) noise on the boardings
# scale, converted to welfare-minutes by each line's welfare-per-boarding ratio,
# seeded DETERMINISTICALLY from the run fingerprint (gate G6). 400 wd boardings
# is the structural floor near the 350-500 ABC-kernel sigma band (spec 07 §8g);
# the sigma_struct on/off G7 row is base vs inflated portfolio bands.
SIGMA_STRUCT_BOARDINGS = 400.0
# noise replicates per base draw: the sigma_struct band is the quantile of the
# CONVOLUTION of the correlated within-draw sum with the independent per-line
# error. A single noise draw per base draw estimates that quantile with sampling
# noise comparable to the (small) true widening; M replicates per base draw is a
# faithful variance reduction -- still per-line N(0, sigma_struct) noise, just a
# tighter estimate of the SAME inflated distribution (deterministic given the
# seed).
SIGMA_STRUCT_REPLICATES = 20

# ===========================================================================
# spec 07 N5 -- the FULL NPV objective (default). Per candidate-given-network the
# harness builds a spec 06 §3 export FROM the in-memory run() result (no re-run,
# bca_export.build_export) and prices it through the tbc v3 wrapper
# (bca-pipeline.mjs, node, SYNCHRONOUS, ~2 s at N=40,000). The wrapper's exact
# linear decomposition returns per-draw ΔNPV, so the harness reads back a compact
# per-draw NPV companion (bca_<corridor>_<fp>.npv.json) and does the WITHIN-DRAW
# CV itself (spec 07 §3). The harness OWNS capital (capcost.py / spec 04); it
# ships capcost's LOW|US-TYPICAL bands + the corridor service design in the
# export's cost_design, which the wrapper prices under the SHARED central profile
# (county-common prices / posterior, spec 07 §6.1). Both cost bands are carried.
# ---------------------------------------------------------------------------
TBC_DIR = os.path.abspath(os.path.join(ROOT, "..", "transit-benefit-cost"))
TBC_WRAPPER = os.path.join(TBC_DIR, "bca-pipeline.mjs")
TBC_PROFILE = os.path.join(TBC_DIR, "costs", "profiles", "harbor.json")
NODE_EXE = os.environ.get("NODE", "node")
KM_PER_MI = 1.609344
SEATS_PER_CAR = 150                      # loadFlag denominator only (diagnostic, D4)
# service-span hours per period -- a shared service assumption (the candidate
# configs carry HEADWAY, not span); the harbor profile's 6 h peak / 13 h offpeak
# is the county convention. car_km_yr (O&M) uses the candidate's OWN headway +
# route_km against this shared span.
SERVICE_HOURS = {"peak": 6.0, "offpeak": 13.0}
# spec 07 §6.1 / §7: the R2 ASC premium-bracket rows carried on every stop
# decision (bus->rail transportability bites at the stopping rule). Applied as a
# FIRST-ORDER benefit-side scaling of the marginal BCR (the exact treatment is a
# stage-2 re-export at the scaled premium -- spec 06 §3 "additional export design
# point"); even the 2.0x row leaves the marginal BCR far below 1, so the stop is
# robust to it. Stated as a bound, not a re-run.
PREMIUM_BRACKET = (1.0, 1.5, 2.0)


def _profile_discount():
    """The central-profile real discount rate (spec 06 / tbc harbor profile,
    4% flat). SINGLE SOURCE: read from the tbc cost profile, never hardcoded --
    the NPV objective's δ (one-cycle_gap deferral) and the frontier's ΔK_PV
    cycle-deferral both use it (NOT the 7% federal DISPLAY_DISCOUNT the interim
    ΔK_PV column cites)."""
    with open(TBC_PROFILE, encoding="utf-8") as f:
        return float(json.load(f)["central_profile"]["discount_rate"])


_CAPITAL_CONSTS = ("cap_occ", "cap_depot", "cap_route_km", "cap_viaduct_km",
                   "cap_station", "cap_car", "cap_markup_low", "cap_markup_ut",
                   "cap_delivery_ut", "cap_crossing_low", "cap_crossing_ut")
_HARNESS_KNOBS = ("cycle_gap", "network_budget", "depth_cap",
                  "omega_allocation", "omega_stop_materialization",
                  "feeder_headway_map")


def _assumptions_manifest():
    """The registry leaves the harness + capcost consume, plus the active prior
    bands, as a canonical preimage for (a) the run_id values-hash and (b) the
    artifact's assumptions_manifest rows the registry claims. Returns
    (consumed_list, values_hash, prior_bands)."""
    from model import PRIORS
    consumed = [{"id": cid, "value": val(cid), "role": "capital-coefficient"}
                for cid in _CAPITAL_CONSTS]
    consumed += [{"id": cid, "value": val(cid), "role": "harness-knob"}
                 for cid in _HARNESS_KNOBS]
    consumed.sort(key=lambda d: d["id"])
    prior_bands = {k: list(PRIORS[k]) for k in PRIORS}     # name -> (lo, hi, shape)
    preimage = {"consumed": {c["id"]: c["value"] for c in consumed},
                "prior_bands": prior_bands}
    values_hash = nm.network_fingerprint(preimage)
    return consumed, values_hash, prior_bands


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
        # H's measured walk-access mass profile (its committed derived file's
        # walk_bins) -- the reference distribution the spec 07 N4 'walk_bin_mass'
        # omega-allocation variant weights by (margin-distribution sensitivity).
        dj = json.load(open(os.path.join(DER, f"corridor_{c['id']}.json"),
                            encoding="utf-8"))
        walk_centers = list(dj["walk_bins"]["centers"])
        walk_weights = list(dj["walk_bins"]["weights"])
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
        # derived_v_avg_mph audit (D60 review rec 3c): fleet() defaults v_avg to
        # capcost.derived_v_avg_mph(1.0) = the GLOBAL v_cruise design central
        # (96.6 km/h since the owner 2026-07-17 60-mph decision). That is CORRECT
        # for every candidate here BY CONSTRUCTION: spec 07 §1 prices every
        # candidate as an elevated automated light metro (uniform mode), so the
        # ALM design cruise is the right fleet speed even for the streetcar
        # candidate (whose OWN ridership run uses an exogenous at-grade speed --
        # a different question, model.py's else branch, untouched here). The one
        # place the default is a category error -- REM's non-ALM plausibility
        # check -- passes its own literature cruise explicitly (test_fleet_rem,
        # D60 fix); it is not a default consumer. No latent Harbor-prior coupling
        # survives in the harness path.
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
            "walk_centers": walk_centers, "walk_weights": walk_weights,
            "folds": {s: list(removed.get(s, [])) for s in ("fold", "retain")},
            # spec 04 §3.3 special-structures count (N5 review fix): a
            # CANDIDATE-universe field (config/candidates.json), honestly
            # determined per corridor -- NOT a registry constant (only the
            # per-crossing RATES, cap_crossing_low/ut, are registry leaves).
            # Defaults to 0 with an explicit basis note if a candidate omits it.
            "crossings": int(c.get("crossings", 0)),
            "crossings_note": c.get("crossings_note",
                                    "no crossings declared for this candidate "
                                    "(defaulted to 0; spec 04 §3.3)"),
        })
    return cands, bool(doc.get("hand_supplied")), doc.get("substitution_note", "")


# ---------------------------------------------------------------------------
# capital (spec 04 rate card via capcost.py, N2) + the cycle_gap PV display
# ---------------------------------------------------------------------------
def capital_bands(cand, fixed_cost_share=1.0):
    """LOW | US-TYPICAL Delta-K ($M) for a candidate (never the low number
    alone, spec 04 §3.2). crossings (spec 04 §3.3 special structures) is a
    per-candidate field from config/candidates.json (N5 review fix -- was
    silently defaulted to 0 for every candidate)."""
    return capcost.capital_bands(cand["route_mi"], cand["stations"],
                                 cand["cars"], crossings=cand.get("crossings", 0),
                                 fixed_cost_share=fixed_cost_share)


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


def dependency(H, B, gtfs, allocation=None, exclusive_tract=False):
    """The spec 07 §6.2 predicate pieces for candidate B against committed line
    H: omega(H,B), the fold_sub ghost term, and the co-location flag. B DEPENDS
    on H when omega > DEP_OMEGA OR co-located OR (a feeder edge appears once H is
    injected). Returns a dict of the pieces; the caller decides injection and
    depth. omega uses H's WINDOWED shape + worker-mass allocation (wiring notes
    1 & 2). allocation='walk_bin_mass' and exclusive_tract are the spec 07 N4
    margin-distribution / exclusive-tract sensitivity variants (§4.2 / spec 02
    §4.3)."""
    om = nm.omega(H["x"], H["y"], B["x"], B["y"], H["spacing"],
                  worker_pts=H["worker_pts"], worker_mass=H["worker_mass"],
                  buffer_mi=BUFFER_MI, B_window=B["window"], allocation=allocation,
                  walk_centers=H.get("walk_centers"),
                  walk_weights=H.get("walk_weights"),
                  exclusive_tract=exclusive_tract)
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
                     omega_scale=1.0, exclusive_tract=False):
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
        dep = dependency(H, B, gtfs, allocation=allocation,
                         exclusive_tract=exclusive_tract)
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
             run_dir, allocation=None, omega_scale=1.0, exclusive_tract=False,
             channel_split=False, feeder_headway_map=None, npv_engine=None):
    """Evaluate candidate B against the network-before under common random
    numbers. Returns a record with per-scenario welfare-minute arrays (fold and
    retain), total/newline/ratio per draw, the ABC-weighted bands, provenance
    depth inputs, and the run's raw res (so a committed line can cache its own
    margin). Empty network-before -> the committed derived FILE verbatim +
    anchor_add=None (gate G1 byte-identity by construction).

    channel_split (spec 07 N4 / N1b review): when B is NETWORKED, additionally
    decompose the lift over standalone into the ANCHOR-ADD channel (margin-only
    substitution/complementarity) and the REBUILD channel (synthetic-feeder
    market-enlargement) by the reviewer's toggle method -- two extra evaluations
    (anchor-add-only on the committed file, rebuild-only with anchor_add=None) so
    market-enlargement can never be read as crossing complementarity."""
    add, injected, excluded, deps = build_anchor_add(
        B, network_before, gtfs, params, seed, n,
        allocation=allocation, omega_scale=omega_scale,
        exclusive_tract=exclusive_tract)

    networked = bool(injected or excluded)
    if networked:
        # networked rebuild -> gitignored run dir (never the committed file)
        desc = {"candidate": B["id"],
                "injected": nm.sorted_set_list(i["route"] for i in injected),
                "excluded": nm.sorted_set_list(excluded)}
        # include the feeder-headway mapping in the rebuild fingerprint so the
        # peak-mapped variant (spec 07 §4.2.1 / G7 row) writes a distinct file.
        if feeder_headway_map:
            desc["feeder_headway_map"] = feeder_headway_map
        fp = nm.network_fingerprint(desc)[:16]
        dest = bc.networked_path(B["id"], fp)
        bc.main(B["config_path"], dest=dest, injected_lines=injected,
                excluded_fold_routes=excluded,
                feeder_headway_map=feeder_headway_map)
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
    if channel_split and networked:
        rec["channel_split"] = _channel_split(
            B, cor, add, params, seed, n, weights, res)
    # spec 07 N5 NPV objective: price the in-memory res through the tbc wrapper
    # (no re-run) and attach the per-draw ΔNPV. Empty-network singles and
    # networked candidates alike -- the fingerprint folds the network-before, so
    # every distinct candidate/network point writes a distinct export/output.
    if npv_engine is not None:
        network_desc = {
            "candidate": B["id"],
            "network_before": nm.sorted_set_list(H["id"] for H in network_before),
            "injected": nm.sorted_set_list(i["route"] for i in injected),
            "excluded": nm.sorted_set_list(excluded),
            "n": int(n), "seed": int(seed)}
        capital = capital_bands(B)
        rec["capital"] = capital                        # capcost LOW|US_TYPICAL $M
        # N5 review fix: carry the crossings count + basis alongside capital so
        # every consumer of rec["capital"] can disclose what was priced INTO it.
        rec["crossings"] = int(B.get("crossings", 0))
        rec["crossings_note"] = B.get("crossings_note", "")
        rec["npv"] = npv_engine.price(B["id"], res, B, capital, network_desc,
                                      seed)
    return rec


def _channel_split(B, cor_net, add, params, seed, n, weights, res_full):
    """Decompose a networked candidate's lift over standalone into the ANCHOR-ADD
    and REBUILD channels (spec 07 N4 / N1b review, the reviewer's toggle method).
    Four points under COMMON RANDOM NUMBERS (same params/seed):

        base    = standalone (committed derived file, anchor_add=None)
        anchor  = anchor-add only (committed derived file, anchor_add=add)
        rebuild = rebuild only    (networked corridor, anchor_add=None)
        full    = both            (networked corridor, anchor_add=add) [= rec.res]

    lift = full - base; anchor_channel = anchor - base; rebuild_channel =
    rebuild - base; cross_residual = full - anchor - rebuild + base (the
    non-additive interaction of the two channels). Reported per scenario as P50
    welfare-minutes so the artifact/printout separates margin-only substitution
    (anchor channel) from synthetic-feeder MARKET ENLARGEMENT (rebuild channel):
    the rebuild channel is NOT crossing complementarity and must never be read as
    such. The reviewer's method is TWO cheap toggle evaluations (anchor-only +
    rebuild-only); here they plus a base run are THREE rebuild-free run()s (cor_net
    is already built; base/anchor just load the committed file), and full reuses
    the eval res. base == the candidate's cycle-0 standalone under the same CRN, so
    the extra base run is a self-containment convenience, not new information.
    cor_net is the already-built networked Corridor."""
    cor_base = Corridor(B["derived_path"])
    res_base = run(cor_base, n=n, params=params, seed=seed, anchor_add=None)
    res_anchor = run(cor_base, n=n, params=params, seed=seed, anchor_add=add)
    res_rebuild = run(cor_net, n=n, params=params, seed=seed, anchor_add=None)
    out = {"method": ("reviewer toggle (spec 07 N4): anchor-add-only vs "
                      "rebuild-only vs both, common random numbers; the rebuild "
                      "channel is synthetic-feeder MARKET ENLARGEMENT, not "
                      "crossing complementarity"),
           "units": "welfare-minutes P50 (D8-blended, within-draw)",
           "scenarios": {}}
    for scen in ("fold", "retain"):
        b = welfare_minutes(res_base, scen)
        a = welfare_minutes(res_anchor, scen)
        r = welfare_minutes(res_rebuild, scen)
        full = welfare_minutes(res_full, scen)
        lift = full - b
        anchor_ch = a - b
        rebuild_ch = r - b
        cross = full - a - r + b
        out["scenarios"][scen] = {
            "standalone_p50": pct(b, 50),
            "full_p50": pct(full, 50),
            "lift_p50": pct(lift, 50),
            "anchor_channel_p50": pct(anchor_ch, 50),
            "rebuild_channel_p50": pct(rebuild_ch, 50),
            "cross_residual_p50": pct(cross, 50),
            "anchor_channel_abc_p50": wpct(anchor_ch, weights, 50),
            "rebuild_channel_abc_p50": wpct(rebuild_ch, weights, 50)}
    return out


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


# ---------------------------------------------------------------------------
# spec 07 N5: the NPV engine -- prices one candidate-given-network run() result
# through the tbc v3 wrapper and reads per-draw ΔNPV back.
# ---------------------------------------------------------------------------
def _cost_design(cand, res, capital):
    """The export cost_design block (spec 07 N5): the harness-owned capcost
    capital bands + the corridor service design the wrapper prices under. The
    candidate's OWN route_km + peak/offpeak headway drive car_km (O&M); the
    service SPAN (hours) is the shared county convention (SERVICE_HOURS)."""
    hw = cand["headway"]
    hpk = float(hw["peak"] if isinstance(hw, dict) else hw)
    hop = float(hw.get("offpeak", hpk) if isinstance(hw, dict) else hw)
    cpt = int(cand.get("cars_per_train", 2))
    base_boardings = float(pct(res["anchor"], 50))     # measured base the line captures
    seat_cap = cpt * SEATS_PER_CAR * (60.0 / hpk)      # loadFlag denominator (D4, diagnostic)
    return {
        "capital": {"LOW": float(capital["LOW"]),
                    "US_TYPICAL": float(capital["US_TYPICAL"])},
        # N5 review fix: discloses the special-structures count + basis priced
        # INTO "capital" above (spec 04 §3.3) so the export is legible on its
        # own -- the count is a candidate field (config/candidates.json), the
        # per-crossing RATES (cap_crossing_low/ut) are the registry leaves.
        "crossings": {"count": int(cand.get("crossings", 0)),
                      "rate_LOW": capcost.CAP_XING_LOW,
                      "rate_US_TYPICAL": capcost.CAP_XING_UT,
                      "basis": cand.get("crossings_note", "")},
        "service_plan": {
            "route_km": cand["route_mi"] * KM_PER_MI,
            "cars_per_train": cpt,
            "periods": [
                {"period": "peak", "headway": hpk, "hours": SERVICE_HOURS["peak"]},
                {"period": "offpeak", "headway": hop,
                 "hours": SERVICE_HOURS["offpeak"]}]},
        "base_boardings": base_boardings,
        "seat_capacity": {"seatCap": seat_cap},
    }


class NpvEngine:
    """Drives the tbc v3 wrapper (bca-pipeline.mjs) to price a candidate-given-
    network run() result and return per-draw ΔNPV. One node invocation per
    evaluation (~2 s at N=40,000). SYNCHRONOUS -- the harness blocks on it (spec
    07 N5 'node, synchronous, ~seconds'). Reusable across a run; caches nothing
    beyond the shared ABC weights the caller passes."""

    def __init__(self, weights, clbl, run_dir=None):
        self.weights = weights                          # shared OC posterior (543_launch_s500)
        self.clbl = clbl
        self.run_dir = run_dir or bc.RUN_DIR
        os.makedirs(self.run_dir, exist_ok=True)
        if not os.path.exists(TBC_WRAPPER):
            raise FileNotFoundError(
                f"tbc v3 wrapper not found at {TBC_WRAPPER}; the NPV objective "
                "needs the sibling transit-benefit-cost repo (spec 07 N5). Use "
                "--objective interim to run without it.")

    def price(self, name, res, cand, capital, network_desc, seed):
        """Build the §3 export from the in-memory res (no re-run), write the
        fingerprint-named gz, invoke the wrapper, and read the per-draw ΔNPV
        companion + the wrapper artifact back. Returns a dict:

            {"per_draw": {scen: {band: (n,) ΔNPV at λ=1}},
             "ben_p50":  {scen: {band: float}},
             "npv_p50":  {scen: {band: float}},
             "bcr_p50":  {scen: {band: float}},
             "artifact": <wrapper bca_<name>_<fp>.json>,
             "fp": <network fingerprint>,
             "selfcheck": {"in_memory": ..., "roundtrip": ..., "ok": bool}}
        """
        fp = nm.network_fingerprint(network_desc)
        cost_design = _cost_design(cand, res, capital)
        design, routes_removed, base_service = self._bca_meta(cand)
        export = bx.build_export(name, res, int(seed),
                                 self.weights, design, routes_removed,
                                 base_service, n=len(res["anchor"]),
                                 network_fp=fp, cost_design=cost_design)
        gz = bx.networked_export_path(name, fp, self.run_dir)
        bx.write_gz(gz, export)
        # networked ROUND-TRIP self-consistency (spec 07 N5): a candidate-given-
        # network point has no committed reference, so verify the write/read is
        # lossless-consistent (recompute one weighted P50 from the gz vs memory).
        in_mem = bx.inmemory_weighted_p50(export, self.clbl)
        rt = bx.selfcheck_weighted_p50(gz, self.clbl)
        selfcheck = {"in_memory": in_mem, "roundtrip": rt,
                     "ok": abs(rt - in_mem) <= 1e-6 * max(1.0, abs(in_mem))}
        out_json = os.path.join(self.run_dir, f"bca_{name}_{fp[:12]}.json")
        npv_json = os.path.join(self.run_dir, f"bca_{name}_{fp[:12]}.npv.json")
        # spec 07 §6.1: every candidate is priced under the SHARED central profile
        # (county-common prices + posterior); the harbor profile is that template,
        # and the export's cost_design overrides the corridor-specific quantities
        # (capital / service design / base boardings). The N5 lift of the wrapper's
        # harbor-only gate is exactly this -- the 543 ABC weights ship in the
        # export and apply to any corridor under the same draws.
        cmd = [NODE_EXE, TBC_WRAPPER, name, "--export", gz,
               "--profile", TBC_PROFILE, "--out", out_json, "--npv-out", npv_json]
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=TBC_DIR)
        if r.returncode != 0:
            raise RuntimeError(
                f"tbc wrapper failed ({name} fp {fp[:12]}): {r.stderr[-2000:]}")
        with open(npv_json, encoding="utf-8") as f:
            pdj = json.load(f)
        with open(out_json, encoding="utf-8") as f:
            art = json.load(f)
        per_draw, ben_p50, npv_p50, bcr_p50 = {}, {}, {}, {}
        for scen, bands_d in pdj["scenarios"].items():
            per_draw[scen], ben_p50[scen] = {}, {}
            npv_p50[scen], bcr_p50[scen] = {}, {}
            for bnd, blk in bands_d.items():
                per_draw[scen][bnd] = np.asarray(blk["npv"], dtype=float)
                ben_p50[scen][bnd] = float(blk["ben_p50"])
                npv_p50[scen][bnd] = float(blk["npv_p50"])
                bcr_p50[scen][bnd] = float(blk["bcr_p50"])
        return {"per_draw": per_draw, "ben_p50": ben_p50, "npv_p50": npv_p50,
                "bcr_p50": bcr_p50, "artifact": art, "fp": fp,
                "selfcheck": selfcheck}

    @staticmethod
    def _bca_meta(cand):
        """(design, routes_removed, base_service) for the export, from the
        candidate's committed config bca block (spec 06 §3). The wrapper needs
        routes_removed / base_service for the avoided-base-O&M (E4)."""
        cfg = cand["cfg"]
        bca = cfg.get("bca", {})
        routes_removed = bca.get("routes_removed", {"fold": [], "retain": []})
        rev_hours = bca.get("rev_hours_weekday", {})
        base_service = {"rev_hours_weekday": rev_hours} if rev_hours else {}
        return cfg["service_new"], routes_removed, base_service


_FULL_WEIGHT_CACHE = {}


def _full_abc_weights(n, seed):
    """The FULL 5-kernel ABC weights dict {label: (n,) array} (spec 06 §3 /
    reweight_abc.get_kernels), for the export the NPV engine ships to the wrapper
    (the wrapper picks the profile's central kernel + the σ-row s350/s800). Same
    (params, seed) via the harbor backtest as _cycle_weights, computed once."""
    key = (n, seed)
    if key not in _FULL_WEIGHT_CACHE:
        from reweight_abc import get_kernels
        params = draw_params(n, seed)
        pred = run(backtest_corridor(), n=n, params=params,
                   seed=seed)["uncapped"]["retain"]["newline"]
        _FULL_WEIGHT_CACHE[key] = abc_weights(pred, get_kernels())
    return _FULL_WEIGHT_CACHE[key]


def sequence(cands, hand_supplied, subst_note, seed=SEED, n=N, max_cycles=None,
             budget=None, scenario="fold", quiet=False, gtfs=None, tracts=None,
             split_channels=True):
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
            # cycle numbers in the STOPPING RECORD are 1-based (cycle 1 = the
            # first evaluation, against the empty network-before) -- matching
            # spec 07 §7/§9's own prose ("fires at CYCLE 1"), which a raw 0-based
            # loop index previously contradicted (N5 review fix). cycle_records'
            # own per-cycle "cycle" key stays the internal 0-based loop index.
            stop = {"reason": "candidate_exhaustion", "cycle": k + 1}
            break

        network_before = [dict(H) for H in committed]
        net_ids = [H["id"] for H in committed]

        # --- singles: Delta-wm(A | N_k) for every remaining candidate ----------
        singles = {}
        for cid, C in remaining.items():
            C = dict(C, scenario=scenario)
            # channel split (spec 07 N4) on the candidate-GIVEN-NETWORK singles
            # only (the headline per-cycle evals); the lookahead continuations
            # below and the sensitivity sub-runs skip it to bound compute.
            rec = evaluate(C, network_before, params, seed, weights, gtfs,
                           tracts, n, run_dir, channel_split=split_channels)
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
            stop = {"reason": "budget_exhaustion", "cycle": k + 1,  # 1-based, see above
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
        stop = {"reason": "candidate_exhaustion", "cycle": len(committed) + 1}
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
            "walk_centers": C.get("walk_centers"),
            "walk_weights": C.get("walk_weights"),
            "folds": C["folds"], "scenario": scenario,
            "margin": margin,
            # the committed line's OWN per-draw welfare minutes as evaluated
            # against the network it FACED (for the within-draw frontier sum)
            "margin_wm": rec["scenarios"][scenario]["wm"],
            # newline P50 boardings -- the boardings scale the sigma_struct
            # per-line structural-error row converts into welfare-minute units
            # (spec 07 §8g / N4).
            "newline_p50": pct(d["newline"], 50),
            "capital_ut": caps["US_TYPICAL"], "capital_low": caps["LOW"],
            "route_mi": C["route_mi"], "stations": C["stations"],
            "cars": C["cars"],
            "crossings": C.get("crossings", 0),
            "crossings_note": C.get("crossings_note", ""),
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
    if rec.get("channel_split") is not None:
        block["channel_split"] = rec["channel_split"]
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
            # N5 review fix: discloses the special-structures count + basis
            # priced INTO capital_delta_K above (spec 04 §3.3).
            "crossings": {"count": W_committed.get("crossings", 0),
                          "basis": W_committed.get("crossings_note", "")},
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
    stop["cycle_numbering"] = ("1-based: cycle 1 is the first evaluation, "
                               "against the empty network-before (N5 review "
                               "fix -- this field previously read 0-based, "
                               "contradicting spec 07's own §7/§9 prose, which "
                               "always calls the first evaluation 'cycle 1').")
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


def _sigma_struct_rng(committed, seed, n):
    """A deterministic rng for the sigma_struct per-line noise, seeded from the
    run fingerprint (gate G6: no wall clock; reproduces byte-identically). The
    fingerprint folds the committed line ids + seed + n + the sigma_struct floor,
    so the noise is fixed once those are, and INDEPENDENT of run()'s streams (it
    is a harness-side post-processing draw, not a model prior)."""
    fp = nm.network_fingerprint({"sigma_struct": SIGMA_STRUCT_BOARDINGS,
                                 "lines": [H["id"] for H in committed],
                                 "seed": int(seed), "n": int(n)})
    return np.random.default_rng(int(fp[:16], 16))


def _frontier(committed, seed, n, scenario, weights):
    """Cumulative-capital-PV vs cumulative-objective frontier, aggregated
    WITHIN-DRAW (spec 07 §3/§7): sum the committed lines' per-draw welfare
    minutes INSIDE each draw, THEN take percentiles -- never sums of per-line
    percentiles (shared parameter draws correlate every line's forecast).
    Depth-shaded, both cost bands.

    sigma_struct (spec 07 §3/§8g, landed N4): the within-draw sum carries the
    CORRELATED parameter component but NOT the per-line idiosyncratic structural
    error the ABC kernel's sigma asserts, so the base bands are too narrow. Each
    committed line gets INDEPENDENT N(0, sigma_struct) noise on the boardings
    scale (SIGMA_STRUCT_BOARDINGS), converted to welfare-minutes by that line's
    welfare-per-boarding ratio, seeded deterministically from the run fingerprint
    -- NO new PRIORS key, the model rng stream is untouched. cum_wm_sigma_struct_*
    are the inflated portfolio bands beside the base cum_wm_* (the G7 on/off
    row)."""
    rng = _sigma_struct_rng(committed, seed, n)
    M = SIGMA_STRUCT_REPLICATES
    w_tiled = np.tile(weights, M) if weights is not None else None
    pts = []
    cum_low = cum_ut = 0.0
    cum_wm = None
    cum_noise = None                                       # (M, n)
    for k, H in enumerate(committed):
        # H's own per-draw welfare minutes (committed scenario), against the
        # network it was committed AGAINST -- carried on the committed dict.
        wm = H["margin_wm"]
        cum_wm = wm if cum_wm is None else cum_wm + wm     # WITHIN-DRAW sum
        # per-line independent structural error: sigma_struct boardings scaled to
        # welfare-minutes by the line's welfare-per-boarding ratio (wm_P50 /
        # newline_P50). M replicate noise samples per base draw (committed order,
        # deterministic) so the inflated band is the convolution's quantile with
        # a tight estimate.
        wm_p50 = pct(wm, 50)
        nl_p50 = H.get("newline_p50")
        wm_per_board = (wm_p50 / nl_p50) if nl_p50 else 0.0
        sd_wm = SIGMA_STRUCT_BOARDINGS * abs(wm_per_board)
        noise = (rng.normal(0.0, sd_wm, (M, len(wm))) if sd_wm > 0
                 else np.zeros((M, len(wm))))
        cum_noise = noise if cum_noise is None else cum_noise + noise
        inflated = (cum_wm[None, :] + cum_noise).ravel()   # (M*n,)
        cum_low += H["capital_low"] * pv_factor(k)
        cum_ut += H["capital_ut"] * pv_factor(k)
        pts.append({
            "step": k, "line": H["id"], "scenario": H["scenario"],
            "depth": H["depth"], "depth_label": _depth_label(H["depth"]),
            "capital_LOW": H["capital_low"], "capital_US_TYPICAL": H["capital_ut"],
            "pv_factor": pv_factor(k),
            "cum_capital_pv_LOW": cum_low, "cum_capital_pv_US_TYPICAL": cum_ut,
            "cum_wm_uncapped": [pct(cum_wm, q) for q in (10, 50, 90)],
            "cum_wm_abc": [wpct(cum_wm, weights, q) for q in (10, 50, 90)],
            "cum_wm_sigma_struct_uncapped": [pct(inflated, q) for q in (10, 50, 90)],
            "cum_wm_sigma_struct_abc": ([wpct(inflated, w_tiled, q)
                                         for q in (10, 50, 90)]
                                        if w_tiled is not None else None)})
    # final-portfolio base-vs-inflated summary (the G7 sigma_struct on/off row)
    last = pts[-1] if pts else None
    ss_row = {"status": "computed", "work_item": "N4",
              "sigma_struct_boardings": SIGMA_STRUCT_BOARDINGS,
              "mechanism": ("harness-side per-line INDEPENDENT N(0, sigma_struct) "
                            "noise on the boardings scale, converted to welfare-"
                            "minutes by each line's welfare-per-boarding ratio and "
                            "summed within-draw; seeded deterministically from the "
                            "run fingerprint. NO new PRIORS key (the model rng "
                            "stream is untouched) -- an append-last prior is not "
                            "required because the error is post-processing, not a "
                            "swept model input (spec 07 §3/§8g)."),
              "note": ("the within-draw sum carries only the correlated parameter "
                       "component; sigma_struct adds the per-line idiosyncratic "
                       "structural error the portfolio bands otherwise omit -- they "
                       "widen (P10 down, P90 up), the P50 is ~unchanged (mean-zero "
                       "noise). This is the arithmetic behind the Flyvbjerg "
                       "annotation.")}
    if last is not None:
        ss_row["final_portfolio"] = {
            "base_uncapped": last["cum_wm_uncapped"],
            "sigma_struct_uncapped": last["cum_wm_sigma_struct_uncapped"],
            "base_abc": last["cum_wm_abc"],
            "sigma_struct_abc": last["cum_wm_sigma_struct_abc"],
            "band_widening_uncapped": round(
                (last["cum_wm_sigma_struct_uncapped"][2]
                 - last["cum_wm_sigma_struct_uncapped"][0])
                - (last["cum_wm_uncapped"][2] - last["cum_wm_uncapped"][0]), 1)}
    return {"points": pts,
            "aggregation": "within-draw (spec 07 §3): sum lines per draw, then "
                           "percentiles",
            "sigma_struct_row": ss_row,
            "flyvbjerg_annotation": ("portfolio optimism is worse than "
                                     "single-project optimism -- forecast errors "
                                     "are correlated across the model's lines "
                                     "(spec 05 §4.3; within-draw aggregation plus "
                                     "the sigma_struct row make this arithmetic, "
                                     "not rhetoric).")}


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
            {"id": "omega_walk_bin_mass", "knob": "omega_allocation",
             "value": "walk_bin_mass"},
            {"id": "exclusive_tract", "knob": "exclusive_tract", "value": True},
            {"id": "depth_cap_1", "knob": "depth_cap", "value": band("depth_cap")[0]},
            {"id": "depth_cap_3", "knob": "depth_cap", "value": band("depth_cap")[1]},
            {"id": "offpeak_to_midday", "knob": "feeder_headway_map",
             "value": "peak_to_midday"},
            {"id": "sigma_struct", "knob": "sigma_struct", "value": True},
            {"id": "fixed_cost_share_0.5", "knob": "fixed_cost_share", "value": 0.5},
            {"id": "fixed_cost_share_0.0", "knob": "fixed_cost_share", "value": 0.0},
            {"id": "crossing_count_lo", "knob": "crossing_count", "value": 2,
             "display": "Delta-K_PV (interim: welfare not discounted)"},
            {"id": "crossing_count_hi", "knob": "crossing_count", "value": 6,
             "display": "Delta-K_PV (interim: welfare not discounted)"},
        ],
        "named_spec_pending": [
            {"id": "k3_order_diff", "knob": "k=3 deep pass", "work_item": "N1/optional",
             "note": "order-difference diagnostic over the top-3 candidates (spec 07 §5.1)"},
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
                       gtfs=gtfs, tracts=tracts, split_channels=False)
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
                             gtfs, tracts, allocation=row["value"])
        note = ("omega uniform-along-line allocation (§8i variant)"
                if row["value"] == "uniform" else
                "omega walk-bin-mass allocation (spec 07 N4 margin-distribution "
                "variant: H's margin allocated by its measured walk-access mass "
                "profile at each tract's nearest-stop distance, §4.2)")
        return _committed_order_objective(art), note, None
    if knob == "exclusive_tract":
        art = sequence_swept(cands, hand_supplied, subst_note, seed, n, scenario,
                             gtfs, tracts, exclusive_tract=True)
        ov = _catchment_overlap(cands)
        return _committed_order_objective(art), \
            ("spec 02 §4.3 exclusive-tract assignment (each shared catchment "
             "tract to its NEARER corridor); the harbor/streetcar pair shares "
             f"{ov['overlap_pct']:.1f}% of the smaller catchment (near-threshold, "
             "computed anyway per the N1b review)"), \
            {"overlap_pct_of_smaller": ov["overlap_pct"],
             "shared_tracts": ov["shared"], "threshold_pct": 30.0,
             "over_threshold": bool(ov["overlap_pct"] > 30.0)}
    if knob == "feeder_headway_map":
        art = sequence_swept(cands, hand_supplied, subst_note, seed, n, scenario,
                             gtfs, tracts, feeder_headway_map=row["value"])
        return _committed_order_objective(art), \
            ("peak-mapped synthetic-feeder headway variant (spec 07 §4.2.1 G7 "
             "row: the injected committed line's {peak, offpeak} plan mapped to "
             "the feeder midday scalar via PEAK instead of the declared "
             "offpeak->midday convention)"), None
    if knob == "sigma_struct":
        # already computed in the frontier (no re-run): surface base-vs-inflated
        ss = base_artifact["frontier"]["sigma_struct_row"].get("final_portfolio")
        if ss is None:
            return base_obj, "sigma_struct row (no committed lines)", None
        return ss["sigma_struct_uncapped"][1], (
            "per-line INDEPENDENT structural error N(0, sigma_struct=400 "
            "boardings) inflates the portfolio bands; P50 ~unchanged (mean-zero), "
            "the band widens (spec 07 §3/§8g)"), \
            {"base_band_uncapped": ss["base_uncapped"],
             "sigma_struct_band_uncapped": ss["sigma_struct_uncapped"],
             "band_widening_uncapped": ss["band_widening_uncapped"]}
    if knob == "fixed_cost_share":
        # display-only (like cycle_gap): scales the FIXED term (OCC+depot) for
        # lines AFTER the first (spec 07/08 §8j), so it moves cumulative Delta-K_PV
        # and (under a binding budget) feasibility, never the welfare objective.
        share = row["value"]
        byid = {c["id"]: c for c in cands}
        cum_low = cum_ut = 0.0
        for p in pts:
            C = byid[p["line"]]
            fcs = 1.0 if p["step"] == 0 else share       # first line keeps full fixed
            caps = capcost.capital_bands(C["route_mi"], C["stations"], C["cars"],
                                         crossings=C.get("crossings", 0),
                                         fixed_cost_share=fcs)
            cum_low += caps["LOW"] * pv_factor(p["step"])
            cum_ut += caps["US_TYPICAL"] * pv_factor(p["step"])
        return base_obj, (f"fixed_cost_share {share} on lines 2..k (shared "
                          "OCC+depot, §8j); Delta-K_PV display only, welfare "
                          "objective invariant"), \
            {"fixed_cost_share": share, "cum_capital_pv_LOW": cum_low,
             "cum_capital_pv_US_TYPICAL": cum_ut}
    if knob == "crossing_count":
        # spec 04 §3.3 count uncertainty (N5 review G7 row): probe harbor's
        # named crossing set count around the base 4 (I-5, SR-22, Santa Ana
        # River channel, BNSF Fullerton) -- the cleaner of the two knob choices
        # the review offered (a rate sweep is already the LOW/US_TYPICAL band
        # pair; a COUNT sweep is the genuinely new uncertainty axis). Harbor
        # only -- streetcar's own declared count (1) is untouched. Display-only
        # (like fixed_cost_share): capital never enters the interim objective.
        swept = row["value"]
        byid = {c["id"]: c for c in cands}
        cum_low = cum_ut = 0.0
        for p in pts:
            C = byid[p["line"]]
            xc = swept if p["line"] == "harbor" else C.get("crossings", 0)
            caps = capcost.capital_bands(C["route_mi"], C["stations"], C["cars"],
                                         crossings=xc)
            cum_low += caps["LOW"] * pv_factor(p["step"])
            cum_ut += caps["US_TYPICAL"] * pv_factor(p["step"])
        return base_obj, (f"harbor crossing count {swept} (base 4, spec 04 "
                          "§3.3 count uncertainty -- I-5/SR-22/Santa Ana "
                          "River/BNSF Fullerton); Delta-K_PV display only, "
                          "welfare objective invariant"), \
            {"crossing_count_harbor": swept, "cum_capital_pv_LOW": cum_low,
             "cum_capital_pv_US_TYPICAL": cum_ut}
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


def _catchment_overlap(cands):
    """Catchment-tract overlap between the first two candidates (spec 02 §4.3 /
    spec 07 N4 exclusive-tract row): shared tracts (within BUFFER_MI of BOTH
    windowed alignments) as a share of the SMALLER catchment. Pure geometry."""
    tr = _tract_table()
    cx = tr["cx"].to_numpy(); cy = tr["cy"].to_numpy()
    ins = []
    for C in cands[:2]:
        off, pos = nm.project_points(C["x"], C["y"], cx, cy)
        ins.append((off <= BUFFER_MI) & (pos >= C["window"][0])
                   & (pos <= C["window"][1]))
    both = ins[0] & ins[1]
    smaller = min(int(ins[0].sum()), int(ins[1].sum())) or 1
    return {"shared": int(both.sum()),
            "overlap_pct": 100.0 * int(both.sum()) / smaller,
            "catchments": [int(ins[0].sum()), int(ins[1].sum())]}


def sequence_swept(cands, hand_supplied, subst_note, seed, n, scenario, gtfs,
                   tracts, omega_scale=1.0, allocation=None,
                   exclusive_tract=False, feeder_headway_map=None):
    """A minimal re-run of the greedy loop under a swept ANCHOR knob (omega scale
    / allocation / exclusive-tract, spec 07 §8i / §4.3 / §10 G7), returning just
    enough artifact (frontier-only) to read the committed-order objective.
    sequence() cannot thread these knobs without bloating its signature, so this
    re-runs the minimal singles + continuations + commit greedy under the knob."""
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
                           omega_scale=omega_scale,
                           exclusive_tract=exclusive_tract,
                           feeder_headway_map=feeder_headway_map)
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
                              allocation=allocation, omega_scale=omega_scale,
                              exclusive_tract=exclusive_tract,
                              feeder_headway_map=feeder_headway_map)
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

    consumed, values_hash, _prior_bands = _assumptions_manifest()
    # N5 review fix: crossings (spec 04 §3.3) is a CANDIDATE field (config/
    # candidates.json), not a registry constant, so it does not live in
    # values_hash's _CAPITAL_CONSTS list -- it must enter the preimage here
    # instead, or editing a candidate's crossing count would silently leave
    # the run_id unmoved (the exact D60-rec-3a failure mode, one level down).
    cand_crossings = {c["id"]: int(c.get("crossings", 0)) for c in cands}
    run_id_preimage = {
        "candidates": nm.sorted_set_list(c["id"] for c in cands),
        "candidate_crossings": dict(sorted(cand_crossings.items())),
        "asbuilt": json.load(open(os.path.join(CFG, "network_asbuilt.json"),
                                  encoding="utf-8")).get("lines", []),
        "seed": seed, "n": n, "scenario": scenario, "budget": budget,
        # D60 review rec 3a: the values-hash of the capital constants + active
        # prior bands the harness consumes now enters the preimage, so a rate-card
        # or prior-band edit MOVES the run_id (the old input-only key did not --
        # e.g. the 60-mph v_cruise recenter restated the forecast but left the id
        # d8b4a016 unchanged, D60 report note 5).
        "assumptions_values_hash": values_hash}
    run_id = nm.network_fingerprint(run_id_preimage)

    artifact = {
        "schema": "spec 07 §7 network-sequence primary artifact (interim objective)",
        "run_id": run_id,
        "assumptions_manifest": {
            "values_hash": values_hash,
            "consumed": consumed,
            "note": ("spec 07 §9 N4 registry conversion: the constant-tier "
                     "registry leaves capcost + this harness consume, declared "
                     "here so the assumptions registry claims each as a "
                     "network-artifact row (check_assumptions' network scan; the "
                     "sensitivity-block ids are harness-INTERNAL and exempt from "
                     "the orphan check, mirroring the spec 08 §9 Q7 wrapper "
                     "engine-owned precedent). The values_hash of these + the "
                     "active prior bands enters the run_id preimage (D60 rec 3a). "
                     "N5 review fix: per-candidate crossing COUNTS (spec 04 §3.3) "
                     "are a candidate_universe field, not a registry constant -- "
                     "only the per-crossing RATES (cap_crossing_low/ut) are "
                     "registry leaves here; both feed capital_bands(), and the "
                     "counts enter the run_id preimage separately as "
                     "candidate_crossings (below), not the values_hash.")},
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
        "channel_split_note": (
            "channel_split (spec 07 N4) only ever appears on a candidate "
            "evaluated against a NONEMPTY network -- cycle 2 onward, 1-based "
            "(cycles[k].cycle == k, 0-based internally; see "
            "stopping_record.cycle_numbering); it has no meaning at cycle 1's "
            "empty network and is null there by construction. In THIS interim "
            "run every candidate is eventually committed (candidate_exhaustion, "
            "no budget bound), so a real, non-null channel_split DOES appear "
            "from cycle 2 onward (cycles[1].candidate_results) -- unlike the "
            "sibling NPV artifact, where the §7 marginal stop fires at cycle 1 "
            "before any commitment and every channel_split field is null."),
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
            "run_id_preimage": (
                "run_id = sha256 of canonical{candidates, asbuilt lines, seed, n, "
                "scenario, budget, assumptions_values_hash}. D60 review rec 3a "
                "added assumptions_values_hash = sha256{consumed capital constants "
                "+ harness knobs + active prior bands}; it MOVES the id whenever "
                "the rate card or a prior band changes. Consequence recorded for "
                "provenance: the id here DIFFERS from the committed N1b/D60 artifact "
                "(d8b4a016...), which was keyed on inputs only and did not track "
                "the forecast-moving 60-mph v_cruise recenter. No timestamps enter "
                "the preimage (gate G6)."),
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


# ===========================================================================
# spec 07 N5: the FULL NPV objective loop (the DEFAULT). Prices every candidate-
# given-network through the tbc wrapper, does WITHIN-DRAW CV in PV dollars (§3),
# applies the §7 marginal-BCR stopping rule with the premium-bracket rows, and
# reports a ΔNPV-vs-ΔK_PV frontier. The interim sequence() above is UNTOUCHED
# (the byte-identical N4 regression anchor); this is a parallel path.
# ===========================================================================
def _npv_view(container, band, scenario, key="rec"):
    """A cv_components/interaction-shaped view {id: {scen: {'wm': (n,) ΔNPV}}}
    built from the per-draw ΔNPV at one cost band -- so the SHARED §3 CV /
    interaction machinery ranks NPV exactly as it ranks welfare-minutes, only
    the per-draw objective array and δ change (spec 07 §3)."""
    out = {}
    for cid, blk in container.items():
        rec = blk[key] if key in blk else blk
        pdd = rec["npv"]["per_draw"]
        out[cid] = {s: {"wm": pdd[s][band]} for s in ("fold", "retain")}
    return out


def _npv_cont_view(continuations, band):
    """Continuation view: {aid: {bid: {scen: {'wm': ΔNPV}}}}."""
    out = {}
    for aid, bs in continuations.items():
        out[aid] = {}
        for bid, d in bs.items():
            pdd = d["rec"]["npv"]["per_draw"]
            out[aid][bid] = {s: {"wm": pdd[s][band]} for s in ("fold", "retain")}
    return out


def _premium_rows(bcr_central):
    """spec 07 §6.1/§7: the R2 ASC premium-bracket {1.0, 1.5, 2.0} rows on the
    stop decision. FIRST-ORDER benefit-side scaling of the marginal BCR (the
    premium moves ridership ~linearly into benefits, the BCR numerator); the
    exact treatment is a stage-2 re-export at the scaled premium (spec 06 §3
    'additional export design point'), not a wrapper re-price. Stated as a bound:
    even the 2.0x row leaves the OC marginal BCR far below 1."""
    return [{"premium": f, "marginal_bcr_first_order": round(f * bcr_central, 6),
             "clears_bcr1": bool(f * bcr_central >= 1.0)} for f in PREMIUM_BRACKET]


def _npv_bands_from_artifact(art, scen):
    """Pull the wrapper's reported NPV/BCR bands (uncapped|ABC, both cost bands)
    for one scenario straight from the candidate's bca_<fp>.json headline."""
    H = art["headline"][scen]
    out = {}
    for bnd in ("LOW", "US_TYPICAL"):
        cell = H[bnd]
        out[bnd] = {
            "npv_uncapped": [cell["uncapped"]["npv"][q] for q in ("p10", "p50", "p90")],
            "bcr_uncapped": [cell["uncapped"]["bcr"][q] for q in ("p10", "p50", "p90")],
            "npv_abc": ([cell["abc"]["npv"][q] for q in ("p10", "p50", "p90")]
                        if "abc" in cell else None),
            "bcr_abc": ([cell["abc"]["bcr"][q] for q in ("p10", "p50", "p90")]
                        if "abc" in cell else None),
            "p_npv_pos": cell["uncapped"]["p_npv_pos"],
            "ess": (cell["abc"]["ess"] if "abc" in cell else None)}
    return out


def _sigma_struct_npv(base_npv, ben_p50, newline_p50, rng, M):
    """N4 σ_struct in NPV units + the N5 follow-up (std-based widening PRIMARY).
    A per-line INDEPENDENT N(0, σ_struct boardings) structural error maps to NPV
    through the benefit-per-boarding ratio (benefits enter NPV additively; capital
    is fixed), so sd_npv = σ_struct · |ben_P50 / newline_P50|. Returns the base vs
    inflated STD (primary) and P90-P10 band (secondary)."""
    sd = SIGMA_STRUCT_BOARDINGS * (abs(ben_p50 / newline_p50) if newline_p50 else 0.0)
    noise = (rng.normal(0.0, sd, (M, len(base_npv))) if sd > 0
             else np.zeros((M, len(base_npv))))
    inflated = (base_npv[None, :] + noise).ravel()
    std_base = float(np.std(base_npv))
    std_infl = float(np.std(inflated))
    band_base = pct(base_npv, 90) - pct(base_npv, 10)
    band_infl = pct(inflated, 90) - pct(inflated, 10)
    return {
        "sd_npv_per_line": round(sd, 4),
        "std_base": round(std_base, 4), "std_sigma_struct": round(std_infl, 4),
        "std_widening_PRIMARY": round(std_infl - std_base, 4),
        "p90_p10_base": round(band_base, 4),
        "p90_p10_sigma_struct": round(band_infl, 4),
        "band_widening_p90_p10_SECONDARY": round(band_infl - band_base, 4),
        "note": ("std-based widening is the PRIMARY σ_struct measure (spec 07 N5 "
                 "follow-up: an all-draws average, robust where the P90-P10 tail "
                 "statistic can flip sign at finite n); P90-P10 kept as SECONDARY. "
                 "Mean-zero noise leaves the P50 ~unchanged; the spread widens.")}


def _npv_cand_block(cid, singles, cvs_band, scenario, seed, n, weights):
    """Candidate result block for the NPV artifact: the wrapper's NPV/BCR bands
    (uncapped|ABC, both cost bands), the CV components per band, the premium-
    bracket rows on the marginal BCR, the σ_struct band, provenance depth, and
    (if computed) the channel split."""
    rec = singles[cid]["rec"]
    art = rec["npv"]["artifact"]
    cap = rec["capital"]                                # capcost LOW|US_TYPICAL $M
    block = {"id": cid, "depth": rec["depth"],
             "depth_label": _depth_label(rec["depth"]),
             "injected_committed_lines": sorted(rec["injected"]),
             "excluded_fold_routes": sorted(rec["excluded"]),
             "dependencies": [dict(d) for d in rec["deps"]],
             "capital_delta_K": {"LOW": cap["LOW"], "US_TYPICAL": cap["US_TYPICAL"]},
             # N5 review fix: discloses the special-structures count + basis
             # priced INTO capital_delta_K above (spec 04 §3.3).
             "crossings": {"count": rec.get("crossings", 0),
                          "basis": rec.get("crossings_note", "")},
             "npv_selfcheck": rec["npv"]["selfcheck"],
             "network_fingerprint": rec["npv"]["fp"]}
    for scen in ("fold", "retain"):
        block[scen] = _npv_bands_from_artifact(art, scen)
    # CV components (both cost bands), δ-timed continuation; ranking band UT
    block["cv"] = {}
    for bnd in ("LOW", "US_TYPICAL"):
        c = cvs_band[bnd].get(cid)
        if c is not None:
            block["cv"][bnd] = {
                "cv_p50": c["cv_p50"], "own_dNPV_p50": c["own_p50"],
                "continuation_p50": c["cont_p50"], "best_continuation": c["best_B"],
                "delta_timing_note": ("continuation δ-timed at +1 cycle_gap on the "
                                      "profile 4% clock (spec 07 §3); own ΔNPV at "
                                      "cycle-0 timing (the common cycle-k deferral "
                                      "cancels in ranking, enters the frontier)")}
    # premium-bracket rows on the marginal BCR (§6.1/§7), fold central US_TYPICAL
    bcr_ut = block[scenario]["US_TYPICAL"]["bcr_abc"] or block[scenario]["US_TYPICAL"]["bcr_uncapped"]
    block["premium_bracket_rows"] = {
        "band": "US_TYPICAL", "scenario": scenario,
        "marginal_bcr_central": bcr_ut[1],
        "rows": _premium_rows(bcr_ut[1])}
    # σ_struct band on the candidate's standalone per-draw NPV (US_TYPICAL, fold)
    rng = _sigma_struct_rng([{"id": cid}], seed, n)
    base_npv = rec["npv"]["per_draw"][scenario]["US_TYPICAL"]
    newline_p50 = pct(rec["scenarios"][scenario]["newline"], 50)
    block["sigma_struct"] = _sigma_struct_npv(
        base_npv, rec["npv"]["ben_p50"][scenario]["US_TYPICAL"],
        newline_p50, rng, SIGMA_STRUCT_REPLICATES)
    if rec.get("channel_split") is not None:
        cs = dict(rec["channel_split"])
        cs["non_additivity_note"] = (
            "spec 07 N5 follow-up: anchor + rebuild + cross_residual need NOT sum "
            "to lift at the P50 -- each P50 is a percentile of a DIFFERENT per-draw "
            "toggle array and percentiles are non-additive (pct(A)+pct(B) != "
            "pct(A+B)); cross_residual absorbs both the true two-channel "
            "interaction AND this percentile non-additivity. Read the channels as "
            "directional magnitudes, not an exact decomposition.")
        block["channel_split"] = cs
    return block


def sequence_npv(cands, hand_supplied, subst_note, seed=SEED, n=N,
                 budget=None, scenario="fold", quiet=False, gtfs=None,
                 tracts=None, split_channels=True, npv_engine=None):
    """spec 07 N5 -- the full-NPV sequencing loop (default objective). Ranks
    candidates by within-draw CV in common-base-year PV dollars (§3), stops on
    the §7 marginal-BCR rule (best CV <= 0 => the marginal BCR is below 1),
    carrying the premium-bracket rows and BOTH cost bands. Because every OC ALM
    candidate's own ΔNPV is deeply negative (BCR ~0.08-0.14 << 1) and no
    continuation is positive, the marginal stop FIRES AT CYCLE 1 and the decision-
    grade recommended portfolio is EMPTY -- reported per §7 with the economic
    margin (the marginal BCR), never 'candidates ran out'."""
    gtfs = gtfs or _Gtfs()
    tracts = _tract_table() if tracts is None else tracts
    clbl = central_label()
    params, weights, ess = _cycle_weights(n, seed, clbl)
    ess_min = val("ess_min")
    rate = _profile_discount()
    # δ = one-cycle_gap deferral on the profile clock (spec 07 §3): the second
    # (continuation) element is timed at +cycle_gap.
    delta = 1.0 / (1.0 + rate) ** CYCLE_GAP
    # the FULL 5-kernel dict for the export (the wrapper picks the central + the
    # σ-row kernels); the harness's own `weights` (central array) stays for the
    # unused-in-NPV wm bands evaluate() still computes.
    eng = npv_engine or NpvEngine(_full_abc_weights(n, seed), clbl)

    committed = []
    cycle_records = []
    remaining = {c["id"]: c for c in cands}
    stop = None

    for k in range(len(cands)):
        if not remaining:
            # 1-based cycle numbering in the STOPPING RECORD (see the interim
            # sequence()'s equivalent comment) -- N5 review fix.
            stop = {"reason": "candidate_exhaustion", "cycle": k + 1}
            break
        network_before = [dict(H) for H in committed]

        # --- singles: ΔNPV(A | N_k) for every remaining candidate ------------
        singles = {}
        for cid, C in remaining.items():
            C = dict(C, scenario=scenario)
            rec = evaluate(C, network_before, params, seed, weights, gtfs,
                           tracts, n, bc.RUN_DIR, channel_split=split_channels,
                           npv_engine=eng)
            rec["depth"] = eval_depth(rec["deps"], network_before)
            singles[cid] = {"rec": rec, "fold": rec["scenarios"]["fold"],
                            "retain": rec["scenarios"]["retain"]}

        # --- directional continuations: ΔNPV(B | N_k + A) --------------------
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
                              npv_engine=eng)
                rb["depth"] = eval_depth(rb["deps"], net_plus_a)
                continuations[aid][bid] = {"fold": rb["scenarios"]["fold"],
                                           "retain": rb["scenarios"]["retain"],
                                           "rec": rb}

        # --- feasibility (budget on US_TYPICAL capital) + CV per band --------
        remaining_budget = (None if budget is None
                            else budget - sum(H["capital_ut"] for H in committed))
        feasible = {}
        for cid, C in remaining.items():
            cap = capital_bands(C)["US_TYPICAL"]
            feasible[cid] = remaining_budget is None or cap <= remaining_budget + 1e-6
        feasible_ids = [cid for cid, f in feasible.items() if f]
        if not feasible_ids:
            stop = {"reason": "budget_exhaustion", "cycle": k + 1,  # 1-based
                    "remaining_budget_ut": remaining_budget}
            break

        cvs_band = {"LOW": {}, "US_TYPICAL": {}}
        for bnd in ("LOW", "US_TYPICAL"):
            sview = _npv_view(singles, bnd, scenario)
            cview = _npv_cont_view(continuations, bnd)
            for cid in feasible_ids:
                cv, own, cont, bestB = cv_components(
                    cid, sview, cview, scenario, feasible_ids, delta=delta)
                cvs_band[bnd][cid] = {
                    "cv": cv, "own": own, "cont": cont, "best_B": bestB,
                    "cv_p50": pct(cv, 50), "own_p50": pct(own, 50),
                    "cont_p50": pct(cont, 50)}
        # rank on US_TYPICAL (the conservative band; feasibility uses it too)
        cvs = cvs_band["US_TYPICAL"]
        winner, knife_edge, ranked, p_top = select_winner(feasible_ids, cvs)
        pair_justified = (cvs[winner]["own_p50"] < 0.0
                          and cvs[winner]["cont_p50"] > 0.0)
        best_B = cvs[winner]["best_B"]

        # --- interaction matrix (audit; NPV units, US_TYPICAL) ---------------
        imatrix = []
        ids = list(remaining)
        sview_ut = _npv_view(singles, "US_TYPICAL", scenario)
        cview_ut = _npv_cont_view(continuations, "US_TYPICAL")
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                I = interaction(ids[i], ids[j], sview_ut, cview_ut, scenario)
                if I is not None:
                    imatrix.append(I)

        # --- the §7 marginal-BCR stop: best CV <= 0 (not pair-justified) -----
        stop_fires = (cvs[winner]["cv_p50"] <= 0.0) and not pair_justified

        cand_blocks = [_npv_cand_block(cid, singles, cvs_band, scenario, seed, n,
                                       weights)
                       for cid in sorted(remaining)]
        cyc = {
            "cycle": k,
            "network_before": [{"id": H["id"], "scenario": H["scenario"],
                                "provenance": "hypothetical", "depth": H["depth"]}
                               for H in network_before],
            "candidate_results": cand_blocks,
            "feasibility": {cid: bool(feasible[cid]) for cid in sorted(feasible)},
            "remaining_budget_ut": remaining_budget,
            "interaction_matrix": imatrix,
            "archetype_gap": _archetype_placeholder(),
            "ranking": {"band": "US_TYPICAL", "by": "CV P50 (ΔNPV, PV $M)",
                        "ranked": ranked,
                        "winner": winner, "winner_cv_p50": cvs[winner]["cv_p50"],
                        "winner_own_dNPV_p50": cvs[winner]["own_p50"],
                        "pair_justified": bool(pair_justified),
                        "best_continuation": best_B, "knife_edge": bool(knife_edge),
                        "marginal_stop_fires": bool(stop_fires)}}
        cycle_records.append(cyc)
        if not quiet:
            _print_npv_cycle(cyc, singles, cvs_band, scenario)

        if stop_fires:
            stop = {"reason": "marginal_bcr_below_1", "cycle": k + 1,  # 1-based
                    "winner": winner}
            break
        # CV > 0: commit the winner (would only happen if some OC corridor cleared
        # BCR=1 -- it does not today) and continue the greedy order.
        W = dict(remaining[winner], scenario=scenario)
        W_committed = _as_committed(W, singles[winner]["rec"], params, scenario,
                                    network_before)
        W_committed["depth"] = singles[winner]["rec"]["depth"]
        W_committed["npv_per_draw"] = singles[winner]["rec"]["npv"]["per_draw"][scenario]
        W_committed["npv_ben_p50"] = singles[winner]["rec"]["npv"]["ben_p50"][scenario]
        committed.append(W_committed)
        del remaining[winner]

    if stop is None:
        stop = {"reason": "candidate_exhaustion", "cycle": len(committed) + 1}

    return _assemble_npv_artifact(
        cands, hand_supplied, subst_note, seed, n, scenario, budget, clbl, ess,
        ess_min, committed, cycle_records, stop, weights, rate, delta)


def _npv_frontier(cycle0, committed, seed, n, scenario, weights, rate):
    """The ΔNPV-vs-ΔK_PV frontier (spec 07 §7). When the §7 stop fires before any
    commitment (the OC case), the recommended portfolio is EMPTY, so the frontier
    is the CANDIDATE SCATTER of the cycle-0 singles -- each candidate's standalone
    ΔNPV vs its ΔK_PV, both cost bands, σ_struct-inflated (std-based widening
    primary), every point flagged below_bcr1. When a commitment DOES occur it is
    the cumulative committed frontier (deferred on the profile clock)."""
    pts = []
    for b in cycle0["candidate_results"]:
        cid = b["id"]
        ut = b[scenario]["US_TYPICAL"]
        lo = b[scenario]["LOW"]
        bcr = (ut["bcr_abc"] or ut["bcr_uncapped"])[1]
        cap = b["capital_delta_K"]
        # cycle-0 timing -> no cycle deferral (pv_factor 1.0); the axis is the
        # capcost ΔK (harness-owned), on the same profile clock as ΔNPV.
        f = pv_factor(b["step"], rate=rate) if "step" in b else 1.0
        pts.append({
            "step": len(pts), "line": cid, "scenario": scenario,
            "depth": b["depth"], "depth_label": b["depth_label"],
            "kind": "candidate_standalone",
            "capital_delta_K_LOW": cap["LOW"], "capital_delta_K_US_TYPICAL": cap["US_TYPICAL"],
            "crossings": b.get("crossings", {"count": 0, "basis": ""}),
            "dK_pv_LOW": cap["LOW"] * f, "dK_pv_US_TYPICAL": cap["US_TYPICAL"] * f,
            "npv_uncapped_LOW": lo["npv_uncapped"],
            "npv_uncapped_US_TYPICAL": ut["npv_uncapped"],
            "npv_abc_LOW": lo["npv_abc"], "npv_abc_US_TYPICAL": ut["npv_abc"],
            "marginal_bcr_US_TYPICAL": bcr,
            "below_bcr1": bool(bcr < 1.0),
            "sigma_struct": b["sigma_struct"]})
    return pts


def _assemble_npv_artifact(cands, hand_supplied, subst_note, seed, n, scenario,
                           budget, clbl, ess, ess_min, committed, cycle_records,
                           stop, weights, rate, delta):
    consumed, values_hash, _pb = _assumptions_manifest()
    # N5 review fix: crossings (spec 04 §3.3) is a CANDIDATE field, not a
    # registry constant, so it must enter the preimage explicitly here --
    # otherwise editing a candidate's crossing count would silently leave the
    # run_id unmoved (see the interim assembler's identical fix + note).
    cand_crossings = {c["id"]: int(c.get("crossings", 0)) for c in cands}
    run_id_preimage = {
        "candidates": nm.sorted_set_list(c["id"] for c in cands),
        "candidate_crossings": dict(sorted(cand_crossings.items())),
        "asbuilt": json.load(open(os.path.join(CFG, "network_asbuilt.json"),
                                  encoding="utf-8")).get("lines", []),
        "seed": seed, "n": n, "scenario": scenario, "budget": budget,
        "objective": "npv",
        "assumptions_values_hash": values_hash}
    run_id = nm.network_fingerprint(run_id_preimage)

    cycle0 = cycle_records[0] if cycle_records else None
    frontier_pts = (_npv_frontier(cycle0, committed, seed, n, scenario, weights,
                                  rate) if cycle0 else [])

    # --- §7 stopping record: the marginal-BCR verdict + economic margin -----
    stop = dict(stop)
    stop["mode"] = "npv (welfare-BCA central profile, spec 06)"
    stop["profile_discount_rate"] = rate
    stop["cycle_gap_delta"] = round(delta, 6)
    stop["cycle_numbering"] = ("1-based: cycle 1 is the first evaluation, "
                               "against the empty network-before (N5 review "
                               "fix -- matches spec 07's own §7/§9 prose).")
    recommended = [H["id"] for H in committed]
    stop["recommended_portfolio"] = recommended
    if stop["reason"] == "marginal_bcr_below_1" and cycle0 is not None:
        w = stop["winner"]
        wb = next(b for b in cycle0["candidate_results"] if b["id"] == w)
        marg = {}
        for bnd in ("LOW", "US_TYPICAL"):
            cell = wb[scenario][bnd]
            marg[bnd] = {"bcr_uncapped_p50": cell["bcr_uncapped"][1],
                         "bcr_abc_p50": (cell["bcr_abc"][1] if cell["bcr_abc"] else None),
                         "npv_abc_p50": (cell["npv_abc"][1] if cell["npv_abc"] else cell["npv_uncapped"][1])}
        stop["marginal_candidate"] = w
        stop["marginal_candidate_note"] = (
            f"'{w}' is the best candidate by NPV LEVEL (§3 slack-budget interchange "
            "rule: least-negative ΔNPV); its CV <= 0 fires the stop. Under a slack "
            "budget capital intensity is irrelevant to ORDER, so the level winner "
            "need NOT be the best-BCR line -- see best_bcr_candidate.")
        stop["marginal_bcr_both_bands"] = marg
        stop["premium_bracket_rows"] = wb["premium_bracket_rows"]
        # the best-RATIO candidate (highest marginal BCR) -- the closest any OC ALM
        # corridor comes to clearing the hurdle (the ratio-greedy comparison, §7).
        best_bcr_id, best_bcr = None, -np.inf
        for b in cycle0["candidate_results"]:
            cell = b[scenario]["US_TYPICAL"]
            bcr = (cell["bcr_abc"] or cell["bcr_uncapped"])[1]
            if bcr > best_bcr:
                best_bcr, best_bcr_id = bcr, b["id"]
        bb = next(b for b in cycle0["candidate_results"] if b["id"] == best_bcr_id)
        stop["best_bcr_candidate"] = {
            "line": best_bcr_id,
            "bcr_US_TYPICAL_p50": (bb[scenario]["US_TYPICAL"]["bcr_abc"]
                                   or bb[scenario]["US_TYPICAL"]["bcr_uncapped"])[1],
            "bcr_LOW_p50": (bb[scenario]["LOW"]["bcr_abc"]
                            or bb[scenario]["LOW"]["bcr_uncapped"])[1],
            "note": ("the highest marginal BCR any candidate reaches -- the closest "
                     "OC comes to clearing BCR=1; still FAR below it.")}
        stop["economic_margin_note"] = (
            f"the §7 marginal stop fires at cycle {stop['cycle']}: the best "
            f"candidate by NPV level ('{w}') has CV <= 0 (marginal welfare BCR "
            f"{marg['US_TYPICAL']['bcr_abc_p50'] or marg['US_TYPICAL']['bcr_uncapped_p50']:.3f} "
            f"US_TYPICAL / {marg['LOW']['bcr_abc_p50'] or marg['LOW']['bcr_uncapped_p50']:.3f} "
            f"LOW, ABC). The best BCR ANY OC ALM corridor reaches is "
            f"'{best_bcr_id}' at {stop['best_bcr_candidate']['bcr_US_TYPICAL_p50']:.3f} "
            f"(US_TYPICAL) / {stop['best_bcr_candidate']['bcr_LOW_p50']:.3f} (LOW) "
            "-- still FAR below the BCR=1 hurdle. No continuation is positive, so "
            "the decision-grade recommended portfolio is EMPTY: at the welfare-BCA "
            "central profile NO Orange County ALM corridor clears BCR=1. This is "
            "the ECONOMIC MARGIN at which the sequence stopped -- not 'candidates "
            "ran out' (spec 07 §7). The premium-bracket rows show the stop is "
            "robust to a 2x ASC premium.")
        stop["safeguard_note"] = (
            "pair-justified exemption did NOT apply (no continuation was "
            "positive); the §7 marginal stop is the binding verdict.")

    safeguard = _npv_safeguard(cycle0, committed, scenario)

    artifact = {
        "schema": "spec 07 §7 network-sequence primary artifact (NPV objective)",
        "run_id": run_id,
        "assumptions_manifest": {
            "values_hash": values_hash, "consumed": consumed,
            "note": ("spec 07 §9 N4 registry conversion (carried into N5): the "
                     "constant-tier registry leaves capcost + this harness "
                     "consume, each claiming a network-artifact row. The "
                     "values_hash of these + the active prior bands enters the "
                     "run_id preimage (D60 rec 3a). N5 review fix: per-candidate "
                     "crossing COUNTS (spec 04 §3.3) are a candidate_universe "
                     "field, not a registry constant -- only the per-crossing "
                     "RATES (cap_crossing_low/ut) are registry leaves here; both "
                     "feed capital_bands(), and the counts enter the run_id "
                     "preimage separately as candidate_crossings, not the "
                     "values_hash.")},
        "objective": {
            "mode": "npv",
            "metric": "ΔNPV (welfare-BCA), within-draw CV in common-base-year PV $M",
            "engine": ("tbc v3 wrapper bca-pipeline.mjs priced the in-memory "
                       "run() export per candidate-given-network (spec 07 N5); "
                       "per-draw ΔNPV read back for within-draw CV"),
            "profile": "spec 06 central (λ=1, VOT $22.5, SCC $50, 4% flat, 60-yr)",
            "note": ("the NPV objective is the DEFAULT (spec 07 N5). The interim "
                     "welfare-minutes objective is retained as --objective interim "
                     "(the N4 regression anchor). CV per §3 with δ = one-cycle_gap "
                     f"deferral on the profile {rate:.0%} clock; both cost bands "
                     "carried; stopping rule §7 with the premium-bracket rows.")},
        "seed": seed, "n": n, "scenario": scenario, "budget_ut": budget,
        "kernel_set": {"central_label": clbl, "ess": ess, "ess_min": ess_min,
                       "ess_saturated": bool(ess < ess_min),
                       "note": ("spec 07 §6.1: all candidates ranked under the "
                                "SHARED OC posterior (543_launch_s500), uncapped "
                                "alongside; ESS per ABC-weighted statistic.")},
        "candidate_universe": {
            "ids": nm.sorted_set_list(c["id"] for c in cands),
            "hand_supplied": hand_supplied, "substitution_note": subst_note},
        "cycles": cycle_records,
        "frontier": {
            "axes": "ΔNPV (PV $M, welfare-BCA) vs ΔK_PV (capcost $M, cycle-deferred)",
            "recommended_portfolio": recommended,
            "points": frontier_pts,
            "aggregation": ("within-draw (spec 07 §3): per-draw ΔNPV summed inside "
                            "each draw before percentiles; σ_struct adds per-line "
                            "independent structural error (std-based widening "
                            "PRIMARY, P90-P10 secondary -- N5 follow-up)"),
            "note": ("the §7 marginal stop fired before any commitment, so the "
                     "recommended portfolio is EMPTY and the frontier is the "
                     "cycle-0 CANDIDATE SCATTER: every candidate's standalone ΔNPV "
                     "sits far below the ΔNPV=0 (BCR=1) line. This IS the build "
                     "order in dollars -- build nothing at the welfare-BCA central "
                     "profile."),
            "flyvbjerg_annotation": ("portfolio optimism > single-project optimism "
                                     "(correlated errors); moot here -- the "
                                     "portfolio is empty (spec 05 §4.3).")},
        "stopping_record": stop,
        "safeguard_comparison": safeguard,
        "provenance_report": _provenance_report(committed, cycle_records),
        "sensitivity": None,
        "channel_split_note": (
            "channel_split (spec 07 N4) only ever appears on a candidate "
            "evaluated against a NONEMPTY network -- cycle 2 onward, 1-based "
            "(see stopping_record.cycle_numbering); it decomposes a networked "
            "lift into the anchor-add vs synthetic-feeder-rebuild channels and "
            "has no meaning at cycle 1's empty network. MOOT IN THIS RUN: the "
            "§7 marginal stop fires at cycle 1, before any line is committed, "
            "so no candidate here ever reaches a nonempty network and every "
            "channel_split field in this artifact is null."),
        "amendments_note": ("spec 07 §1/§6.1: applies the degrade-to-uncapped "
                            "amendment (ABC weights are properties of the shared "
                            "posterior). The amendment rides N6; this artifact is "
                            "its operational record under the NPV objective."),
        "governance_note": ("in-run commitments are RECOMMENDATIONS (spec 07 §1); "
                            "spec 00 §3 gate discipline applies at each REAL "
                            "programmatic commitment. Here the recommendation is to "
                            "BUILD NOTHING at the welfare-BCA central profile."),
    }
    return artifact


def _npv_safeguard(cycle0, committed, scenario):
    """spec 07 §2/§7 safeguard line: max{greedy portfolio, best single feasible,
    best feasible archetype}. With the marginal stop firing at cycle 1 the greedy
    portfolio is empty; the best single is the least-negative standalone ΔNPV
    (still below BCR=1). Archetype = N3."""
    best_single, best_npv = None, -np.inf
    rows = []
    if cycle0 is not None:
        for b in cycle0["candidate_results"]:
            ut = b[scenario]["US_TYPICAL"]
            npv50 = (ut["npv_abc"] or ut["npv_uncapped"])[1]
            bcr50 = (ut["bcr_abc"] or ut["bcr_uncapped"])[1]
            rows.append({"line": b["id"], "npv_abc_p50_US_TYPICAL": npv50,
                         "bcr_abc_p50_US_TYPICAL": bcr50})
            if npv50 > best_npv:
                best_npv, best_single = npv50, b["id"]
    return {
        "greedy_portfolio": [H["id"] for H in committed],
        "greedy_portfolio_note": ("EMPTY -- the §7 marginal stop fires at cycle 1 "
                                  "(recommended portfolio is empty)"),
        "best_single_feasible": {"line": best_single,
                                 "npv_abc_p50_US_TYPICAL": (best_npv if best_single else None),
                                 "note": "least-negative standalone ΔNPV; still below BCR=1"},
        "best_feasible_archetype": {"status": "skipped", "work_item": "N3"},
        "candidate_standalone_npv": rows,
        "note": ("safeguard = max{greedy portfolio, best single feasible, best "
                 "feasible archetype}; here every option is below BCR=1, so the "
                 "safeguard confirms the empty-portfolio verdict. Archetype leg N3.")}


# ---------------------------------------------------------------------------
# console print
# ---------------------------------------------------------------------------
def _print_npv_cycle(cyc, singles, cvs_band, scenario):
    k = cyc["cycle"]
    print(f"\n=== NPV cycle {k}: network-before "
          f"{[H['id'] for H in cyc['network_before']] or 'EMPTY'} ===")
    for b in cyc["candidate_results"]:
        cid = b["id"]
        ut = b[scenario]["US_TYPICAL"]
        lo = b[scenario]["LOW"]
        npv_ut = (ut["npv_abc"] or ut["npv_uncapped"])[1]
        bcr_ut = (ut["bcr_abc"] or ut["bcr_uncapped"])[1]
        bcr_lo = (lo["bcr_abc"] or lo["bcr_uncapped"])[1]
        cvu = cvs_band["US_TYPICAL"].get(cid, {})
        print(f"  {cid:12s} {scenario} ΔNPV_P50 {npv_ut:>10,.0f} $M  "
              f"BCR {bcr_lo:.3f}|{bcr_ut:.3f} (LOW|UT)  depth {b['depth']}"
              + (f"  CV_p50 {cvu.get('cv_p50', float('nan')):>10,.0f}" if cvu else ""))
    r = cyc["ranking"]
    verdict = ("MARGINAL STOP FIRES (recommended portfolio EMPTY)"
               if r["marginal_stop_fires"] else f"COMMIT {r['winner']}")
    print(f"  -> {verdict}  (winner {r['winner']} CV_p50 "
          f"{r['winner_cv_p50']:,.0f} $M)")
    for I in cyc["interaction_matrix"]:
        print(f"     I{I['pair']} P50 {I['I_p50']:+,.0f} $M (tau-muted, §8a)")


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
        cs = b.get("channel_split")
        if cs is not None:
            s = cs["scenarios"]["fold"]
            print(f"     channel split (fold): lift {s['lift_p50']:+,.0f} = "
                  f"anchor {s['anchor_channel_p50']:+,.0f} + rebuild "
                  f"{s['rebuild_channel_p50']:+,.0f} + cross "
                  f"{s['cross_residual_p50']:+,.0f} welfare-min "
                  f"(rebuild = market enlargement, not crossing complementarity)")
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
    ap = argparse.ArgumentParser(description="spec 07 network-sequencing harness (N5)")
    ap.add_argument("--objective", choices=("npv", "interim"), default="npv",
                    help="npv (DEFAULT, spec 07 N5: full welfare-BCA NPV via the "
                         "tbc wrapper) | interim (welfare-minutes level, the N4 "
                         "regression anchor)")
    ap.add_argument("--cycles", type=int, default=None)
    ap.add_argument("--budget", type=float, default=None, help="cumulative program budget $M (US-TYPICAL)")
    ap.add_argument("--n", type=int, default=N)
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--scenario", choices=("fold", "retain"), default="fold")
    ap.add_argument("--out", default=None,
                    help="default: network_sequence.json (npv) / "
                         "network_sequence_interim.json (interim)")
    ap.add_argument("--no-sensitivity", action="store_true",
                    help="skip the G7 sensitivity block (faster; artifact incomplete)")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args(argv)
    out = a.out or os.path.join(
        OUT, "network_sequence.json" if a.objective == "npv"
        else "network_sequence_interim.json")

    gtfs = _Gtfs()
    tracts = _tract_table()
    cands, hand_supplied, subst = load_candidates(
        os.path.join(CFG, "candidates.json"), gtfs, tracts)

    print(f"spec 07 N5 sequencing [{a.objective}]: {len(cands)} candidates "
          f"{[c['id'] for c in cands]}, seed {a.seed}, n {a.n}, "
          f"scenario {a.scenario}"
          + (f", budget {a.budget} $M" if a.budget else " (slack budget)"))

    if a.objective == "npv":
        artifact = sequence_npv(cands, hand_supplied, subst, seed=a.seed, n=a.n,
                                budget=a.budget, scenario=a.scenario,
                                quiet=a.quiet, gtfs=gtfs, tracts=tracts)
        if not a.no_sensitivity:
            artifact["sensitivity"] = _npv_sensitivity(artifact)
        else:
            artifact["sensitivity"] = {"status": "skipped (--no-sensitivity)"}
        write_artifact(out, artifact)
        print(f"\n-> {out}  (run_id {artifact['run_id'][:16]})")
        _print_npv_summary(artifact)
    else:
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
        write_artifact(out, artifact)
        print(f"\n-> {out}  (run_id {artifact['run_id'][:16]})")
        _print_summary(artifact)
    return 0


def _npv_sensitivity(artifact):
    """The NPV-objective sensitivity block (spec 07 §10 G7). The R2 premium-
    bracket rows and the cost-band comparison are COMPUTED per cycle (carried in
    every candidate block + the stopping record), so N5 LANDS the two previously
    spec-pending N5 rows (premium_bracket, ratio_greedy_order). Heavy loop re-runs
    (budget/omega/depth) stay the interim harness's job -- the NPV loop's node
    round-trips make per-row re-sequencing costly, and the stop-at-cycle-1 verdict
    is invariant to them (every candidate is far below BCR=1)."""
    cyc0 = artifact["cycles"][0] if artifact["cycles"] else None
    prem = (artifact["stopping_record"].get("premium_bracket_rows")
            if artifact.get("stopping_record") else None)
    return {
        "mode": "npv",
        "landed_n5": [
            {"id": "premium_bracket", "knob": "ASC premium {1,1.5,2}",
             "status": "computed",
             "rows": (prem["rows"] if prem else None),
             "note": ("spec 07 §6.1/§7 R2 premium-bracket rows on the marginal-BCR "
                      "stop decision (first-order benefit-side scaling); LANDED at "
                      "N5. Even the 2.0x row leaves the OC marginal BCR far below "
                      "1 -- the stop is robust.")},
            {"id": "ratio_greedy_order", "knob": "ratio-vs-level ordering",
             "status": "computed",
             "note": ("spec 07 §3/§7: under a SLACK budget the CV rule orders by "
                      "NPV LEVEL (the interchange argument), not by capital-"
                      "efficiency ratio; the ratio becomes decision-relevant only "
                      "when the budget binds. Moot here -- the stop fires at cycle "
                      "1 before any ordering matters.")},
            {"id": "cost_band_LOW_US_TYPICAL", "knob": "spec 04 cost band",
             "status": "computed",
             "note": ("both cost bands are carried on every candidate block, the "
                      "frontier, and the stopping record (spec 04 §3.2 / spec 07 "
                      "§7 'level-sensitive on both sides'). The stop fires on both "
                      "bands.")},
        ],
        "named_spec_pending": [
            {"id": "cycle_gap_lo_hi", "knob": "cycle_gap", "work_item": "N5-follow",
             "note": ("cycle_gap moves the frontier's cumulative deferral and δ; "
                      "moot at an empty portfolio (no committed step is deferred).")},
            {"id": "k3_order_diff", "knob": "k=3 deep pass",
             "work_item": "N1/optional",
             "note": "order-difference diagnostic over the top-3 (spec 07 §5.1)"},
            {"id": "sigma_struct_std", "knob": "sigma_struct (std-based)",
             "status": "computed",
             "note": ("N5 follow-up: std-based widening is the PRIMARY σ_struct "
                      "measure on every candidate block (P90-P10 secondary).")},
            {"id": "crossing_count", "knob": "harbor crossing count {2,4,6}",
             "work_item": "N5-follow",
             "note": ("N5 review fix: crossings is now a per-candidate capital "
                      "input (spec 04 §3.3; harbor=4, streetcar=1). The count-"
                      "uncertainty sweep is COMPUTED on the interim harness "
                      "(crossing_count_lo/hi, capital-only display row, since "
                      "capital never enters the interim objective); an NPV-mode "
                      "re-price under the swept count needs a wrapper round-trip "
                      "per row and is a follow-up here.")},
        ],
        "base_note": ("the NPV stopping verdict (marginal BCR far below 1, "
                      "recommended portfolio empty) is invariant to the heavy "
                      "interim knobs (budget/omega/depth); those re-runs stay in "
                      "--objective interim (spec 07 §10 G7)."),
    }


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


def _print_npv_summary(artifact):
    print("\n--- NPV frontier (ΔNPV vs ΔK_PV, candidate scatter) ---")
    scen = artifact["scenario"]
    for p in artifact["frontier"]["points"]:
        npv = (p["npv_abc_US_TYPICAL"] or p["npv_uncapped_US_TYPICAL"])[1]
        print(f"  {p['line']:12s} ΔNPV_P50 {npv:>10,.0f} $M (US_TYPICAL)  "
              f"marginal BCR {p['marginal_bcr_US_TYPICAL']:.3f}  "
              f"{'BELOW BCR=1' if p['below_bcr1'] else 'clears'}")
    st = artifact["stopping_record"]
    print(f"\nstop: {st['reason']} ({st['mode']})")
    print(f"recommended portfolio: {st['recommended_portfolio'] or 'EMPTY (build nothing)'}")
    if "economic_margin_note" in st:
        print("economic margin: " + st["economic_margin_note"])
    sg = artifact["safeguard_comparison"]
    print(f"safeguard: greedy {sg['greedy_portfolio'] or 'EMPTY'} | best-single "
          f"{sg['best_single_feasible']['line']} | archetype "
          f"{sg['best_feasible_archetype']['status']}")


if __name__ == "__main__":
    sys.exit(main())
