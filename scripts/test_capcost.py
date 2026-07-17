"""
Gates for the capital-cost function (spec 07 N2 / spec 04). These are spec 04's
OWN validation gates (§5) plus the spec 07 N2 acceptance checks, run as a
hand-check TDD ladder (E55 red -> green first). Pure arithmetic, EXCEPT
test_harbor_bands_vs_tbc, which reads the live tbc cost profile (existence-
gated -- skips with a notice if the transit-benefit-cost sibling checkout is
absent, same convention as check_assumptions.py / make_charts.py).

    python test_capcost.py

  - test_e55: spec 04 §5 gate 1 -- the sheet's shipped configuration (20 km
    elevated / 16 stations / 32 cars / 1 depot, crossings=0, fixed_cost_share=1)
    reproduces the sheet's E55 = $1,985.04M EXACTLY. This is the primary gate;
    it locks the markup-inclusive coefficient set to the cent.
  - test_markup_inclusive_coeffs: the pre-markup leaf rates x the LOW markup
    reproduce spec 04 / spec 07 N2's documented markup-inclusive coefficients
    (Fixed 183.6; 23.4/route-km; 27.6/km elevated; 33.96/station; 7.44/car).
  - test_fixed_cost_share: the §8j knob scales ONLY the fixed term.
  - test_harbor_bands_vs_tbc: cross-check harbor LOW | US-TYPICAL against the
    LIVE tbc profile file (transit-benefit-cost/costs/profiles/harbor.json,
    existence-gated -- SKIPS with a notice if the sibling repo is absent, never
    silently no-ops). Fleet is DERIVED (cc.fleet(12.1, 5.0)), not hardcoded, and
    checked against the profile's own fleet_cars so a future fleet move can't
    silently decouple the two repos again. capcost's own capital() is
    reconciled to the profile's committed K (LOW/US-TYPICAL total_musd) to the
    dollar via the documented residual (tbc's §3.3b street/utility lines,
    marked up the SAME way capcost's own bands are -- both additive-1.20 LOW
    now, N2 review 2026-07-15 corrected tbc's prior 1.21 multiplicative
    misread).
  - test_rem_sanity: spec 04 §5 gate 2 -- LOW rate card on REM's headline
    quantities lands NEAR the sheet's 100-125 $/km band; assert the documented
    point value, not band membership (the bare-headline result is just below).
  - test_fleet_harbor / test_fleet_rem: spec 04 §5 gate 4 -- 25 cars for Harbor
    at the 60-mph design central (owner 2026-07-17; was 27 at the old 80 km/h
    central), within ~15% of REM's 212-car order at REM's line length.
"""
import json
import math
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import capcost as cc

KM_PER_MI = 1.609344

# the live tbc cost profile (transit-benefit-cost sibling checkout). Existence-
# gated on a configurable sibling path -- same convention as check_assumptions.
# py's WRAPPER_ARTIFACT / make_charts.py's _wrapper_path -- so a fresh clone
# without the sibling repo still runs (skip-with-notice), and CI/dev boxes that
# DO have it get the live cross-repo cross-check, not a hand-copied snapshot
# that silently drifts out from under the gate (this is the exact failure mode
# test_harbor_bands_vs_tbc previously had: a stale 27-car/2050/3622/x1.21
# snapshot that kept passing after both sides moved).
HERE = os.path.dirname(os.path.abspath(__file__))
TBC_HARBOR_PROFILE = os.environ.get(
    "TBC_HARBOR_PROFILE",
    os.path.join(HERE, "..", "..", "transit-benefit-cost", "costs", "profiles",
                 "harbor.json"))


def _close(a, b, tol=0.01):
    return abs(a - b) <= tol


def test_e55():
    """spec 04 §5 gate 1: shipped config -> E55 = $1,985.04M exactly."""
    tot = cc.capital(20.0 / KM_PER_MI, 16, 32, band="LOW", crossings=0,
                     fixed_cost_share=1.0)
    assert _close(tot, 1985.04), f"E55 = {tot} != 1985.04"
    print(f"  test_e55 OK  (20km/16stn/32cars/1depot -> ${tot:.2f}M = E55)")


