"""v2.1 stage-1 screen predictor machinery (spec 01 §9.1-§9.3; phase 2a).

Block-resolution, vintage-matched successor to screen_common.py's tract
machinery. ONE function -- compute_predictors_v21(data, proj, w0, w1,
vintage) -- computes the §9.1 predictor vector for one window of one shape:

    l_flows    log1p(LODES8 both-ends-in block O-D flows in catchment)   b1
    l_zveh_hh  log1p(ACS B25044 zero-vehicle HOUSEHOLDS, owner E003 +
               renter E010, in catchment)                                b2
    l_rvh      PASSTHROUGH SLOT: log(annual revenue hours) when the
               caller supplies rvh, else None -- RVH is a route-year
               attribute of the fit-side table (phase 2b), never
               geometry, so this module only carries the slot            b3
    l_genjobs  log1p(LODES8 WAC generator jobs: the val("gen_jobs_naics")
               columns CNS15+16+17+18 = NAICS 61/62/71/72, TechDoc8.3)   b4
    l_len      log(window length mi)                                     b5

plus the §9.1 swap-row RAW inputs (the phase-2b fit layer owns their
transforms): popden (B01003 population / ALAND sq-mi in catchment),
e016 / e002 (legacy B08141 sums), gen_dummy / gen_types (geometric,
config/special_generators.json -- the gen_dummy_swap row input).

Catchment v2.1 (§9.2): a census BLOCK is in the catchment iff its INTERNAL
POINT's |offset| <= buffer (val("buffer_mi") unless a sensitivity row passes
another) AND its projected position lies in [w0, w1], with [w0, w1] clipped
to the shape's [0, L]. Inclusive bounds, identical to the v2.0 tract rule.
LODES flows are BOTH-ends-in; intra-block rows (h == w) included.

Vintage plumbing (§9.3): each boardings year gets its own predictor vintage
-- fy2017 -> LODES 2017 / ACS 2013-17; fy2019 and fy2020q3 -> LODES 2019 /
ACS 2015-19; the scan -> LODES 2022 / ACS 2019-23. resolve_vintage() is the
single dispatch table.

Tract -> block apportionment (documented honestly): ACS tables are published
at TRACT level; per-block values are tract totals apportioned by 2020
DECENNIAL BLOCK POPULATION within the tract (PL 94-171 P1 via oc_blocks.csv)
-- the same 2020 weights for EVERY ACS vintage, because no block-level
population exists on the 2020 frame for 2017/2019. Tracts whose blocks sum
to zero population split equally across their blocks. The 2013-17 and
2015-19 tables are additionally published on 2010 TRACT geography, so they
are first bridged 2010-tract -> 2020-tract through the committed
oc_tract10_to_tract20.csv shares (pop-land overlap estimator: exact for 1:1
tracts and pure splits, a uniform-density-within-2020-tract approximation
for merges/complex -- the OC mix is 292 1:1 / 7 split / 107 merge / 188
complex, printed by acs_vintage_build.py). Every stage conserves tract
totals by construction. This is a stated approximation of the §9.2 rule's
input side, not a hidden one.

PRE-REGISTRATION HOLD (spec 01 §9): NO FIT LIVES IN THIS MODULE. It computes
input-side predictor vectors only; nothing here reads boardings, joins
predictors to outcomes, or estimates anything. Fitting stays in screen_fit
(v2.0) until phase 2b runs the pre-registered rebuild -- test_screen_v21.py
carries a standing guard test on this.
"""
import gzip
import json
import math
import os

import numpy as np

from assumptions import val
from build_corridor import Line                       # geo frame single-source
from screen_common import MI_LAT, MI_LON, project_points, window_starts

__all__ = ["VINTAGES", "resolve_vintage", "apportion_to_blocks",
           "apply_bridge", "ShapeProjV21", "CatchmentViewV21",
           "ScreenDataV21", "compute_predictors_v21", "load_data_v21",
           "window_starts", "MI_LAT", "MI_LON", "SQM_PER_SQMI"]

SQM_PER_SQMI = 1609.344 ** 2                 # ALAND20 m^2 -> sq mi

# §9.3 vintage-match table: boardings-year label -> table vintages.
VINTAGES = {
    "fy2017":   {"od": "2017", "wac": "2017", "acs": "2017"},
    "fy2019":   {"od": "2019", "wac": "2019", "acs": "2019"},
    "fy2020q3": {"od": "2019", "wac": "2019", "acs": "2019"},
    "scan":     {"od": "2022", "wac": "2022", "acs": "2023"},
}


