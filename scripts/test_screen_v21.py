"""v2.1 predictor-machinery tests (spec 01 §9; phase 2a).

ALL tests run on a committed SYNTHETIC fixture (toy blocks/tracts/vintages
defined below, mi-space) -- NO real data is fitted or even read, honoring
the §9 pre-registration hold: the archived-GTFS input is still blocked, so
the rebuilt fit must not run, and this file never joins predictors to
boardings.

  V1  vintage dispatch table (fy2017/fy2019/fy2020q3/scan; unknown raises)
  V2  pop-weight apportionment arithmetic (conservation, zero-pop equal
      split, missing-tract zeros)
  V3  tract10 -> tract20 bridge shares (conservation through apply_bridge)
  V4  catchment membership: |offset| <= buffer AND position in [w0, w1],
      inclusive; buffer edge behavior
  V5  window clipping to [0, L]; l_len from the clipped window; empty
      windows raise
  V6  both-ends-in O-D window summing (intra-block rows included), per
      vintage
  V7  vintage dispatch through compute_predictors_v21: fy2017 != fy2019
      numbers; fy2020q3 == fy2019 exactly; scan reads 2022/2023
  V8  the §9.1 vector arithmetic: log1p sums, l_rvh passthrough (None
      without rvh; log(rvh) with; nonpositive raises), popden, gen dummy
  V9  loader round-trip: fixture CSVs (schema-identical to the
      build_derived_v21 outputs) written to a scratch dir, loaded via
      load_data_v21, reproduce the in-memory fixture's numbers
  V10 GUARD (standing): no fit machinery exists in screen_common_v21 --
      no *fit* name, no statsmodels/OLS import; fitting stays in
      screen_fit until phase 2b

    python -X utf8 scripts/test_screen_v21.py
"""
import gzip
import math
import os
import sys
import tempfile

import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import screen_common_v21 as sv                                 # noqa: E402
from assumptions import val                                    # noqa: E402

SQMI = sv.SQM_PER_SQMI


# ---------------------------------------------------------------------------
# synthetic fixture: one straight 10-mi shape on the x-axis; 6 blocks in
# 3 tracts; 2 vintages of OD/WAC/ACS with deliberately different numbers.
# ---------------------------------------------------------------------------
#   block  x     y     tract  pop  aland(sqmi)
#   0      1.0   0.2   T1     10   0.5
#   1      2.0  -0.5   T1     30   1.0
#   2      6.0   0.9   T2     20   0.5     (buffer edge: |off| == 0.9)
#   3      6.5   0.0   T2      0   0.25
#   4      9.5   0.3   T3      0   0.25    (T3 pop total 0 -> equal split)
#   5     12.0   0.0   T3      0   1.0     (beyond L -> pos clamps to 10)
BLOCK_TRACT = ["T1", "T1", "T2", "T2", "T3", "T3"]
BLOCK_POP = np.array([10.0, 30.0, 20.0, 0.0, 0.0, 0.0])
BLOCK_ALAND = np.array([0.5, 1.0, 0.5, 0.25, 0.25, 1.0]) * SQMI  # m^2
BX = np.array([1.0, 2.0, 6.0, 6.5, 9.5, 12.0])
BY = np.array([0.2, -0.5, 0.9, 0.0, 0.3, 0.0])

