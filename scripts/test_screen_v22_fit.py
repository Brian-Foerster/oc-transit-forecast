"""v2.2 phase-2b PRODUCTIVITY fit gate tests (spec 01 §10; the once-only
governed-method-change fit).

Fast tests read the committed artifact outputs/screen_results_v22.json and the
registry; the DV test unit-checks the estimand with NO data/raw; the
determinism test rebuilds twice in-process. Data-gated integration is guarded
(house Q6 pattern: skip cleanly when data/raw is absent). NONE of these tests
re-specs or tunes the fit.

  V1  the fit consumed the FROZEN thresholds via val() (not hardcoded literals)
      AND the estimand DV is log(boardings/RVH): design_matrix_v22 returns
      y = log(boardings) - log(RVH) and b3 (RVH) is GONE from the RHS
  V2  artifact battery rows == screen_battery_rows_v22 exactly (order included,
      17 rows) and it excludes the three productivity-undefined v21 rows
  V3  the fit universe (300 route-years / 63 clusters) + the pre-registered
      drops are as frozen (§10 D8 / §9.9.7); every kept row has RVH > 0
  V4  b4_wrong_sign flag is set (b4 negative under productivity too) and the
      §9.1/§10 D3 README known-issue exists
  V5  in-process double-run byte-identity of screen_results_v22.json
  V6  v2.0 screen_results.json (b88f9b65) + v2.1 screen_results_v21.json
      (83aeb032) stay byte-identical -- v2.2 is a NEW artifact
  V7  the artifact declares the v2.2 governance ids consumed via val()
      (screen_estimand_v22 + screen_battery_rows_v22) and does NOT consume the
      RETIRED screen_svc_std nor the v2.1 battery list (§10 D4/D6)

    python -X utf8 scripts/test_screen_v22_fit.py
"""
import hashlib
import json
import math
import os
import sys

import numpy as np
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "outputs")
RAW = os.path.join(HERE, "..", "data", "raw")
ART = os.path.join(OUT, "screen_results_v22.json")
V20 = os.path.join(OUT, "screen_results.json")
V21 = os.path.join(OUT, "screen_results_v21.json")

from assumptions import val                                     # noqa: E402
import screen_fit_v22 as sf                                     # noqa: E402

HAVE_DATA = (os.path.exists(os.path.join(RAW, "gtfs", "trips.txt"))
             and os.path.exists(os.path.join(RAW, "gtfs_archive",
                                             "octa_gtfs_fy2017_20170201.zip")))


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _mini_fit_rows():
    """A 4-row synthetic fit frame (2 routes x 2 panel FYs) with the columns
    design_matrix_v22 reads -- exercises the ESTIMAND with NO data/raw."""
    rows = []
    for rt, (b17, r17, b19, r19) in {
            "1": (1000.0, 100.0, 2000.0, 250.0),
            "2": (5000.0, 400.0, 6000.0, 500.0)}.items():
        for fy, b, rvh in (("fy2017", b17, r17), ("fy2019", b19, r19)):
            rows.append({"route": rt, "fy": fy, "boardings": b, "rvh": rvh,
                         "log_b": math.log(b), "L": 10.0, "flows": 50.0,
                         "zveh": 5.0, "e002": 3.0, "e016": 2.0, "popden": 100.0,
                         "genjobs": 20.0, "gen_dummy": 0,
                         "cns_CNS15": 1.0, "cns_CNS16": 1.0,
                         "cns_CNS17": 1.0, "cns_CNS18": 1.0})
    return pd.DataFrame(rows)


