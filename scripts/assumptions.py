"""
Assumptions registry (spec 08): the single source of truth for every asserted
quantity in the stage-2 pipeline. Code IMPORTS values from here -- this is the
repo's first data structure that model code reads values out of, so the
literals below are RULE-BEARING, not documentation.

Schema (one dict per assumption, keyed by a stable machine id):

    tier      prior | constant | config | structural | data
              A1 OWNS prior + constant (they carry a `value`); config/
              structural/data are NOT owned here (A2 harvests them, no value
              field -- they point at configs / name toggles / record vintages).
    status    active | superseded-kept-as-row | retired
    value     the exact Python literal the code imports (OWNED tiers only).
              LITERAL TYPING IS LOAD-BEARING: floats stay floats (70.0 not 70)
              because auto sensitivity-row labels derive from float repr; an
              int would silently change a results-file label. Priors store the
              (lo, hi, shape) 3-tuple plus an `order` int.
    band      (lo, hi) uncertainty band where one is meaningful; None for
              definitional values (a defined/chosen point with no propagated
              band -- unit conversions, clips, thresholds, grids, seeds). For
              priors band() derives (lo, hi) from the value tuple.
    basis     measured | locally-calibrated | literature | judgment |
              definitional
    history   append-only [(date, value, basis, ref)] transitions; current
              state is the last element; the basis census and what-changed
              appendix generate from this.
    provenance  prose source.
    rows      per-artifact sensitivity-row ids ({} until A2 fills them;
              priors carry the literal "auto" -- their lo/hi rows generate).
    no_row_reason / accepted / logged / upgrade  legibility bookkeeping;
              A2 fills accepted + rows and refines logged/upgrade.

The prior append-only guard is NOT a self-consistency assertion (a consistent
renumber passes any static check). It is a committed FINGERPRINT: the contract
test in test_bca_export.py pins the sha256 of the ordered prior-name tuple.
Updating that hash is the explicit, greppable act of appending a prior --
never reorder. build_priors() reproduces model.PRIORS sorted by `order`, and
draw_params consumes the rng in that order, so a reorder is also caught by the
byte-identical regression gate (the ultimate backstop).

Dependency-free: this module imports nothing from the pipeline (verified
acyclic -- model <- backtest_543 <- reweight_abc <- bca_export all import it,
it imports none of them).
"""