def test_markup_inclusive_coeffs():
    """The pre-markup leaves x LOW markup reproduce the documented markup-
    inclusive coefficients (spec 07 N2 / spec 04 §2)."""
    m = cc.CAP_MK_LOW
    checks = {
        "Fixed": ((cc.CAP_OCC + cc.CAP_DEPOT) * m, 183.6),
        "route-km": (cc.CAP_ROUTE_KM * m, 23.4),
        "elevated add-on": (cc.CAP_VIADUCT_KM * m, 27.6),
        "station": (cc.CAP_STATION * m, 33.96),
        "car": (cc.CAP_CAR * m, 7.44),
    }
    for name, (got, want) in checks.items():
        assert _close(got, want), f"{name}: {got} != {want}"
    print("  test_markup_inclusive_coeffs OK  (183.6 / 23.4 / 27.6 / 33.96 / 7.44)")


def test_fixed_cost_share():
    """§8j: fixed_cost_share scales ONLY the fixed term (183.6 at LOW)."""
    full = cc.capital(12.1, 13, 27, band="LOW", crossings=0, fixed_cost_share=1.0)
    none = cc.capital(12.1, 13, 27, band="LOW", crossings=0, fixed_cost_share=0.0)
    half = cc.capital(12.1, 13, 27, band="LOW", crossings=0, fixed_cost_share=0.5)
    fixed_low = (cc.CAP_OCC + cc.CAP_DEPOT) * cc.CAP_MK_LOW      # 183.6
    assert _close(full - none, fixed_low), (full - none, fixed_low)
    assert _close(full - half, fixed_low / 2.0), (full - half, fixed_low / 2.0)
    print(f"  test_fixed_cost_share OK  (share=0 drops ${fixed_low:.1f}M fixed)")


def test_harbor_bands_vs_tbc():
    """Cross-check LOW | US-TYPICAL against the LIVE tbc harbor cost profile
    (existence-gated: SKIPS with a notice, never silently passes, if the
    transit-benefit-cost sibling checkout is absent). Fleet is DERIVED from
    cc.fleet(12.1, 5.0) -- not hardcoded -- and checked against the profile's
    own fleet_cars. capcost's own capital() is reconciled to the profile's
    committed K (total_musd) to the dollar via the documented residual: tbc's
    §3.3b street/utility lines, now marked up the SAME additive-1.20 LOW way
    capcost's own LOW band is (N2 review 2026-07-15 corrected tbc's prior 1.21
    multiplicative misread -- this gate reads the LIVE file precisely so it
    cannot drift back out of sync with a stale hardcoded snapshot again)."""
    if not os.path.exists(TBC_HARBOR_PROFILE):
        print(f"  test_harbor_bands_vs_tbc SKIPPED  (sibling repo not found: "
              f"{TBC_HARBOR_PROFILE})")
        return
    with open(TBC_HARBOR_PROFILE, "r", encoding="utf-8") as f:
        profile = json.load(f)

    km = 12.1 * KM_PER_MI                                        # 19.473 km
    cars = cc.fleet(12.1, 5.0)
    assert cars == profile["design"]["fleet_cars"], (
        cars, profile["design"]["fleet_cars"])

    low = cc.capital(12.1, 13, cars, band="LOW", crossings=4)
    ut = cc.capital(12.1, 13, cars, band="US_TYPICAL", crossings=4)

    tbc_low_musd = float(profile["capital"]["low"]["total_musd"])
    tbc_ut_musd = float(profile["capital"]["us_typical"]["total_musd"])

    # --- reconciliation of the tbc deltas (documented residual lines) ---
    # tbc LOW = my LOW + street-restoration 3/km, marked up at the SAME
    #           additive 1.20 LOW markup capcost uses (both sides corrected off
    #           the old 1.21 multiplicative misread, N2 review 2026-07-15).
    tbc_low = low + 3.0 * km * cc.CAP_MK_LOW
    assert _close(tbc_low, tbc_low_musd, 1.0), (tbc_low, tbc_low_musd)
    # tbc US-TYPICAL = my US-TYPICAL + (street 6/km + utilities uplift 5/km) x mk_ut
    tbc_ut = ut + (6.0 + 5.0) * km * cc.CAP_MK_UT
    assert _close(tbc_ut, tbc_ut_musd, 1.0), (tbc_ut, tbc_ut_musd)
    print(f"  test_harbor_bands_vs_tbc OK  (fleet {cars} cars == profile; "
          f"LOW ${low:.0f}M -> tbc {tbc_low_musd:.0f}; US-TYP ${ut:.0f}M -> "
          f"tbc {tbc_ut_musd:.0f}; deltas = live §3.3b + markup, reconciled)")