ACS_FIX = {
    # per-block apportioned values, computed by hand from tract tables:
    # 2017: T1 zveh=40 (block0 10, block1 30), T2 zveh=8 (b2 8, b3 0),
    #       T3 zveh=6 (equal split 3/3); pop: T1 400, T2 200, T3 60
    "2017": {"zveh": np.array([10.0, 30.0, 8.0, 0.0, 3.0, 3.0]),
             "pop": np.array([100.0, 300.0, 200.0, 0.0, 30.0, 30.0]),
             "e016": np.array([1.0, 3.0, 4.0, 0.0, 0.5, 0.5]),
             "e002": np.array([2.0, 6.0, 8.0, 0.0, 1.0, 1.0])},
    # 2019: doubled tract totals -> doubled per-block values
    "2019": {"zveh": np.array([20.0, 60.0, 16.0, 0.0, 6.0, 6.0]),
             "pop": np.array([200.0, 600.0, 400.0, 0.0, 60.0, 60.0]),
             "e016": np.array([2.0, 6.0, 8.0, 0.0, 1.0, 1.0]),
             "e002": np.array([4.0, 12.0, 16.0, 0.0, 2.0, 2.0])},
    "2023": {"zveh": np.array([30.0, 90.0, 24.0, 0.0, 9.0, 9.0]),
             "pop": np.array([300.0, 900.0, 600.0, 0.0, 90.0, 90.0]),
             "e016": np.array([3.0, 9.0, 12.0, 0.0, 1.5, 1.5]),
             "e002": np.array([6.0, 18.0, 24.0, 0.0, 3.0, 3.0])},
}
OD_FIX = {
    # (h_idx, w_idx, n): includes an intra-block row (1,1) and a pair whose
    # far end (block 4, pos 9.5) leaves the [0, 7] window
    "2017": (np.array([0, 1, 0, 2]), np.array([1, 1, 4, 3]),
             np.array([5.0, 3.0, 7.0, 9.0])),
    "2019": (np.array([0, 1]), np.array([1, 1]), np.array([11.0, 13.0])),
    "2022": (np.array([2, 4]), np.array([3, 4]), np.array([17.0, 19.0])),
}
GENJOBS_FIX = {
    "2017": np.array([100.0, 0.0, 40.0, 0.0, 6.0, 0.0]),
    "2019": np.array([200.0, 0.0, 80.0, 0.0, 12.0, 0.0]),
    "2022": np.array([300.0, 0.0, 120.0, 0.0, 18.0, 0.0]),
}
GEN_XY = (np.array([6.0, 2.0]), np.array([0.5, -2.0]))   # G0 in, G1 off-line
GEN_TYPES = ["resort", "college"]


def _data():
    geoids = [f"06059000{i}00{i}00{i}" for i in range(6)]
    return sv.ScreenDataV21(geoids, BX, BY, BLOCK_ALAND / SQMI, BLOCK_POP,
                            {k: dict(v) for k, v in ACS_FIX.items()},
                            dict(OD_FIX), dict(GENJOBS_FIX),
                            GEN_XY[0], GEN_XY[1], GEN_TYPES)


def _proj(data):
    return sv.ShapeProjV21("toy", np.array([0.0, 10.0]),
                           np.array([0.0, 0.0]), (data.bx, data.by),
                           GEN_XY, GEN_TYPES)


def test_v1_vintage_table():
    assert sv.resolve_vintage("fy2017") == {"od": "2017", "wac": "2017",
                                            "acs": "2017"}
    assert sv.resolve_vintage("fy2019") == {"od": "2019", "wac": "2019",
                                            "acs": "2019"}
    assert sv.resolve_vintage("fy2020q3") == sv.resolve_vintage("fy2019")
    assert sv.resolve_vintage("scan") == {"od": "2022", "wac": "2022",
                                          "acs": "2023"}
    try:
        sv.resolve_vintage("fy2021")
        raise AssertionError("unknown vintage did not raise")
    except KeyError:
        pass
    print("  V1 OK  vintage dispatch table (§9.3), unknown label raises")


