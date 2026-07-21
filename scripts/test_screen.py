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
  P10 tie_churn_stats (shortlist-stability arithmetic) on synthetic tie
      sets: margin-defined tie_in/tie_out, Jaccard, tie_churn_frac, and
      the empty-set edge cases

Data-gated tests (house Q6 pattern -- skip cleanly when data/raw or the
generated artifact is absent):

  D1  fit==scan predictor identity on Route 43 (spec 01 §3.2 / panel D6)
  D2  artifact schema (top-level + per-window + the 16 sensitivity ids +
      shortlist_stability per-row ids == the FROZEN registry battery list,
      order included, with explicit unit fields)
  D3  ordinal guardrails: no boardings-denominated field anywhere in the
      artifact; predictions at exactly TWO service levels (D10)
  D4  in-process double-run determinism of the scan pipeline (reduced B)
  D5  same-exposure index rebase (SC batch 2026-07-19) is a positive scalar
      multiple of the superseded own-length-route baseline -- rank vector
      identical (monotone rescale)
  D6  decision_output tripwire v2 (spec 01 §5, owner review 2026-07-20):
      pos_frac values recomputed from the stored replicate_signs strings;
      pass booleans recomputed; tie_churn threshold null -> pass null ->
      ordinal_ok FALSE BY CONSTRUCTION (fail-safe); shortlist ==
      tie_with_cutoff windows grouped by host; stability aggregate
      recomputed from the stored per-row entries
  D7  nb2_beta_fixed_alpha (the stability block's fixed-alpha NB2 refit)
      reproduces the statsmodels NB2 beta at the headline alpha

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


def test_p10_tie_churn_stats():
    """Owner review 2026-07-20: the shortlist-stability arithmetic on
    synthetic tie sets -- margin-defined replacements vs the headline tie
    set, Jaccard, tie_churn_frac, empty-set edges."""
    from screen_scan import tie_churn_stats
    head = {"a", "b", "c", "d"}
    st = tie_churn_stats(head, {"a", "b", "e"})
    assert st["tie_in"] == ["e"] and st["tie_out"] == ["c", "d"]
    assert st["n_tie_in"] == 1 and st["n_tie_out"] == 2
    assert abs(st["jaccard"] - 2.0 / 5.0) < 1e-12
    assert abs(st["tie_churn_frac"] - 2.0 / 4.0) < 1e-12   # max(1,2)/|head|
    # identical sets: no churn, jaccard 1
    st = tie_churn_stats(head, set(head))
    assert st["jaccard"] == 1.0 and st["tie_churn_frac"] == 0.0
    assert st["tie_in"] == [] and st["tie_out"] == []
    # disjoint sets: jaccard 0; churn frac max(in,out)/|head|
    st = tie_churn_stats(head, {"x", "y"})
    assert st["jaccard"] == 0.0
    assert abs(st["tie_churn_frac"] - 4.0 / 4.0) < 1e-12
    # both empty: jaccard defined as 1.0, frac 0 (max(1,|head|) guard)
    st = tie_churn_stats(set(), set())
    assert st["jaccard"] == 1.0 and st["tie_churn_frac"] == 0.0
    # empty headline, non-empty row: guard denominator 1
    st = tie_churn_stats(set(), {"x"})
    assert st["jaccard"] == 0.0 and st["tie_churn_frac"] == 1.0
    print("  P10 OK  tie_churn_stats (margin-defined churn arithmetic)")


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
              "shortlist_stability", "decision_output", "notes"):
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
    # FROZEN battery row list (owner review 2026-07-20): the registry list
    # is the single source; the artifact's sensitivity ids and the
    # shortlist_stability per-row ids must match it exactly -- the
    # stability rows IN ORDER (adding/dropping a row is an owner-approved
    # spec amendment; the battery is a MIN)
    frozen = val("screen_battery_rows")
    assert SENS_IDS == set(frozen), "SENS_IDS drifted from the registry"
    assert {r["id"] for r in a["sensitivity"]} == set(frozen)
    ss = a["shortlist_stability"]
    assert set(ss) == {"per_row", "aggregate", "note"}
    assert [r["id"] for r in ss["per_row"]] == list(frozen), \
        "shortlist_stability rows != frozen registry battery list (order)"
    # explicit per-row unit fields ('host_shape' only for the two
    # window-length rows -- the artifact's two admitted churn units)
    for r in ss["per_row"]:
        want = ("host_shape" if r["id"] in ("window_10", "window_15")
                else "window_id")
        assert r["unit"] == want, (r["id"], r["unit"])
        assert r["hard_top8_churn"]["unit"] == want
        for k in ("n_tie_row", "n_tie_headline", "tie_in", "tie_out",
                  "n_tie_in", "n_tie_out", "jaccard", "tie_churn_frac",
                  "hard_top8_churn"):
            assert k in r, (r["id"], k)
    assert set(ss["aggregate"]) == {
        "min_jaccard", "worst_row", "max_tie_churn_frac_window",
        "max_tie_churn_row_window", "max_tie_churn_frac_hostshape",
        "max_tie_churn_row_hostshape", "n_tie_headline",
        "stable_core", "n_stable_core"}
    # criterion-3 UNIT FIX report-only exclusion is GONE (owner review
    # 2026-07-20 ratification batch -- dual threshold; window_10/window_15
    # feed the host-shape sub-criterion, not an exclusion list)
    assert "criterion3_excluded_rows" not in ss["aggregate"]
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


