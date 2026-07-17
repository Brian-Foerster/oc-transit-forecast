"""
capcost.py -- spec 04 capital-cost rate card as code (spec 07 work item N2).

Prices ONE mode: elevated automated light metro, REM-class (spec 04 mode
decision 2026-07-08). Two exports: `capital()` (markup-inclusive $M, LOW |
US-TYPICAL bands) and `fleet()` (derived car count, spec 04 §3.1). The spec 07
interim objective shows Delta-K beside Delta(welfare-minutes) as the spec 04 §3.2
LOW | US-TYPICAL band pair (never the low number alone); the full-NPV objective
(N5) consumes the same two functions.

    python capcost.py <route_mi> <stations> <headway_peak_min>
        -> LOW and US-TYPICAL capital ($M and $/km) + derived fleet

SINGLE SOURCE. Every rate-card number is imported from the assumptions registry
(scripts/assumptions.py, constant tier, basis measured -- REM rate card); this
module DERIVES the markup-inclusive coefficients from those pre-markup leaves.
The average-speed coupling reuses model.py's grade-separated derived-speed
machinery (grade_sep_min_per_mile) at the prior-central cruise/dwell -- the same
single source model.py's own main() reads -- so the fleet cycle time cannot
drift from the ridership model's speed physics.

--- The rate card (spec 04 §2; costs/metro_cost_model.xlsx) --------------------
Linear MECE structure:

    subtotal = fixed*fixed_cost_share
             + route_km_rate * route_km
             + viaduct_rate  * delivery * route_km        (fully elevated)
             + station_rate  * delivery * stations
             + car_rate      * cars
             + crossings     * crossing_rate
    capital  = subtotal * markup

LOW is the sheet's efficient-agency scenario: markup 1.20 (10% design + 10%
contingency, ADDITIVE), delivery 1.0. The markup-inclusive coefficients this
yields -- Fixed 183.6; 23.4 $M/route-km; +27.6 $M/km elevated; 33.96 $M/station;
7.44 $M/car -- reproduce the sheet's shipped-config total E55 = $1,985.04M to
the cent (gate, test_capcost.test_e55).

US-TYPICAL applies spec 04 §3.2: markup 1.3923 (soft 1.17 x contingency 1.19,
multiplicative) and a 1.75x delivery-environment factor on the civil items
(viaduct + stations). This is the transformation the tbc harbor profile used;
this function reproduces its LOW | US-TYPICAL structure, with the residual
deltas (tbc's §3.3b dense-segment street/utility lines, and its 1.21 vs the
sheet's E55-locked 1.20 LOW markup) documented and reconciled to the dollar in
test_capcost.test_harbor_bands_vs_tbc.

Fully-elevated assumption: the mode is elevated ALM, so the viaduct add-on
applies to all route_mi (matches the E55 config and Harbor). A corridor with an
at-grade split would need an `elevated_mi` extension -- out of scope for N2.

Special structures (spec 04 §3.3): freeway/river/railroad crossings break the
repetitive-guideway calibration, so they are a separate count x rate line
(placeholder band 30-80 $M/crossing, FLAGGED for an engineering reference). The
per-crossing rate is parameterized (crossing_rate=), defaulting to the band-
appropriate registry constant.
"""
import math
import sys

from assumptions import val
from model import PRIORS, grade_sep_min_per_mile

KM_PER_MI = 1.609344   # exact (val('kmh_per_mph')); local literal to avoid the
                       # registry round-trip for a definitional conversion

# --- pre-markup rate-card leaves ($M, 2026 US$; assumptions registry) ---------
CAP_OCC = val("cap_occ")                 # 28.0  operations control centre (fixed)
CAP_DEPOT = val("cap_depot")             # 125.0 depot (fixed, 1 per line)
CAP_ROUTE_KM = val("cap_route_km")       # 19.5  track+traction+CBTC+utilities /km
CAP_VIADUCT_KM = val("cap_viaduct_km")   # 23.0  elevated viaduct add-on /km
CAP_STATION = val("cap_station")         # 28.3  elevated station
CAP_CAR = val("cap_car")                 # 6.2   rolling stock /car
# --- scenario transformation factors ------------------------------------------
CAP_MK_LOW = val("cap_markup_low")       # 1.20  additive design+contingency (E55)
CAP_MK_UT = val("cap_markup_ut")         # 1.3923 soft x contingency (§3.2)
CAP_DELIV_UT = val("cap_delivery_ut")    # 1.75  delivery-env on viaduct+stations
CAP_XING_LOW = val("cap_crossing_low")   # 30.0  crossing rate, LOW
CAP_XING_UT = val("cap_crossing_ut")     # 65.0  crossing rate, US-TYPICAL

BANDS = ("LOW", "US_TYPICAL")


def _band_factors(band):
    """(markup, civil-delivery factor, default crossing rate) for a band."""
    if band == "LOW":
        return CAP_MK_LOW, 1.0, CAP_XING_LOW
    if band == "US_TYPICAL":
        return CAP_MK_UT, CAP_DELIV_UT, CAP_XING_UT
    raise ValueError(f"unknown band {band!r}; expected one of {BANDS}")


