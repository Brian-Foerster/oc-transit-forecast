"""v2.2 PRE-REGISTRATION gate tests (spec 01 §10; the productivity estimand).

These tests are REGISTRY-ONLY and artifact-independent: nothing here reads a
v2.2 artifact, joins a predictor, or fits anything. They lock the
pre-registration's frozen decisions (spec 01 §10 D4/D5) so no batch can silently
retune the bar or edit the battery. The phase-2b-v22 fit has SINCE LANDED
(2026-07-21); these registry-only locks continue to hold, and P3 now asserts
the LANDED disposition (spec-pending:01§10 -> definitional). The fit-side gates
live in test_screen_v22_fit.py.

  P1  screen_battery_rows_v22 == the frozen 17-row list, ORDER-EXACT, and is
      exactly screen_battery_rows_v21 MINUS {drop_rh, svc_p25, svc_p75}
      (the three rows undefined under productivity, D5)
  P2  the v2.2 thresholds resolve to the SAME val() as v2.1 -- the carry-over
      (D4): NO new threshold id is minted; the only new v22 registry ids are
      screen_estimand_v22 + screen_battery_rows_v22, neither a threshold
  P3  the v2.2 estimand entry is log(boardings/RVH), a rowless structural-
      governance constant (the screen_battery_rows / screen_regime_split
      precedent that avoids the check-5 trap), LANDED (definitional) after the
      phase-2b-v22 fit consumed it
  P4  the pre-registration touched NO fitted artifact: v2.0 screen_results.json
      (b88f9b65) and v2.1 screen_results_v21.json (83aeb032) stay byte-identical

    python -X utf8 scripts/test_screen_v22_prereg.py
"""
import hashlib
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "outputs")

from assumptions import val, ASSUMPTIONS                        # noqa: E402

# the frozen §10 D5 list, written here so the test pins an EXPLICIT literal
# (not a transform of the registry it is meant to guard).
V22_EXPECTED = [
    "buffer_lo", "buffer_hi", "window_10", "window_15", "drop_fy2020",
    "e016_swap", "e002_swap", "popden_swap", "genjobs_off",
    "genjobs_leave_class_out", "gen_dummy_swap", "nb_estimator",
    "offset_variant", "overlap_lo", "overlap_hi", "year_fe_vs_pooled", "loyo",
]
V22_DROPPED = ("drop_rh", "svc_p25", "svc_p75")

# the ratified v2.1 threshold values the v2.2 fit CARRIES OVER unchanged (D4).
V21_THRESHOLDS = {
    "screen_pos_frac_min": 0.841,
    "screen_battery_rho_min": 0.7,
    "screen_tie_churn_max_window": 0.20,
    "screen_tie_churn_max_hostshape": 2.0 / 14.0,
}


def test_p1_battery_rows_v22():
    """screen_battery_rows_v22 == the frozen 17-row list (order-exact) and is
    exactly screen_battery_rows_v21 MINUS {drop_rh, svc_p25, svc_p75}."""
    v22 = list(val("screen_battery_rows_v22"))
    assert v22 == V22_EXPECTED, (v22, V22_EXPECTED)
    assert len(v22) == 17, len(v22)
    # exclusion of the three productivity-undefined rows (D5)
    for r in V22_DROPPED:
        assert r not in v22, f"{r} must be excluded from screen_battery_rows_v22"
    # order-preserving subset of the v21 list with exactly those 3 removed
    v21 = list(val("screen_battery_rows_v21"))
    assert [r for r in v21 if r not in V22_DROPPED] == v22, (v21, v22)
    assert set(v21) - set(v22) == set(V22_DROPPED), set(v21) - set(v22)
    print("  P1 OK  screen_battery_rows_v22 = 17 rows, order-exact = "
          "screen_battery_rows_v21 MINUS {drop_rh, svc_p25, svc_p75}")


def test_p2_thresholds_carry_over_no_new_ids():
    """The v2.2 fit reuses the EXACT ratified v2.1 threshold values via the
    SAME registry ids (D4). No *_v22 threshold id is minted -- the only new
    v22 ids are the estimand + the battery list, neither a threshold."""
    for tid, want in V21_THRESHOLDS.items():
        got = val(tid)
        assert abs(float(got) - want) < 1e-15, (tid, got, want)
    # the new v22 registry ids are EXACTLY the two governance entries
    v22_ids = {aid for aid in ASSUMPTIONS if "v22" in aid}
    assert v22_ids == {"screen_estimand_v22", "screen_battery_rows_v22"}, v22_ids
    # neither new id is a numeric threshold (a method change never mints a bar)
    assert isinstance(val("screen_estimand_v22"), str)
    assert isinstance(val("screen_battery_rows_v22"), list)
    for aid in v22_ids:
        assert not isinstance(val(aid), (int, float)), \
            f"{aid} looks like a threshold value -- D4 forbids a new bar"
    print("  P2 OK  v2.2 thresholds carry over via the v2.1 ids "
          "(0.841/0.7/0.20/2·14⁻¹); no new threshold id minted")


def test_p3_estimand_governance_entry():
    """screen_estimand_v22 = log(boardings/RVH), a rowless structural-
    governance CONSTANT (screen_battery_rows precedent, avoids the check-5
    trap). LANDED 2026-07-21: the phase-2b-v22 fit consumed it, so the
    disposition FLIPPED spec-pending:01§10 -> definitional (the §9
    spec-pending:01§9 -> landed precedent). The structural-governance shape
    (rowless, band None, accepted stamped) is unchanged."""
    e = ASSUMPTIONS["screen_estimand_v22"]
    assert val("screen_estimand_v22") == "log(boardings/RVH)"
    assert e["tier"] == "constant" and e["status"] == "active"
    assert e["band"] is None
    assert not e.get("rows"), "governance entry must own no sensitivity rows"
    # LANDED: no longer spec-pending; a definitional rowless disposition
    assert e["no_row_reason"] == "definitional", e["no_row_reason"]
    assert not str(e["no_row_reason"]).startswith("spec-pending:")
    assert e["accepted"] not in (None, False)
    # the battery list is likewise a rowless (now definitional) governance const
    b = ASSUMPTIONS["screen_battery_rows_v22"]
    assert b["tier"] == "constant" and b["band"] is None
    assert b["no_row_reason"] == "definitional", b["no_row_reason"]
    assert not str(b["no_row_reason"]).startswith("spec-pending:")
    print("  P3 OK  screen_estimand_v22 = log(boardings/RVH); rowless "
          "structural-governance constant, LANDED (spec-pending:01§10 -> "
          "definitional)")


def test_p4_fitted_artifacts_byte_identical():
    """The pre-registration ran NO fit: v2.0 + v2.1 screen artifacts stay
    byte-identical at their frozen shas."""
    for name, want in (("screen_results.json", "b88f9b65"),
                       ("screen_results_v21.json", "83aeb032")):
        p = os.path.join(OUT, name)
        if not os.path.exists(p):
            print(f"  P4 SKIP ({name} absent)")
            continue
        h = hashlib.sha256(open(p, "rb").read()).hexdigest()
        assert h.startswith(want), f"{name} sha changed: {h[:16]} (want {want})"
    print("  P4 OK  v2.0 (b88f9b65) + v2.1 (83aeb032) artifacts "
          "byte-identical -- no fit ran")


if __name__ == "__main__":
    test_p1_battery_rows_v22()
    test_p2_thresholds_carry_over_no_new_ids()
    test_p3_estimand_governance_entry()
    test_p4_fitted_artifacts_byte_identical()
    print("ALL V22 PRE-REGISTRATION TESTS PASS")