def test_v2_apportionment():
    vals = {"T1": 40.0, "T2": 8.0, "T3": 6.0}
    out = sv.apportion_to_blocks(vals, BLOCK_TRACT, BLOCK_POP)
    assert np.allclose(out, [10.0, 30.0, 8.0, 0.0, 3.0, 3.0]), out
    # conservation per tract (incl. the zero-pop equal split for T3)
    for t, v in vals.items():
        got = out[[i for i, bt in enumerate(BLOCK_TRACT) if bt == t]].sum()
        assert abs(got - v) < 1e-12, (t, got, v)
    # a tract with no blocks contributes nothing; missing tracts -> zeros
    out2 = sv.apportion_to_blocks({"T9": 100.0}, BLOCK_TRACT, BLOCK_POP)
    assert (out2 == 0).all()
    print("  V2 OK  pop-weight apportionment (conserving; zero-pop equal "
          "split)")


def test_v3_bridge():
    t10 = {"A": 100.0, "B": 50.0}
    rows = [("A", "T1", 0.75), ("A", "T2", 0.25), ("B", "T2", 1.0)]
    t20 = sv.apply_bridge(t10, rows)
    assert t20 == {"T1": 75.0, "T2": 75.0}, t20
    assert abs(sum(t20.values()) - sum(t10.values())) < 1e-12
    print("  V3 OK  tract10->tract20 bridge (shares applied, conserving)")


def test_v4_membership():
    data, = [_data()]
    proj = _proj(data)
    p = sv.compute_predictors_v21(data, proj, 0.0, 7.0, "fy2017",
                                  buffer_mi=0.9)
    # block 2 at |off| == 0.9 exactly is IN (inclusive, the §3.2/§9.2 rule);
    # block 4 at pos 9.5 out of window; block 5 clamps to pos 10 -> out
    assert list(p["block_idx"]) == [0, 1, 2, 3], p["block_idx"]
    tight = sv.compute_predictors_v21(data, proj, 0.0, 7.0, "fy2017",
                                      buffer_mi=0.89)
    assert list(tight["block_idx"]) == [0, 1, 3], tight["block_idx"]
    full = sv.compute_predictors_v21(data, proj, 0.0, 10.0, "fy2017",
                                     buffer_mi=0.9)
    # block 5 (x=12) clamps to pos 10.0, |off| 2.0 -> out of buffer;
    # block 4 (pos 9.5, off 0.3) in
    assert list(full["block_idx"]) == [0, 1, 2, 3, 4], full["block_idx"]
    print("  V4 OK  block catchment membership (buffer inclusive, position "
          "window)")


def test_v5_clipping():
    data = _data()
    proj = _proj(data)
    # w1 beyond L clips to L; w0 below 0 clips to 0
    p = sv.compute_predictors_v21(data, proj, -3.0, 25.0, "fy2017",
                                  buffer_mi=0.9)
    assert p["window_mi"] == 10.0
    assert abs(p["l_len"] - math.log(10.0)) < 1e-15
    q = sv.compute_predictors_v21(data, proj, 8.0, 25.0, "fy2017",
                                  buffer_mi=0.9)
    assert q["window_mi"] == 2.0 and list(q["block_idx"]) == [4]
    try:
        sv.compute_predictors_v21(data, proj, 11.0, 25.0, "fy2017",
                                  buffer_mi=0.9)
        raise AssertionError("empty clipped window did not raise")
    except ValueError:
        pass
    print("  V5 OK  window clipped to [0, L]; l_len on the clipped length; "
          "empty raises")


def test_v6_od_window_sums():
    data = _data()
    proj = _proj(data)
    p = sv.compute_predictors_v21(data, proj, 0.0, 7.0, "fy2017",
                                  buffer_mi=0.9)
    # 2017 OD: (0,1,5) both in [0,7]; intra (1,1,3) in; (0,4,7) far end at
    # 9.5 -> out; (2,3,9) both in -> flows = 5+3+9
    assert p["flows"] == 17.0, p["flows"]
    full = sv.compute_predictors_v21(data, proj, 0.0, 10.0, "fy2017",
                                     buffer_mi=0.9)
    assert full["flows"] == 24.0, full["flows"]        # + (0,4,7); b5 never in
    late = sv.compute_predictors_v21(data, proj, 8.0, 10.0, "fy2017",
                                     buffer_mi=0.9)
    assert late["flows"] == 0.0, late["flows"]
    print("  V6 OK  both-ends-in O-D window sums (intra-block included)")


