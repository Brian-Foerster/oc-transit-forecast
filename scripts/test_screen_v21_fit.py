"""v2.1 phase-2b fit gate tests (spec 01 §9; the once-only rebuild).

Fast tests read the committed artifact outputs/screen_results_v21.json and the
registry; the determinism test rebuilds twice in-process. Data-gated on the
archived GTFS + block/vintage tables (house Q6 pattern: skip cleanly when
absent). NONE of these tests re-specs or tunes the fit.

  W1  decision-output thresholds equal the FROZEN registry values (val()),
      not hardcoded literals -- and the source carries no threshold literal
  W2  artifact battery rows == screen_battery_rows_v21 exactly, order included
  W3  the fit universe + the pre-registered drops are as frozen (§9.3/§9.9.7)
  W4  b4_wrong_sign flag is set (b4 negative) and the README known-issue exists
  W5  in-process double-run byte-identity of screen_results_v21.json
  W6  the committed v2.0 screen_results.json is byte-identical (b88f9b65) --
      v2.1 is a NEW artifact, v2.0 untouched
  W7  the v2.1 fit uses the EXACT frozen 6-FY panel + regime-split gate ids

    python -X utf8 scripts/test_screen_v21_fit.py
"""
import hashlib
import json
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "outputs")
RAW = os.path.join(HERE, "..", "data", "raw")
ART = os.path.join(OUT, "screen_results_v21.json")
V20 = os.path.join(OUT, "screen_results.json")

from assumptions import val                                    # noqa: E402

HAVE_DATA = (os.path.exists(os.path.join(RAW, "gtfs", "trips.txt"))
             and os.path.exists(os.path.join(RAW, "gtfs_archive",
                                             "octa_gtfs_fy2017_20170201.zip")))


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def test_w1_thresholds_via_val():
    """Every decision threshold in the artifact equals its FROZEN registry
    value, and no threshold literal is hardcoded in the fit/scan source."""
    if not os.path.exists(ART):
        print("  W1 SKIP  (v2.1 artifact absent)")
        return
    c = _load(ART)["decision_output"]["criteria"]
    assert c["sign_pos_frac"]["threshold"] == val("screen_pos_frac_min")
    assert c["battery_rho"]["threshold"] == val("screen_battery_rho_min")
    assert c["tie_churn"]["window"]["threshold"] == \
        val("screen_tie_churn_max_window")
    # the artifact canon-rounds floats to 6 dp; 2/14 stores as 0.142857
    assert c["tie_churn"]["hostshape"]["threshold"] == \
        round(val("screen_tie_churn_max_hostshape"), 6)
    # source carries no threshold literal (the distinctive tripwire values
    # must come from val(), never a hardcoded number)
    for fn in ("screen_scan_v21.py", "screen_fit_v21.py"):
        src = open(os.path.join(HERE, fn), encoding="utf-8").read()
        for lit in ("0.841", "0.142857"):
            assert lit not in src, f"{fn} hardcodes threshold literal {lit!r}"
    print("  W1 OK  decision thresholds consumed via val(); no hardcoded "
          "threshold literal in the fit/scan source")


def test_w2_battery_rows_frozen():
    """Artifact sensitivity rows == screen_battery_rows_v21 exactly (order
    included) -- the battery criterion is a MIN, so an unfrozen list is a
    tunable bar (test D2 pattern extended to v2.1)."""
    if not os.path.exists(ART):
        print("  W2 SKIP  (v2.1 artifact absent)")
        return
    rows = [r["id"] for r in _load(ART)["sensitivity"]]
    assert rows == list(val("screen_battery_rows_v21")), (rows,
                                                          val("screen_battery_rows_v21"))
    assert len(rows) == 20
    print(f"  W2 OK  artifact battery == frozen screen_battery_rows_v21 "
          f"(20 rows, order included)")


