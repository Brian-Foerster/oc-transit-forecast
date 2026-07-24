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
      the FOUR failure modes named EXACTLY (catchment_width / spatial_resolution
      / specification / estimation_uncertainty -- the fourth added 2026-07-22),
      and the per-version row->mode map covering v2.0/v2.1/v2.2/v2.4-anchor with
      the v2.4-anchor quad = buffer / min_sep-identity / swap / coeff_resample
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

# the FOUR failure modes, written here as an EXPLICIT literal (not a transform
# of the registry the test is meant to guard). The fourth, estimation_uncertainty
# (coefficient-sampling), was added 2026-07-22 as the load-bearing threat.
MODES_EXPECTED = ("catchment_width", "spatial_resolution", "specification",
                  "estimation_uncertainty")

# the per-version row->mode map (spec 01 §5 FAILURE-MODE GATE). Row ids can't
# stay constant across the window->anchor geometry change, so the map names the
# perturbation per mode per version. Positional:
# [catchment_width, spatial_resolution, specification, estimation_uncertainty].
# v2.4-anchor is the NORMATIVE row: buffer / min_sep-identity / swap /
# coeff_resample; the fourth slot is documentary for v2.0/v2.1/v2.2.
ROW_MAP_EXPECTED = {
    "v2.0": ["buffer", "window_len", "estimator-or-swap", "coeff_resample"],
    "v2.1": ["buffer", "window_len", "swap", "coeff_resample"],
    "v2.2": ["buffer", "window_len", "swap", "coeff_resample"],
    "v2.4-anchor": ["buffer", "min_sep-identity", "swap", "coeff_resample"],
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
    FOUR modes named exactly and the per-version row->mode map (v2.4-anchor =
    buffer / min_sep-identity / swap / coeff_resample)."""
    assert "screen_gate_failure_modes" in ASSUMPTIONS
    e = ASSUMPTIONS["screen_gate_failure_modes"]
    assert e["tier"] == "constant" and e["status"] == "active"
    assert e["band"] is None
    assert not e.get("rows"), "governance entry must own no sensitivity rows"
    assert e["no_row_reason"] == "spec-pending:01§12", e["no_row_reason"]
    assert e["accepted"] not in (None, False)
    v = val("screen_gate_failure_modes")
    assert isinstance(v, dict)
    # the FOUR modes, named exactly (fourth = estimation_uncertainty, 2026-07-22)
    assert tuple(v["modes"].keys()) == MODES_EXPECTED, tuple(v["modes"].keys())
    # per-version row->mode map, covering all four versions with 4-item quads
    rm = v["row_map"]
    assert rm == ROW_MAP_EXPECTED, rm
    for ver, quad in rm.items():
        assert len(quad) == 4, (ver, quad)
    # the v2.4-anchor mode instantiation (the normative one), incl. the 4th slot
    assert rm["v2.4-anchor"] == ["buffer", "min_sep-identity", "swap",
                                 "coeff_resample"]
    # the fourth mode is coeff_resample in every version's 4th slot
    for ver, quad in rm.items():
        assert quad[3] == "coeff_resample", (ver, quad)
    assert v["normative_for"] == ["v2.4-anchor"]
    assert set(v["documentary_for"]) == {"v2.0", "v2.1", "v2.2"}
    # the direction note is present and states the "easier in expectation" fact
    assert "noisier" in v["direction_note"] and "EASIER" in v["direction_note"]
    # the fourth-mode note is present and states the load-bearing/bind rationale
    assert "fourth_mode_note" in v, "fourth_mode_note missing"
    assert "BIND" in v["fourth_mode_note"] and "load-bearing" in \
        v["fourth_mode_note"]
    print("  G1 OK  screen_gate_failure_modes: rowless CONSTANT governance leaf, "
          "spec-pending:01§12; modes = catchment_width/spatial_resolution/"
          "specification/estimation_uncertainty; v2.4-anchor = "
          "buffer/min_sep-identity/swap/coeff_resample")


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


# the §13 DRAFT standalone knob entries (criterion A: every knob has a registry
# entry). All spec-pending:01§13, DRAFT (not yet owner-ratified).
V24_KNOB_ENTRIES = ("screen_anchor_min_sep", "screen_anchor_membership_buffer",
                    "screen_anchor_pair_dist_cap", "screen_anchor_peak_pool",
                    "screen_anchor_path_exclusion", "screen_v24_ranking_measure",
                    "screen_v24_cost_model", "screen_v24_exposure",
                    "screen_v24_prereg")

# mode -> v2.4-anchor row, derived POSITIONALLY from the frozen row_map so the
# knob->home map cannot drift from the failure-mode gate (§5). The four gated
# knobs in knob_home_map must map one-to-one onto these (mode, row) pairs.
MODE_TO_ROW = dict(zip(MODES_EXPECTED, ROW_MAP_EXPECTED["v2.4-anchor"]))


def test_g4_v24_prereg_draft_knob_home_map():
    """The §13 DRAFT pre-registration: every v2.4 knob has a registry entry
    (criterion A) with an explicit HOME, and each of the FOUR failure modes is
    instantiated by EXACTLY ONE gated row whose (mode, row) matches the frozen
    v2.4-anchor row_map (criterion C). DRAFT -- NOT FROZEN."""
    # criterion A: every named §13 knob is a real registry entry, spec-pending
    # :01§13, with a non-null (DRAFT) accepted disposition stamp.
    for aid in V24_KNOB_ENTRIES:
        assert aid in ASSUMPTIONS, f"{aid}: §13 knob missing a registry entry"
        e = ASSUMPTIONS[aid]
        assert e["tier"] == "constant" and e["status"] == "active", aid
        assert e.get("no_row_reason") == "spec-pending:01§13", (aid,
            e.get("no_row_reason"))
        assert e.get("accepted") not in (None, False), \
            f"{aid}: rowless spec-pending leaf needs a (DRAFT) accepted stamp"
        # DRAFT, not ratified -- the stamp must SAY draft/not-frozen
        assert "DRAFT" in e["accepted"][0], f"{aid}: accepted stamp not DRAFT"

    # the umbrella carries the machine-readable §13 and the DRAFT status.
    pre = val("screen_v24_prereg")
    assert isinstance(pre, dict)
    assert pre["draft"] is True and pre["frozen"] is False, "must be DRAFT"
    assert "owner ratification" in pre["freeze_requires"]
    assert pre["no_new_fit"] is True
    # NO new fit: the reused v2.2 coefficients are recorded EXACTLY.
    rc = pre["reuses_v22_coeffs"]
    assert abs(rc["b1_flows"] - 0.256194) < 1e-12
    assert abs(rc["b2_zveh"] - 0.382547) < 1e-12
    assert abs(rc["b4_genjobs"] - (-0.041057)) < 1e-12
    assert abs(rc["b5_len"] - (-0.22846)) < 1e-12
    # thresholds unchanged (no *_v24 bar) -- the §13 gate names the frozen ids.
    assert pre["thresholds_unchanged"] == ["screen_pos_frac_min",
        "screen_battery_rho_min", "screen_tie_churn_max_window",
        "screen_tie_churn_max_hostshape"], pre["thresholds_unchanged"]

    # criterion A+C: the knob->home map. Every knob has a home AND a rationale.
    khm = pre["knob_home_map"]
    for knob, m in khm.items():
        assert "home" in m and m["home"], f"{knob}: no home"
        assert m.get("rationale"), f"{knob}: no rationale (criterion C)"

    # criterion A (registry-presence hardening): every knob_home_map key must
    # resolve to a REAL registry entry -- EXCEPT the two documented non-registry
    # references. A key that presents as a registry id (or `screen_*`-prefixed)
    # but has no entry is a HOMELESS KNOB and must fail here. This closes the
    # gap that let the map name `screen_v24_queue_len` (no entry) pass GREEN:
    # the criterion-A loop above iterates V24_KNOB_ENTRIES, not the map keys.
    #   - reused_v22_coefficients: the reused v2.2 coefficients live in
    #     screen_results_v22.json / screen_v24_prereg.reuses_v22_coeffs, not a
    #     standalone entry (home = failure_mode 4, documented reuse).
    #   - queue_length: homed as the screen_v24_prereg.deliverable sub-field
    #     (spec 01 §13.7), a definitional property of the deliverable, not a
    #     tunable registry knob.
    NON_REGISTRY_KNOBS = {"reused_v22_coefficients", "queue_length"}
    for knob in khm:
        if knob in NON_REGISTRY_KNOBS:
            # a non-registry reference must NOT masquerade as a registry id
            assert not knob.startswith("screen_"), \
                f"{knob}: non-registry knob keyed as a `screen_*` registry id"
            continue
        assert knob in ASSUMPTIONS, \
            f"{knob}: knob_home_map key has no registry entry (homeless knob)"

    # exactly FOUR gated knobs, mapping ONE-TO-ONE onto the four failure modes.
    gated = {k: m for k, m in khm.items() if m.get("gated")}
    assert len(gated) == 4, f"expected 4 gated knobs, got {sorted(gated)}"
    gated_modes = sorted(m["mode"] for m in gated.values())
    assert gated_modes == sorted(MODES_EXPECTED), gated_modes
    # each gated knob's (mode, row) matches the frozen v2.4-anchor row_map.
    for knob, m in gated.items():
        assert MODE_TO_ROW[m["mode"]] == m["row"], (knob, m["mode"], m["row"],
            "does not match the frozen v2.4-anchor row_map")

    # the gated knobs are the load-bearing four: min_sep (resolution), buffer_mi
    # (width), the ranking measure (specification), the reused coeffs
    # (estimation). Each resolves to a registry entry OR is a documented reuse.
    assert gated["screen_anchor_min_sep"]["mode"] == "spatial_resolution"
    assert gated["buffer_mi"]["mode"] == "catchment_width"
    assert gated["screen_v24_ranking_measure"]["mode"] == "specification"
    assert gated["reused_v22_coefficients"]["mode"] == "estimation_uncertainty"

    # every non-gated knob is homed in a NON-failure-mode disposition (criterion
    # A: a home that is NOT a gate row -- disclosed diagnostic / universe
    # predicate / frozen convention / deliverable).
    non_gate_homes = {"disclosed_diagnostic", "universe_predicate",
                      "frozen_convention", "deliverable"}
    for knob, m in khm.items():
        if not m.get("gated"):
            assert m["home"] in non_gate_homes, (knob, m["home"])

    # the universe-defining constant is FROZEN at the min_sep-under-M2_fit value.
    assert abs(val("screen_anchor_min_sep") - 1.5) < 1e-12

    print("  G4 OK  §13 DRAFT knob->home map: 9 knob entries (spec-pending:01"
          "§13, DRAFT); knob_home_map homes every knob with a rationale; the "
          "FOUR modes each instantiated by exactly ONE gated row matching the "
          "frozen v2.4-anchor row_map (buffer / min_sep-identity / swap / "
          "coeff_resample); min_sep frozen at 1.5")


if __name__ == "__main__":
    test_g1_failure_mode_gate_entry()
    test_g2_thresholds_unchanged_no_new_bar()
    test_g3_fitted_artifacts_byte_identical()
    test_g4_v24_prereg_draft_knob_home_map()
    print("ALL V24 GOVERNANCE PRE-COMMITMENT + §13 DRAFT LOCK TESTS PASS")
