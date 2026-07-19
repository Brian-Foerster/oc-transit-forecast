"""Shared stage-1 screen predictor machinery (spec 01 §3.2 / panel D6).

ONE function -- compute_predictors(view, w0, w1, values) -- computes the
catchment predictors on BOTH sides of the screen: screen_fit.py calls it with
the full-shape window [0, L] (route = its own window), screen_scan.py with
sliding windows. Fit/scan consistency is therefore structural, and the Route
43 identity test (test_screen.py D1) machine-checks it.

Catchment rule (identical to build_corridor.py's corr/posmap logic):
tract centroid |offset| <= buffer AND projected position in [w0, w1]
(inclusive, matching pandas .between). LODES flows are BOTH-ends-in (home AND
work tract in the catchment); intra-tract rows (h == w in the catchment) are
included identically on both sides. The special-generator dummy is geometric
on both sides: any config/special_generators.json site with |offset| <=
buffer AND position in [w0, w1].

Zero handling (documented rule): the fit consumes these sums through
log1p, not log -- log1p(0) = 0 keeps empty-catchment windows finite without
introducing a new floor constant, and at catchment magnitudes (10^3-10^5)
log1p is indistinguishable from log. Stated in the artifact notes.

Performance structure (spec 01 §6): per-shape precompute of (offset,
position) for all 614 tract centroids via ONE vectorized projection
(ShapeProj); per-(shape, buffer) LODES both-in-buffer subset (CatchmentView);
per-window work is boolean masks + sums. build_corridor is imported for
Line/MI_LAT/MI_LON only -- NEVER build_corridor.main().
"""
import math

import numpy as np

from build_corridor import Line, MI_LAT, MI_LON   # geo frame single-source

__all__ = ["ShapeProj", "CatchmentView", "compute_predictors",
           "window_starts", "overlap_groups", "pairwise_shares",
           "project_points", "MI_LAT", "MI_LON"]


def project_points(line, px, py):
    """Vectorized build_corridor.Line.project over many points.
    Returns (|offset| mi, position mi) arrays. Same segment math, same
    argmin-first tie behavior; the screen only needs the unsigned offset."""
    px = np.asarray(px, float)
    py = np.asarray(py, float)
    if len(px) == 0:
        return np.empty(0), np.empty(0)
    dxp = px[:, None] - line.ax[None, :]
    dyp = py[:, None] - line.ay[None, :]
    t = np.clip((dxp * line.dx[None, :] + dyp * line.dy[None, :])
                / line.L2[None, :], 0.0, 1.0)
    qx = line.ax[None, :] + t * line.dx[None, :]
    qy = line.ay[None, :] + t * line.dy[None, :]
    d = np.hypot(px[:, None] - qx, py[:, None] - qy)
    i = np.argmin(d, axis=1)
    r = np.arange(len(px))
    pos = line.cum[i] + t[r, i] * line.seg[i]
    return d[r, i], pos


class ShapeProj:
    """Per-shape precompute: ONE Line + tract/generator projections.
    Buffer-independent, so buffer sensitivity rows reuse it."""

    def __init__(self, route_id, x, y, tract_xy, gen_xy, gen_types):
        self.route_id = str(route_id)
        self.line = Line(np.asarray(x, float), np.asarray(y, float))
        self.L = float(self.line.L)
        self.t_off, self.t_pos = project_points(self.line, *tract_xy)
        self.g_off, self.g_pos = project_points(self.line, *gen_xy)
        self.g_types = list(gen_types)


class CatchmentView:
    """A (shape, buffer) view: in-buffer tract mask + the shape's
    both-ends-in-buffer LODES subset (window predicate applied per call)."""

    def __init__(self, proj, buffer_mi, od_h, od_w, od_n):
        self.proj = proj
        self.buffer_mi = float(buffer_mi)
        self.inbuf = proj.t_off <= self.buffer_mi
        m = self.inbuf[od_h] & self.inbuf[od_w]
        hpos = proj.t_pos[od_h[m]]
        wpos = proj.t_pos[od_w[m]]
        self.od_lo = np.minimum(hpos, wpos)
        self.od_hi = np.maximum(hpos, wpos)
        self.od_n = np.asarray(od_n, float)[m]
        self.g_in = proj.g_off <= self.buffer_mi