def test_v7_vintage_dispatch_compute():
    data = _data()
    proj = _proj(data)
    a = sv.compute_predictors_v21(data, proj, 0.0, 7.0, "fy2017",
                                  buffer_mi=0.9)
    b = sv.compute_predictors_v21(data, proj, 0.0, 7.0, "fy2019",
                                  buffer_mi=0.9)
    c = sv.compute_predictors_v21(data, proj, 0.0, 7.0, "fy2020q3",
                                  buffer_mi=0.9)
    s = sv.compute_predictors_v21(data, proj, 0.0, 7.0, "scan",
                                  buffer_mi=0.9)
    # fy2019: OD (0,1,11)+(1,1,13) = 24; ACS zveh doubled: 96+0 -> blocks
    # 0,1,2,3 = 20+60+16+0 = 96; genjobs 200+80 = 280
    assert b["flows"] == 24.0 and c["flows"] == 24.0
    assert b["zveh_hh"] == 96.0 and b["genjobs"] == 280.0
    assert a["zveh_hh"] == 48.0 and a["genjobs"] == 140.0
    # fy2020q3 == fy2019 EXACTLY (same tables, §9.3)
    ka = {k: v for k, v in b.items() if k != "block_idx"}
    kc = {k: v for k, v in c.items() if k != "block_idx"}
    assert ka == kc and list(b["block_idx"]) == list(c["block_idx"])
    # scan: OD 2022 (2,3,17)+(4,4,19 out of window) = 17; ACS 2023 zveh
    # 30+90+24+0 = 144; WAC 2022 300+120 = 420
    assert s["flows"] == 17.0 and s["zveh_hh"] == 144.0 \
        and s["genjobs"] == 420.0
    assert s["vintage"] == {"od": "2022", "wac": "2022", "acs": "2023"}
    print("  V7 OK  vintage dispatch in compute (fy2020q3==fy2019; scan "
          "reads 2022/2023)")


def test_v8_vector_arithmetic():
    data = _data()
    proj = _proj(data)
    p = sv.compute_predictors_v21(data, proj, 0.0, 7.0, "fy2017",
                                  buffer_mi=0.9)
    assert abs(p["l_flows"] - math.log1p(17.0)) < 1e-15
    assert abs(p["l_zveh_hh"] - math.log1p(48.0)) < 1e-15
    assert abs(p["l_genjobs"] - math.log1p(140.0)) < 1e-15
    assert abs(p["l_len"] - math.log(7.0)) < 1e-15
    # swap inputs: popden = pop sum / aland sum over blocks 0-3
    pop = 100.0 + 300.0 + 200.0 + 0.0
    aland = 0.5 + 1.0 + 0.5 + 0.25
    assert abs(p["popden"] - pop / aland) < 1e-12
    assert p["e002"] == 16.0 and p["e016"] == 8.0
    assert p["gen_dummy"] == 1 and p["gen_types"] == ["resort"]
    early = sv.compute_predictors_v21(data, proj, 0.0, 5.5, "fy2017",
                                      buffer_mi=0.9)
    assert early["gen_dummy"] == 0 and early["gen_types"] == []
    # l_rvh passthrough slot
    assert p["l_rvh"] is None
    r = sv.compute_predictors_v21(data, proj, 0.0, 7.0, "fy2017",
                                  rvh=1234.5, buffer_mi=0.9)
    assert abs(r["l_rvh"] - math.log(1234.5)) < 1e-15
    try:
        sv.compute_predictors_v21(data, proj, 0.0, 7.0, "fy2017",
                                  rvh=0.0, buffer_mi=0.9)
        raise AssertionError("rvh=0 did not raise")
    except ValueError:
        pass
    print("  V8 OK  §9.1 vector arithmetic (log1p sums, l_rvh passthrough, "
          "popden, gen dummy)")