def test_d5_rebase_rank_invariance():
    """SC batch 2026-07-19 item 1: the same-exposure baseline (median fitted
    host route's own BEST 12.5-mi-window prediction) is a POSITIVE SCALAR
    MULTIPLE of the superseded own-length-route baseline, so the rank vector
    is identical (monotone rescale)."""
    if not HAVE_DATA:
        print("  D5 SKIP  (data/raw absent)")
        return
    import screen_fit as sf
    import screen_scan as ss
    inputs = sf.load_screen_inputs()
    projs = sf.gtfs_universe(inputs)
    asm = ss.assemble(inputs, projs, {}, val("buffer_mi"),
                      val("screen_window_mi"), val("screen_step_mi"))
    head = ss.score(asm, sf.BASE_CFG, val("screen_svc_std"))
    # superseded baseline: lower-median fitted route AT ITS OWN LENGTH
    rp = np.asarray(head["route_pred"])
    old_base = float(np.sort(rp)[(len(rp) - 1) // 2])
    old_idx = 100.0 * np.exp(head["win_pred"] - old_base)
    new_idx = np.asarray(head["index"])
    ratio = new_idx / old_idx
    assert ratio.min() > 0.0
    assert np.allclose(ratio, ratio[0], rtol=1e-12, atol=0.0), \
        "rebase is not a common positive scalar multiple"
    wids = asm["W"]["window_id"]
    r_old, _ = ss._ranking(old_idx, wids)
    r_new, _ = ss._ranking(new_idx, wids)
    assert (r_old == r_new).all(), "rank vector changed under the rebase"
    # baseline really is the lower-median of per-fitted-route best windows
    best = [float(head["win_pred"][g].max()) for g in head["host_groups"]]
    assert abs(head["base_logpred"]
               - sorted(best)[(len(best) - 1) // 2]) < 1e-12
    print(f"  D5 OK  same-exposure rebase = x{ratio[0]:.6f} common rescale; "
          f"rank vector identical over {len(wids)} windows "
          f"({len(best)} fitted host routes in the baseline median)")


def test_d6_decision_output():
    """Decision tripwire v2 (owner review 2026-07-20, ratification batch):
    criterion 1's pos_frac recomputed from the stored replicate_signs;
    criterion 2's 0.7 threshold LIVE (the 'provisional' marker removed);
    criterion 3 a DUAL THRESHOLD (window-unit + host-shape-unit
    sub-criteria, BOTH fail on v2.0; the PW-batch report-only exclusion of
    window_10/window_15 is REVERTED and criterion3_excluded_rows is GONE --
    the two length rows feed the host-shape sub-criterion); ordinal_ok
    recomputed from the three criteria and FALSE on v2.0; the three
    new/changed threshold ids are consumed in the manifest; shortlist ==
    tie_with_cutoff windows grouped by host; stability aggregate recomputed
    from the stored per-row entries."""
    if not os.path.exists(ARTIFACT):
        print("  D6 SKIP  (outputs/screen_results.json absent)")
        return
    a = json.load(open(ARTIFACT, encoding="utf-8"))
    do = a["decision_output"]
    assert set(do) == {"ordinal_ok", "criteria", "decision_format",
                       "shortlist", "note", "diagnostics",
                       "replicate_signs"}, set(do)
    c = do["criteria"]
    assert set(c) == {"sign_pos_frac", "battery_rho", "tie_churn"}
    assert set(c["sign_pos_frac"]) == {"b1_pos_frac", "b2_pos_frac",
                                       "threshold", "pass"}
    # criterion 2 is LIVE: no 'provisional' threshold_status marker anymore
    assert set(c["battery_rho"]) == {"min_rho", "worst_row_id", "threshold",
                                     "pass"}
    assert "threshold_status" not in c["battery_rho"]
    # criterion 3 is a DUAL THRESHOLD: window + hostshape sub-criteria, each
    # {max, threshold, worst_row, pass}; there is NO top-level tie_churn.pass
    tc = c["tie_churn"]
    assert set(tc) == {"window", "hostshape"}
    assert "pass" not in tc
    tw, th = tc["window"], tc["hostshape"]
    assert set(tw) == {"max_over_window_unit_rows", "threshold", "worst_row",
                       "pass"}
    assert set(th) == {"max_over_window10_window15", "threshold", "worst_row",
                       "pass"}
    # thresholds: all registry-sourced and LIVE (criterion 3 no longer null).
    # Artifact floats are canonically rounded to CANON_DECIMALS=6 dp on write
    # (_canon), so the STORED threshold is the 6dp image of the registry value.
    # screen_tie_churn_max_hostshape is now the EXACT rational 2/14 =
    # 0.142857142857... (reviewer fix 2026-07-21 -- so the '<=' cap boundary is
    # exact at runtime, where the comparison uses the raw val(), not this
    # rounded display); its 6dp image is 0.142857. The other three thresholds
    # are 6dp-exact so round() is a no-op for them.
    import screen_scan as _ss
    rnd = lambda x: round(x, _ss.CANON_DECIMALS)
    assert c["sign_pos_frac"]["threshold"] == rnd(val("screen_pos_frac_min"))
    assert c["battery_rho"]["threshold"] == rnd(val("screen_battery_rho_min"))
    assert tw["threshold"] == rnd(val("screen_tie_churn_max_window"))
    assert th["threshold"] == rnd(val("screen_tie_churn_max_hostshape"))
    # the runtime cap boundary itself is exact: a phase-2b 2-shape flip of
    # churn exactly 2/14 passes '<= val()' because val() is the exact rational
    assert (2.0 / 14.0) <= val("screen_tie_churn_max_hostshape")
    # the three new/changed threshold ids are CONSUMED in the manifest
    # (check_assumptions verifies the same; a standing test pins it here)
    consumed = {cc["id"] for cc in a["assumptions_manifest"]["consumed"]}
    for tid in ("screen_battery_rho_min", "screen_tie_churn_max_window",
                "screen_tie_churn_max_hostshape"):
        assert tid in consumed, f"{tid} not consumed in the manifest"
    # criterion 1: recompute pos_frac from the stored replicate signs
    rs = do["replicate_signs"]
    n_boot = a["n_boot"]
    for k in ("b1", "b2", "b4"):
        assert len(rs[k]) == n_boot and set(rs[k]) <= {"+", "-"}, k
    b1_pf = rs["b1"].count("+") / n_boot
    b2_pf = rs["b2"].count("+") / n_boot
    assert abs(b1_pf - c["sign_pos_frac"]["b1_pos_frac"]) < 1e-6
    assert abs(b2_pf - c["sign_pos_frac"]["b2_pos_frac"]) < 1e-6
    assert abs(rs["b4"].count("+") / n_boot
               - do["diagnostics"]["b4_pos_frac"]) < 1e-6
    # internal consistency: recompute the pass booleans + ordinal_ok
    assert c["sign_pos_frac"]["pass"] == (
        min(b1_pf, b2_pf) >= c["sign_pos_frac"]["threshold"])
    assert c["battery_rho"]["pass"] == (c["battery_rho"]["min_rho"]
                                        >= c["battery_rho"]["threshold"])
    assert tw["pass"] == (tw["max_over_window_unit_rows"] <= tw["threshold"])
    assert th["pass"] == (th["max_over_window10_window15"] <= th["threshold"])
    # ordinal_ok = criterion 1 AND criterion 2 AND BOTH criterion-3 subs
    crit3_pass = tw["pass"] and th["pass"]
    ok = (c["sign_pos_frac"]["pass"] is True
          and c["battery_rho"]["pass"] is True
          and crit3_pass is True)
    assert do["ordinal_ok"] == ok
    # measured on the current v2.0 artifact: BOTH criterion-3 sub-criteria
    # FAIL (window-unit e016_swap churn 0.848 > 0.20; host-shape window_10
    # churn 8/14 = 0.571 > 2/14) -> ordinal_ok FALSE
    assert tw["pass"] is False and th["pass"] is False
    assert do["ordinal_ok"] is False
    assert do["decision_format"] == "threshold_shortlist"
    # diagnostics: analytic |t| retained, recomputable from coefficients
    coef = a["fit_diagnostics"]["coefficients"]
    min_t = min(abs(v["est"]) / v["se_cluster"] for k, v in coef.items()
                if k.startswith(("b1_", "b2_")))
    assert abs(min_t - do["diagnostics"]["min_abs_t_demand"]) < 1e-4
    # criterion 2 cross-check vs the stored sensitivity rows
    rhos = {r["id"]: r["detail"]["rho"] for r in a["sensitivity"]}
    assert abs(min(rhos.values()) - c["battery_rho"]["min_rho"]) < 5e-6
    assert c["battery_rho"]["worst_row_id"] in rhos
    # criterion 3 == stability aggregate; aggregate recomputed from the
    # stored per-row entries (dual-threshold tie-churn recomputation)
    ss = a["shortlist_stability"]
    agg = ss["aggregate"]
    assert tw["max_over_window_unit_rows"] == agg["max_tie_churn_frac_window"]
    assert tw["worst_row"] == agg["max_tie_churn_row_window"]
    assert (th["max_over_window10_window15"]
            == agg["max_tie_churn_frac_hostshape"])
    assert th["worst_row"] == agg["max_tie_churn_row_hostshape"]
    # by_class rows contribute CLASS-WISE extremes to the aggregate
    # (review 2026-07-20 major finding 2: Jaccard-min and churn-frac-max
    # need not coincide in one class; per_row-only scanning could
    # understate criterion 3 -- bias toward PASS)
    def _jacs(r):
        bc = r.get("by_class")
        return ([v["jaccard"] for v in bc.values()] if bc
                else [r["jaccard"]])

    def _fracs(r):
        bc = r.get("by_class")
        return ([v["tie_churn_frac"] for v in bc.values()] if bc
                else [r["tie_churn_frac"]])

    # DUAL THRESHOLD (owner review 2026-07-20 ratification batch): the
    # window-unit max scans unit=='window_id' rows; the host-shape max scans
    # window_10/window_15 (unit=='host_shape'); the PW-batch exclusion list
    # is GONE. min_jaccard stays an all-rows report aggregate (feeds no
    # criterion).
    win_rows = [r for r in ss["per_row"] if r["unit"] == "window_id"]
    host_rows = [r for r in ss["per_row"] if r["unit"] == "host_shape"]
    assert {r["id"] for r in host_rows} == {"window_10", "window_15"}
    fracs_w = [max(_fracs(r)) for r in win_rows]
    fracs_h = [max(_fracs(r)) for r in host_rows]
    jacs = [min(_jacs(r)) for r in ss["per_row"]]
    assert abs(max(fracs_w) - agg["max_tie_churn_frac_window"]) < 5e-6
    assert abs(max(fracs_h) - agg["max_tie_churn_frac_hostshape"]) < 5e-6
    assert abs(min(jacs) - agg["min_jaccard"]) < 5e-6
    worst = ss["per_row"][jacs.index(min(jacs))]["id"]
    assert agg["worst_row"] == worst
    assert (win_rows[fracs_w.index(max(fracs_w))]["id"]
            == agg["max_tie_churn_row_window"])
    assert (host_rows[fracs_h.index(max(fracs_h))]["id"]
            == agg["max_tie_churn_row_hostshape"])
    assert "criterion3_excluded_rows" not in agg
    # the by_class entry tuple is the min-Jaccard class (published rule)
    for r in ss["per_row"]:
        if "by_class" in r:
            assert abs(r["jaccard"] - min(_jacs(r))) < 5e-6, r["id"]
    # per-row churn stats recompute from the stored tie_in/tie_out lists
    for r in ss["per_row"]:
        assert r["n_tie_in"] == len(r["tie_in"])
        assert r["n_tie_out"] == len(r["tie_out"])
        expect = (max(r["n_tie_in"], r["n_tie_out"])
                  / max(1, r["n_tie_headline"]))
        # artifact floats are canonically rounded to 6 dp (CANON_DECIMALS)
        assert abs(r["tie_churn_frac"] - expect) < 5e-6, r["id"]
    # stable core: a subset of the headline tie set, consistent with every
    # window-unit row's tie_out and every host-unit row's surviving hosts
    ties = {w["window_id"]: w for w in a["windows"] if w["tie_with_cutoff"]}
    core = set(agg["stable_core"])
    assert core <= set(ties)
    assert agg["n_stable_core"] == len(core)
    for r in ss["per_row"]:
        if r["unit"] != "window_id":
            continue
        if "by_class" in r:
            for cls, v in r["by_class"].items():
                assert not (core & set(v["tie_out"])), (r["id"], cls)
        else:
            assert not (core & set(r["tie_out"])), r["id"]
    # shortlist: exactly the tie_with_cutoff windows, indicators intact,
    # grouped by host shape (each host's entries contiguous)
    assert {s["window_id"] for s in do["shortlist"]} == set(ties)
    for s in do["shortlist"]:
        assert set(s) == {"route_id", "window_id", "screen_index_p50",
                          "underservice_flag"}
        w = ties[s["window_id"]]
        assert s["route_id"] == w["route_id"]
        assert s["screen_index_p50"] == w["screen_index_p50"]
        assert s["underservice_flag"] == w["underservice_flag"]
    seen, prev = set(), None
    for s in do["shortlist"]:
        h = s["route_id"]
        if h != prev:
            assert h not in seen, "shortlist not grouped by host shape"
            seen.add(h)
            prev = h
    print(f"  D6 OK  decision_output v2 dual-threshold; format "
          f"{do['decision_format']}; pos_frac b1 "
          f"{c['sign_pos_frac']['b1_pos_frac']:.4f} / b2 "
          f"{c['sign_pos_frac']['b2_pos_frac']:.4f} vs "
          f"{c['sign_pos_frac']['threshold']} "
          f"({'PASS' if c['sign_pos_frac']['pass'] else 'FAIL'}); "
          f"min rho {c['battery_rho']['min_rho']:.3f} "
          f"({c['battery_rho']['worst_row_id']}) vs "
          f"{c['battery_rho']['threshold']} live "
          f"({'PASS' if c['battery_rho']['pass'] else 'FAIL'}); tie_churn "
          f"window {tw['max_over_window_unit_rows']:.3f} ({tw['worst_row']}) "
          f"vs {tw['threshold']} ({'PASS' if tw['pass'] else 'FAIL'}) / "
          f"hostshape {th['max_over_window10_window15']:.3f} "
          f"({th['worst_row']}) vs {th['threshold']} "
          f"({'PASS' if th['pass'] else 'FAIL'}); ordinal_ok "
          f"{do['ordinal_ok']}; stable core "
          f"{agg['n_stable_core']}/{agg['n_tie_headline']}; shortlist "
          f"{len(do['shortlist'])} windows / {len(seen)} host shapes")


def test_d7_nb2_fixed_alpha():
    """The stability block's fixed-alpha NB2 refit (stated approximation,
    spec 01 §5): at the statsmodels headline alpha, Fisher-scored beta
    reproduces the statsmodels NB2 beta (at the joint MLE the fixed-alpha
    beta optimum IS the joint beta optimum)."""
    if not HAVE_DATA:
        print("  D7 SKIP  (data/raw absent)")
        return
    import numpy as np
    import screen_fit as sf
    inputs = sf.load_screen_inputs()
    projs = sf.gtfs_universe(inputs)
    fit = sf.build_fit_frame(projs, inputs, val("buffer_mi"))
    y, X, names, groups, df = sf.design_matrix(fit["rows"], sf.BASE_CFG)
    beta_ols = sf.ols_beta(y, X)
    counts = df["boardings"].to_numpy(float)
    nb_beta, alpha, conv = sf.fit_nb2(counts, y, X, beta_ols)
    assert conv
    resid = y - X @ beta_ols
    s2 = float(resid @ resid) / max(len(y) - X.shape[1], 1)
    start = beta_ols.copy()
    start[0] += s2 / 2.0
    fb = sf.nb2_beta_fixed_alpha(counts, X, alpha, start)
    diff = float(np.max(np.abs(fb - nb_beta)))
    assert diff < 1e-5, f"fixed-alpha Fisher beta off by {diff}"
    print(f"  D7 OK  nb2_beta_fixed_alpha == statsmodels NB2 beta at "
          f"headline alpha {alpha:.5f} (max |diff| {diff:.2e})")


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
    test_p10_tie_churn_stats()
    test_d1_fit_scan_identity()
    test_d2_artifact_schema()
    test_d3_ordinal_guardrails()
    test_d4_double_run_determinism()
    test_d5_rebase_rank_invariance()
    test_d6_decision_output()
    test_d7_nb2_fixed_alpha()
    print("ALL SCREEN TESTS PASS")
