"""
Pure network-sequencing mechanics (spec 07 N1a -- the model-side half).

Two families of PURE FUNCTIONS, no pipeline imports (numpy + stdlib + the
assumptions registry only, all acyclic), so build_corridor.py and model.py can
both import this without a dependency cycle:

  * canonical serialization (gate G6 determinism, spec 07 §10): a network
    fingerprint is the sha256 of a sort_keys / compact-separator JSON dump, and
    every set-derived list is sorted before it enters a fingerprinted object.
  * polyline geometry + the §4.2 anchor adjustment: shape truncation, stop
    materialization, the worker-mass allocation share omega(H, B), fold_sub(H, B),
    and the per-draw anchor_add = omega*margin - fold_sub the model consumes via
    run(anchor_add=...).

Everything here is a pure function of its arguments -- no file, rng, or global
state. The per-cycle harness loop, the CV selection rule, the interaction
matrix, and the primary artifact are N1b, not this module.

Coordinates are the SAME flat-earth mi-scaled frame build_corridor.py uses
(lon*MI_LON, lat*MI_LAT); callers pass shapes already in that frame.
"""
import hashlib
import json

import numpy as np

from assumptions import val

# 0.9-mi candidate buffer -- shared leaf with build_corridor's BUFFER_MI so a
# candidate's omega/fold_sub geometry uses the same catchment the rebuild does.
BUFFER_MI = val("buffer_mi")


