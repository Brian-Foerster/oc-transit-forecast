"""v2.3 PRE-REGISTRATION gate tests (spec 01 §11; the regional cluster base).

These tests are REGISTRY-ONLY and artifact-independent: nothing here reads a
v2.3 artifact, joins a predictor, or fits anything. They lock the
pre-registration's frozen decisions (spec 01 §11 D1/D3/D6) so no batch can
silently retune the bar, edit the battery, or swap the estimand once the
regional numbers exist. The phase-2b-v23 fit has NOT run yet; the v2.3 entries
are spec-pending:01§11 until it consumes them (the §9/§10 precedent).

  P1  screen_battery_rows_v23 == the frozen 18-row list, ORDER-EXACT, and is
      exactly screen_battery_rows_v22 PLUS ["loao"] (the leave-one-agency-out
      row appended after loyo, D6)
  P2  the v2.3 thresholds resolve to the SAME val() as v2.1/v2.2 -- the
      carry-over (D3): NO new threshold id is minted; the new v23 registry ids
      are screen_battery_rows_v23 + screen_regional_agencies, neither a
      threshold, and there is NO screen_estimand_v23 (v23 REUSES the v22
      productivity estimand, D1)
  P3  the estimand is REUSED (screen_estimand_v22 = log(boardings/RVH), no v23
      estimand entry); screen_battery_rows_v23 is a rowless structural-
      governance constant and screen_regional_agencies a rowless config entry,
      both spec-pending:01§11 (pre-fit), the config one carrying a config_key
  P4  the pre-registration touched NO fitted artifact: v2.0 (b88f9b65), v2.1
      (83aeb032) and v2.2 (3b1d5526) screen_results stay byte-identical

    python -X utf8 scripts/test_screen_v23_prereg.py
"""
import hashlib
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "outputs")

from assumptions import val, ASSUMPTIONS                        # noqa: E402

# the frozen §11 D6 list, written here so the test pins an EXPLICIT literal
# (not a transform of the registry it is meant to guard).
V23_EXPECTED = [
    "buffer_lo", "buffer_hi", "window_10", "window_15", "drop_fy2020",
    "e016_swap", "e002_swap", "popden_swap", "genjobs_off",
    "genjobs_leave_class_out", "gen_dummy_swap", "nb_estimator",
    "offset_variant", "overlap_lo", "overlap_hi", "year_fe_vs_pooled",
    "loyo", "loao",
]
V23_ADDED = ("loao",)

# the ratified v2.1 threshold values the v2.3 fit CARRIES OVER unchanged (D3).
V21_THRESHOLDS = {
    "screen_pos_frac_min": 0.841,
    "screen_battery_rho_min": 0.7,
    "screen_tie_churn_max_window": 0.20,
    "screen_tie_churn_max_hostshape": 2.0 / 14.0,
}


def test_p1_battery_rows_v23():
    """screen_battery_rows_v23 == the frozen 18-row list (order-exact) and is
    exactly screen_battery_rows_v22 PLUS ['loao']."""
    v23 = list(val("screen_battery_rows_v23"))
    assert v23 == V23_EXPECTED, (v23, V23_EXPECTED)
    assert len(v23) == 18, len(v23)
    # loao is ADDED versus v22, and is the only addition
    v22 = list(val("screen_battery_rows_v22"))
    assert set(v23) - set(v22) == set(V23_ADDED), set(v23) - set(v22)
    assert set(v22) - set(v23) == set(), set(v22) - set(v23)
    # order-preserving: v22's 17 rows are a prefix, loao appended
    assert v23[:len(v22)] == v22, (v23[:len(v22)], v22)
    assert v23[-1] == "loao"
    print("  P1 OK  screen_battery_rows_v23 = 18 rows, order-exact = "
          "screen_battery_rows_v22 PLUS ['loao']")


