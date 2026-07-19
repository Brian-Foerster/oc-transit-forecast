"""Stage-1 screen tests (spec 01 §6 / panel D22).

Pure-logic tests run on a committed SYNTHETIC fixture (toy tracts/shapes
defined below in mi-space) with no data/raw dependency:

  P1  vectorized projection == build_corridor.Line.project semantics
  P2  catchment membership (|off| <= buffer AND pos in [w0, w1], inclusive)
  P3  both-ends-in LODES window sums (intra-tract rows included identically)
  P4  ACS column sums over the catchment tract set
  P5  special-generator dummy (geometric, same rule as tracts)
  P6  buffer sensitivity of P2-P3 (the buffer_lo/hi row mechanics)
  P7  window grid: w0 = k*step exactly, count = floor((L-win)/step)+1
  P8  overlap grouping: connected components over >threshold shared tracts,
      deterministic group ids (lexicographically smallest member window_id)

Data-gated tests (house Q6 pattern -- skip cleanly when data/raw or the
generated artifact is absent):

  D1  fit==scan predictor identity on Route 43 (spec 01 §3.2 / panel D6)
  D2  artifact schema (top-level + per-window + the 16 sensitivity ids)
  D3  ordinal guardrails: no boardings-denominated field anywhere in the
      artifact; predictions at exactly TWO service levels (D10)
  D4  in-process double-run determinism of the scan pipeline (reduced B)

    python test_screen.py
"""
import json
import math
import os
import sys

import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "outputs")
RAW = os.path.join(HERE, "..", "data", "raw")

import screen_common as sc                                    # noqa: E402
from assumptions import val                                   # noqa: E402

HAVE_DATA = os.path.exists(os.path.join(RAW, "gtfs", "trips.txt"))
ARTIFACT = os.path.join(OUT, "screen_results.json")


# ---------------------------------------------------------------------------
# synthetic fixture (mi-space; no data/raw)
# ---------------------------------------------------------------------------
def _fixture():
    """One straight 20-mi shape along the x-axis; 7 toy tracts; 2 generators;
    5 toy LODES flows. All coordinates directly in the mi frame."""
    x = np.array([0.0, 20.0])
    y = np.array([0.0, 0.0])
    # tract (x, y): index 0..6
    tx = np.array([1.0, 5.0, 5.0, 12.0, 13.0, 19.5, 30.0])
    ty = np.array([0.2, 0.5, 1.1, -0.8, 0.0, 0.4, 5.0])
    e002 = np.array([10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0])
    # LODES (h_idx, w_idx, n)
    od_h = np.array([0, 0, 1, 2, 4])
    od_w = np.array([1, 4, 1, 0, 5])
    od_n = np.array([5.0, 7.0, 3.0, 9.0, 4.0])
    # generators (x, y, type): G0 in-buffer at pos 12; G1 off-line
    gx = np.array([12.0, 2.0])
    gy = np.array([0.5, -2.0])
    gt = ["resort", "college"]
    proj = sc.ShapeProj("toy", x, y, (tx, ty), (gx, gy), gt)
    return proj, e002, od_h, od_w, od_n


def test_p1_projection():
    proj, *_ = _fixture()
    # scalar Line.project agreement on every fixture tract
    from build_corridor import Line
    line = Line(np.array([0.0, 20.0]), np.array([0.0, 0.0]))
    tx = np.array([1.0, 5.0, 5.0, 12.0, 13.0, 19.5, 30.0])
    ty = np.array([0.2, 0.5, 1.1, -0.8, 0.0, 0.4, 5.0])
    for i in range(len(tx)):
        off_s, pos_s = line.project(tx[i], ty[i])
        assert abs(abs(off_s) - proj.t_off[i]) < 1e-12, (i, off_s, proj.t_off[i])
        assert abs(pos_s - proj.t_pos[i]) < 1e-12, (i, pos_s, proj.t_pos[i])
    # clamping beyond the end: tract 6 projects to the endpoint
    assert abs(proj.t_pos[6] - 20.0) < 1e-12
    assert abs(proj.t_off[6] - math.hypot(10.0, 5.0)) < 1e-12
    print("  P1 OK  vectorized projection == Line.project")