# ---------------------------------------------------------------------------
# canonical serialization (gate G6: reproducible fingerprints)
# ---------------------------------------------------------------------------
def canonical_json(obj):
    """The canonical serialization for network fingerprints (spec 07 §10 G6):
    compact separators, keys sorted, no incidental whitespace. Deterministic
    across processes -- the ONLY input to the fingerprint hash."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False)


def network_fingerprint(descriptor):
    """sha256 hexdigest of the canonical serialization of a network descriptor
    (G6). No timestamps enter it; callers pass sorted_set_list for any
    set-derived field so iteration order can never perturb the hash."""
    return hashlib.sha256(canonical_json(descriptor).encode("utf-8")).hexdigest()


def sorted_set_list(items):
    """Deterministic sorted list from any iterable / set (G6: 'every set-derived
    list sorted before writing'). De-duplicates, then sorts."""
    return sorted(set(items))


# ---------------------------------------------------------------------------
# polyline geometry (self-contained; no build_corridor import)
# ---------------------------------------------------------------------------
def _cumlen(x, y):
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    seg = np.hypot(np.diff(x), np.diff(y))
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    return x, y, cum


def polyline_length(x, y):
    """Total arc length (mi) of the polyline."""
    return float(_cumlen(x, y)[2][-1])


def _point_at(x, y, cum, s):
    """(px, py) at arc-length s along the polyline (endpoints clamped)."""
    s = float(np.clip(s, 0.0, cum[-1]))
    i = int(np.searchsorted(cum, s) - 1)
    i = max(0, min(i, len(cum) - 2))
    seg = cum[i + 1] - cum[i]
    t = 0.0 if seg == 0 else (s - cum[i]) / seg
    return x[i] + t * (x[i + 1] - x[i]), y[i] + t * (y[i + 1] - y[i])


def truncate_polyline(x, y, w0, w1):
    """Sub-polyline between arc-lengths w0..w1 -- the committed-window shape
    truncation (spec 07 §4.2.1; new code, no shape-truncation path existed in
    build_corridor). Interpolates the two cut endpoints and keeps every interior
    vertex. Returns (x', y') numpy arrays."""
    x, y, cum = _cumlen(x, y)
    L = cum[-1]
    w0 = max(0.0, min(float(w0), L))
    w1 = max(w0, min(float(w1), L))
    px0, py0 = _point_at(x, y, cum, w0)
    px1, py1 = _point_at(x, y, cum, w1)
    keep = (cum > w0) & (cum < w1)
    xs = np.concatenate([[px0], x[keep], [px1]])
    ys = np.concatenate([[py0], y[keep], [py1]])
    return xs, ys


def materialize_stops(x, y, spacing, w0=0.0, w1=None):
    """Stop coordinates every `spacing` mi along the polyline within [w0, w1]
    (spec 07 §4.2: 'stops materialized every `spacing` mi along H's alignment
    polyline'). First stop at w0, last at or before w1. Returns an (m, 2) array
    of (sx, sy). The materialization rule is registry-owned
    (omega_stop_materialization = 'line_spacing')."""
    rule = val("omega_stop_materialization")
    if rule != "line_spacing":
        raise ValueError(f"unsupported stop-materialization rule {rule!r}")
    if spacing <= 0:
        raise ValueError("spacing must be > 0")
    x, y, cum = _cumlen(x, y)
    L = cum[-1]
    w1 = L if w1 is None else min(float(w1), L)
    w0 = max(0.0, min(float(w0), L))
    m = int(np.floor((w1 - w0) / spacing + 1e-9)) + 1
    ss = w0 + spacing * np.arange(m)
    return np.array([_point_at(x, y, cum, s) for s in ss])


def project_points(bx, by, px, py):
    """Perpendicular offset (mi, unsigned) and along-line position (mi) of each
    query point onto polyline B = (bx, by), vectorized over query points. Same
    nearest-segment projection as build_corridor.Line.project but standalone.
    Returns (offset (m,), position (m,))."""
    bx = np.asarray(bx, float)
    by = np.asarray(by, float)
    ax, ay = bx[:-1], by[:-1]
    dx, dy = np.diff(bx), np.diff(by)
    seg = np.hypot(dx, dy)
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    L2 = np.where(seg == 0, 1.0, seg ** 2)
    px = np.atleast_1d(np.asarray(px, float))
    py = np.atleast_1d(np.asarray(py, float))
    t = np.clip(((px[:, None] - ax[None, :]) * dx[None, :]
                 + (py[:, None] - ay[None, :]) * dy[None, :]) / L2[None, :],
                0.0, 1.0)
    qx = ax[None, :] + t * dx[None, :]
    qy = ay[None, :] + t * dy[None, :]
    d = np.hypot(px[:, None] - qx, py[:, None] - qy)
    i = np.argmin(d, axis=1)
    m = np.arange(len(px))
    off = d[m, i]
    pos = cum[i] + t[m, i] * seg[i]
    return off, pos


def _inside_buffer(off, pos, buffer_mi, window):
    inside = off <= buffer_mi
    if window is not None:
        inside = inside & (pos >= window[0]) & (pos <= window[1])
    return inside


# ---------------------------------------------------------------------------
# omega(H, B) -- share of H's forecast allocated to stops inside B's buffer
# ---------------------------------------------------------------------------
def omega(H_x, H_y, B_x, B_y, spacing, worker_pts=None, worker_mass=None,
          stop_mass=None, buffer_mi=BUFFER_MI, B_window=None, allocation=None):
    """omega(H, B): the share of committed line H's forecast attributable to H's
    stops that fall inside candidate B's `buffer_mi` buffer (spec 07 §4.2).

    Stops are materialized every `spacing` mi along H (materialize_stops). Each
    stop carries an allocation weight (registry omega_allocation default):
      * 'worker_mass' (default) -- worker mass of the corridor tracts assigned
        to their nearest H-stop; pass worker_pts (k, 2) tract centroids in the
        SAME mi-scaled frame and worker_mass (k,);
      * 'uniform' -- the §4.2 / §8i sensitivity-row variant: every stop weight 1
        (also used automatically when no worker mass is supplied).
    Pre-computed per-stop weights may be passed via stop_mass to skip the tract
    step. A stop is 'inside B' when its perpendicular offset from B is
    <= buffer_mi (and, if B_window is given, its along-B position is within it).

    Returns a scalar in [0, 1]. Across candidates whose buffers do not overlap,
    sum(omega(H, B_i)) <= 1 by construction (each stop's mass is counted once
    per buffer; disjoint buffers partition it)."""
    allocation = allocation or val("omega_allocation")
    stops = materialize_stops(H_x, H_y, spacing)
    if stop_mass is not None:
        w = np.asarray(stop_mass, float)
    elif allocation == "uniform" or worker_pts is None or worker_mass is None:
        w = np.ones(len(stops))
    elif allocation == "worker_mass":
        wp = np.asarray(worker_pts, float)
        wm = np.asarray(worker_mass, float)
        d = np.hypot(wp[:, None, 0] - stops[None, :, 0],
                     wp[:, None, 1] - stops[None, :, 1])
        nearest = np.argmin(d, axis=1)
        w = np.zeros(len(stops))
        np.add.at(w, nearest, wm)
    else:
        raise ValueError(f"unknown omega allocation {allocation!r}")
    total = w.sum()
    if total <= 0:
        return 0.0
    off, pos = project_points(B_x, B_y, stops[:, 0], stops[:, 1])
    inside = _inside_buffer(off, pos, buffer_mi, B_window)
    return float(w[inside].sum() / total)


# ---------------------------------------------------------------------------
# fold_sub(H, B) -- folded routes' measured boardings inside B's buffer
# ---------------------------------------------------------------------------
def geometric_share_in_buffer(route_x, route_y, B_x, B_y, buffer_mi=BUFFER_MI,
                              B_window=None, samples=None):
    """Fraction of a route's LENGTH whose points lie within `buffer_mi` of
    polyline B (and within B_window along B, if given). Arc-length resampled so
    the share is length-weighted, not vertex-weighted."""
    rx, ry, cum = _cumlen(route_x, route_y)
    L = cum[-1]
    if L <= 0:
        return 0.0
    if samples is None:
        # ~3 samples per buffer width -> the share is stable to O(buffer/3)
        samples = max(2, int(L / max(buffer_mi / 3.0, 1e-6)) + 1)
    ss = np.linspace(0.0, L, samples)
    pts = np.array([_point_at(rx, ry, cum, s) for s in ss])
    off, pos = project_points(B_x, B_y, pts[:, 0], pts[:, 1])
    inside = _inside_buffer(off, pos, buffer_mi, B_window)
    return float(inside.mean())


def fold_sub(folded_routes, B_x, B_y, buffer_mi=BUFFER_MI, B_window=None):
    """The §4.2 'ghosts' term: sum over folded routes of measured_boardings x
    geometric share of the route inside B's buffer. Removes the folded routes'
    measured boardings attributable inside B's catchment -- riders that a fold
    deleted must not still appear inside anchor_B_measured.

    folded_routes: iterable of {'boardings': float, 'x': [...], 'y': [...]}
    (shapes in the mi-scaled frame). Returns a scalar (boardings to subtract).
    Deterministic: routes summed in the given order."""
    total = 0.0
    for r in folded_routes:
        share = geometric_share_in_buffer(r["x"], r["y"], B_x, B_y,
                                          buffer_mi, B_window)
        total += float(r["boardings"]) * share
    return total


# ---------------------------------------------------------------------------
# the per-draw anchor adjustment (fed to model.run(anchor_add=...))
# ---------------------------------------------------------------------------
def anchor_adjustment(omega_HB, margin, fold_sub_HB):
    """The §4.2 anchor adjustment for candidate B against committed line H:

        anchor_add(draw) = omega(H, B) * margin(draw) - fold_sub(H, B)

    `margin` is the (n,) per-draw committed-scenario MARGIN [total_H - anchor_H]
    (both exported per draw, spec 06 §3) -- the margin-only rule: NEVER gross
    newline (that double-counts diverted riders already inside
    anchor_B_measured). omega and fold_sub are scalars. Returns the (n,) array to
    pass as run(anchor_add=...)."""
    return omega_HB * np.asarray(margin, float) - float(fold_sub_HB)


# ---------------------------------------------------------------------------
# synthetic-feeder headway mapping (used by build_corridor's injection block)
# ---------------------------------------------------------------------------
def feeder_headway(committed_headway, mapping=None):
    """Map a committed line's {peak, offpeak} (or scalar) headway plan to the
    single midday scalar build_corridor's feeder convention carries. Declared
    convention 'offpeak_to_midday' (registry feeder_headway_map); the
    peak-mapped variant is the §4.2 / G7 sensitivity row. Scalar headways pass
    through unchanged; None stays None."""
    mapping = mapping or val("feeder_headway_map")
    if not isinstance(committed_headway, dict):
        return committed_headway
    if mapping == "offpeak_to_midday":
        return committed_headway.get("offpeak", committed_headway.get("peak"))
    if mapping == "peak_to_midday":
        return committed_headway.get("peak", committed_headway.get("offpeak"))
    raise ValueError(f"unknown feeder headway mapping {mapping!r}")


# ---------------------------------------------------------------------------
# empty-network predicate (the verbatim-config rule, spec 07 §4.2 / gate G1)
# ---------------------------------------------------------------------------
def is_empty_network(injected_lines, excluded_fold_routes):
    """True when a cycle's network-before contributes nothing to the rebuild --
    no persistent/feeder injection and no fold propagation. The harness passes
    the committed corridor FILE through verbatim in this case (gate G1 by
    construction); build_corridor with both args empty is byte-identical to the
    committed build regardless."""
    return not injected_lines and not excluded_fold_routes