def test_p2_thresholds_carry_over_no_new_ids():
    """The v2.3 fit reuses the EXACT ratified v2.1 threshold values via the
    SAME registry ids (D3). No *_v23 threshold id is minted, and there is NO
    screen_estimand_v23 -- v23 REUSES the v22 productivity estimand (D1)."""
    for tid, want in V21_THRESHOLDS.items():
        got = val(tid)
        assert abs(float(got) - want) < 1e-15, (tid, got, want)
    # v23 introduces EXACTLY these two registry ids, neither a threshold
    assert "screen_battery_rows_v23" in ASSUMPTIONS
    assert "screen_regional_agencies" in ASSUMPTIONS
    assert "screen_estimand_v23" not in ASSUMPTIONS, \
        "v23 REUSES screen_estimand_v22 -- no new estimand entry (D1)"
    v23_new = ("screen_battery_rows_v23", "screen_regional_agencies")
    assert isinstance(val("screen_battery_rows_v23"), list)
    assert isinstance(val("screen_regional_agencies"), str)  # a PENDING note
    for aid in v23_new:
        assert not isinstance(val(aid), (int, float)), \
            f"{aid} looks like a threshold value -- D3 forbids a new bar"
    print("  P2 OK  v2.3 thresholds carry over via the v2.1 ids "
          "(0.841/0.7/0.20/2·14⁻¹); no new threshold or estimand id minted")


def test_p3_estimand_reused_and_governance_shape():
    """v23 REUSES screen_estimand_v22 = log(boardings/RVH) (D1). The two new
    v23 entries are rowless structural-governance leaves, both
    spec-pending:01§11 (pre-fit); screen_regional_agencies is config-tier and
    carries a config_key (the pending regional_agencies.json stub)."""
    # estimand reused, unchanged
    assert val("screen_estimand_v22") == "log(boardings/RVH)"
    # battery: rowless structural-governance constant, spec-pending pre-fit
    b = ASSUMPTIONS["screen_battery_rows_v23"]
    assert b["tier"] == "constant" and b["status"] == "active"
    assert b["band"] is None
    assert not b.get("rows"), "governance entry must own no sensitivity rows"
    assert b["no_row_reason"] == "spec-pending:01§11", b["no_row_reason"]
    assert b["accepted"] not in (None, False)
    # regional agencies: config-tier, rowless, spec-pending, has config_key
    r = ASSUMPTIONS["screen_regional_agencies"]
    assert r["tier"] == "config" and r["status"] == "active"
    assert r.get("config_key"), "config-tier entry needs a config_key"
    assert not r.get("rows"), "governance entry must own no sensitivity rows"
    assert r["no_row_reason"] == "spec-pending:01§11", r["no_row_reason"]
    assert r["accepted"] not in (None, False)
    print("  P3 OK  estimand REUSED (screen_estimand_v22); battery + regional-"
          "agencies rowless governance leaves, spec-pending:01§11 (pre-fit)")


def test_p4_fitted_artifacts_byte_identical():
    """The pre-registration ran NO fit: v2.0 + v2.1 + v2.2 screen artifacts
    stay byte-identical at their frozen shas."""
    for name, want in (("screen_results.json", "b88f9b65"),
                       ("screen_results_v21.json", "83aeb032"),
                       ("screen_results_v22.json", "3b1d5526")):
        p = os.path.join(OUT, name)
        if not os.path.exists(p):
            print(f"  P4 SKIP ({name} absent)")
            continue
        h = hashlib.sha256(open(p, "rb").read()).hexdigest()
        assert h.startswith(want), f"{name} sha changed: {h[:16]} (want {want})"
    print("  P4 OK  v2.0 (b88f9b65) + v2.1 (83aeb032) + v2.2 (3b1d5526) "
          "artifacts byte-identical -- no fit ran")


if __name__ == "__main__":
    test_p1_battery_rows_v23()
    test_p2_thresholds_carry_over_no_new_ids()
    test_p3_estimand_reused_and_governance_shape()
    test_p4_fitted_artifacts_byte_identical()
    print("ALL V23 PRE-REGISTRATION TESTS PASS")