def test_p2_catchment_membership():
    proj, e002, od_h, od_w, od_n = _fixture()
    view = sc.CatchmentView(proj, 0.9, od_h, od_w, od_n)
    p = sc.compute_predictors(view, 0.0, 12.5, {"e002": e002})
    assert list(p["tract_idx"]) == [0, 1, 3], p["tract_idx"]
    full = sc.compute_predictors(view, 0.0, 20.0, {"e002": e002})
    assert list(full["tract_idx"]) == [0, 1, 3, 4, 5], full["tract_idx"]
    late = sc.compute_predictors(view, 7.5, 20.0, {"e002": e002})
    assert list(late["tract_idx"]) == [3, 4, 5], late["tract_idx"]
    print("  P2 OK  catchment membership (buffer AND position, inclusive)")


def test_p3_lodes_window_sums():
    proj, e002, od_h, od_w, od_n = _fixture()
    view = sc.CatchmentView(proj, 0.9, od_h, od_w, od_n)
    # window [0, 12.5]: (0,1,5) both-in + intra (1,1,3); (0,4,7) has tract 4
    # at pos 13.0 -> out; (2,0,9) tract 2 off 1.1 -> out of buffer
    p = sc.compute_predictors(view, 0.0, 12.5, {})
    assert p["lodes_both"] == 8.0, p["lodes_both"]
    # window [7.5, 20]: only (4,5,4)
    late = sc.compute_predictors(view, 7.5, 20.0, {})
    assert late["lodes_both"] == 4.0, late["lodes_both"]
    # full shape [0, 20]: 5 + 7 + 3 + 4 (tract 2 still out of buffer)
    full = sc.compute_predictors(view, 0.0, 20.0, {})
    assert full["lodes_both"] == 19.0, full["lodes_both"]
    print("  P3 OK  both-ends-in LODES window sums (intra-tract included)")


def test_p4_acs_sums():
    proj, e002, od_h, od_w, od_n = _fixture()
    view = sc.CatchmentView(proj, 0.9, od_h, od_w, od_n)
    p = sc.compute_predictors(view, 0.0, 12.5, {"e002": e002})
    assert p["sum_e002"] == 70.0, p["sum_e002"]           # tracts 0,1,3
    late = sc.compute_predictors(view, 7.5, 20.0, {"e002": e002})
    assert late["sum_e002"] == 150.0, late["sum_e002"]    # tracts 3,4,5
    print("  P4 OK  ACS catchment sums")


def test_p5_generator_dummy():
    proj, e002, od_h, od_w, od_n = _fixture()
    view = sc.CatchmentView(proj, 0.9, od_h, od_w, od_n)
    p = sc.compute_predictors(view, 0.0, 12.5, {})
    assert p["gen_dummy"] == 1 and p["gen_types"] == ["resort"], p
    # a window ending before the generator: G0 pos 12.0 -> out of [0, 11.5]
    early = sc.compute_predictors(view, 0.0, 11.5, {})
    assert early["gen_dummy"] == 0 and early["gen_types"] == [], early
    # G1 (off 2.0) never qualifies
    assert "college" not in sc.compute_predictors(view, 0.0, 20.0, {})["gen_types"]
    print("  P5 OK  geometric generator dummy (binary cliff at the buffer edge)")


def test_p6_buffer_sensitivity():
    proj, e002, od_h, od_w, od_n = _fixture()
    wide = sc.CatchmentView(proj, 1.25, od_h, od_w, od_n)
    p = sc.compute_predictors(wide, 0.0, 12.5, {"e002": e002})
    # tract 2 (off 1.1) enters at 1.25; flow (2,0,9) becomes both-ends-in
    assert list(p["tract_idx"]) == [0, 1, 2, 3], p["tract_idx"]
    assert p["sum_e002"] == 100.0, p["sum_e002"]
    assert p["lodes_both"] == 17.0, p["lodes_both"]
    print("  P6 OK  buffer change moves membership + both-ends flows")


def test_p7_window_grid():
    w0s = sc.window_starts(20.0, 12.5, 0.5)
    assert len(w0s) == 16, len(w0s)
    assert w0s[0] == 0.0 and w0s[-1] == 7.5
    # w0 = k*step exactly (integer k; never accumulated floats)
    for k, w0 in enumerate(w0s):
        assert w0 == k * 0.5, (k, w0)
    assert len(sc.window_starts(12.5, 12.5, 0.5)) == 1
    assert len(sc.window_starts(12.4, 12.5, 0.5)) == 0
    print("  P7 OK  integer-step window grid")