def resolve_vintage(label):
    """§9.3 dispatch: 'fy2017'/'fy2019'/'fy2020q3'/'scan' -> vintage dict.
    Unknown labels raise (no silent fallback vintage)."""
    if label not in VINTAGES:
        raise KeyError(f"unknown vintage label {label!r}; "
                       f"expected one of {sorted(VINTAGES)}")
    return dict(VINTAGES[label])


# ---------------------------------------------------------------------------
# tract -> block apportionment
# ---------------------------------------------------------------------------
def apportion_to_blocks(tract_vals, block_tract, block_pop):
    """Apportion {tract_id: value} to blocks by 2020 block population within
    each tract; zero-total-population tracts split equally across their
    blocks. Conserves each tract's total exactly (for tracts that have at
    least one block in `block_tract`; tract ids with no blocks contribute
    nothing and are the caller's coverage concern). Returns a float array
    aligned to `block_tract`."""
    block_tract = list(block_tract)
    block_pop = np.asarray(block_pop, float)
    tract_pop, tract_n = {}, {}
    for t, p in zip(block_tract, block_pop):
        tract_pop[t] = tract_pop.get(t, 0.0) + p
        tract_n[t] = tract_n.get(t, 0) + 1
    out = np.zeros(len(block_tract))
    for i, t in enumerate(block_tract):
        v = tract_vals.get(t)
        if not v:
            continue
        if tract_pop[t] > 0:
            out[i] = v * block_pop[i] / tract_pop[t]
        else:
            out[i] = v / tract_n[t]
    return out


def apply_bridge(t10_vals, bridge_rows):
    """{tract10: value} -> {tract20: value} through (tract10, tract20, share)
    rows (oc_tract10_to_tract20.csv). Shares sum to 1 per tract10, so tract10
    totals are conserved over the covered tract20 set."""
    out = {}
    for t10, t20, share in bridge_rows:
        v = t10_vals.get(t10)
        if v:
            out[t20] = out.get(t20, 0.0) + v * float(share)
    return out


# ---------------------------------------------------------------------------
# geometry (block internal points; same projection math as v2.0)
# ---------------------------------------------------------------------------
class ShapeProjV21:
    """Per-shape precompute: ONE Line + block/generator projections.
    Buffer- and vintage-independent, so every sensitivity row and every
    vintage reuses it."""

    def __init__(self, route_id, x, y, block_xy, gen_xy=((), ()),
                 gen_types=()):
        self.route_id = str(route_id)
        self.line = Line(np.asarray(x, float), np.asarray(y, float))
        self.L = float(self.line.L)
        self.b_off, self.b_pos = project_points(self.line, *block_xy)
        self.g_off, self.g_pos = project_points(self.line, *gen_xy)
        self.g_types = list(gen_types)


class CatchmentViewV21:
    """A (shape, buffer, OD-vintage) view: in-buffer block mask + the
    both-ends-in-buffer LODES block-pair subset (window predicate per call)."""

    def __init__(self, proj, buffer_mi, od_h, od_w, od_n):
        self.proj = proj
        self.buffer_mi = float(buffer_mi)
        self.inbuf = proj.b_off <= self.buffer_mi
        od_h = np.asarray(od_h, int)
        od_w = np.asarray(od_w, int)
        m = self.inbuf[od_h] & self.inbuf[od_w]
        hpos = proj.b_pos[od_h[m]]
        wpos = proj.b_pos[od_w[m]]
        self.od_lo = np.minimum(hpos, wpos)
        self.od_hi = np.maximum(hpos, wpos)
        self.od_n = np.asarray(od_n, float)[m]
        self.g_in = proj.g_off <= self.buffer_mi