# ---------------------------------------------------------------------------
# loader round-trip on a fixture DIRECTORY (schema-identical to the
# build_derived_v21 outputs; no real data touched)
# ---------------------------------------------------------------------------
def _write_fixture_dir(d):
    lat = BY / sv.MI_LAT                     # invert the loader's mi frame
    lon = BX / sv.MI_LON
    geoids = [f"0605900110{i}100{i}" for i in range(6)]   # tract20 = [:11]
    t20 = sorted({g[:11] for g in geoids})   # 3 fixture "2020 tracts"
    t10 = ["A", "B", "C"]                    # fixture "2010 tracts", 1:1
    with open(os.path.join(d, "oc_blocks.csv"), "w", encoding="utf-8",
              newline="\n") as f:
        f.write("GEOID20,INTPTLAT20,INTPTLON20,ALAND20,pop2020\n")
        for i, g in enumerate(geoids):
            f.write(f"{g},{lat[i]:+.7f},{lon[i]:+.7f},"
                    f"{int(BLOCK_ALAND[i])},{int(BLOCK_POP[i])}\n")
    with open(os.path.join(d, "oc_tract10_to_tract20.csv"), "w",
              encoding="utf-8", newline="\n") as f:
        f.write("tract10,tract20,share\n")
        for a, b in zip(t10, t20):
            f.write(f"{a},{b},1.00000000\n")
    # ACS tidies: tract tables whose apportionment reproduces ACS_FIX
    tract_of = {t: [i for i, g in enumerate(geoids) if g[:11] == t]
                for t in t20}
    def tract_sum(arr, t):
        return sum(arr[i] for i in tract_of[t])
    for v, geo_ids in (("2017", t10), ("2019", t10), ("2023", t20)):
        fx = ACS_FIX[v]
        with open(os.path.join(d, f"oc_b25044_{v}.csv"), "w",
                  encoding="utf-8", newline="\n") as f:
            f.write("GEOID,B25044_E001,B25044_E003,B25044_E010\n")
            for gid, t in zip(geo_ids, t20):
                z = tract_sum(fx["zveh"], t)
                f.write(f"{gid},{z * 3},{z / 3},{z * 2 / 3}\n")
        with open(os.path.join(d, f"oc_b01003_{v}.csv"), "w",
                  encoding="utf-8", newline="\n") as f:
            f.write("GEOID,B01003_E001\n")
            for gid, t in zip(geo_ids, t20):
                f.write(f"{gid},{tract_sum(fx['pop'], t)}\n")
        name = "oc_b08141.csv" if v == "2023" else f"oc_b08141_{v}.csv"
        with open(os.path.join(d, name), "w", encoding="utf-8",
                  newline="\n") as f:
            f.write("GEOID,B08141_E002,B08141_E016\n")
            for gid, t in zip(geo_ids, t20):
                f.write(f"{gid},{tract_sum(fx['e002'], t)},"
                        f"{tract_sum(fx['e016'], t)}\n")
    naics = val("gen_jobs_naics")
    for v in ("2017", "2019", "2022"):
        h, w, n = OD_FIX[v]
        with gzip.open(os.path.join(d, f"oc_block_od_{v}.csv.gz"), "wt",
                       encoding="utf-8", newline="\n") as f:
            f.write("h,w,n\n")
            for hi, wi, ni in zip(h, w, n):
                f.write(f"{geoids[hi]},{geoids[wi]},{int(ni)}\n")
        with open(os.path.join(d, f"oc_block_wac_{v}.csv"), "w",
                  encoding="utf-8", newline="\n") as f:
            f.write("GEOID20," + ",".join(["C000"] + naics[1:]
                                          + [naics[0]]) + "\n")
            # column order shuffled on purpose: the loader reads by NAME
            for i, g in enumerate(geoids):
                gj = GENJOBS_FIX[v][i]
                f.write(f"{g},{gj * 2},{gj / 4},{gj / 4},{gj / 4},"
                        f"{gj / 4}\n")
    gens = {"generators": [
        {"name": "G0", "type": "resort",
         "lat": 0.5 / sv.MI_LAT, "lon": 6.0 / sv.MI_LON},
        {"name": "G1", "type": "college",
         "lat": -2.0 / sv.MI_LAT, "lon": 2.0 / sv.MI_LON}]}
    import json
    gp = os.path.join(d, "gens.json")
    with open(gp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(gens, f)
    return gp


def test_v9_loader_roundtrip():
    with tempfile.TemporaryDirectory() as d:
        gp = _write_fixture_dir(d)
        data = sv.load_data_v21(der_dir=d, gens_path=gp)
        proj = data.proj("toy", np.array([0.0, 10.0]), np.array([0.0, 0.0]))
        p = sv.compute_predictors_v21(data, proj, 0.0, 7.0, "fy2017",
                                      buffer_mi=0.9)
        assert list(p["block_idx"]) == [0, 1, 2, 3], p["block_idx"]
        assert p["flows"] == 17.0, p["flows"]
        assert abs(p["zveh_hh"] - 48.0) < 1e-9, p["zveh_hh"]
        assert abs(p["genjobs"] - 140.0) < 1e-9, p["genjobs"]
        assert abs(p["e002"] - 16.0) < 1e-9 and abs(p["e016"] - 8.0) < 1e-9
        assert p["gen_dummy"] == 1 and p["gen_types"] == ["resort"]
        pop, aland = 600.0, 2.25
        # fixture writes ALAND20 as int m^2 (like the real table), so allow
        # the truncation's ~1e-7 relative wobble
        assert abs(p["popden"] - pop / aland) < 1e-4 * (pop / aland), \
            p["popden"]
        s = sv.compute_predictors_v21(data, proj, 0.0, 7.0, "scan",
                                      buffer_mi=0.9)
        assert s["flows"] == 17.0 and abs(s["zveh_hh"] - 144.0) < 1e-9 \
            and abs(s["genjobs"] - 420.0) < 1e-9
    print("  V9 OK  loader round-trip on a schema-identical fixture dir "
          "(t10 bridge + apportionment + od/wac by name)")


def test_v10_guard_no_fit():
    """STANDING GUARD (spec 01 §9 pre-registration hold): screen_common_v21
    owns input-side predictor machinery ONLY. No fit function exists here
    -- fitting stays in screen_fit until phase 2b -- and the module never
    imports an estimator."""
    offenders = [n for n in dir(sv) if "fit" in n.lower()]
    assert not offenders, f"fit-shaped names in screen_common_v21: {offenders}"
    src_path = os.path.join(os.path.dirname(os.path.abspath(sv.__file__)),
                            "screen_common_v21.py")
    with open(src_path, encoding="utf-8") as f:
        src = f.read()
    for banned in ("statsmodels", "sm.OLS", "linalg.lstsq", "polyfit",
                   "route_boardings"):
        assert banned not in src, \
            f"screen_common_v21.py mentions {banned!r} -- the §9 hold " \
            "keeps every estimator + boardings input out of this module"
    assert "NO FIT" in src, "the module must state the no-fit hold"
    print("  V10 OK  guard: no fit machinery / no boardings input in "
          "screen_common_v21 (fitting stays in screen_fit until 2b)")


if __name__ == "__main__":
    test_v1_vintage_table()
    test_v2_apportionment()
    test_v3_bridge()
    test_v4_membership()
    test_v5_clipping()
    test_v6_od_window_sums()
    test_v7_vintage_dispatch_compute()
    test_v8_vector_arithmetic()
    test_v9_loader_roundtrip()
    test_v10_guard_no_fit()
    print("ALL V21 SCREEN TESTS PASS")