def test_v1_thresholds_via_val_and_productivity_dv():
    """The fit consumes the frozen thresholds via val() (no hardcoded literal)
    AND the DV is log(boardings/RVH): design_matrix_v22's y equals
    log(boardings) - log(RVH), and b3 (RVH) is absent from the RHS."""
    # (a) the estimand is the productivity DV, consumed via val()
    assert val("screen_estimand_v22") == "log(boardings/RVH)"
    df = _mini_fit_rows()
    y, X, names, groups, _ = sf.design_matrix_v22(df, sf.BASE_CFG_V22)
    expect = np.log(df["boardings"].to_numpy(float)) \
        - np.log(df["rvh"].to_numpy(float))
    assert np.allclose(y, expect), "DV is not log(boardings/RVH)"
    # b3 (RVH) is GONE from the RHS; the demand block + scale remain
    assert "b3_rvh" not in names, names
    for want in ("const", "b1_flows", "b2_zveh", "b4_genjobs", "b5_len"):
        assert want in names, (want, names)
    # RVH > 0 is asserted (DV finite) -- rvh = 0 must raise
    bad = df.copy(); bad.loc[0, "rvh"] = 0.0
    try:
        sf.design_matrix_v22(bad, sf.BASE_CFG_V22)
        raise SystemExit("design_matrix_v22 accepted rvh=0")
    except AssertionError:
        pass
    # (b) no threshold literal is hardcoded in the fit/scan source -- the
    # distinctive tripwire values must come from val(), never a literal
    for fn in ("screen_scan_v22.py", "screen_fit_v22.py"):
        src = open(os.path.join(HERE, fn), encoding="utf-8").read()
        for lit in ("0.841", "0.142857"):
            assert lit not in src, f"{fn} hardcodes threshold literal {lit!r}"
    # (c) the artifact's decision thresholds equal their frozen registry values
    if os.path.exists(ART):
        c = _load(ART)["decision_output"]["criteria"]
        assert c["sign_pos_frac"]["threshold"] == val("screen_pos_frac_min")
        assert c["battery_rho"]["threshold"] == val("screen_battery_rho_min")
        assert c["tie_churn"]["window"]["threshold"] == \
            val("screen_tie_churn_max_window")
        assert c["tie_churn"]["hostshape"]["threshold"] == \
            round(val("screen_tie_churn_max_hostshape"), 6)
    print("  V1 OK  DV = log(boardings/RVH) (b3 gone from the RHS); thresholds "
          "consumed via val(); no hardcoded threshold literal")


def test_v2_battery_rows_frozen():
    """Artifact sensitivity rows == screen_battery_rows_v22 exactly (order,
    17 rows) and it excludes the three productivity-undefined v21 rows."""
    if not os.path.exists(ART):
        print("  V2 SKIP  (v2.2 artifact absent)")
        return
    rows = [r["id"] for r in _load(ART)["sensitivity"]]
    assert rows == list(val("screen_battery_rows_v22")), rows
    assert len(rows) == 17, len(rows)
    for gone in ("drop_rh", "svc_p25", "svc_p75"):
        assert gone not in rows, f"{gone} must be absent under productivity"
    print("  V2 OK  artifact battery == frozen screen_battery_rows_v22 "
          "(17 rows, order-exact; drop_rh/svc_p25/svc_p75 excluded)")


def test_v3_universe_and_drops():
    """The fit universe (N route-years, cluster count) + drops are as frozen
    (§10 D8 / §9.9.7); every kept row has RVH > 0 (the productivity DV needs it)."""
    if not os.path.exists(ART):
        print("  V3 SKIP  (v2.2 artifact absent)")
        return
    d = _load(ART)["fit_diagnostics"]
    assert d["n_route_years"] == 300, d["n_route_years"]
    assert d["n_routes"] == 63, d["n_routes"]
    assert set(d["dropped_route_years_shapeless"]) == {
        "53X fy2017", "57X fy2017", "64X fy2017", "529 fy2022"}, \
        d["dropped_route_years_shapeless"]
    assert not any("553" in s for s in d["dropped_route_years_shapeless"])
    assert d["estimand"] == "log(boardings/RVH)"
    print("  V3 OK  fit N=300 route-years / 63 clusters; shapeless drops = "
          "the pre-registered 4 (553/fy2023 KEPT); estimand log(b/RVH)")


