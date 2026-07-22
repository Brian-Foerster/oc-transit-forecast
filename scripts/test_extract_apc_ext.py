"""Tests for extract_apc_ext.py: parser units on real printed rows, the
wrap-regrouping, the 2dp interval gate, and the CONTAMINATION GUARD
extension -- route_boardings_ext.csv is outcome data and must stay out of
every predictor/fit module until phase 2b (the committed v2.0 variance
decomposition remains the only power-machinery input).

usage: python test_extract_apc_ext.py
"""
import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import extract_apc_ext as ex                          # noqa: E402
from extract_apc import rvh_check_ok                  # noqa: E402


def test_t1_standard_row():
    """Real FY2021 Q4 line (first table row carries attached $ signs)."""
    ln = ("057 C 7.2% 8.98$ 5.08$ 3.41$ 0.49$ 0.66$ 1,632,887 174.41$ "
          "113.83$ 16.42$ 19.05 85,733 30 - -")
    route, b, rvh, printed = ex.parse_row_ext(ln.split())
    assert (route, b, rvh, printed) == ("57", 1632887, 85733, 19.05)
    assert rvh_check_ok(b, rvh, printed)
    print("  T1 OK  standard 17-token row with attached $")


def test_t2_submode_row():
    """FY2020-era Stationlink rows carry an extra Submode token (18)."""
    ln = ("463 C RCL 3.5% 20.00 11.00 7.50 1.50 0.70 4,096 191.79 96.52 "
          "17.58 2.79 1,471 4 - -")
    route, b, rvh, printed = ex.parse_row_ext(ln.split())
    assert (route, b, rvh, printed) == ("463", 4096, 1471, 2.79)
    print("  T2 OK  18-token Stationlink Submode row")


def test_t3_paren_negatives():
    """Real Q2-FY2021 route 079 row: negative farebox '(0.4)%' and revenue
    '(0.07)' print as parenthesized values."""
    ln = ("079 C (0.4)% 17.84 10.03 6.96 0.85 (0.07) 65,777 143.92 86.55 "
          "12.75 8.51 7,734 3 - -")
    route, b, rvh, printed = ex.parse_row_ext(ln.split())
    assert (route, b, rvh, printed) == ("79", 65777, 7734, 8.51)
    print("  T3 OK  parenthesized-negative farebox/revenue tokens")


def test_t4_shapes():
    """Non-rows -> None; short route-start -> 'short'; misfit -> error."""
    assert ex.parse_row_ext("Route Zone Farebox Subsidy".split()) is None
    assert ex.parse_row_ext(["40", "FT", "32", "FT", "60", "FT"]) is None
    assert ex.parse_row_ext("057 C 7.2% 8.98$ 5.08$".split()) == "short"
    try:
        ex.parse_row_ext(("057 C 7.2% NOTMONEY 5.08 3.41 0.49 0.66 1,632,887"
                          " 174.41 113.83 16.42 19.05 85,733 30 - -").split())
    except ValueError:
        pass
    else:
        raise AssertionError("misfit route-like line must raise ValueError")
    print("  T4 OK  header/None, short, misfit-ValueError shapes")


def test_t5_wrap_regroup():
    """A row split across extracted text lines (recon warning) regroups;
    a dangling route-start line at page end raises."""
    text = ("OCTA Operating Statistics By Route for X\n"
            "057 C 7.2% 8.98 5.08 3.41\n"
            "\n"
            "0.49 0.66 1,632,887 174.41 113.83 16.42 19.05 85,733 30 - -\n"
            "060 C 6.1% 9.38 5.39 3.62 0.37 0.59 1,427,161 188.06 123.11 "
            "15.69 19.59 72,836 33 - -\n")
    rows = ex.parse_text_rows(text)
    assert rows == [("57", 1632887, 85733, 19.05),
                    ("60", 1427161, 72836, 19.59)], rows
    try:
        ex.parse_text_rows("057 C 7.2% 8.98\n")
    except AssertionError:
        pass
    else:
        raise AssertionError("dangling wrapped tokens must raise")
    print("  T5 OK  wrapped-row regrouping + dangling-tokens error")


def test_t6_interval_gate():
    """The 2dp gate is the interval test from extract_apc: binding case
    FY2017 Stationlink 411 (5,837/863 = 6.7636 printed 6.77) passes; an
    off-by-one RVH fails."""
    assert rvh_check_ok(5837, 863, 6.77)
    assert not rvh_check_ok(5837, 863, 6.83)
    assert not rvh_check_ok(992766, 42238, 18.57)   # FY2017 route 70 defect
    print("  T6 OK  2dp interval gate semantics")