def test_w3_universe_and_drops():
    """The fit universe (N route-years, cluster count) and the pre-registered
    contemporaneous-shape drops are as frozen (§9.3/§9.9.7)."""
    if not os.path.exists(ART):
        print("  W3 SKIP  (v2.1 artifact absent)")
        return
    d = _load(ART)["fit_diagnostics"]
    assert d["n_route_years"] == 300, d["n_route_years"]
    assert d["n_routes"] == 63, d["n_routes"]
    assert set(d["dropped_route_years_shapeless"]) == {
        "53X fy2017", "57X fy2017", "64X fy2017", "529 fy2022"}, \
        d["dropped_route_years_shapeless"]
    # 553/fy2023 must be KEPT (§9.9.7 correction), not dropped
    assert not any("553" in s for s in d["dropped_route_years_shapeless"])
    print(f"  W3 OK  fit N=300 route-years / 63 clusters; shapeless drops = "
          f"the pre-registered 4 (553/fy2023 KEPT)")


def test_w4_b4_wrong_sign_logged():
    """b4 came back negative -> the §9.1 b4_wrong_sign flag is SET, and the
    obligation (a README known-issue entry) is discharged."""
    if not os.path.exists(ART):
        print("  W4 SKIP  (v2.1 artifact absent)")
        return
    fd = _load(ART)["fit_diagnostics"]
    ws = fd["b4_wrong_sign"]
    assert ws["flag"] is True and ws["b4_genjobs_est"] < 0.0, ws
    assert _load(ART)["decision_output"]["b4_wrong_sign"] is True
    readme = open(os.path.join(HERE, "..", "README.md"),
                  encoding="utf-8").read()
    assert "b4_wrong_sign" in readme, "the §9.1-obligated README entry is missing"
    print(f"  W4 OK  b4_wrong_sign flag set (b4_genjobs "
          f"{ws['b4_genjobs_est']:+.4f}); README known-issue present")


def test_w5_determinism():
    """Dual in-process build byte-identity of the v2.1 artifact (determinism
    gate; the manual dual FRESH-PROCESS check is in the batch report)."""
    if not HAVE_DATA:
        print("  W5 SKIP  (data/raw absent)")
        return
    import screen_scan_v21 as ss
    a = ss.build_artifact(n_boot=48, quiet=True)
    b = ss.build_artifact(n_boot=48, quiet=True)
    sa = json.dumps(ss._canon(a), sort_keys=True, indent=2)
    sb = json.dumps(ss._canon(b), sort_keys=True, indent=2)
    assert sa == sb, "v2.1 artifact not byte-identical on in-process rerun"
    print(f"  W5 OK  in-process double-run byte-identity (B=48, "
          f"{len(sa):,} bytes)")


def test_w6_v20_untouched():
    """The committed v2.0 screen_results.json stays byte-identical (b88f9b65)
    -- v2.1 is a NEW artifact and never overwrites it."""
    if not os.path.exists(V20):
        print("  W6 SKIP  (v2.0 artifact absent)")
        return
    h = hashlib.sha256(open(V20, "rb").read()).hexdigest()
    assert h.startswith("b88f9b65"), f"v2.0 artifact sha changed: {h[:16]}"
    print(f"  W6 OK  v2.0 screen_results.json byte-identical (sha {h[:8]})")


def test_w7_frozen_panel_and_regime():
    """The v2.1 fit consumed the frozen 6-FY panel and the regime-split gate;
    the artifact declares them in its assumptions_manifest (consumption via
    val(), spec 01 §9.10 / §9.9)."""
    if not os.path.exists(ART):
        print("  W7 SKIP  (v2.1 artifact absent)")
        return
    A = _load(ART)
    consumed = {c["id"] for c in
                A["assumptions_manifest"]["consumed"]}
    for cid in ("screen_panel_ext_fys", "screen_regime_split",
                "screen_battery_rows_v21", "screen_pos_frac_min"):
        assert cid in consumed, f"{cid} not declared consumed"
    rs = A["decision_output"]["regime_split"]
    assert set(A["fit_diagnostics"]["rows_by_fy"]) == set(
        val("screen_panel_ext_fys"))
    assert "pre2020_pf" in rs and "regime_split_downgrade" in rs
    print("  W7 OK  frozen 6-FY panel + regime-split gate consumed and "
          "declared")


if __name__ == "__main__":
    test_w1_thresholds_via_val()
    test_w2_battery_rows_frozen()
    test_w3_universe_and_drops()
    test_w4_b4_wrong_sign_logged()
    test_w6_v20_untouched()
    test_w7_frozen_panel_and_regime()
    test_w5_determinism()
    print("ALL V21 PHASE-2B FIT TESTS PASS")
