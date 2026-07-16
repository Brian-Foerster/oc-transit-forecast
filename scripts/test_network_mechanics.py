"""
Unit gates for scripts/network_mechanics.py -- the pure §4.2 mechanics + the G6
canonical-serialization utilities (spec 07 N1a). No files, no rng; pure
arithmetic and geometry.

    python test_network_mechanics.py

  - canonical serialization / fingerprint: sort-invariant, deterministic sha256,
    set-derived lists sorted (gate G6).
  - truncate_polyline: window length + endpoints (new shape-truncation path).
  - materialize_stops: count + spacing along the line.
  - omega(H, B): in [0, 1]; a buffer covering all of H -> 1; DISJOINT candidate
    buffers sum to <= 1 (the acceptance check); worker-mass vs uniform variants.
  - fold_sub: measured boardings x geometric share within B's buffer.
  - anchor_adjustment: linear in the per-draw margin; omega*margin - fold_sub.
"""
import sys

import numpy as np

import network_mechanics as nm

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def _close(a, b, tol=1e-9):
    return abs(a - b) <= tol


def test_canonical_and_fingerprint():
    """G6: canonical serialization is key-order-invariant; the fingerprint is a
    deterministic sha256 of it; set-derived lists are sorted."""
    a = {"b": 1, "a": [3, 2, 1], "c": {"y": 2, "x": 1}}
    b = {"c": {"x": 1, "y": 2}, "a": [3, 2, 1], "b": 1}
    assert nm.canonical_json(a) == nm.canonical_json(b), "key order leaks"
    assert " " not in nm.canonical_json(a), "non-compact separators"
    fp1 = nm.network_fingerprint(a)
    fp2 = nm.network_fingerprint(b)
    assert fp1 == fp2 and len(fp1) == 64, (fp1, fp2)
    # a changed descriptor changes the hash
    assert nm.network_fingerprint({"a": [1, 2, 3]}) != fp1
    assert nm.sorted_set_list(["543", "43", "543", "1"]) == ["1", "43", "543"]
    print(f"  test_canonical_and_fingerprint OK  (fp {fp1[:12]}...)")


def test_truncate_polyline():
    """A straight 10-mi line truncated to [2, 7] -> a 5-mi segment with the cut
    endpoints interpolated exactly."""
    x = np.array([0.0, 10.0])
    y = np.array([0.0, 0.0])
    tx, ty = nm.truncate_polyline(x, y, 2.0, 7.0)
    assert _close(nm.polyline_length(tx, ty), 5.0), nm.polyline_length(tx, ty)
    assert _close(tx[0], 2.0) and _close(tx[-1], 7.0), (tx[0], tx[-1])
    assert np.allclose(ty, 0.0)
    print("  test_truncate_polyline OK  (10-mi -> [2,7] = 5.0 mi)")


def test_materialize_stops():
    """Stops every 1 mi along a 5-mi line -> 6 stops at 0..5."""
    x = np.array([0.0, 5.0])
    y = np.array([0.0, 0.0])
    stops = nm.materialize_stops(x, y, spacing=1.0)
    assert len(stops) == 6, len(stops)
    assert np.allclose(stops[:, 0], np.arange(6)), stops[:, 0]
    assert np.allclose(stops[:, 1], 0.0)
    print(f"  test_materialize_stops OK  ({len(stops)} stops @ 1-mi on a 5-mi line)")


def test_omega_full_and_disjoint():
    """omega in [0,1]: a buffer over ALL of H -> 1; disjoint half-buffers sum to
    <= 1 (the acceptance check -- omega apportions H's mass, counted once per
    disjoint buffer)."""
    # H: a 6-mi east-west line at y=0, stops every 1 mi (7 stops at x=0..6).
    Hx = np.array([0.0, 6.0])
    Hy = np.array([0.0, 0.0])
    # B_all: parallel line 0.1 mi north covering the whole length -> all stops in
    # its 0.9-mi buffer -> omega = 1.
    Ball_x = np.array([-1.0, 7.0])
    Ball_y = np.array([0.1, 0.1])
    w_all = nm.omega(Hx, Hy, Ball_x, Ball_y, spacing=1.0)
    assert _close(w_all, 1.0), w_all
    # Two DISJOINT candidate buffers: short parallel stubs near x in [0,2] and
    # [4,6], each 0.1 mi off, windows keeping them from overlapping in coverage.
    Bl_x, Bl_y = np.array([0.0, 2.0]), np.array([0.1, 0.1])
    Br_x, Br_y = np.array([4.0, 6.0]), np.array([0.1, 0.1])
    wl = nm.omega(Hx, Hy, Bl_x, Bl_y, spacing=1.0, B_window=(0.0, 2.0))
    wr = nm.omega(Hx, Hy, Br_x, Br_y, spacing=1.0, B_window=(0.0, 2.0))
    assert 0.0 <= wl <= 1.0 and 0.0 <= wr <= 1.0, (wl, wr)
    assert wl + wr <= 1.0 + 1e-9, f"disjoint buffers sum {wl + wr} > 1"
    print(f"  test_omega_full_and_disjoint OK  (full={w_all:.2f}; "
          f"disjoint {wl:.2f}+{wr:.2f}={wl + wr:.2f} <= 1)")