# ---------------------------------------------------------------------------
# data container
# ---------------------------------------------------------------------------
class ScreenDataV21:
    """All v2.1 predictor inputs on the common 2020-block frame.

    geoids     block GEOID20 list (defines the block index)
    bx, by     block internal points in the mi frame
    aland_sqmi per-block land area
    pop2020    per-block decennial population (apportionment weights)
    acs        {acs_vintage: {"zveh": arr, "pop": arr, "e016": arr,
                "e002": arr}} per-block apportioned values
    od         {od_vintage: (od_h, od_w, od_n)} block-index arrays
    genjobs    {wac_vintage: arr} per-block CNS15+16+17+18
    gx, gy, gtypes   special-generator sites (config, judgment data)
    """

    def __init__(self, geoids, bx, by, aland_sqmi, pop2020, acs, od,
                 genjobs, gx=(), gy=(), gtypes=()):
        self.geoids = list(geoids)
        self.bx = np.asarray(bx, float)
        self.by = np.asarray(by, float)
        self.aland_sqmi = np.asarray(aland_sqmi, float)
        self.pop2020 = np.asarray(pop2020, float)
        self.acs = acs
        self.od = od
        self.genjobs = {k: np.asarray(v, float) for k, v in genjobs.items()}
        self.gx = np.asarray(gx, float)
        self.gy = np.asarray(gy, float)
        self.gtypes = list(gtypes)
        self._views = {}

    def proj(self, route_id, x, y):
        return ShapeProjV21(route_id, x, y, (self.bx, self.by),
                            (self.gx, self.gy), self.gtypes)

    def view(self, proj, od_vintage, buffer_mi):
        """Cached per (shape, buffer, OD vintage)."""
        key = (proj.route_id, float(buffer_mi), od_vintage)
        v = self._views.get(key)
        if v is None or v.proj is not proj:
            od_h, od_w, od_n = self.od[od_vintage]
            v = CatchmentViewV21(proj, buffer_mi, od_h, od_w, od_n)
            self._views[key] = v
        return v


# ---------------------------------------------------------------------------
# THE shared predictor computation (fit side 2b == scan side, one function)
# ---------------------------------------------------------------------------
def compute_predictors_v21(data, proj, w0, w1, vintage, rvh=None,
                           buffer_mi=None):
    """§9.1 predictor vector for window [w0, w1] of `proj` at `vintage`
    (a resolve_vintage label). Returns the log-form headline slots
    {l_flows, l_zveh_hh, l_rvh, l_genjobs, l_len}, the raw swap-row inputs
    (popden, e016, e002, gen_dummy/gen_types), the raw catchment sums and
    block_idx (diagnostics), and the resolved vintage dict. `rvh` is the
    b3 passthrough: l_rvh = log(rvh) when given, else None."""
    vin = resolve_vintage(vintage)
    if buffer_mi is None:
        buffer_mi = val("buffer_mi")
    w0c = max(0.0, float(w0))
    w1c = min(proj.L, float(w1))
    if not w1c > w0c:
        raise ValueError(f"empty window [{w0}, {w1}] clipped to "
                         f"[{w0c}, {w1c}] on shape of length {proj.L}")
    view = data.view(proj, vin["od"], buffer_mi)

    inwin = view.inbuf & (proj.b_pos >= w0c) & (proj.b_pos <= w1c)
    block_idx = np.flatnonzero(inwin)
    flows = float(view.od_n[(view.od_lo >= w0c) & (view.od_hi <= w1c)].sum())

    acs = data.acs[vin["acs"]]
    zveh = float(acs["zveh"][block_idx].sum())
    pop = float(acs["pop"][block_idx].sum())
    e016 = float(acs["e016"][block_idx].sum())
    e002 = float(acs["e002"][block_idx].sum())
    genjobs = float(data.genjobs[vin["wac"]][block_idx].sum())
    aland = float(data.aland_sqmi[block_idx].sum())
    popden = pop / aland if aland > 0 else 0.0

    gmask = view.g_in & (proj.g_pos >= w0c) & (proj.g_pos <= w1c)
    gen_types = sorted({proj.g_types[i] for i in np.flatnonzero(gmask)})

    if rvh is not None and not rvh > 0:
        raise ValueError(f"rvh passthrough must be positive, got {rvh!r}")
    return {
        # §9.1 headline slots (log form; zero handling = log1p, the
        # screen_common documented rule)
        "l_flows": math.log1p(flows),
        "l_zveh_hh": math.log1p(zveh),
        "l_rvh": (math.log(rvh) if rvh is not None else None),
        "l_genjobs": math.log1p(genjobs),
        "l_len": math.log(w1c - w0c),
        # swap-row inputs (raw; the 2b fit layer owns their transforms)
        "popden": popden,
        "e016": e016,
        "e002": e002,
        "gen_dummy": 1 if gmask.any() else 0,
        "gen_types": gen_types,
        # raw sums + membership (diagnostics / tests)
        "flows": flows,
        "zveh_hh": zveh,
        "genjobs": genjobs,
        "pop": pop,
        "aland_sqmi": aland,
        "block_idx": block_idx,
        "window_mi": w1c - w0c,
        "vintage": vin,
    }