def capital(route_mi, stations, cars, band="LOW", crossings=0,
            crossing_rate=None, fixed_cost_share=1.0):
    """Markup-inclusive capital cost ($M) for an elevated ALM line.

    route_mi          route length (miles); fully elevated (viaduct add-on on all)
    stations          elevated station count
    cars              fleet car count (derive with fleet())
    band              "LOW" | "US_TYPICAL" (spec 04 §3.2; never LOW alone)
    crossings         count of major special structures (spec 04 §3.3)
    crossing_rate     $M per crossing; default = band constant (parameterized,
                      band 30-80 $M placeholder)
    fixed_cost_share  scales the fixed term (OCC + depot) for lines after the
                      first (spec 08 §8j / spec 07 §8j knob; rows {1, 0.5, 0})
    """
    markup, delivery, xing_default = _band_factors(band)
    if crossing_rate is None:
        crossing_rate = xing_default
    route_km = route_mi * KM_PER_MI
    fixed = (CAP_OCC + CAP_DEPOT) * fixed_cost_share
    subtotal = (fixed
                + CAP_ROUTE_KM * route_km
                + CAP_VIADUCT_KM * delivery * route_km
                + CAP_STATION * delivery * stations
                + CAP_CAR * cars
                + crossings * crossing_rate)
    return subtotal * markup


def capital_bands(route_mi, stations, cars, crossings=0, crossing_rate_low=None,
                  crossing_rate_ut=None, fixed_cost_share=1.0):
    """Convenience: both bands as a dict {"LOW": $M, "US_TYPICAL": $M}."""
    return {
        "LOW": capital(route_mi, stations, cars, "LOW", crossings,
                       crossing_rate_low, fixed_cost_share),
        "US_TYPICAL": capital(route_mi, stations, cars, "US_TYPICAL", crossings,
                              crossing_rate_ut, fixed_cost_share),
    }


# --- derived average speed (single source: model.py grade-separated physics) ---
def _central(prior):
    """Prior-central value = band midpoint, matching model.py main()'s vc_c/dw_c
    (sum(PRIORS[k][:2]) / 2). Single source: model.PRIORS is built from the same
    registry this module reads."""
    lo, hi, _ = PRIORS[prior]
    return (lo + hi) / 2.0


def derived_v_avg_mph(spacing_mi=1.0):
    """Grade-separated average speed (mph) at the prior-central cruise/dwell and
    the given station spacing, via model.grade_sep_min_per_mile (spec 02 §4.9b,
    the ridership model's own speed machinery). Default spacing 1.0 mi is the
    mode's canonical station spacing (spec 04, '1-mi stations'); pass the actual
    spacing for other designs (e.g. REM's ~1.6 mi). At the owner 2026-07-17
    60-mph design central (v_cruise 96.6 km/h) / 25 s dwell / 1.0-mi spacing this
    returns ~31.82 mph (~51.2 km/h) -- the tbc profile's cycle-time input (was
    ~29.76 mph / ~47.9 km/h at the old 80 km/h literature central)."""
    mpm = float(grade_sep_min_per_mile(_central("v_cruise"), _central("dwell"),
                                       spacing_mi))
    return 60.0 / mpm


def fleet(route_mi, headway_peak_min, cars_per_train=2, v_avg_mph=None,
          layover_frac=0.15, spare_frac=0.12):
    """Derived fleet size (cars), spec 04 §3.1:

        cycle_time     = 2 * route_length / v_avg * (1 + layover_frac)
        trainsets_peak = ceil( cycle_time / headway_peak )
        cars           = ceil( trainsets_peak * cars_per_train * (1 + spare_frac) )

    Keys on the PEAK consist only (spec 04 §3.1 consist policy). v_avg defaults
    to the grade-separated derived speed at the mode's 1.0-mi canonical spacing
    (derived_v_avg_mph). Spare cars rounded UP (whole-car procurement). Harbor
    (12.1 mi, 5-min peak, 2-car) -> 25 cars at the 60-mph design central (gate;
    was 27 at the old 80 km/h literature central)."""
    if v_avg_mph is None:
        v_avg_mph = derived_v_avg_mph(1.0)
    cycle_min = 2.0 * route_mi / v_avg_mph * (1.0 + layover_frac) * 60.0
    trainsets_peak = math.ceil(cycle_min / headway_peak_min)
    return math.ceil(trainsets_peak * cars_per_train * (1.0 + spare_frac))


def _cli(route_mi, stations, headway_peak_min, cars_per_train=2, crossings=0):
    cars = fleet(route_mi, headway_peak_min, cars_per_train=cars_per_train)
    km = route_mi * KM_PER_MI
    v = derived_v_avg_mph(1.0)
    print(f"elevated automated light metro (spec 04 rate card as code)")
    print(f"  route      {route_mi:.2f} mi ({km:.2f} km), fully elevated")
    print(f"  stations   {stations}")
    print(f"  fleet      {cars} cars ({cars_per_train}-car peak consist, "
          f"{headway_peak_min:g}-min peak; v_avg {v:.1f} mph derived)")
    print(f"  crossings  {crossings} @ {CAP_XING_LOW:g}/{CAP_XING_UT:g} $M "
          f"(LOW/US-TYPICAL)")
    print(f"  --- capital (never present the low number alone, spec 04 §3.2) ---")
    for band in BANDS:
        tot = capital(route_mi, stations, cars, band, crossings=crossings)
        print(f"  {band:<11} ${tot:8.1f}M   (${tot / km:6.2f}M/km)")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    a = sys.argv[1:]
    if len(a) < 3:
        print("usage: python capcost.py <route_mi> <stations> <headway_peak_min>"
              " [cars_per_train] [crossings]")
        sys.exit(1)
    _cli(float(a[0]), int(a[1]), float(a[2]),
         cars_per_train=int(a[3]) if len(a) > 3 else 2,
         crossings=int(a[4]) if len(a) > 4 else 0)