# ---------------------------------------------------------------------------
# ASSUMPTIONS -- pure literal. Do not compute values here; derived quantities
# (MU_LAUNCH, the street calibration, MI_LON) stay computed in their consumers
# from the leaves below.
# ---------------------------------------------------------------------------
ASSUMPTIONS = {

    # ===== prior tier (model.PRIORS; order 0..18 is load-bearing) ==========
    "bivt": {
        "title": "in-vehicle time coefficient",
        "tier": "prior", "status": "active",
        "value": (-0.035, -0.018, "tri"), "order": 0, "units": "util/min",
        "basis": "judgment",
        "history": [("2026-07-11", (-0.035, -0.018, "tri"), "judgment",
                     "spec08 A1 harvest -- introduced spec02")],
        "provenance": "peaked triangular IVT disutility range for local "
                      "transit mode choice (spec 02)",
        "rows": "auto", "no_row_reason": None, "accepted": None,
        "logged": None, "upgrade": "stated-preference survey / STOPS calibration",
    },
    "ovt": {
        "title": "out-of-vehicle time multiplier (wait & walk vs IVT)",
        "tier": "prior", "status": "active",
        "value": (1.6, 2.5, "tri"), "order": 1, "units": "ratio",
        "basis": "literature",
        "history": [("2026-07-11", (1.6, 2.5, "tri"), "literature",
                     "spec08 A1 harvest -- introduced spec02")],
        "provenance": "OVT weighted ~1.6-2.5x IVT (transit mode-choice "
                      "literature staple)",
        "rows": "auto", "no_row_reason": None, "accepted": None,
        "logged": None, "upgrade": "stated-preference survey",
    },
    "asc": {
        "title": "new-line alternative-specific constant (image/reliability)",
        "tier": "prior", "status": "active",
        "value": (0.0, 0.40, "tri"), "order": 2, "units": "util",
        "basis": "judgment",
        "history": [("2026-07-11", (0.0, 0.40, "tri"), "judgment",
                     "spec08 A1 harvest -- introduced spec02")],
        "provenance": "rail/BRT image-and-reliability premium, trimmed 0-0.40; "
                      "the ABC-calibrated posterior is reported separately "
                      "(README issue 14)",
        "rows": "auto",
        # prior EXTRA (spec 08 §2): the untrimmed asc=0.55 probe, beyond the
        # auto lo/hi edge rows -- per-artifact, present in both corridor results.
        "extras": {"harbor": ["asc_untrimmed"], "streetcar": ["asc_untrimmed"]},
        "no_row_reason": None, "accepted": None,
        "logged": "README known-issue 14", "upgrade": "ABC posterior / observed launch",
    },
    "w0": {
        "title": "scheduled-arrival platform wait intercept",
        "tier": "prior", "status": "active",
        "value": (4.0, 7.0, "uni"), "order": 3, "units": "min",
        "basis": "judgment",
        "history": [("2026-07-11", (4.0, 7.0, "uni"), "judgment",
                     "spec08 A1 harvest -- introduced spec02")],
        "provenance": "arrival-strategy closed-form wait intercept (spec 02)",
        "rows": "auto", "no_row_reason": None, "accepted": None,
        "logged": None, "upgrade": "AVL wait observations",
    },
    "lam": {
        "title": "schedule-delay slope",
        "tier": "prior", "status": "active",
        "value": (0.10, 0.25, "uni"), "order": 4, "units": "dimensionless",
        "basis": "judgment",
        "history": [("2026-07-11", (0.10, 0.25, "uni"), "judgment",
                     "spec08 A1 harvest -- introduced spec02")],
        "provenance": "arrival-strategy schedule-delay slope on headway (spec 02)",
        "rows": "auto", "no_row_reason": None, "accepted": None,
        "logged": None, "upgrade": "AVL wait observations",
    },
    "xcap": {
        "title": "transfer-wait cap",
        "tier": "prior", "status": "active",
        "value": (10.0, 15.0, "uni"), "order": 5, "units": "min",
        "basis": "judgment",
        "history": [("2026-07-11", (10.0, 15.0, "uni"), "judgment",
                     "spec08 A1 harvest -- introduced spec02")],
        "provenance": "cap on transfer wait (timed-connection assumption, spec 02)",
        "rows": "auto", "no_row_reason": None, "accepted": None,
        "logged": None, "upgrade": "observed transfer waits",
    },
    "tau": {
        "title": "transfer share of base boardings",
        "tier": "prior", "status": "active",
        "value": (0.25, 0.40, "uni"), "order": 6, "units": "share",
        "basis": "judgment",
        "history": [("2026-07-11", (0.25, 0.40, "uni"), "judgment",
                     "spec08 A1 harvest -- introduced spec02")],
        "provenance": "transfer-market pin as a share of base boardings (spec 02)",
        "rows": "auto", "no_row_reason": None, "accepted": None,
        "logged": None, "upgrade": "on-board survey transfer rates",
    },
    "phi": {
        "title": "visitor share of base boardings",
        "tier": "prior", "status": "active",
        "value": (0.05, 0.15, "uni"), "order": 7, "units": "share",
        "basis": "judgment",
        "history": [("2026-07-11", (0.05, 0.15, "uni"), "judgment",
                     "spec08 A1 harvest -- introduced spec02")],
        "provenance": "visitor-market pin as a share of base boardings (spec 02)",
        "rows": "auto", "no_row_reason": None, "accepted": None,
        "logged": None, "upgrade": "resort-market survey",
    },
    "s0v": {
        "title": "visitor base transit share",
        "tier": "prior", "status": "active",
        "value": (0.10, 0.30, "uni"), "order": 8, "units": "share",
        "basis": "judgment",
        "history": [("2026-07-11", (0.10, 0.30, "uni"), "judgment",
                     "spec08 A1 harvest -- introduced spec02")],
        "provenance": "visitor base transit mode share (spec 02)",
        "rows": "auto", "no_row_reason": None, "accepted": None,
        "logged": None, "upgrade": "resort-market survey",
    },
    "ws": {
        "title": "work share of boardings",
        "tier": "prior", "status": "active",
        "value": (0.40, 0.60, "uni"), "order": 9, "units": "share",
        "basis": "judgment",
        "history": [("2026-07-11", (0.40, 0.60, "uni"), "judgment",
                     "spec08 A1 harvest -- introduced spec02")],
        "provenance": "work vs non-work split for the ws/kappa expansion (spec 02)",
        "rows": "auto", "no_row_reason": None, "accepted": None,
        "logged": None, "upgrade": "NHTS / on-board trip-purpose split",
    },
    "kappa": {
        "title": "non-work responsiveness",
        "tier": "prior", "status": "active",
        "value": (0.60, 1.00, "uni"), "order": 10, "units": "dimensionless",
        "basis": "judgment",
        "history": [("2026-07-11", (0.60, 1.00, "uni"), "judgment",
                     "spec08 A1 harvest -- introduced spec02")],
        "provenance": "non-work responsiveness relative to work (spec 02)",
        "rows": "auto", "no_row_reason": None, "accepted": None,
        "logged": None, "upgrade": "NHTS elasticities",
    },
    "pkshare": {
        "title": "peak share of boardings (TOD blend)",
        "tier": "prior", "status": "active",
        "value": (0.45, 0.60, "uni"), "order": 11, "units": "share",
        "basis": "judgment",
        "history": [("2026-07-11", (0.45, 0.60, "uni"), "judgment",
                     "spec08 A1 harvest -- introduced spec02")],
        "provenance": "peak share for the time-of-day utility blend (spec 02)",
        "rows": "auto", "no_row_reason": None, "accepted": None,
        "logged": None, "upgrade": "APC time-of-day boardings",
    },
    "vot_behav": {
        "title": "behavioral value of time (fare response)",
        "tier": "prior", "status": "active",
        "value": (10.0, 22.0, "tri"), "order": 12, "units": "$/hr",
        "basis": "literature",
        "history": [("2026-07-11", (10.0, 22.0, "tri"), "literature",
                     "spec08 A1 harvest -- introduced spec06 D3")],
        "provenance": "behavioral VOT band for the fare-response utility term "
                      "(spec 06 D3); money is never monetized through it",
        "rows": "auto", "no_row_reason": None, "accepted": None,
        "logged": None, "upgrade": "local fare-elasticity study",
    },
    "pcar0": {
        "title": "car-diversion probability, 0-vehicle segment",
        "tier": "prior", "status": "active",
        "value": (0.05, 0.25, "uni"), "order": 13, "units": "prob",
        "basis": "judgment",
        "history": [("2026-07-11", (0.05, 0.25, "uni"), "judgment",
                     "spec08 A1 harvest -- introduced spec06 D7")],
        "provenance": "car-diversion probability priced by the BCA wrapper "
                      "(spec 06 D7); model code does not consume pcar*",
        "rows": "auto", "no_row_reason": None, "accepted": None,
        "logged": None, "upgrade": "diverted-mode survey / STOPS",
    },
    "pcar1": {
        "title": "car-diversion probability, 1-vehicle segment",
        "tier": "prior", "status": "active",
        "value": (0.35, 0.65, "uni"), "order": 14, "units": "prob",
        "basis": "judgment",
        "history": [("2026-07-11", (0.35, 0.65, "uni"), "judgment",
                     "spec08 A1 harvest -- introduced spec06 D7")],
        "provenance": "car-diversion probability priced by the BCA wrapper "
                      "(spec 06 D7); model code does not consume pcar*",
        "rows": "auto", "no_row_reason": None, "accepted": None,
        "logged": None, "upgrade": "diverted-mode survey / STOPS",
    },
    "pcar2": {
        "title": "car-diversion probability, 2+-vehicle segment",
        "tier": "prior", "status": "active",
        "value": (0.55, 0.85, "uni"), "order": 15, "units": "prob",
        "basis": "judgment",
        "history": [("2026-07-11", (0.55, 0.85, "uni"), "judgment",
                     "spec08 A1 harvest -- introduced spec06 D7")],
        "provenance": "car-diversion probability priced by the BCA wrapper "
                      "(spec 06 D7); model code does not consume pcar*",
        "rows": "auto", "no_row_reason": None, "accepted": None,
        "logged": None, "upgrade": "diverted-mode survey / STOPS",
    },
    "pcarv": {
        "title": "car-diversion probability, visitor market",
        "tier": "prior", "status": "active",
        "value": (0.00, 0.30, "uni"), "order": 16, "units": "prob",
        "basis": "judgment",
        "history": [("2026-07-11", (0.00, 0.30, "uni"), "judgment",
                     "spec08 A1 harvest -- introduced spec06 D7")],
        "provenance": "car-diversion probability priced by the BCA wrapper "
                      "(spec 06 D7); model code does not consume pcar*",
        "rows": "auto", "no_row_reason": None, "accepted": None,
        "logged": None, "upgrade": "diverted-mode survey / STOPS",
    },
    "v_cruise": {
        "title": "grade-separated cruise speed (ALM)",
        "tier": "prior", "status": "active",
        "value": (70.0, 90.0, "uni"), "order": 17, "units": "km/h",
        "basis": "literature",
        "history": [("2026-07-11", (70.0, 90.0, "uni"), "literature",
                     "spec08 A1 harvest -- introduced spec02 s4.9 R6, 23c6cca")],
        "provenance": "REM-class automated-light-metro cruise speed; derived "
                      "average speed (spec 02 s4.9 R6)",
        "rows": "auto", "no_row_reason": None, "accepted": None,
        "logged": None, "upgrade": "vehicle procurement spec / observed REM telemetry",
    },
    "dwell": {
        "title": "station dwell (ALM)",
        "tier": "prior", "status": "active",
        "value": (20.0, 30.0, "uni"), "order": 18, "units": "s",
        "basis": "literature",
        "history": [("2026-07-11", (20.0, 30.0, "uni"), "literature",
                     "spec08 A1 harvest -- introduced spec02 s4.9 R6, 23c6cca")],
        "provenance": "REM-class automated-light-metro station dwell; derived "
                      "average speed (spec 02 s4.9 R6)",
        "rows": "auto", "no_row_reason": None, "accepted": None,
        "logged": None, "upgrade": "vehicle procurement spec / observed REM telemetry",
    },

    # ===== constant tier (module constants; code imports, names kept) =======

    # ---- model.py --------------------------------------------------------
    "n": {
        "title": "Monte-Carlo draw count",
        "tier": "constant", "status": "active",
        "value": 40000, "units": "draws", "band": None, "basis": "definitional",
        "history": [("2026-07-11", 40000, "definitional",
                     "spec08 A1 harvest -- introduced spec02")],
        "provenance": "headline/BCA draw count; ESS and percentile-stability knob",
        "rows": {}, "no_row_reason": "quality-knob",
        "accepted": ("owner-directive 2026-07-11", "2026-07-11"),
        "logged": None, "upgrade": "convergence study",
    },
    "walk_mph": {
        "title": "pedestrian walk speed",
        "tier": "constant", "status": "active",
        "value": 3.0, "units": "mph", "band": (2.5, 3.5), "basis": "literature",
        "history": [("2026-07-11", 3.0, "literature",
                     "spec08 A1 harvest -- introduced spec02")],
        "provenance": "standard pedestrian speed ~3 mph (~1.4 m/s); spec 08 "
                      "s7 {2.5, 3.5} point rows generated from this band (A2)",
        "rows": {"harbor": ["walk_mph_lo", "walk_mph_hi"],
                 "streetcar": ["walk_mph_lo", "walk_mph_hi"]},
        "no_row_reason": None, "accepted": None,
        "logged": None, "upgrade": "observed access speeds",
    },
    "subk": {
        "title": "within-cell rider-position quadrature nodes",
        "tier": "constant", "status": "active",
        "value": 8, "units": "nodes", "band": None, "basis": "definitional",
        "history": [("2026-07-11", 8, "definitional",
                     "spec08 A1 harvest -- introduced spec03")],
        "provenance": "8 is exact for 0.25/0.5/1.0-mi stop grids (spec 03)",
        "rows": {}, "no_row_reason": "definitional",
        "accepted": ("owner-directive 2026-07-11", "2026-07-11"),
        "logged": None, "upgrade": None,
    },
    "default_fare": {
        "title": "OCTA flat cash fare (reference base)",
        "tier": "constant", "status": "active",
        "value": 2.00, "units": "$", "band": None, "basis": "definitional",
        "history": [("2026-07-11", 2.00, "definitional",
                     "spec08 A1 harvest -- introduced spec06 D3")],
        "provenance": "OCTA flat cash fare, reference base (spec 06 D3); every "
                      "fare term is 0 at flat fares; override via cfg['fare_base']",
        "rows": {}, "no_row_reason": "definitional",
        "accepted": ("owner-directive 2026-07-11", "2026-07-11"),
        "logged": None, "upgrade": "OCTA fare schedule change",
    },
    "a_comfort": {
        "title": "REM-class comfortable acceleration (= deceleration)",
        "tier": "constant", "status": "active",
        "value": 1.0, "units": "m/s^2", "band": (1.0, 1.3), "basis": "literature",
        "history": [("2026-07-11", 1.0, "literature",
                     "spec08 A1 harvest -- introduced spec02 s4.9 R6, 23c6cca")],
        "provenance": "REM-class comfortable accel; sets the per-stop time lost "
                      "vs cruising, grade-separated only (spec 02 s4.9). Band "
                      "1.0 comfortable .. 1.3 performance (the a_comfort_hi probe); "
                      "the comfort value 1.0 is the operative central. Band added "
                      "in A2 harvest (A1 left it None) so the row is check-legible",
        "rows": {"harbor": ["a_comfort_hi"]}, "no_row_reason": None,
        "accepted": None,
        "logged": None, "upgrade": "vehicle procurement spec",
    },
    "j_comfort": {
        "title": "service jerk limit (grade-separated kinematics)",
        "tier": "constant", "status": "active",
        "value": 0.75, "units": "m/s^3", "band": (0.5, 1.0), "basis": "literature",
        "history": [("2026-07-11", 0.75, "literature",
                     "spec08 A1 harvest -- introduced spec02 s4.9b, 5e63eb2")],
        "provenance": "EN 13452-family passenger comfort band 0.5-1.0; "
                      "REM-class service (spec 02 s4.9b). Band edges jk_lo/jk_hi "
                      "plus the jk_trapezoid (j->inf) R6 regression row are the "
                      "harbor grade-separated derived-speed rows",
        "rows": {"harbor": ["jk_lo", "jk_hi", "jk_trapezoid"]},
        "no_row_reason": None, "accepted": None,
        "logged": "README known-issue 25 addendum",
        "upgrade": "vehicle procurement spec / observed REM telemetry",
    },
    "kmh_per_mph": {
        "title": "miles-to-kilometers conversion",
        "tier": "constant", "status": "active",
        "value": 1.609344, "units": "km/mi", "band": None, "basis": "definitional",
        "history": [("2026-07-11", 1.609344, "definitional",
                     "spec08 A1 harvest -- introduced spec02 s4.9 R6, 23c6cca")],
        "provenance": "exact international mile definition (1 mi = 1.609344 km)",
        "rows": {}, "no_row_reason": "definitional",
        "accepted": ("owner-directive 2026-07-11", "2026-07-11"),
        "logged": None, "upgrade": None,
    },
    "street_cal_local": {
        "title": "street calibration point -- Route 43 local (avg speed, spacing)",
        "tier": "constant", "status": "active",
        "value": (11.4, 0.25), "units": "(mph, mi)", "band": None,
        "basis": "measured",
        "history": [("2026-07-11", (11.4, 0.25), "measured",
                     "spec08 A1 harvest -- introduced spec02 s4.9 R6, 23c6cca")],
        "provenance": "measured OCTA Route 43 local avg speed at 0.25-mi stop "
                      "spacing (this repo's GTFS/anchor provenance); one of two "
                      "points identifying the street-variant speed curve",
        "rows": {}, "no_row_reason": None, "accepted": None,
        "logged": None, "upgrade": "APC/GTFS speed re-measure",
    },
    "street_cal_rapid": {
        "title": "street calibration point -- Route 543 rapid (avg speed, spacing)",
        "tier": "constant", "status": "active",
        "value": (12.8, 1.0), "units": "(mph, mi)", "band": None,
        "basis": "measured",
        "history": [("2026-07-11", (12.8, 1.0), "measured",
                     "spec08 A1 harvest -- introduced spec02 s4.9 R6, 23c6cca")],
        "provenance": "measured OCTA Route 543 rapid avg speed at 1.0-mi stop "
                      "spacing (this repo's GTFS/anchor provenance); one of two "
                      "points identifying the street-variant speed curve",
        "rows": {}, "no_row_reason": None, "accepted": None,
        "logged": None, "upgrade": "APC/GTFS speed re-measure",
    },
    "tsp_speedup": {
        "title": "TSP corridor speed-up (informational, no consumer)",
        "tier": "constant", "status": "active",
        "value": 0.075, "units": "fraction", "band": (0.07, 0.08),
        "basis": "literature",
        "history": [("2026-07-11", 0.075, "literature",
                     "spec08 A1 harvest -- introduced spec02 s4.9 R6, 23c6cca")],
        "provenance": "2024 OCTA TSP study ~7-8% corridor speed-up; "
                      "informational only, no consumer yet (spec 08 s7) -- a row "
                      "is impossible until TSP is wired into the street speed",
        "rows": {}, "no_row_reason": "spec-pending:02§4.9",
        "accepted": ("owner-directive 2026-07-11", "2026-07-11"),
        "logged": None, "upgrade": "held-out TSP experiment",
    },
    "dv_clip": {
        "title": "utility-difference clip (overflow guard)",
        "tier": "constant", "status": "active",
        "value": 20, "units": "utils", "band": None, "basis": "definitional",
        "history": [("2026-07-11", 20, "definitional",
                     "spec08 A1 harvest -- introduced spec02")],
        "provenance": "symmetric +/-20 clamp on dv before exp() -- numerical "
                      "overflow guard, not a behavioral bound; verified NOT to "
                      "bind at central (max|dv| << 20), so a point row is 0.0%",
        "rows": {}, "no_row_reason": "definitional",
        "accepted": ("owner-directive 2026-07-11", "2026-07-11"),
        "logged": None, "upgrade": None,
    },
    "tie_epsilon": {
        "title": "best-service tie-break epsilon",
        "tier": "constant", "status": "active",
        "value": 1e-12, "units": "utils", "band": None, "basis": "definitional",
        "history": [("2026-07-11", 1e-12, "definitional",
                     "spec08 A1 harvest -- introduced spec02")],
        "provenance": "tolerance for the best-service indicator (near-perfect "
                      "substitutes tie at the util level)",
        "rows": {}, "no_row_reason": "definitional",
        "accepted": ("owner-directive 2026-07-11", "2026-07-11"),
        "logged": None, "upgrade": None,
    },
    "sens_n": {
        "title": "one-at-a-time / point sensitivity draw count",
        "tier": "constant", "status": "active",
        "value": 4000, "units": "draws", "band": None, "basis": "definitional",
        "history": [("2026-07-11", 4000, "definitional",
                     "spec08 A2 harvest -- introduced spec02")],
        "provenance": "MC draw count for the point()/sens() rows and the design "
                      "sweep (model.py) -- a percentile-stability quality knob, "
                      "smaller than the N=40,000 headline; backtest_543.py keeps "
                      "a parallel literal 4,000 to unify in A2b",
        "rows": {}, "no_row_reason": "quality-knob",
        "accepted": ("owner-directive 2026-07-11", "2026-07-11"),
        "logged": None, "upgrade": None,
    },
    "visitor_alpha_floor": {
        "title": "visitor-Dirichlet alpha floor",
        "tier": "constant", "status": "active",
        "value": 1e-3, "units": "alpha", "band": None, "basis": "definitional",
        "history": [("2026-07-11", 1e-3, "definitional",
                     "spec08 A2 harvest -- introduced spec02")],
        "provenance": "floor on the visitor bin-weight Dirichlet concentration "
                      "(np.maximum(vw_base, 1e-3)*100) -- guards zero-weight "
                      "bins from a degenerate alpha=0 (spec 08 s7)",
        "rows": {}, "no_row_reason": "definitional",
        "accepted": ("owner-directive 2026-07-11", "2026-07-11"),
        "logged": None, "upgrade": None,
    },
    "s0_pivot_clip": {
        "title": "S0 base-share pivot clips (numerical floor, max-share ceiling)",
        "tier": "constant", "status": "active",
        "value": (1e-6, 0.95), "units": "share", "band": None, "basis": "judgment",
        "history": [("2026-07-11", (1e-6, 0.95), "judgment",
                     "spec08 A2 harvest -- introduced spec02")],
        "provenance": "np.clip on S0 before the pivot: 1e-6 numerical floor and "
                      "0.95 max-share ceiling (a real max-share assumption, spec "
                      "08 s7). Neither binds at central (max base transit share "
                      "<< 0.95, s0v<=0.30), so a point row would be vacuously "
                      "0.0% -- rowless, not counterfactual",
        "rows": {}, "no_row_reason": "definitional",
        "accepted": ("owner-directive 2026-07-11", "2026-07-11"),
        "logged": None, "upgrade": None,
    },
    "subcell_merge_decimals": {
        "title": "sub-cell walk-column merge epsilon (round decimals)",
        "tier": "constant", "status": "active",
        "value": 9, "units": "decimals", "band": None, "basis": "definitional",
        "history": [("2026-07-11", 9, "definitional",
                     "spec08 A2 harvest -- introduced spec03")],
        "provenance": "np.round(W, 9) before np.unique merges identical joint "
                      "walk columns (aligned stop grids collapse K^2 -> ~7); a "
                      "float-dedup tolerance, not a behavioral knob (spec 08 s7)",
        "rows": {}, "no_row_reason": "definitional",
        "accepted": ("owner-directive 2026-07-11", "2026-07-11"),
        "logged": None, "upgrade": None,
    },
    "walk_spread_grid": {
        "title": "walk-taste spread grid (+/-15% axis and its weights)",
        "tier": "constant", "status": "active",
        "value": ((0.85, 1.0, 1.15), (0.25, 0.5, 0.25)),
        "units": "(taste multiplier, weight)", "band": None, "basis": "judgment",
        "history": [("2026-07-11", ((0.85, 1.0, 1.15), (0.25, 0.5, 0.25)),
                     "judgment", "spec08 A2 harvest -- introduced spec02")],
        "provenance": "the +/-15% walk-taste quadrature (0.85/1.0/1.15 at "
                      "0.25/0.5/0.25) applied only when the walk_spread toggle is "
                      "on; the grid's whole effect IS the walk_spread row",
        "rows": {}, "no_row_reason": "covered-elsewhere:walk_spread",
        "accepted": ("owner-directive 2026-07-11", "2026-07-11"),
        "logged": None, "upgrade": None,
    },
    "nonwork_tilt_l": {
        "title": "non-work shorter-trip exponential-tilt scale",
        "tier": "constant", "status": "active",
        "value": 4.0, "units": "mi", "band": None, "basis": "judgment",
        "history": [("2026-07-11", 4.0, "judgment",
                     "spec08 A2 harvest -- introduced spec02")],
        "provenance": "decay length of the exp(-d/L) short-trip tilt applied to "
                      "the non-work market when the nonwork_short toggle is on; "
                      "the tilt's whole effect IS the nonwork_short row",
        "rows": {}, "no_row_reason": "covered-elsewhere:nonwork_short",
        "accepted": ("owner-directive 2026-07-11", "2026-07-11"),
        "logged": None, "upgrade": None,
    },

    # ---- reweight_abc.py -------------------------------------------------
    "upt_fy2013_mb": {
        "title": "OCTA annual bus UPT, motorbus, FY2013 (NTD 90036)",
        "tier": "constant", "status": "active",
        "value": 51_067_292, "units": "unlinked trips/yr", "band": None,
        "basis": "measured",
        "history": [("2026-07-11", 51_067_292, "measured",
                     "spec08 A1 harvest -- introduced spec02 s4.6 (R1), 0e710db")],
        "provenance": "NTD ID 90036 annual bus UPT (MB, DO+PT), FY2013; "
                      "dual-source verified (Socrata 8bui-9xvu + TS2.1 2018 "
                      "Excel); the central back-trend numerator",
        "rows": {}, "no_row_reason": None, "accepted": None,
        "logged": None, "upgrade": "NTD annual refresh",
    },
    "upt_fy2014_mb": {
        "title": "OCTA annual bus UPT, motorbus, FY2014 (NTD 90036)",
        "tier": "constant", "status": "active",
        "value": 48_561_206, "units": "unlinked trips/yr", "band": None,
        "basis": "measured",
        "history": [("2026-07-11", 48_561_206, "measured",
                     "spec08 A1 harvest -- introduced spec02 s4.6 (R1), 0e710db")],
        "provenance": "NTD ID 90036 annual bus UPT (MB, DO+PT), FY2014; the "
                      "FY2014-vintage back-trend numerator (543_launch14 row)",
        "rows": {}, "no_row_reason": None, "accepted": None,
        "logged": None, "upgrade": "NTD annual refresh",
    },
    "upt_fy2017_mb": {
        "title": "OCTA annual bus UPT, motorbus, FY2017 (NTD 90036)",
        "tier": "constant", "status": "active",
        "value": 39_686_125, "units": "unlinked trips/yr", "band": None,
        "basis": "measured",
        "history": [("2026-07-11", 39_686_125, "measured",
                     "spec08 A1 harvest -- introduced spec02 s4.6 (R1), 0e710db")],
        "provenance": "NTD ID 90036 annual bus UPT (MB, DO+PT), FY2017; the "
                      "back-trend denominator (matches the FY2017 543 vintage)",
        "rows": {}, "no_row_reason": None, "accepted": None,
        "logged": None, "upgrade": "NTD annual refresh",
    },
    "obs_543_fy2017": {
        "title": "measured 543 weekday boardings, FY2017 (launch-eq target base)",
        "tier": "constant", "status": "active",
        "value": 4615.0, "units": "wd boardings", "band": None,
        "basis": "measured",
        "history": [("2026-07-11", 4615.0, "measured",
                     "spec08 A1 harvest -- introduced spec02 s4.6 (R1), 0e710db")],
        "provenance": "earliest measured 543 weekday boardings, FY2017 "
                      "(anchor_from_apc.py); scaled by the NTD back-trend to "
                      "the launch-equivalent target MU_LAUNCH (spec 02 s4.6)",
        "rows": {}, "no_row_reason": None, "accepted": None,
        "logged": None, "upgrade": "APC records request",
    },
    "mu_matured": {
        "title": "543 matured six-year-average target (superseded, kept as row)",
        "tier": "constant", "status": "superseded-kept-as-row",
        "value": 4200.0, "units": "wd boardings", "band": None,
        "basis": "measured",
        "history": [("2026-07-11", 4200.0, "measured",
                     "spec08 A1 harvest -- introduced spec02 s4.6 (R1), 0e710db")],
        "provenance": "old six-year-average 543 target; superseded by the "
                      "launch-equivalent retarget but retained as the "
                      "543_matured_s500 sensitivity kernel (spec 02 s4.6)",
        "rows": {}, "no_row_reason": None, "accepted": None,
        "logged": "README known-issue 15", "upgrade": "APC records request",
    },
    "abc_sigma": {
        "title": "ABC Gaussian kernel sigma (central + width sensitivities)",
        "tier": "constant", "status": "active",
        "value": 500.0, "units": "wd boardings", "band": (350.0, 800.0),
        "basis": "judgment",
        "history": [("2026-07-11", 500.0, "judgment",
                     "spec08 A1 harvest -- introduced spec02 s4.6 (R1), 0e710db")],
        "provenance": "central 500 retains the ~400 structural-error floor "
                      "(post-COVID 2022 LODES shape, 2023 ACS proxying 2013, "
                      "unknown 2013 peak headway) plus back-trend vintage "
                      "spread; 350/800 are the width sensitivities",
        "rows": {}, "no_row_reason": None, "accepted": None,
        "logged": None, "upgrade": "STOPS calibration / observed launch",
    },
    "seed": {
        "title": "pipeline RNG seed",
        "tier": "constant", "status": "active",
        "value": 42, "units": None, "band": None, "basis": "definitional",
        "history": [("2026-07-11", 42, "definitional",
                     "spec08 A1 harvest -- introduced spec02")],
        "provenance": "common-random-numbers seed across backtest/forward runs; "
                      "seed+1 is the seed-robustness drift check",
        "rows": {}, "no_row_reason": "definitional",
        "accepted": ("owner-directive 2026-07-11", "2026-07-11"),
        "logged": None, "upgrade": None,
    },
    "ess_min": {
        "title": "effective-sample-size floor (ABC kernel-too-tight warning)",
        "tier": "constant", "status": "active",
        "value": 1000, "units": "draws", "band": None, "basis": "definitional",
        "history": [("2026-07-11", 1000, "definitional",
                     "spec08 A1 harvest -- introduced spec02 s4.6 (R1), 0e710db")],
        "provenance": "conventional ESS rule-of-thumb; below it the kernel is "
                      "too tight -- widen sigma, never filter (spec 08 s7)",
        "rows": {}, "no_row_reason": "quality-knob",
        "accepted": ("owner-directive 2026-07-11", "2026-07-11"),
        "logged": None, "upgrade": None,
    },

    # ---- backtest_543.py -------------------------------------------------
    "obs_543": {
        "title": "measured 543 weekday-boarding display range (FY2019..FY2017)",
        "tier": "constant", "status": "active",
        "value": (3700, 4600), "units": "wd boardings", "band": None,
        "basis": "measured",
        "history": [("2026-07-11", (3700, 4600), "measured",
                     "spec08 A1 harvest -- introduced spec02")],
        "provenance": "measured 543 weekday boardings, FY2019 low .. FY2017 "
                      "high (anchor_from_apc.py); the observed-outcome display "
                      "range printed and exported beside the backtest prediction",
        "rows": {}, "no_row_reason": None, "accepted": None,
        "logged": None, "upgrade": "APC records request",
    },

    # ---- bca_export.py ---------------------------------------------------
    "eq_days": {
        "title": "weekday-to-annual equivalent service days",
        "tier": "constant", "status": "active",
        "value": [300, 330], "units": "days/yr", "band": None,
        "basis": "judgment",
        "history": [("2026-07-11", [300, 330], "judgment",
                     "spec08 A1 harvest -- introduced spec06")],
        "provenance": "weekday->annual conversion band (anchor_from_apc "
                      "convention); low 300, high 330 equivalent service days",
        "rows": {}, "no_row_reason": None, "accepted": None,
        "logged": None, "upgrade": "OCTA service-calendar day counts",
    },

    # ---- build_corridor.py ----------------------------------------------
    "buffer_mi": {
        "title": "corridor tract inclusion buffer",
        "tier": "constant", "status": "active",
        "value": 0.9, "units": "mi", "band": None, "basis": "definitional",
        "history": [("2026-07-11", 0.9, "definitional",
                     "spec08 A1 harvest -- introduced spec01/spec02")],
        "provenance": "centroid-within distance for corridor tract membership",
        "rows": {}, "no_row_reason": None, "accepted": None,
        "logged": None, "upgrade": None,
    },
    "xfer_buffer_mi": {
        "title": "transfer feeder-access buffer",
        "tier": "constant", "status": "active",
        "value": 0.9, "units": "mi", "band": None, "basis": "definitional",
        "history": [("2026-07-11", 0.9, "definitional",
                     "spec08 A1 harvest -- introduced spec01/spec02")],
        "provenance": "outside-tract to feeder-crossing access distance for "
                      "the transfer market",
        "rows": {}, "no_row_reason": None, "accepted": None,
        "logged": None, "upgrade": None,
    },
    "cross_near": {
        "title": "feeder crossing near-threshold",
        "tier": "constant", "status": "active",
        "value": 0.25, "units": "mi", "band": None, "basis": "definitional",
        "history": [("2026-07-11", 0.25, "definitional",
                     "spec08 A1 harvest -- introduced spec01/spec02")],
        "provenance": "|offset| below which a feeder is 'on' the corridor line "
                      "(crossing test)",
        "rows": {}, "no_row_reason": None, "accepted": None,
        "logged": None, "upgrade": None,
    },
    "cross_far": {
        "title": "feeder crossing far-threshold",
        "tier": "constant", "status": "active",
        "value": 1.0, "units": "mi", "band": None, "basis": "definitional",
        "history": [("2026-07-11", 1.0, "definitional",
                     "spec08 A1 harvest -- introduced spec01/spec02")],
        "provenance": "|offset| beyond which a feeder must reach on both sides "
                      "(genuine-crossing test)",
        "rows": {}, "no_row_reason": None, "accepted": None,
        "logged": None, "upgrade": None,
    },
    "bin_edges": {
        "title": "distance-bin edges (walk & transfer markets)",
        "tier": "constant", "status": "active",
        "value": [0.0, 0.5, 2.5, 4.75, 7.5, 10.25, 12.6], "units": "mi",
        "band": None, "basis": "judgment",
        "history": [("2026-07-11", [0.0, 0.5, 2.5, 4.75, 7.5, 10.25, 12.6],
                     "judgment", "spec08 A1 harvest -- introduced spec02")],
        "provenance": "on-line distance-bin partition; first bin 0-0.5 mi "
                      "carries the intra-tract flows",
        "rows": {}, "no_row_reason": None, "accepted": None,
        "logged": None, "upgrade": None,
    },
    "intra_clip": {
        "title": "intra-tract imputed-distance clip bounds",
        "tier": "constant", "status": "active",
        "value": (0.10, 0.45), "units": "mi", "band": None,
        "basis": "definitional",
        "history": [("2026-07-11", (0.10, 0.45), "definitional",
                     "spec08 A1 harvest -- introduced spec02")],
        "provenance": "clamp on the sqrt(ALAND)/3 imputed along-line distance "
                      "for intra-tract walk flows",
        "rows": {}, "no_row_reason": None, "accepted": None,
        "logged": None, "upgrade": None,
    },
    "intra_divisor": {
        "title": "intra-tract E|dx| divisor",
        "tier": "constant", "status": "active",
        "value": 3.0, "units": "dimensionless", "band": None,
        "basis": "definitional",
        "history": [("2026-07-11", 3.0, "definitional",
                     "spec08 A1 harvest -- introduced spec02")],
        "provenance": "E|dx| of two uniform points on [0, L] is L/3; the 1-D "
                      "projection factor for intra-tract flow distance",
        "rows": {}, "no_row_reason": None, "accepted": None,
        "logged": None, "upgrade": None,
    },
    "moe_z": {
        "title": "ACS 90% MOE-to-SE conversion",
        "tier": "constant", "status": "active",
        "value": 1.645, "units": "dimensionless", "band": None,
        "basis": "definitional",
        "history": [("2026-07-11", 1.645, "definitional",
                     "spec08 A1 harvest -- introduced spec02")],
        "provenance": "Census publishes 90% margins of error; SE = MOE / 1.645 "
                      "(documented conversion, spec 08 s4 -- reclassified "
                      "definitional, no counterfactual row)",
        "rows": {}, "no_row_reason": None, "accepted": None,
        "logged": None, "upgrade": None,
    },
    "se_cap": {
        "title": "relative-SE cap on base transit shares",
        "tier": "constant", "status": "active",
        "value": 0.5, "units": "relative", "band": None, "basis": "definitional",
        "history": [("2026-07-11", 0.5, "definitional",
                     "spec08 A1 harvest -- introduced spec02")],
        "provenance": "clamp on the delta-method relative SE of S0 shares "
                      "(guards degenerate small-cell ACS estimates)",
        "rows": {}, "no_row_reason": None, "accepted": None,
        "logged": None, "upgrade": None,
    },
    "feeder_downsample": {
        "title": "feeder polyline downsample step target",
        "tier": "constant", "status": "active",
        "value": 250, "units": "vertices", "band": None, "basis": "definitional",
        "history": [("2026-07-11", 250, "definitional",
                     "spec08 A1 harvest -- introduced spec02")],
        "provenance": "max vertices sampled per feeder shape for the crossing "
                      "test (compute knob)",
        "rows": {}, "no_row_reason": None, "accepted": None,
        "logged": None, "upgrade": None,
    },
    "min_feeder_mi": {
        "title": "minimum feeder shape length",
        "tier": "constant", "status": "active",
        "value": 1.0, "units": "mi", "band": None, "basis": "definitional",
        "history": [("2026-07-11", 1.0, "definitional",
                     "spec08 A1 harvest -- introduced spec02")],
        "provenance": "feeders shorter than this are ignored as crossing "
                      "candidates",
        "rows": {}, "no_row_reason": None, "accepted": None,
        "logged": None, "upgrade": None,
    },
    "mi_lat": {
        "title": "miles per degree latitude (flat-earth projection)",
        "tier": "constant", "status": "active",
        "value": 69.05, "units": "mi/deg", "band": None, "basis": "definitional",
        "history": [("2026-07-11", 69.05, "definitional",
                     "spec08 A1 harvest -- introduced spec02")],
        "provenance": "flat-earth projection constant (miles per degree "
                      "latitude at OC's latitude)",
        "rows": {}, "no_row_reason": None, "accepted": None,
        "logged": None, "upgrade": None,
    },
    "mi_per_deg_lon": {
        "title": "miles per degree longitude at the equator",
        "tier": "constant", "status": "active",
        "value": 69.17, "units": "mi/deg", "band": None, "basis": "definitional",
        "history": [("2026-07-11", 69.17, "definitional",
                     "spec08 A1 harvest -- introduced spec02")],
        "provenance": "flat-earth projection base; scaled by cos(oc_ref_lat) "
                      "to give MI_LON",
        "rows": {}, "no_row_reason": None, "accepted": None,
        "logged": None, "upgrade": None,
    },
    "oc_ref_lat": {
        "title": "Orange County reference latitude",
        "tier": "constant", "status": "active",
        "value": 33.77, "units": "deg", "band": None, "basis": "definitional",
        "history": [("2026-07-11", 33.77, "definitional",
                     "spec08 A1 harvest -- introduced spec02")],
        "provenance": "reference latitude for the flat-earth longitude scale "
                      "(the cos factor in MI_LON)",
        "rows": {}, "no_row_reason": None, "accepted": None,
        "logged": None, "upgrade": None,
    },

    # ===== structural tier (governance toggles; NOT owned) ==================
    # Each names a run() over-key toggle and the sensitivity row-id it produces
    # in BOTH corridor results (spec 08 §2/§3). No value/band -- structural
    # entries satisfy materiality (§5 check 5) because every enumerated
    # alternative code path has a row. Introduced pre-08; harvested in A2.
    "variety_logsum": {
        "title": "variety-logsum choice toggle (red-bus/blue-bus correction)",
        "tier": "structural", "status": "active", "basis": "judgment",
        "history": [("2026-07-11", "variety_logsum", "judgment",
                     "spec08 A2 harvest -- introduced spec02")],
        "provenance": "OFF (headline): near-perfect substitutes on one street "
                      "earn no logsum variety bonus (best-service choice). ON: a "
                      "theta=1 logsum -- the rejected alternative, kept as a row",
        "rows": {"harbor": ["variety_logsum"], "streetcar": ["variety_logsum"]},
        "no_row_reason": None, "accepted": None,
        "logged": None, "upgrade": None,
    },
    "linear_wait": {
        "title": "linear-wait toggle (h/2 vs arrival-strategy closed form)",
        "tier": "structural", "status": "active", "basis": "judgment",
        "history": [("2026-07-11", "linear_wait", "judgment",
                     "spec08 A2 harvest -- introduced spec02")],
        "provenance": "OFF (headline): walk-access wait = min(h/2, w0 + lam*h). "
                      "ON: the old plain h/2 wait -- retained as a row",
        "rows": {"harbor": ["linear_wait"], "streetcar": ["linear_wait"]},
        "no_row_reason": None, "accepted": None,
        "logged": None, "upgrade": None,
    },
    "smooth_k": {
        "title": "sub-cell quadrature toggle (knife-edge vs K-node smoothing)",
        "tier": "structural", "status": "active", "basis": "judgment",
        "history": [("2026-07-11", "smooth_k", "judgment",
                     "spec08 A2 harvest -- introduced spec03")],
        "provenance": "smooth_k=0 restores the old knife-edge point walk "
                      "(spacing/4); the headline uses the SUBK-node within-cell "
                      "quadrature. The knife-edge extreme is the smooth_k row",
        "rows": {"harbor": ["smooth_k"], "streetcar": ["smooth_k"]},
        "no_row_reason": None, "accepted": None,
        "logged": None, "upgrade": None,
    },
    "no_transfer": {
        "title": "transfer-market toggle",
        "tier": "structural", "status": "active", "basis": "judgment",
        "history": [("2026-07-11", "no_transfer", "judgment",
                     "spec08 A2 harvest -- introduced spec02")],
        "provenance": "ON drops the transfer market (fx=0) -- bounds the "
                      "transfer market's contribution to the headline",
        "rows": {"harbor": ["no_transfer"], "streetcar": ["no_transfer"]},
        "no_row_reason": None, "accepted": None,
        "logged": None, "upgrade": None,
    },
    "no_visitor": {
        "title": "visitor-market toggle",
        "tier": "structural", "status": "active", "basis": "judgment",
        "history": [("2026-07-11", "no_visitor", "judgment",
                     "spec08 A2 harvest -- introduced spec02")],
        "provenance": "ON drops the visitor market (fv=0) -- bounds the "
                      "resort/visitor market's contribution to the headline",
        "rows": {"harbor": ["no_visitor"], "streetcar": ["no_visitor"]},
        "no_row_reason": None, "accepted": None,
        "logged": None, "upgrade": None,
    },
    "no_bin0": {
        "title": "sub-half-mile bin toggle (old market definition)",
        "tier": "structural", "status": "active", "basis": "judgment",
        "history": [("2026-07-11", "no_bin0", "judgment",
                     "spec08 A2 harvest -- introduced spec02")],
        "provenance": "ON drops the 0-0.5-mi intra-tract bin and renormalizes "
                      "-- the pre-intra-tract market definition, kept as a row",
        "rows": {"harbor": ["no_bin0"], "streetcar": ["no_bin0"]},
        "no_row_reason": None, "accepted": None,
        "logged": None, "upgrade": None,
    },
    "nonwork_short": {
        "title": "non-work shorter-trip tilt toggle",
        "tier": "structural", "status": "active", "basis": "judgment",
        "history": [("2026-07-11", "nonwork_short", "judgment",
                     "spec08 A2 harvest -- introduced spec02")],
        "provenance": "ON tilts the non-work O-D toward shorter trips (exp decay "
                      "L=nonwork_tilt_l); probes the commute-only-LODES proxy for "
                      "the non-work market",
        "rows": {"harbor": ["nonwork_short"], "streetcar": ["nonwork_short"]},
        "no_row_reason": None, "accepted": None,
        "logged": None, "upgrade": None,
    },
    "exogenous_speed": {
        "title": "exogenous-speed governance toggle (spec 02 §4.9)",
        "tier": "structural", "status": "active", "basis": "judgment",
        "history": [("2026-07-11", "exogenous_speed", "judgment",
                     "spec08 A2 harvest -- introduced spec02 s4.9 R6")],
        "provenance": "ON restores the old config scalar-speed path (the "
                      "exogenous fallback), bypassing the derived_speed block; "
                      "no-op for exogenous corridors (streetcar row = 0.0%)",
        "rows": {"harbor": ["exogenous_speed"], "streetcar": ["exogenous_speed"]},
        "no_row_reason": None, "accepted": None,
        "logged": None, "upgrade": None,
    },
    "walk_spread": {
        "title": "walk-taste spread toggle (+/-15% axis)",
        "tier": "structural", "status": "active", "basis": "judgment",
        "history": [("2026-07-11", "walk_spread", "judgment",
                     "spec08 A2 harvest -- introduced spec02")],
        "provenance": "ON adds the walk_spread_grid +/-15% walk-taste "
                      "quadrature; this toggle's row IS where the walk_spread_grid "
                      "constant is exercised (covered-elsewhere target)",
        "rows": {"harbor": ["walk_spread"], "streetcar": ["walk_spread"]},
        "no_row_reason": None, "accepted": None,
        "logged": None, "upgrade": None,
    },

    # ===== config tier (corridor-owned; entry points at a config key) =======
    # NOT owned here -- the entry names a structured config key and claims the
    # per-artifact rows those config values drive. Harbor and streetcar anchors
    # are SEPARATE entries (spec 08 §3: "anchor -> low" means DIFFERENT
    # assumptions per corridor). The anchor_derivation structured-key promotion
    # (trend / corr_share) and full pointer resolution are A2b.
    "harbor_anchor": {
        "title": "Harbor corridor anchor band (weekday boardings)",
        "tier": "config", "status": "active", "basis": "measured",
        "config_key": "config/harbor.json: anchor_low / anchor_high",
        "history": [("2026-07-11", (7650, 9650), "measured",
                     "spec08 A2 harvest -- config anchor_low/high")],
        "provenance": "543 + 43 FY2019 route totals x FY2019->FY2024 trend x "
                      "corridor share (anchor_from_apc.py / route43_share.py); "
                      "the anchor_lo/anchor_hi sensitivity rows sweep the band",
        "rows": {"harbor": ["anchor_lo", "anchor_hi"]},
        "no_row_reason": None, "accepted": None,
        "logged": None, "upgrade": "APC records request",
    },
    "streetcar_anchor": {
        "title": "OC Streetcar corridor anchor band (weekday boardings)",
        "tier": "config", "status": "active", "basis": "measured",
        "config_key": "config/streetcar.json: anchor_low / anchor_high",
        "history": [("2026-07-11", (3600, 5500), "measured",
                     "spec08 A2 harvest -- config anchor_low/high")],
        "provenance": "composite of parallel-carrier shape-shares x FY2019 "
                      "weekday boardings x uniformity x trend (anchor_streetcar.py; "
                      "MEASURED but WEAK, spec 05 §3.3); anchor_lo/anchor_hi rows",
        "rows": {"streetcar": ["anchor_lo", "anchor_hi"]},
        "no_row_reason": None, "accepted": None,
        "logged": None, "upgrade": "APC records request",
    },
    "harbor_service_new": {
        "title": "Harbor new-line service design (grade-separated ALM)",
        "tier": "config", "status": "active", "basis": "judgment",
        "config_key": "config/harbor.json: service_new / services_base.rapid",
        "history": [("2026-07-11", "service_new", "judgment",
                     "spec08 A2 harvest -- config service_new design axis")],
        "provenance": "owns the harbor design-exploration rows: stop-offset, "
                      "rapid-base GTFS variant, 10/20 & flat-5 headway plans, "
                      "0.5/1.5-mi spacing (spec 08 §3 -- one owner per artifact)",
        "rows": {"harbor": ["grid_phase_half", "rapid_gtfs", "headway_10_20",
                            "headway_flat5", "spacing_05", "spacing_15"]},
        "no_row_reason": None, "accepted": None,
        "logged": None, "upgrade": "OCTA project design docs",
    },
    "streetcar_service_new": {
        "title": "OC Streetcar new-line service design (at-grade)",
        "tier": "config", "status": "active", "basis": "judgment",
        "config_key": "config/streetcar.json: service_new",
        "history": [("2026-07-11", "service_new", "judgment",
                     "spec08 A2 harvest -- config service_new design axis")],
        "provenance": "owns the streetcar design-exploration rows: stop-offset, "
                      "10/20 & flat-5 headway plans, 0.5/1.5-mi spacing (no rapid "
                      "base -> no rapid_gtfs row); spec 08 §3 one-owner rule",
        "rows": {"streetcar": ["grid_phase_half", "headway_10_20",
                              "headway_flat5", "spacing_05", "spacing_15"]},
        "no_row_reason": None, "accepted": None,
        "logged": None, "upgrade": "OCTA project design docs",
    },

    # ===== width-block owners (spec 08 §4; rows in the 'width' artifact) =====
    # The band-WIDTH knobs. A point() row is vacuously 0.0% (it pins fix_bins),
    # so these are exercised by the width_sensitivities block: full reruns under
    # x0.5/x2 scale factors (a scale over-key, NOT new priors). The raw
    # concentration literals (300/300/100/400) remain in run(); single-sourcing
    # them is an A2b/later cleanup -- the width rows already expose the effect.
    "dirichlet_strength": {
        "title": "Dirichlet bin-shape concentration (joint bin-shape trust)",
        "tier": "structural", "status": "active", "basis": "judgment",
        "history": [("2026-07-11", "dirichlet_strength", "judgment",
                     "spec08 A2 harvest -- introduced spec02")],
        "provenance": "the four Dirichlet concentrations -- walk-bin 300, "
                      "transfer-bin 300, visitor-bin 100, car-frac 400 -- encode "
                      "one 'how much do we trust the bin shapes' assumption; the "
                      "width block scales all four jointly x0.5/x2 (spec 08 §4)",
        "rows": {"width": ["dirichlet_half", "dirichlet_double"]},
        "no_row_reason": None, "accepted": None,
        "logged": None, "upgrade": "on-board / APC bin-share observations",
    },
    "s0_se_width": {
        "title": "S0 base-share lognormal jitter width",
        "tier": "structural", "status": "active", "basis": "locally-calibrated",
        "history": [("2026-07-11", "s0_se_width", "locally-calibrated",
                     "spec08 A2 harvest -- introduced spec02")],
        "provenance": "the S0 base-share jitter is lognormal(0, cor.s0_se) with "
                      "cor.s0_se the ACS delta-method relative SEs (data); the "
                      "width block scales that sigma x0.5/x2 (spec 08 §4)",
        "rows": {"width": ["s0se_half", "s0se_double"]},
        "no_row_reason": None, "accepted": None,
        "logged": None, "upgrade": "ACS refresh / observed base shares",
    },
}


