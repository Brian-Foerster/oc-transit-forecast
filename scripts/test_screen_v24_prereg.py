"""v2.4 GOVERNANCE PRE-COMMITMENT lock tests (owner-ratified 2026-07-22).

These tests are REGISTRY-ONLY and artifact-independent: nothing here reads a
v2.4 artifact, joins a predictor, or fits anything. They lock the v2.4
governance pre-commitments (spec 01 §5 failure-mode gate + §9.5 stopping rule +
§12) so no batch can silently retune the bar, re-scope the failure-mode subset,
or mint a new threshold once the v2.4 numbers exist. The v2.4 fit has NOT run;
the governance entry is spec-pending:01§12 until it consumes it (the §9/§10/§11
precedent).

  G1  screen_gate_failure_modes exists as a rowless CONSTANT structural-
      governance leaf: spec-pending:01§12 (pre-fit), band=None, accepted stamp,
      the three failure modes named EXACTLY (catchment_width / spatial_resolution
      / specification), and the per-version row->mode map covering
      v2.0/v2.1/v2.2/v2.4-anchor with the v2.4-anchor triple = buffer /
      min_sep-identity / swap
  G2  the FROZEN thresholds are UNCHANGED IN VALUE -- the failure-mode gate
      re-scopes what criteria 2/3 RANGE OVER (their SUPPORT), never the VALUES
      (0.841 / 0.7 / 0.20 / 2·14⁻¹). No *_v24 threshold id is minted; the only
      new registry id is screen_gate_failure_modes, and it is NOT a numeric
      threshold. The gate NAMES the three thresholds it ranges over, unchanged.
  G3  the pre-commitment ran NO fit: v2.0 (b88f9b65) + v2.1 (83aeb032) + v2.2
      (3b1d5526) screen artifacts stay byte-identical.

    python -X utf8 scripts/test_screen_v24_prereg.py
"""
import hashlib
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "outputs")

from assumptions import val, ASSUMPTIONS                           # noqa: E402

# the three failure modes, written here as an EXPLICIT literal (not a transform
# of the registry the test is meant to guard).
MODES_EXPECTED = ("catchment_width", "spatial_resolution", "specification")

# the per-version row->mode map (spec 01 §5 FAILURE-MODE GATE). Row ids can't
# stay constant across the window->anchor geometry change, so the map names the
# perturbation per mode per version. v2.4-anchor is the NORMATIVE row: buffer /
# min_sep-identity / swap.
ROW_MAP_EXPECTED = {
    "v2.0": ["buffer", "window_len", "estimator-or-swap"],
    "v2.1": ["buffer", "window_len", "swap"],
    "v2.2": ["buffer", "window_len", "swap"],
    "v2.4-anchor": ["buffer", "min_sep-identity", "swap"],
}

# the FROZEN thresholds the failure-mode gate ranges over -- UNCHANGED IN VALUE.
FROZEN_THRESHOLDS = {
    "screen_pos_frac_min": 0.841,
    "screen_battery_rho_min": 0.7,
    "screen_tie_churn_max_window": 0.20,
    "screen_tie_churn_max_hostshape": 2.0 / 14.0,
}


def test_g1_failure_mode_gate_entry():
    """screen_gate_failure_modes is a rowless CONSTANT governance leaf with the
    three modes named exactly and the per-version row->mode map (v2.4-anchor =
    buffer / min_sep-identity / swap)."""
    assert "screen_gate_failure_modes" in ASSUMPTIONS
    e = ASSUMPTIONS["screen_gate_failure_modes"]
    assert e["tier"] == "constant" and e["status"] == "active"
    assert e["band"] is None
    assert not e.get("rows"), "governance entry must own no sensitivity rows"
    assert e["no_row_reason"] == "spec-pending:01§12", e["no_row_reason"]
    assert e["accepted"] not in (None, False)
    v = val("screen_gate_failure_modes")
    assert isinstance(v, dict)
    # the three modes, named exactly
    assert tuple(v["modes"].keys()) == MODES_EXPECTED, tuple(v["modes"].keys())
    # per-version row->mode map, covering all four versions with 3-item triples
    rm = v["row_map"]
    assert rm == ROW_MAP_EXPECTED, rm
    for ver, triple in rm.items():
        assert len(triple) == 3, (ver, triple)
    # the v2.4-anchor mode instantiation (the normative one)
    assert rm["v2.4-anchor"] == ["buffer", "min_sep-identity", "swap"]
    assert v["normative_for"] == ["v2.4-anchor"]
    assert set(v["documentary_for"]) == {"v2.0", "v2.1", "v2.2"}
    # the direction note is present and states the "easier in expectation" fact
    assert "noisier" in v["direction_note"] and "EASIER" in v["direction_note"]
    print("  G1 OK  screen_gate_failure_modes: rowless CONSTANT governance leaf, "
          "spec-pending:01§12; modes = catchment_width/spatial_resolution/"
          "specification; v2.4-anchor = buffer/min_sep-identity/swap")


def test_g2_thresholds_unchanged_no_new_bar():
    """The failure-mode gate re-scopes SUPPORT, not VALUE: the four frozen
    thresholds are unchanged, no *_v24 threshold id is minted, and the new
    governance entry is NOT a numeric threshold."""
    for tid, want in FROZEN_THRESHOLDS.items():
        got = val(tid)
        assert abs(float(got) - want) < 1e-15, (tid, got, want)
    # the gate NAMES exactly these three thresholds it ranges over (crit 2/3)
    named = val("screen_gate_failure_modes")["thresholds_unchanged"]
    assert named == ["screen_battery_rho_min", "screen_tie_churn_max_window",
                     "screen_tie_churn_max_hostshape"], named
    # no v24 threshold id minted anywhere
    for aid in ASSUMPTIONS:
        assert not aid.endswith("_v24"), f"{aid}: a *_v24 id was minted"
    assert "screen_estimand_v24" not in ASSUMPTIONS
    assert "screen_battery_rows_v24" not in ASSUMPTIONS
    # the one new id is not a scalar bar
    assert not isinstance(val("screen_gate_failure_modes"), (int, float))
    print("  G2 OK  thresholds unchanged (0.841/0.7/0.20/2·14⁻¹); failure-mode "
          "gate re-scopes SUPPORT not VALUE; no *_v24 threshold/estimand/battery "
          "id minted")


def test_g3_fitted_artifacts_byte_identical():
    """The pre-commitment ran NO fit: v2.0 + v2.1 + v2.2 screen artifacts stay
    byte-identical at their frozen shas."""
    for name, want in (("screen_results.json", "b88f9b65"),
                       ("screen_results_v21.json", "83aeb032"),
                       ("screen_results_v22.json", "3b1d5526")):
        p = os.path.join(OUT, name)
        if not os.path.exists(p):
            print(f"  G3 SKIP ({name} absent)")
            continue
        h = hashlib.sha256(open(p, "rb").read()).hexdigest()
        assert h.startswith(want), f"{name} sha changed: {h[:16]} (want {want})"
    print("  G3 OK  v2.0 (b88f9b65) + v2.1 (83aeb032) + v2.2 (3b1d5526) "
          "artifacts byte-identical -- no fit ran")


if __name__ == "__main__":
    test_g1_failure_mode_gate_entry()
    test_g2_thresholds_unchanged_no_new_bar()
    test_g3_fitted_artifacts_byte_identical()
    print("ALL V24 GOVERNANCE PRE-COMMITMENT TESTS PASS")