def test_t7_guard_no_predictor_contact():
    """STANDING GUARD (spec 01 §9.9.5): the extended route-year boardings are
    outcome data. The phase-2b HOLD was RELEASED 2026-07-21 when the
    pre-registered v2.1 fit landed -- the AUTHORIZED extended-panel consumers
    are the phase-2b fit modules scripts/screen_fit_v21.py +
    scripts/screen_scan_v21.py AND the spec 01 §10 phase-2b-v22 productivity
    fit modules scripts/screen_fit_v22.py + scripts/screen_scan_v22.py (all
    read route_boardings_ext.csv for the fit, exactly as screen_fit.py reads
    the committed route_boardings.csv; none is in the blanket-ban list). This
    guard now enforces the PERMANENT invariant instead: the INPUT-SIDE
    predictor machinery and every non-v21 fit module below must STILL never
    read the ext table (screen_common_v21.py keeps its no-fit hold; the v2.0
    3-year fit never uses the extended panel), with the SINGLE design-stage
    carve-out for scripts/screen_power.py (guarded loader load_rvh_ext,
    presence + validated b3 RVH only; test_screen_power.py G1/G2e). The
    extraction module itself must carry no estimator and never touch predictor
    machinery."""
    # blanket ban -- every predictor/fit module EXCEPT the one §9.9.5 carve-out
    fit_side = ["screen_common.py", "screen_common_v21.py", "screen_fit.py",
                "screen_scan.py", "build_derived.py",
                "build_derived_v21.py", "model.py", "reweight_abc.py",
                "sequence_network.py", "backtest_543.py"]
    for fname in fit_side:
        with open(os.path.join(HERE, fname), encoding="utf-8") as f:
            src = f.read()
        assert "route_boardings_ext" not in src, (
            f"{fname} references route_boardings_ext -- the phase-2b hold "
            "keeps the extended boardings out of every predictor/fit module "
            "(the ONLY carve-out is screen_power.py, spec 01 §9.9.5)")
    # the single carve-out: screen_power.py MAY read route_boardings_ext, but
    # ONLY inside load_rvh_ext (above fit_universe -- the guarded loader
    # region), and it must carry its own contamination guard. The
    # value-drop / boardings-free confinement is asserted in depth by
    # test_screen_power.py G1 (no CSV read below the loaders) + G2e.
    with open(os.path.join(HERE, "screen_power.py"), encoding="utf-8") as f:
        sp_src = f.read()
    sp_head, sp_tail = sp_src.split("def fit_universe", 1)
    assert "route_boardings_ext" in sp_head, \
        "screen_power.py carve-out moved -- load_rvh_ext must precede " \
        "fit_universe (spec 01 §9.9.5)"
    # the ext table is READ only in the loader region; the artifact prose
    # below may NAME it, but no read_csv may appear past fit_universe (the
    # same confinement test_screen_power.py G1 owns in depth)
    assert "read_csv" not in sp_tail, (
        "screen_power.py opens a CSV BELOW the loader region -- the §9.9.5 "
        "carve-out is confined to load_rvh_ext (presence + RVH only)")
    assert "CONTAMINATION GUARD" in sp_src, \
        "screen_power.py must state the contamination guard"
    with open(os.path.join(HERE, "extract_apc_ext.py"),
              encoding="utf-8") as f:
        src = f.read()
    for banned in ("statsmodels", "sm.OLS", "linalg.lstsq", "polyfit",
                   "screen_common", "screen_fit", "screen_scan",
                   "screen_power", "sklearn"):
        assert banned not in src, (
            f"extract_apc_ext.py mentions {banned!r} -- extraction must "
            "carry no estimator and never import predictor machinery")
    assert "CONTAMINATION GUARD" in src, \
        "extract_apc_ext.py must state the contamination guard"
    print("  T7 OK  guard: ext boardings out of every predictor/fit module "
          "(sole screen_power.py carve-out confined to load_rvh_ext); "
          "no estimator in the extractor")


def test_t8_output_schema():
    """route_boardings_ext.csv (if built): schema, new-FY-only labels, no
    overlap with the committed wide table's route-FY boardings cells, and
    the single documented blank-RVH cell (fy2022 route 560)."""
    dest = os.path.join(HERE, "..", "data", "derived",
                        "route_boardings_ext.csv")
    if not os.path.exists(dest):
        print("  T8 SKIP  route_boardings_ext.csv not built yet")
        return
    with open(dest, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert rows and set(rows[0]) == {"route", "fy", "boardings", "rvh"}
    labs = {r["fy"] for r in rows}
    assert labs == {"fy2020", "fy2021", "fy2022", "fy2023"}, labs
    assert all(int(r["boardings"]) > 0 for r in rows)
    blanks = [(r["route"], r["fy"]) for r in rows if r["rvh"] == ""]
    assert blanks == [("560", "fy2022")], blanks
    seen = {(r["route"], r["fy"]) for r in rows}
    assert len(seen) == len(rows), "duplicate route-year rows"
    print(f"  T8 OK  output schema, {len(rows)} rows, new FYs only, "
          "single documented blank RVH")


if __name__ == "__main__":
    test_t1_standard_row()
    test_t2_submode_row()
    test_t3_paren_negatives()
    test_t4_shapes()
    test_t5_wrap_regroup()
    test_t6_interval_gate()
    test_t7_guard_no_predictor_contact()
    test_t8_output_schema()
    print("extract_apc_ext tests: ALL OK")