# ---------------------------------------------------------------------------
# accessors
# ---------------------------------------------------------------------------
class GeneratedPriors(dict):
    """dict subclass carrying a provenance sentinel so downstream checks can
    prove model.PRIORS was generated by build_priors() rather than hand-typed
    (spec 08 s5 check 4)."""
    generated_by = "assumptions.build_priors"


def val(assumption_id):
    """The imported literal value of an OWNED-tier (prior/constant) entry.
    Priors return the (lo, hi, shape) 3-tuple."""
    return ASSUMPTIONS[assumption_id]["value"]


def band(assumption_id):
    """The (lo, hi) band. Priors derive it from the value tuple; constants
    return their explicit band (None where definitional)."""
    e = ASSUMPTIONS[assumption_id]
    if e["tier"] == "prior":
        lo, hi, _ = e["value"]
        return (lo, hi)
    return e.get("band")


def build_priors():
    """Reproduce model.PRIORS: the prior-tier entries as {id: (lo, hi, shape)},
    emitted sorted by `order`. Asserts the orders are exactly range(len) (a
    static consistency check; the committed fingerprint in test_bca_export.py
    is the actual reorder guard). Returns a GeneratedPriors sentinel dict."""
    priors = sorted(
        ((k, e) for k, e in ASSUMPTIONS.items() if e["tier"] == "prior"),
        key=lambda kv: kv[1]["order"])
    orders = [e["order"] for _, e in priors]
    assert orders == list(range(len(priors))), (
        f"prior `order` ints are not exactly 0..{len(priors) - 1}: {orders}")
    out = GeneratedPriors((k, e["value"]) for k, e in priors)
    out.source = "assumptions.build_priors (spec 08)"
    return out