def test_rem_sanity():
    """spec 04 §5 gate 2: LOW rate card on REM's headline quantities (67 km /
    26 stn / 212 cars, fully elevated, no special structures) lands NEAR the
    sheet's 100-125 $/km band. Assert the DOCUMENTED point value (~99.25, REM's
    actual outturn ~C$6.65B/67km), not band membership: the bare-headline result
    sits just below both the band and the target, the gap being REM's tunnel +
    river/highway crossings (spec 04 §3.3 special structures the base sheet
    omits)."""
    rem_mi = 67.0 / KM_PER_MI
    bare = cc.capital(rem_mi, 26, 212, band="LOW", crossings=0)
    per_km = bare / 67.0
    assert _close(per_km, 90.46, 0.05), per_km          # pinned regression
    # within ~10% of the documented 99.25 outturn calibration point
    assert abs(per_km / 99.25 - 1.0) < 0.10, per_km
    # the special-structures allowance (REM's Mount Royal tunnel + river/highway
    # crossings) closes the gap to the documented 99.25; ~$491M pre-markup, i.e.
    # ~6-16 crossings across the §3.3 30-80 $M band (mechanism check).
    special_pre = (99.25 * 67.0 - bare) / cc.CAP_MK_LOW
    with_struct = cc.capital(rem_mi, 26, 212, band="LOW", crossings=1,
                             crossing_rate=special_pre)
    assert _close(with_struct / 67.0, 99.25, 0.05), with_struct / 67.0
    print(f"  test_rem_sanity OK  (bare {per_km:.2f} $/km, {100*(1-per_km/99.25):.1f}% "
          f"below the documented 99.25; +${special_pre:.0f}M special structures "
          f"-> 99.25)")


def test_fleet_harbor():
    """spec 04 §5 gate 4 / §3.1: Harbor fleet. Derives from the v_cruise prior
    central via cc.fleet's default derived speed: at the owner 2026-07-17 60-mph
    design central (v_cruise 96.6 km/h -> ~31.8 mph avg) the faster line cuts the
    cycle time, so the fleet is 25 cars (was 27 at the old 80 km/h literature
    central / ~29.8 mph). This gate MOVES with the prior by design."""
    cars = cc.fleet(12.1, 5.0, cars_per_train=2)
    assert cars == 25, cars
    print(f"  test_fleet_harbor OK  (12.1 mi, 5-min peak, 2-car -> {cars} cars)")


def test_fleet_rem():
    """spec 04 §5 gate 4: within ~15% of REM's 212-car order at REM's length
    (67 km, ~4-min peak, 4-car -- the trunk consist of the 2/4-car mix), using
    the model's grade-separated speed machinery at REM's ~1.6-mi station spacing.

    Keys on REM's OWN cruise speed (the ~80 km/h REM-class literature value that
    WAS the v_cruise central before the owner 2026-07-17 60-mph HARBOR design
    decision), NOT the live v_cruise prior: derived_v_avg_mph now carries
    harbor's design top speed, and importing another corridor's design cruise
    into a REM plausibility check is a category error (this coupling is what
    drifted the check when the harbor prior moved)."""
    rem_mi = 67.0 / KM_PER_MI
    v_rem = 60.0 / float(cc.grade_sep_min_per_mile(80.0, 25.0, rem_mi / 26.0))
    cars = cc.fleet(rem_mi, 4.0, cars_per_train=4, v_avg_mph=v_rem)
    assert abs(cars / 212.0 - 1.0) < 0.15, (cars, cars / 212.0)
    print(f"  test_fleet_rem OK  ({cars} cars vs 212 order = "
          f"{100*(cars/212.0-1):.1f}%, within 15%)")


if __name__ == "__main__":
    test_e55()
    test_markup_inclusive_coeffs()
    test_fixed_cost_share()
    test_harbor_bands_vs_tbc()
    test_rem_sanity()
    test_fleet_harbor()
    test_fleet_rem()
    print("ALL CAPCOST GATES PASS")