def test_v4_b4_wrong_sign_logged():
    """b4 came back negative under productivity too -> the §9.1/§10 D3
    b4_wrong_sign flag is SET, and the README obligation is discharged."""
    if not os.path.exists(ART):
        print("  V4 SKIP  (v2.2 artifact absent)")
        return
    fd = _load(ART)["fit_diagnostics"]
    ws = fd["b4_wrong_sign"]
    assert ws["flag"] is True and ws["b4_genjobs_est"] < 0.0, ws
    assert _load(ART)["decision_output"]["b4_wrong_sign"] is True
    readme = open(os.path.join(HERE, "..", "README.md"),
                  encoding="utf-8").read()
    assert "b4_wrong_sign" in readme, "the §9.1-obligated README entry is missing"
    print(f"  V4 OK  b4_wrong_sign flag set (b4_genjobs "
          f"{ws['b4_genjobs_est']:+.4f}); README known-issue present")


def test_v5_determinism():
    """Dual in-process build byte-identity of the v2.2 artifact (the manual
    dual FRESH-PROCESS check is in the batch report)."""
    if not HAVE_DATA:
        print("  V5 SKIP  (data/raw absent)")
        return
    import screen_scan_v22 as ss
    a = ss.build_artifact(n_boot=48, quiet=True)
    b = ss.build_artifact(n_boot=48, quiet=True)
    sa = json.dumps(ss._canon(a), sort_keys=True, indent=2)
    sb = json.dumps(ss._canon(b), sort_keys=True, indent=2)
    assert sa == sb, "v2.2 artifact not byte-identical on in-process rerun"
    print(f"  V5 OK  in-process double-run byte-identity (B=48, "
          f"{len(sa):,} bytes)")


def test_v6_v20_v21_untouched():
    """The committed v2.0 + v2.1 screen artifacts stay byte-identical -- v2.2
    is a NEW file and never overwrites them (§10)."""
    for name, path, want in (("v2.0", V20, "b88f9b65"),
                             ("v2.1", V21, "83aeb032")):
        if not os.path.exists(path):
            print(f"  V6 SKIP ({name} absent)")
            continue
        h = hashlib.sha256(open(path, "rb").read()).hexdigest()
        assert h.startswith(want), f"{name} sha changed: {h[:16]} (want {want})"
    print("  V6 OK  v2.0 (b88f9b65) + v2.1 (83aeb032) byte-identical")


def test_v7_manifest_governance_ids():
    """The artifact declares the v2.2 governance ids consumed via val()
    (screen_estimand_v22 + screen_battery_rows_v22) and does NOT consume the
    RETIRED screen_svc_std nor the v2.1 battery list (§10 D4/D6)."""
    if not os.path.exists(ART):
        print("  V7 SKIP  (v2.2 artifact absent)")
        return
    A = _load(ART)
    consumed = {c["id"] for c in A["assumptions_manifest"]["consumed"]}
    for cid in ("screen_estimand_v22", "screen_battery_rows_v22",
                "screen_pos_frac_min", "screen_panel_ext_fys",
                "screen_regime_split"):
        assert cid in consumed, f"{cid} not declared consumed"
    for cid in ("screen_svc_std", "screen_battery_rows_v21"):
        assert cid not in consumed, f"{cid} must NOT be consumed under v2.2"
    rs = A["decision_output"]["regime_split"]
    assert set(A["fit_diagnostics"]["rows_by_fy"]) == set(
        val("screen_panel_ext_fys"))
    assert "pre2020_pf" in rs and "regime_split_downgrade" in rs
    print("  V7 OK  v2.2 governance ids consumed; screen_svc_std + "
          "screen_battery_rows_v21 NOT consumed")


if __name__ == "__main__":
    test_v1_thresholds_via_val_and_productivity_dv()
    test_v2_battery_rows_frozen()
    test_v3_universe_and_drops()
    test_v4_b4_wrong_sign_logged()
    test_v6_v20_v21_untouched()
    test_v7_manifest_governance_ids()
    test_v5_determinism()
    print("ALL V22 PHASE-2B FIT TESTS PASS")