def test_p8_overlap_grouping():
    ids = ["b_002.0", "a_000.0", "a_000.5", "c_010.0"]
    tsets = {"a_000.0": {1, 2, 3, 4}, "a_000.5": {3, 4, 5, 6},
             "b_002.0": {4, 9}, "c_010.0": {7, 8}}
    groups = sc.overlap_groups(ids, tsets, 0.30)
    # a_000.0 ~ a_000.5 share 2/min(4,4)=0.5; b_002.0 shares {4}: 1/min(2,4)=0.5
    assert groups["a_000.0"] == "a_000.0"
    assert groups["a_000.5"] == "a_000.0"
    assert groups["b_002.0"] == "a_000.0"
    assert groups["c_010.0"] == "c_010.0"
    # threshold edge is strict (> not >=): share exactly 0.5 at thr 0.5 -> split
    g2 = sc.overlap_groups(ids, tsets, 0.5)
    assert g2["a_000.5"] == "a_000.5" and g2["b_002.0"] == "b_002.0", g2
    print("  P8 OK  overlap grouping, deterministic ids, strict threshold")


def test_p9_pairwise_shares():
    ids = ["b_002.0", "a_000.0", "a_000.5", "c_010.0"]
    tsets = {"a_000.0": {1, 2, 3, 4}, "a_000.5": {3, 4, 5, 6},
             "b_002.0": {4, 9}, "c_010.0": {7, 8}}
    pairs = sc.pairwise_shares(ids, tsets, 0.30)
    # per-pair, sorted, NO transitive closure; same share rule as P8
    assert pairs == [("a_000.0", "a_000.5", 0.5),
                     ("a_000.0", "b_002.0", 0.5),
                     ("a_000.5", "b_002.0", 0.5)], pairs
    # strict >: exactly-0.5 shares vanish at threshold 0.5
    assert sc.pairwise_shares(ids, tsets, 0.5) == []
    print("  P9 OK  per-pair overlap shares (no transitive closure)")


# ---------------------------------------------------------------------------
# data-gated (house Q6 pattern)
# ---------------------------------------------------------------------------
def test_d1_fit_scan_identity():
    if not HAVE_DATA:
        print("  D1 SKIP  (data/raw absent)")
        return
    import screen_fit as sf
    inputs = sf.load_screen_inputs()
    projs = sf.gtfs_universe(inputs)
    fit = sf.build_fit_frame(projs, inputs, val("buffer_mi"))
    r43 = fit["route_pred"]["43"]
    # scan side: the full-length window [0, L] on 43's shape through the SAME
    # shared function, built from a FRESH view (not the fit's object)
    proj = projs["43"]
    view = sc.CatchmentView(proj, val("buffer_mi"),
                            inputs["od_h"], inputs["od_w"], inputs["od_n"])
    scan = sc.compute_predictors(view, 0.0, proj.L,
                                 {"e002": inputs["e002"],
                                  "e016": inputs["e016"]})
    assert scan["lodes_both"] == r43["lodes_both"]
    assert scan["sum_e002"] == r43["sum_e002"]
    assert scan["sum_e016"] == r43["sum_e016"]
    assert scan["gen_dummy"] == r43["gen_dummy"]
    assert list(scan["tract_idx"]) == list(r43["tract_idx"])
    print(f"  D1 OK  route 43 fit==scan predictor identity "
          f"(lodes {scan['lodes_both']:.0f}, e002 {scan['sum_e002']:.0f}, "
          f"gen {scan['gen_dummy']}, {len(scan['tract_idx'])} tracts)")


SENS_IDS = {"buffer_lo", "buffer_hi", "window_10", "window_15", "drop_fy2020",
            "drop_rh", "e016_swap", "b4_off", "gen_leave_class_out",
            "nb_estimator", "svc_p25", "svc_p75", "offset_variant",
            "overlap_lo", "overlap_hi", "year_fe_vs_pooled"}

WINDOW_KEYS = {"window_id", "route_id", "w0", "w1", "window_mi",
               "screen_index_p50", "screen_index_p10", "screen_index_p90",
               "rank", "rank_ci", "tie_with_cutoff", "decomposition",
               "overlap_group", "underservice_gap", "underservice_flag",
               "leverage_flag", "incumbent_routes"}