# ---------------------------------------------------------------------------
# loader (INPUT-SIDE real-data path; never touches boardings)
# ---------------------------------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))
DER = os.path.join(HERE, "..", "data", "derived")
CFGDIR = os.path.join(HERE, "..", "config")

_ACS_FILES = {          # acs_vintage -> (b25044, b01003, b08141, geography)
    "2017": ("oc_b25044_2017.csv", "oc_b01003_2017.csv",
             "oc_b08141_2017.csv", "t10"),
    "2019": ("oc_b25044_2019.csv", "oc_b01003_2019.csv",
             "oc_b08141_2019.csv", "t10"),
    "2023": ("oc_b25044_2023.csv", "oc_b01003_2023.csv",
             "oc_b08141.csv", "t20"),      # b08141 2023 = the v2.0 table
}


def _read_csv_dicts(path):
    import csv
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _num(s):
    return float(s) if s not in ("", ".", None) else 0.0


def load_data_v21(der_dir=None, gens_path=None,
                  acs_vintages=("2017", "2019", "2023"),
                  lodes_vintages=("2017", "2019", "2022")):
    """Build ScreenDataV21 from the committed derived tables. Pure
    input-side (blocks, catchment inputs, WAC sums, ACS tables) -- reads
    nothing boardings-shaped. `der_dir`/`gens_path` overrides exist so tests
    exercise this loader on a synthetic fixture directory."""
    d = der_dir or DER
    blocks = _read_csv_dicts(os.path.join(d, "oc_blocks.csv"))
    geoids = [r["GEOID20"] for r in blocks]
    lat = np.array([float(r["INTPTLAT20"]) for r in blocks])
    lon = np.array([float(r["INTPTLON20"]) for r in blocks])
    aland_sqmi = np.array([float(r["ALAND20"]) for r in blocks]) / SQM_PER_SQMI
    pop2020 = np.array([float(r["pop2020"]) for r in blocks])
    block_t20 = [g[:11] for g in geoids]
    gidx = {g: i for i, g in enumerate(geoids)}

    bridge = [(r["tract10"], r["tract20"], float(r["share"]))
              for r in _read_csv_dicts(
                  os.path.join(d, "oc_tract10_to_tract20.csv"))]

    def tract_table(fname, cols, geography):
        rows = _read_csv_dicts(os.path.join(d, fname))
        vals = {r["GEOID"]: sum(_num(r[c]) for c in cols) for r in rows}
        if geography == "t10":
            vals = apply_bridge(vals, bridge)
        return apportion_to_blocks(vals, block_t20, pop2020)

    acs = {}
    for v, (f25044, f01003, f08141, geo) in _ACS_FILES.items():
        if v not in acs_vintages:
            continue
        acs[v] = {
            "zveh": tract_table(f25044, ["B25044_E003", "B25044_E010"], geo),
            "pop": tract_table(f01003, ["B01003_E001"], geo),
            "e016": tract_table(f08141, ["B08141_E016"], geo),
            "e002": tract_table(f08141, ["B08141_E002"], geo),
        }

    naics_cols = val("gen_jobs_naics")
    od, genjobs = {}, {}
    for v in lodes_vintages:
        with gzip.open(os.path.join(d, f"oc_block_od_{v}.csv.gz"),
                       "rt", encoding="utf-8") as f:
            import csv
            rd = csv.DictReader(f)
            h, w, n = [], [], []
            for r in rd:
                h.append(gidx[r["h"]])
                w.append(gidx[r["w"]])
                n.append(float(r["n"]))
        od[v] = (np.array(h, int), np.array(w, int), np.array(n))
        gj = np.zeros(len(geoids))
        for r in _read_csv_dicts(os.path.join(d, f"oc_block_wac_{v}.csv")):
            gj[gidx[r["GEOID20"]]] = sum(_num(r[c]) for c in naics_cols)
        genjobs[v] = gj

    gp = gens_path or os.path.join(CFGDIR, "special_generators.json")
    with open(gp, encoding="utf-8") as f:
        gens = json.load(f)["generators"]
    gx = np.array([g["lon"] for g in gens]) * MI_LON
    gy = np.array([g["lat"] for g in gens]) * MI_LAT

    return ScreenDataV21(geoids, lon * MI_LON, lat * MI_LAT, aland_sqmi,
                         pop2020, acs, od, genjobs, gx, gy,
                         [g["type"] for g in gens])