def test_omega_worker_mass_vs_uniform():
    """worker_mass shifts omega toward the mass-heavy end vs uniform; both in
    [0,1]. H 6 mi; B covers only the eastern half; put worker mass on the east
    -> worker_mass omega > uniform omega."""
    Hx = np.array([0.0, 6.0])
    Hy = np.array([0.0, 0.0])
    B_x = np.array([3.0, 7.0])          # buffers the eastern ~half of H
    B_y = np.array([0.1, 0.1])
    # tract centroids: all worker mass clustered at the east end (x=5..6)
    wp = np.array([[5.0, 0.0], [5.5, 0.0], [6.0, 0.0]])
    wm = np.array([100.0, 100.0, 100.0])
    w_worker = nm.omega(Hx, Hy, B_x, B_y, spacing=1.0, worker_pts=wp,
                        worker_mass=wm, B_window=(0.0, 4.0))
    w_uniform = nm.omega(Hx, Hy, B_x, B_y, spacing=1.0, allocation="uniform",
                         B_window=(0.0, 4.0))
    assert 0.0 <= w_uniform <= 1.0 and 0.0 <= w_worker <= 1.0, (w_worker, w_uniform)
    assert w_worker > w_uniform, (w_worker, w_uniform)
    print(f"  test_omega_worker_mass_vs_uniform OK  (worker {w_worker:.2f} > "
          f"uniform {w_uniform:.2f})")


def test_fold_sub():
    """fold_sub = sum boardings x geometric share inside B's buffer. A folded
    route fully inside B's buffer contributes its full boardings; one fully
    outside contributes ~0."""
    B_x = np.array([0.0, 10.0])
    B_y = np.array([0.0, 0.0])
    inside = {"boardings": 1000.0, "x": [1.0, 4.0], "y": [0.2, 0.2]}   # within 0.9
    outside = {"boardings": 500.0, "x": [1.0, 4.0], "y": [5.0, 5.0]}   # far off
    fs = nm.fold_sub([inside, outside], B_x, B_y)
    assert _close(fs, 1000.0, 1.0), fs
    print(f"  test_fold_sub OK  (inside 1000 + outside ~0 -> {fs:.1f})")


def test_anchor_adjustment_linear():
    """anchor_adjustment = omega*margin - fold_sub, elementwise in the per-draw
    margin (linearity: scaling margin scales the omega term exactly)."""
    margin = np.array([100.0, 200.0, -50.0, 0.0])
    om, fs = 0.4, 30.0
    add = nm.anchor_adjustment(om, margin, fs)
    assert np.allclose(add, om * margin - fs), add
    # doubling the margin doubles the omega contribution (fold_sub is a level)
    add2 = nm.anchor_adjustment(om, 2 * margin, fs)
    assert np.allclose(add2 + fs, 2 * (add + fs)), (add2, add)
    print(f"  test_anchor_adjustment_linear OK  (omega*margin - fold_sub)")


def test_feeder_headway_map():
    """offpeak->midday: a {peak, offpeak} plan maps to its offpeak value; scalars
    pass through; the peak-mapped variant is available for the G7 row."""
    assert nm.feeder_headway({"peak": 5.0, "offpeak": 10.0}) == 10.0
    assert nm.feeder_headway({"peak": 5.0, "offpeak": 10.0},
                             mapping="peak_to_midday") == 5.0
    assert nm.feeder_headway(12.0) == 12.0
    assert nm.feeder_headway(None) is None
    print("  test_feeder_headway_map OK  (offpeak->midday default; scalar/None pass)")


if __name__ == "__main__":
    test_canonical_and_fingerprint()
    test_truncate_polyline()
    test_materialize_stops()
    test_omega_full_and_disjoint()
    test_omega_worker_mass_vs_uniform()
    test_fold_sub()
    test_anchor_adjustment_linear()
    test_feeder_headway_map()
    print("ALL NETWORK-MECHANICS GATES PASS")