def test_d2_artifact_schema():
    if not os.path.exists(ARTIFACT):
        print("  D2 SKIP  (outputs/screen_results.json absent)")
        return
    a = json.load(open(ARTIFACT, encoding="utf-8"))
    for k in ("run_id", "schema", "seed", "n_boot", "universe", "vintages",
              "disclaimer", "assumptions_manifest", "windows",
              "overlap_diagnostics", "fit_diagnostics", "sensitivity",
              "notes"):
        assert k in a, f"missing top-level key {k}"
    assert a["schema"] == "01-S1"
    assert a["seed"] == val("screen_seed")
    assert a["n_boot"] == val("screen_n_boot")
    # overlap degeneracy block (review 2026-07-19): best-per-shape covers
    # every host shape; pairwise rows reference best windows only
    od = a["overlap_diagnostics"]
    assert set(od) == {"n_windows", "n_groups", "single_component", "note",
                       "best_window_per_shape", "pairwise_share_gt_threshold"}
    hosts = {w["route_id"] for w in a["windows"]}
    assert {b["route_id"] for b in od["best_window_per_shape"]} == hosts
    best_ids = {b["window_id"] for b in od["best_window_per_shape"]}
    for p in od["pairwise_share_gt_threshold"]:
        assert p["a"] in best_ids and p["b"] in best_ids and p["a"] < p["b"]
        assert p["share"] > val("screen_overlap_threshold")
    assert od["n_windows"] == len(a["windows"])
    # band() edges consumed by sensitivity rows are declared in the manifest
    assert set(a["assumptions_manifest"]["bands"]) == {
        "buffer_mi", "screen_overlap_threshold", "screen_svc_std",
        "screen_window_mi"}
    assert {r["id"] for r in a["sensitivity"]} == SENS_IDS
    for r in a["sensitivity"]:
        assert set(r) >= {"id", "label", "pct", "detail"}, r["id"]
    for w in a["windows"]:
        assert set(w) == WINDOW_KEYS, (w["window_id"], set(w) ^ WINDOW_KEYS)
        assert w["window_id"].startswith(w["route_id"] + "_")
        assert set(w["decomposition"]) == {"demand", "service", "generator",
                                           "scale"}
    assert a["assumptions_manifest"]["values_hash"]
    print(f"  D2 OK  schema ({len(a['windows'])} windows, "
          f"{len(a['sensitivity'])} sensitivity rows)")


def test_d3_ordinal_guardrails():
    if not os.path.exists(ARTIFACT):
        print("  D3 SKIP  (outputs/screen_results.json absent)")
        return
    a = json.load(open(ARTIFACT, encoding="utf-8"))

    def keys(o):
        if isinstance(o, dict):
            for k, v in o.items():
                yield k
                yield from keys(v)
        elif isinstance(o, list):
            for v in o:
                yield from keys(v)

    # (a) no boardings-denominated field anywhere (spec 01 §4 guardrail a)
    bad = [k for k in keys(a)
           if any(s in k.lower() for s in ("boarding", "rider", "ridership"))]
    assert not bad, f"boardings-shaped keys present: {bad}"
    # (b) predictions at exactly TWO service levels (guardrail b)
    lv = a["fit_diagnostics"]["service_levels"]
    assert len(lv) == 2 and lv[0].startswith("standardized") \
        and lv[1].startswith("incumbent-actual"), lv
    # disclaimer present and ordinal-worded
    assert "not a ridership forecast" in a["disclaimer"]
    print("  D3 OK  ordinal guardrails (no boardings fields; two service levels)")


def test_d4_double_run_determinism():
    if not HAVE_DATA:
        print("  D4 SKIP  (data/raw absent)")
        return
    import screen_scan as ss
    a = ss.build_artifact(n_boot=80, quiet=True)
    b = ss.build_artifact(n_boot=80, quiet=True)
    sa = json.dumps(ss._canon(a), sort_keys=True, indent=2)
    sb = json.dumps(ss._canon(b), sort_keys=True, indent=2)
    assert sa == sb, "screen artifact not byte-identical on in-process rerun"
    print(f"  D4 OK  in-process double-run byte-identity (B=80, "
          f"{len(sa):,} bytes)")


if __name__ == "__main__":
    test_p1_projection()
    test_p2_catchment_membership()
    test_p3_lodes_window_sums()
    test_p4_acs_sums()
    test_p5_generator_dummy()
    test_p6_buffer_sensitivity()
    test_p7_window_grid()
    test_p8_overlap_grouping()
    test_p9_pairwise_shares()
    test_d1_fit_scan_identity()
    test_d2_artifact_schema()
    test_d3_ordinal_guardrails()
    test_d4_double_run_determinism()
    print("ALL SCREEN TESTS PASS")