def compute_predictors(view, w0, w1, values):
    """The shared fit/scan predictor computation for one window [w0, w1] of
    one CatchmentView. `values` maps name -> per-tract vector (aligned to the
    global tract order); each yields a 'sum_<name>' catchment sum.

    Returns {tract_idx (global indices, ascending), lodes_both, gen_dummy,
    gen_types (sorted), window_mi, sum_<name>...}. Raw sums only -- the fit
    layer owns the log1p transform (see module docstring)."""
    p = view.proj
    inwin = view.inbuf & (p.t_pos >= w0) & (p.t_pos <= w1)
    tract_idx = np.flatnonzero(inwin)
    lodes = float(view.od_n[(view.od_lo >= w0) & (view.od_hi <= w1)].sum())
    gmask = view.g_in & (p.g_pos >= w0) & (p.g_pos <= w1)
    gen_types = sorted({p.g_types[i] for i in np.flatnonzero(gmask)})
    out = {"tract_idx": tract_idx, "lodes_both": lodes,
           "gen_dummy": 1 if gmask.any() else 0, "gen_types": gen_types,
           "window_mi": float(w1) - float(w0)}
    for name, vec in values.items():
        out[f"sum_{name}"] = float(np.asarray(vec, float)[tract_idx].sum())
    return out


def window_starts(L, window_mi, step_mi):
    """Window start positions: w0 = k*step exactly (integer k -- determinism
    checklist item 3), for every window fully inside [0, L]."""
    if L < window_mi:
        return np.empty(0)
    kmax = int(math.floor((L - window_mi) / step_mi + 1e-9))
    return np.arange(kmax + 1) * step_mi


def overlap_groups(window_ids, tract_sets, threshold):
    """Connected components over windows sharing > threshold of catchment
    tracts (share = |A ∩ B| / min(|A|, |B|) -- containment-sensitive, so a
    short window nested in a longer catchment groups with it; strict >).
    Group id = lexicographically smallest member window_id (deterministic --
    spec 01 §3.3 / determinism checklist item 4).
    Returns {window_id: group_id}."""
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
            # keep the lexicographically smaller root (ids are sorted)
            lo, hi = (ra, rb) if ra < rb else (rb, ra)
            parent[hi] = lo

    sets = [tract_sets[i] for i in ids]
    sizes = [len(s) for s in sets]
    for a in range(n):
        if sizes[a] == 0:
            continue
        sa = sets[a]
        for b in range(a + 1, n):
            if sizes[b] == 0:
                continue
            inter = len(sa & sets[b])
            if inter and inter / min(sizes[a], sizes[b]) > threshold:
                union(a, b)
    return {ids[a]: ids[find(a)] for a in range(n)}


def pairwise_shares(window_ids, tract_sets, threshold):
    """Per-pair overlap shares WITHOUT transitive closure. Measured outcome
    on the real universe (review 2026-07-19): overlap_groups() collapses to a
    single county-wide connected component at the 0.30 headline threshold
    (single-linkage transitivity chains ~96%-overlapping adjacent windows and
    the min-denominator share links parallel/crossing routes), so gate-1
    deduplication uses THESE per-pair shares among best-per-shape shortlist
    windows instead (spec 01 §3.3 degeneracy caveat / §4b step 2).
    Returns sorted [(a, b, share)] for every pair with share > threshold;
    same share definition and strict > as overlap_groups()."""
    ids = sorted(window_ids)
    out = []
    for a in range(len(ids)):
        sa = tract_sets[ids[a]]
        if not sa:
            continue
        for b in range(a + 1, len(ids)):
            sb = tract_sets[ids[b]]
            if not sb:
                continue
            inter = len(sa & sb)
            if inter and inter / min(len(sa), len(sb)) > threshold:
                out.append((ids[a], ids[b], inter / min(len(sa), len(sb))))
    return out
