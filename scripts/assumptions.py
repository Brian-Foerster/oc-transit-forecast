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
        # prior EXTRA (spec 08 §2): the untrimmed asc=0.55 probe (both corridor
        # results) and the no-Bravo-branding asc=0 probe in the backtest artifact
        # -- per-artifact, beyond the auto lo/hi edge rows.
        "extras": {"harbor": ["asc_untrimmed"], "streetcar": ["asc_untrimmed"],
                   "backtest": ["bt_asc0"]},
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
        "provenance": "non-work responsiveness relative to work (spec 02). The "
                      "wrapper's kappa_1 (kappa->1) row re-blends the exported "
                      "pre-blend quantity streams -- a QUANTITY blend, not a "
                      "revaluation (spec 06 D8/W1)",
        "rows": "auto",
        "extras": {"wrapper": ["kappa_1"]},
        "no_row_reason": None, "accepted": None,
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
                      "(spec 06 D3); money is never monetized through it. Baked "
                      "into the exported utility, so its wrapper rows "
                      "(vot_behav_lo/vot_behav_hi) read 0.0% at flat fare and need "
                      "a stage-2 re-export to sweep -- exposed regardless (spec 06 "
                      "W1 / rule 2)",
        "rows": "auto",
        "extras": {"wrapper": ["vot_behav_lo", "vot_behav_hi"]},
        "no_row_reason": None, "accepted": None,
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
                      "(spec 06 D7); model code does not consume pcar*. Owns the "
                      "wrapper's JOINT pcar-set rows (pcar_lo/pcar_hi) on behalf "
                      "of the pcar0/1/2/v family -- the wrapper sweeps all four "
                      "diversion priors to their band edges together, so the D7 "
                      "diverted-car-mile set is one wrapper row pair (spec 06 W1)",
        "rows": "auto",
        "extras": {"wrapper": ["pcar_lo", "pcar_hi"]},
        "no_row_reason": None, "accepted": None,
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
                      "points identifying the street-variant speed curve, which "
                      "only prices HYPOTHETICAL bus designs -- no live config uses "
                      "the derived_speed street variant yet, so no row (measured "
                      "stays measured; base services keep their config scalars)",
        "rows": {}, "no_row_reason": "spec-pending:02§4.9",
        "accepted": ("owner-directive 2026-07-11", "2026-07-11"),
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
                      "points identifying the street-variant speed curve, which "
                      "only prices HYPOTHETICAL bus designs -- no live config uses "
                      "the derived_speed street variant yet, so no row",
        "rows": {}, "no_row_reason": "spec-pending:02§4.9",
        "accepted": ("owner-directive 2026-07-11", "2026-07-11"),
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
        "provenance": "symmetric +/-20 clamp on dv before exp() -- a numerical "
                      "overflow guard, NOT a behavioral bound (its own definition, "
                      "not a swept assumption); verified never to bind at central "
                      "(widening DV_CLIP 20->1000 left the central point at "
                      "12035.819133041561 unchanged, A2a report). Basis AND no-row "
                      "reason are both DEFINITIONAL: an overflow clamp is a "
                      "definition, so it is not laundered through 'non-binding' "
                      "(spec 08 A3 handoff -- resolving the A2b addendum-0b "
                      "contradiction the simple direction: a definitional guard "
                      "stays definitional; s0_pivot_clip's 0.95 ceiling, a REAL "
                      "max-share judgment, keeps its non-binding disposition)",
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
                      "0.95 max-share ceiling (a REAL max-share assumption, basis "
                      "judgment, spec 08 s7). Neither binds at central (max base "
                      "transit share 0.227 << 0.95, s0v<=0.30), so a point row is "
                      "vacuously 0.0% -- rowless via the non-binding disposition, "
                      "NOT laundered as definitional (spec 08 A2b addendum 0b: the "
                      "0.95 ceiling is a judgment assumption that provably never "
                      "binds, not a definition)",
        "rows": {}, "no_row_reason": "non-binding:db4af97",
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
    "asc_calibrated": {
        "title": "calibrated new-line ASC (matured-era posterior central; display)",
        "tier": "constant", "status": "active",
        "value": 0.109, "units": "util", "band": None,
        "basis": "locally-calibrated",
        "history": [("2026-07-14", 0.109, "locally-calibrated",
                     "spec08 A2b harvest -- model.py asc_bracket fallback, spec05 s3.4")],
        "provenance": "the MATURED-era ABC posterior ASC central from the bus 543 "
                      "experiment, used as the display anchor for the streetcar "
                      "rail-ASC premium bracket (config asc_calibrated x "
                      "{1.0,1.5,2.0}; model.py stdout only -- NOT in results JSON). "
                      "VALUE UNCHANGED at 0.109: it feeds display output, so "
                      "revaluing would breach the byte-identity gate. The streetcar "
                      "config carries its own 0.109; this constant single-sources "
                      "the model.py fallback literal (spec 08 A2b addendum 0a). "
                      "Rowless: the ASC's ridership channel is fully swept by the "
                      "asc PRIOR rows (asc_lo/asc_hi/asc_untrimmed)",
        "rows": {}, "no_row_reason": "covered-elsewhere:asc_untrimmed",
        "accepted": ("owner-directive 2026-07-11", "2026-07-11"),
        "logged": "README known-issue 14",
        "upgrade": "refresh to the launch-equivalent posterior (0.19, abc_harbor "
                   "central-kernel asc P50) or compute from abc_harbor.json -- a "
                   "deliberate revaluation, own commit",
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
                      "Excel); the central back-trend numerator (feeds the CENTRAL "
                      "kernel 543_launch_s500, which is not a sensitivity row). Its "
                      "vintage-choice sensitivity is the FY2014 alternative reading",
        "rows": {}, "no_row_reason": "covered-elsewhere:543_launch14_s500",
        "accepted": ("owner-directive 2026-07-11", "2026-07-11"),
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
                      "FY2014-vintage back-trend numerator. Owns the "
                      "543_launch14_s500 ABC kernel row -- the defensible alternate "
                      "reading of 'launch-equivalent' (mu ~5,647 vs the FY2013 "
                      "central ~5,938), exposed not silently chosen against",
        "rows": {"abc": ["543_launch14_s500"]},
        "no_row_reason": None, "accepted": None,
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
                      "back-trend denominator (matches the FY2017 543 vintage). "
                      "Shared by both the central (FY2013) and FY2014 back-trends; "
                      "its vintage-choice sensitivity is the 543_launch14_s500 row",
        "rows": {}, "no_row_reason": "covered-elsewhere:543_launch14_s500",
        "accepted": ("owner-directive 2026-07-11", "2026-07-11"),
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
                      "the launch-equivalent target MU_LAUNCH (spec 02 s4.6). A "
                      "measured factor of BOTH the central (FY2013 back-trend) and "
                      "the FY2014-vintage kernels; its readings are exposed by the "
                      "543_launch14_s500 alternative-vintage row",
        "rows": {}, "no_row_reason": "covered-elsewhere:543_launch14_s500",
        "accepted": ("owner-directive 2026-07-11", "2026-07-11"),
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
                      "543_matured_s500 sensitivity kernel (spec 02 s4.6), which "
                      "this entry owns in the ABC artifact",
        "rows": {"abc": ["543_matured_s500"]},
        "no_row_reason": None, "accepted": None,
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
                      "spread; 350/800 are the width sensitivities, owned here as "
                      "the 543_launch_s350 / 543_launch_s800 ABC kernel rows (and "
                      "the abc_s350 / abc_s800 rows in the welfare-BCA wrapper "
                      "tornado, which re-weights the same draws by these kernels -- "
                      "spec 06 W1)",
        "rows": {"abc": ["543_launch_s350", "543_launch_s800"],
                 "wrapper": ["abc_s350", "abc_s800"]},
        "no_row_reason": None, "accepted": None,
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
                      "range printed and exported beside the backtest prediction "
                      "(backtest_543.json / abc_harbor.json observed_543). A "
                      "DISPLAY range, not a swept input -- the target-level "
                      "uncertainty it represents is bracketed by the ABC kernels "
                      "(matured 4,200 sits inside 3,700-4,600)",
        "rows": {}, "no_row_reason": "covered-elsewhere:543_matured_s500",
        "accepted": ("owner-directive 2026-07-11", "2026-07-11"),
        "logged": None, "upgrade": "APC records request",
    },

    # ---- bca_export.py ---------------------------------------------------
    "eq_days": {
        "title": "weekday-to-annual equivalent service days",
        "tier": "constant", "status": "active",
        "value": [300, 330], "units": "days/yr", "band": (300, 330),
        "basis": "judgment",
        "history": [("2026-07-11", [300, 330], "judgment",
                     "spec08 A1 harvest -- introduced spec06")],
        "provenance": "weekday->annual conversion band (anchor_from_apc "
                      "convention); low 300, high 330 equivalent service days. "
                      "Exported to bca_export (eq_days); its band far edge is the "
                      "eq_days_330 tornado row in the welfare-BCA wrapper artifact "
                      "(bca_harbor.json). LANDED 2026-07-15 (spec 06 W1): the "
                      "wrapper-artifact scan (spec 08 §5 check 2 / §9 Q7) flipped "
                      "this from a spec-pending:06§E4 warning to a real check-2 "
                      "coverage claim",
        "rows": {"wrapper": ["eq_days_330"]},
        "no_row_reason": None, "accepted": None,
        "logged": None, "upgrade": "OCTA service-calendar day counts",
    },

    # ---- build_corridor.py ----------------------------------------------
    "buffer_mi": {
        "title": "corridor tract inclusion buffer",
        "tier": "constant", "status": "active",
        "value": 0.9, "units": "mi", "band": None, "basis": "definitional",
        "history": [("2026-07-11", 0.9, "definitional",
                     "spec08 A1 harvest -- introduced spec01/spec02")],
        "provenance": "centroid-within distance for corridor tract membership; a "
                      "build-geometry knob (a rebuilt-variant sensitivity is "
                      "possible but not mandated -- disposition-only, spec 08 A2b)",
        "rows": {}, "no_row_reason": "quality-knob",
        "accepted": ("owner-directive 2026-07-11", "2026-07-11"),
        "logged": None, "upgrade": "corridor-membership rebuilt-variant sensitivity",
    },
    "xfer_buffer_mi": {
        "title": "transfer feeder-access buffer",
        "tier": "constant", "status": "active",
        "value": 0.9, "units": "mi", "band": None, "basis": "definitional",
        "history": [("2026-07-11", 0.9, "definitional",
                     "spec08 A1 harvest -- introduced spec01/spec02")],
        "provenance": "outside-tract to feeder-crossing access distance for "
                      "the transfer market; a build-geometry knob (rebuilt-variant "
                      "sensitivity possible, not mandated -- disposition-only)",
        "rows": {}, "no_row_reason": "quality-knob",
        "accepted": ("owner-directive 2026-07-11", "2026-07-11"),
        "logged": None, "upgrade": "transfer-access rebuilt-variant sensitivity",
    },
    "cross_near": {
        "title": "feeder crossing near-threshold",
        "tier": "constant", "status": "active",
        "value": 0.25, "units": "mi", "band": None, "basis": "definitional",
        "history": [("2026-07-11", 0.25, "definitional",
                     "spec08 A1 harvest -- introduced spec01/spec02")],
        "provenance": "|offset| below which a feeder is 'on' the corridor line "
                      "(crossing test); a build-geometry knob (rebuilt-variant "
                      "sensitivity possible, not mandated -- disposition-only)",
        "rows": {}, "no_row_reason": "quality-knob",
        "accepted": ("owner-directive 2026-07-11", "2026-07-11"),
        "logged": None, "upgrade": "crossing-test rebuilt-variant sensitivity",
    },
    "cross_far": {
        "title": "feeder crossing far-threshold",
        "tier": "constant", "status": "active",
        "value": 1.0, "units": "mi", "band": None, "basis": "definitional",
        "history": [("2026-07-11", 1.0, "definitional",
                     "spec08 A1 harvest -- introduced spec01/spec02")],
        "provenance": "|offset| beyond which a feeder must reach on both sides "
                      "(genuine-crossing test); a build-geometry knob "
                      "(rebuilt-variant sensitivity possible, not mandated)",
        "rows": {}, "no_row_reason": "quality-knob",
        "accepted": ("owner-directive 2026-07-11", "2026-07-11"),
        "logged": None, "upgrade": "crossing-test rebuilt-variant sensitivity",
    },
    "bin_edges": {
        "title": "distance-bin edges (walk & transfer markets)",
        "tier": "constant", "status": "active",
        "value": [0.0, 0.5, 2.5, 4.75, 7.5, 10.25, 12.6], "units": "mi",
        "band": None, "basis": "judgment",
        "history": [("2026-07-11", [0.0, 0.5, 2.5, 4.75, 7.5, 10.25, 12.6],
                     "judgment", "spec08 A1 harvest -- introduced spec02")],
        "provenance": "on-line distance-bin partition; first bin 0-0.5 mi "
                      "carries the intra-tract flows. A discretization-resolution "
                      "knob (a finer partition / rebuilt-variant sensitivity is "
                      "possible, not mandated -- disposition-only, spec 08 A2b)",
        "rows": {}, "no_row_reason": "quality-knob",
        "accepted": ("owner-directive 2026-07-11", "2026-07-11"),
        "logged": None, "upgrade": "finer partition / rebuilt-variant sensitivity",
    },
    "intra_clip": {
        "title": "intra-tract imputed-distance clip bounds",
        "tier": "constant", "status": "active",
        "value": (0.10, 0.45), "units": "mi", "band": None,
        "basis": "definitional",
        "history": [("2026-07-11", (0.10, 0.45), "definitional",
                     "spec08 A1 harvest -- introduced spec02")],
        "provenance": "clamp on the sqrt(ALAND)/intra_divisor imputed along-line "
                      "distance for intra-tract walk flows; the clip is part of "
                      "the intra-tract distance RULE whose sensitivity is the "
                      "rebuilt-variant intra_tract_alt row (owned by intra_divisor)",
        "rows": {}, "no_row_reason": "covered-elsewhere:intra_tract_alt",
        "accepted": ("owner-directive 2026-07-11", "2026-07-11"),
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
                      "projection factor for intra-tract flow distance. The "
                      "ALTERNATIVE imputation sqrt(ALAND)/intra_divisor_alt is the "
                      "spec 08 §4 rebuilt-variant intra_tract_alt row: a SCRATCH "
                      "corridor rebuilt with the alt divisor (build_corridor "
                      "--variant), rows in BOTH corridor results",
        "rows": {"harbor": ["intra_tract_alt"], "streetcar": ["intra_tract_alt"]},
        "no_row_reason": None, "accepted": None,
        "logged": None, "upgrade": None,
    },
    "intra_divisor_alt": {
        "title": "intra-tract imputed-distance ALTERNATIVE divisor (rebuilt row)",
        "tier": "constant", "status": "active",
        "value": 2.0, "units": "dimensionless", "band": None,
        "basis": "judgment",
        "history": [("2026-07-14", 2.0, "judgment",
                     "spec08 A2b -- intra_tract_alt rebuilt-variant divisor")],
        "provenance": "the alternative intra-tract distance rule sqrt(ALAND)/2 "
                      "(vs the L/3 central), clip [0.10, 0.45] UNCHANGED; consumed "
                      "by build_corridor --variant intra_tract_alt to rebuild a "
                      "scratch corridor the intra_tract_alt sensitivity row runs "
                      "against (spec 08 §4/§7). The '0.9 clip scale' hint in the "
                      "original draft was ambiguous -- resolved to clip-unchanged "
                      "and documented (spec 08 A2b brief)",
        "rows": {}, "no_row_reason": "covered-elsewhere:intra_tract_alt",
        "accepted": ("owner-directive 2026-07-11", "2026-07-11"),
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
        "rows": {}, "no_row_reason": "definitional",
        "accepted": ("owner-directive 2026-07-11", "2026-07-11"),
        "logged": None, "upgrade": None,
    },
    "se_cap": {
        "title": "relative-SE cap on base transit shares",
        "tier": "constant", "status": "active",
        "value": 0.5, "units": "relative", "band": None, "basis": "definitional",
        "history": [("2026-07-11", 0.5, "definitional",
                     "spec08 A1 harvest -- introduced spec02")],
        "provenance": "clamp on the delta-method relative SE of S0 shares "
                      "(guards degenerate small-cell ACS estimates); a numerical "
                      "guard, superseded in effect by the s0_se_width block which "
                      "scales the jitter width",
        "rows": {}, "no_row_reason": "definitional",
        "accepted": ("owner-directive 2026-07-11", "2026-07-11"),
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
        "rows": {}, "no_row_reason": "quality-knob",
        "accepted": ("owner-directive 2026-07-11", "2026-07-11"),
        "logged": None, "upgrade": None,
    },
    "min_feeder_mi": {
        "title": "minimum feeder shape length",
        "tier": "constant", "status": "active",
        "value": 1.0, "units": "mi", "band": None, "basis": "definitional",
        "history": [("2026-07-11", 1.0, "definitional",
                     "spec08 A1 harvest -- introduced spec02")],
        "provenance": "feeders shorter than this are ignored as crossing "
                      "candidates; a build-geometry knob (rebuilt-variant "
                      "sensitivity possible, not mandated -- disposition-only)",
        "rows": {}, "no_row_reason": "quality-knob",
        "accepted": ("owner-directive 2026-07-11", "2026-07-11"),
        "logged": None, "upgrade": "feeder-length rebuilt-variant sensitivity",
    },
    "mi_lat": {
        "title": "miles per degree latitude (flat-earth projection)",
        "tier": "constant", "status": "active",
        "value": 69.05, "units": "mi/deg", "band": None, "basis": "definitional",
        "history": [("2026-07-11", 69.05, "definitional",
                     "spec08 A1 harvest -- introduced spec02")],
        "provenance": "flat-earth projection constant (miles per degree "
                      "latitude at OC's latitude)",
        "rows": {}, "no_row_reason": "definitional",
        "accepted": ("owner-directive 2026-07-11", "2026-07-11"),
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
        "rows": {}, "no_row_reason": "definitional",
        "accepted": ("owner-directive 2026-07-11", "2026-07-11"),
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
        "rows": {}, "no_row_reason": "definitional",
        "accepted": ("owner-directive 2026-07-11", "2026-07-11"),
        "logged": None, "upgrade": None,
    },

    # ---- network_mechanics.py (spec 07 N1a network-sequencing mechanics) ---
    # The three declared conventions §4.2 requires because no pipeline output
    # allocates a line's boardings along its length or maps a committed plan to
    # the feeder scalar. Each is imported (single-sourced into network_mechanics
    # -- omega_allocation / omega_stop_materialization into omega(), the headway
    # map into feeder_headway), so they are RULE-BEARING, not documentation. All
    # rowless: the sensitivity rows they anticipate (uniform-along-line omega,
    # the peak-mapped feeder headway -- spec 07 §8i / §10 G7) live in the
    # network-sequence primary artifact, which does not exist until N4 -- hence
    # spec-pending:07§9-N4, mirroring the N2 capital leaves. NO new priors
    # (constant tier only; the prior-order fingerprint is untouched).
    "omega_allocation": {
        "title": "omega boardings-allocation rule along a committed line",
        "tier": "constant", "status": "active",
        "value": "worker_mass", "units": "choice", "band": None,
        "basis": "judgment",
        "history": [("2026-07-16", "worker_mass", "judgment",
                     "spec07 N1a -- omega worker-mass vs uniform allocation")],
        "provenance": "how omega(H, B) apportions committed line H's forecast "
                      "along its length to its materialized stops (spec 07 §4.2): "
                      "'worker_mass' (default) allocates proportional to "
                      "corridor-tract worker mass; the 'uniform'-along-line "
                      "variant is the §8i / §10 G7 sensitivity row (rows omega x "
                      "{0.5, 1.5} + uniform). A DECLARED judgment -- no pipeline "
                      "output allocates a line's boardings along its length",
        "rows": {}, "no_row_reason": "spec-pending:07§9-N4",
        "accepted": ("spec07-N1a network-mechanics landing", "2026-07-16"),
        "logged": None, "upgrade": "on-board / APC boarding-by-stop profile",
    },
    "omega_stop_materialization": {
        "title": "omega stop-materialization spacing rule",
        "tier": "constant", "status": "active",
        "value": "line_spacing", "units": "choice", "band": None,
        "basis": "judgment",
        "history": [("2026-07-16", "line_spacing", "judgment",
                     "spec07 N1a -- materialize stops every line-spacing mi")],
        "provenance": "the rule network_mechanics.materialize_stops uses to place "
                      "H's stops for the omega allocation (spec 07 §4.2: 'stops "
                      "materialized every `spacing` mi along H's alignment "
                      "polyline'). 'line_spacing' = every H-spacing mi from the "
                      "window start; a finer/coarser materialization is the "
                      "anticipated §10 G7 row (network-sequence artifact, N4)",
        "rows": {}, "no_row_reason": "spec-pending:07§9-N4",
        "accepted": ("spec07-N1a network-mechanics landing", "2026-07-16"),
        "logged": None, "upgrade": "engineered stop plan per committed line",
    },
    "feeder_headway_map": {
        "title": "synthetic-feeder headway mapping convention (offpeak->midday)",
        "tier": "constant", "status": "active",
        "value": "offpeak_to_midday", "units": "choice", "band": None,
        "basis": "judgment",
        "history": [("2026-07-16", "offpeak_to_midday", "judgment",
                     "spec07 N1a -- committed {peak,offpeak} plan -> feeder scalar")],
        "provenance": "how a committed line's {peak, offpeak} headway plan maps "
                      "to the single midday scalar build_corridor's feeder "
                      "convention carries when the line is injected as a synthetic "
                      "feeder (spec 07 §4.2.1). 'offpeak_to_midday' is the declared "
                      "convention; the peak-mapped variant is its §10 G7 "
                      "sensitivity row (network-sequence artifact, N4)",
        "rows": {}, "no_row_reason": "spec-pending:07§9-N4",
        "accepted": ("spec07-N1a network-mechanics landing", "2026-07-16"),
        "logged": None, "upgrade": "committed-line published service plan",
    },

    # ---- sequence_network.py knobs (spec 07 N1b sequencing harness) -------
    # The three harness-level knobs the greedy loop introduces. CONSTANT tier
    # (NOT priors -- none is consumed by draw_params, so the prior-order
    # fingerprint is untouched, exactly as N1a promised). Each carries a band so
    # its lo/hi (or cap 1/3) sensitivity rows can source their edges. All rowless
    # for the registry's ROW-tracking: the rows they anticipate live in the
    # network-sequence PRIMARY ARTIFACT (outputs/network_sequence.json.sensitivity),
    # a separate output schema check_assumptions does not scan (it tracks the
    # per-corridor results_*.json tornado). The rows ARE present in that artifact
    # this same commit (gate G7); formal registry row-tracking of the network
    # artifact is a later integration -- hence spec-pending:07§9-N4, mirroring the
    # sibling omega_* / cap_* entries. cycle_gap is §11 Q1's exposed knob (prior
    # U(4,8) yr as a CONCEPT -- but a harness constant, not a draw_params prior).
    "cycle_gap": {
        "title": "years between real programmatic build cycles",
        "tier": "constant", "status": "active",
        "value": 6.0, "units": "yr", "band": (4.0, 8.0), "basis": "judgment",
        "history": [("2026-07-16", 6.0, "judgment",
                     "spec07 N1b -- cycle_gap knob (§11 Q1 U(4,8) yr, lo/hi rows)")],
        "provenance": "the gap between real funded build cycles (spec 07 §3/§11 "
                      "Q1): a candidate committed at cycle k opens (k-1)*cycle_gap "
                      "+ build_years later, so its capital is discounted to the "
                      "common base year. An EXPOSED knob, NOT an optimization "
                      "variable (timing optimization adds a dimension the "
                      "provenance cap cannot discipline). Central 6 = midpoint of "
                      "the §11 Q1 U(4,8) prior; the lo/hi (4/8 yr) rows land in the "
                      "network-sequence artifact's Delta-K_PV display (interim: "
                      "welfare-minutes are a level and never discounted)",
        "rows": {}, "no_row_reason": "spec-pending:07§9-N4",
        "accepted": ("spec07-N1b sequencing-harness landing", "2026-07-16"),
        "logged": None, "upgrade": "adopted capital program cadence",
    },
    "network_budget": {
        "title": "cumulative program capital budget (US-TYPICAL band)",
        "tier": "constant", "status": "active",
        "value": 3000.0, "units": "$M", "band": (2000.0, 5000.0),
        "basis": "judgment",
        "history": [("2026-07-16", 3000.0, "judgment",
                     "spec07 N1b -- cumulative program budget knob (§7/Q2 lo/hi)")],
        "provenance": "the cumulative program capital budget the knapsack "
                      "feasibility constraint enters through (spec 07 §7/§11 Q2: a "
                      "cumulative program budget, NOT per-cycle caps -- those bias "
                      "toward small lines). Under a SLACK budget the §3 rule orders "
                      "by welfare LEVEL and the budget is inert; a BINDING budget "
                      "makes capital-efficiency decision-relevant. Central 3000 is "
                      "a reference; the lo/hi (2000/5000 $M) rows are the G7 budget "
                      "sensitivity in the network-sequence artifact. The harness "
                      "CLI --budget overrides it; default is a slack (None) budget",
        "rows": {}, "no_row_reason": "spec-pending:07§9-N4",
        "accepted": ("spec07-N1b sequencing-harness landing", "2026-07-16"),
        "logged": None, "upgrade": "adopted capital program envelope",
    },
    "depth_cap": {
        "title": "provenance-DAG depth cap (decision-grade vs exploratory)",
        "tier": "constant", "status": "active",
        "value": 2, "units": "levels", "band": (1, 3), "basis": "judgment",
        "history": [("2026-07-16", 2, "judgment",
                     "spec07 N1b -- provenance depth cap (§6.2 cap 1/3 rows)")],
        "provenance": "the recursive provenance-DAG depth beyond which network "
                      "output is labeled EXPLORATORY and excluded from gate memos "
                      "(spec 07 §6.2). depth(measured)=0; depth(eval)=1+max{depth(H) "
                      ": candidate depends on H}. A spatially spread program stays "
                      "decision-grade for many cycles; a tightly chained one goes "
                      "exploratory by cycle 4. Central cap 2; the cap 1/3 "
                      "labeling-sensitivity rows land in the network-sequence "
                      "artifact (they relabel the exploratory tail, not the "
                      "objective)",
        "rows": {}, "no_row_reason": "spec-pending:07§9-N4",
        "accepted": ("spec07-N1b sequencing-harness landing", "2026-07-16"),
        "logged": None, "upgrade": "adopted provenance-governance threshold",
    },

    # ---- capcost.py (spec 04 capital rate card as code, spec 07 N2) -------
    # PRE-markup line-item leaves (2026 US$M) from costs/metro_cost_model.xlsx
    # §2 / spec 04 §2. capcost.capital() DERIVES the markup-inclusive
    # coefficients (Fixed 183.6 / 23.4 route-km / 27.6 elevated / 33.96 station
    # / 7.44 car) from these leaves x cap_markup_low (E55-locked). All rowless:
    # the capital sensitivity rows (fixed_cost_share {1,0.5,0}, LOW|US-TYPICAL
    # band, crossing sweep) are spec 07 §10 G7 rows in the network-sequence
    # primary artifact, which does not exist until N4 -- hence spec-pending:
    # 07§9-N4. NO tbc-wrapper capital rows exist to claim (the wrapper carries
    # capital as a fixed K input, not a swept tornado row), so a covered-
    # elsewhere claim would be spurious. NO new priors (constant tier only).
    "cap_occ": {
        "title": "operations control centre (fixed capital)",
        "tier": "constant", "status": "active",
        "value": 28.0, "units": "$M", "band": None, "basis": "measured",
        "history": [("2026-07-16", 28.0, "measured",
                     "spec07 N2 -- spec 04 §2 rate card as code")],
        "provenance": "OCC fixed capital, REM-calibrated rate card "
                      "(costs/metro_cost_model.xlsx §2, spec 04 §2). Part of the "
                      "fixed term (OCC + depot) the §8j fixed_cost_share knob scales",
        "rows": {}, "no_row_reason": "spec-pending:07§9-N4",
        "accepted": ("spec07-N2 rate-card landing", "2026-07-16"),
        "logged": None, "upgrade": "engineering cost reference / procurement",
    },
    "cap_depot": {
        "title": "depot / maintenance facility (fixed capital, 1 per line)",
        "tier": "constant", "status": "active",
        "value": 125.0, "units": "$M", "band": None, "basis": "measured",
        "history": [("2026-07-16", 125.0, "measured",
                     "spec07 N2 -- spec 04 §2 rate card as code")],
        "provenance": "depot fixed capital, REM-calibrated rate card (spec 04 "
                      "§2); dimensioned for the 4-car option-preserving envelope "
                      "(spec 04 §3.1). The '1 depot' quantity of the E55 gate; "
                      "scaled with OCC by the §8j fixed_cost_share knob",
        "rows": {}, "no_row_reason": "spec-pending:07§9-N4",
        "accepted": ("spec07-N2 rate-card landing", "2026-07-16"),
        "logged": None, "upgrade": "engineering cost reference / procurement",
    },
    "cap_route_km": {
        "title": "at-grade civil per route-km (track+traction+CBTC+utilities)",
        "tier": "constant", "status": "active",
        "value": 19.5, "units": "$M/km", "band": None, "basis": "measured",
        "history": [("2026-07-16", 19.5, "measured",
                     "spec07 N2 -- spec 04 §2 rate card as code")],
        "provenance": "per route-km civil base = track 4 + traction 8.5 + CBTC "
                      "wayside 4 + utilities 3 (spec 04 §2). The elevated viaduct "
                      "is the SEPARATE cap_viaduct_km add-on. Utilities 3/km is "
                      "the sheet's clean-ROW floor; §3.3b dense-segment uplift is "
                      "a corridor-quantity refinement, not this base rate",
        "rows": {}, "no_row_reason": "spec-pending:07§9-N4",
        "accepted": ("spec07-N2 rate-card landing", "2026-07-16"),
        "logged": None, "upgrade": "engineering cost reference / procurement",
    },
    "cap_viaduct_km": {
        "title": "elevated viaduct add-on per km",
        "tier": "constant", "status": "active",
        "value": 23.0, "units": "$M/km", "band": None, "basis": "measured",
        "history": [("2026-07-16", 23.0, "measured",
                     "spec07 N2 -- spec 04 §2 rate card as code")],
        "provenance": "elevated viaduct per-km add-on (spec 04 §2), calibrated on "
                      "REPETITIVE guideway (~30-40 m spans); barrier crossings are "
                      "priced separately via cap_crossing_* (spec 04 §3.3). Gets "
                      "the US-TYPICAL cap_delivery_ut factor (§3.2)",
        "rows": {}, "no_row_reason": "spec-pending:07§9-N4",
        "accepted": ("spec07-N2 rate-card landing", "2026-07-16"),
        "logged": None, "upgrade": "engineering cost reference / procurement",
    },
    "cap_station": {
        "title": "elevated station (LEAN + PSD + telecom + AFC)",
        "tier": "constant", "status": "active",
        "value": 28.3, "units": "$M/station", "band": None, "basis": "measured",
        "history": [("2026-07-16", 28.3, "measured",
                     "spec07 N2 -- spec 04 §2 rate card as code")],
        "provenance": "per elevated station = LEAN 22 + platform-screen-doors 2.3 "
                      "+ telecom 2.3 + AFC 1.7 (spec 04 §2); 76 m platforms (4-car "
                      "option envelope). Gets the US-TYPICAL cap_delivery_ut factor",
        "rows": {}, "no_row_reason": "spec-pending:07§9-N4",
        "accepted": ("spec07-N2 rate-card landing", "2026-07-16"),
        "logged": None, "upgrade": "engineering cost reference / procurement",
    },
    "cap_car": {
        "title": "rolling stock per car (vehicle + stabling + spares)",
        "tier": "constant", "status": "active",
        "value": 6.2, "units": "$M/car", "band": None, "basis": "measured",
        "history": [("2026-07-16", 6.2, "measured",
                     "spec07 N2 -- spec 04 §2 rate card as code")],
        "provenance": "per car = vehicle 3.4 + stabling 2.3 + spares 0.5 (spec 04 "
                      "§2); the 2->4-car expansion prices additional cars at this "
                      "same rate (spec 04 §3.1). Car COUNT is derived (capcost.fleet)",
        "rows": {}, "no_row_reason": "spec-pending:07§9-N4",
        "accepted": ("spec07-N2 rate-card landing", "2026-07-16"),
        "logged": None, "upgrade": "engineering cost reference / procurement",
    },
    "cap_markup_low": {
        "title": "LOW-scenario markup (design + contingency, additive)",
        "tier": "constant", "status": "active",
        "value": 1.20, "units": "factor", "band": None, "basis": "definitional",
        "history": [("2026-07-16", 1.20, "definitional",
                     "spec07 N2 -- spec 04 §2 rate card as code")],
        "provenance": "sheet's efficient-agency markup = 1 + 10% design + 10% "
                      "contingency, ADDITIVE (spec 04 §2). This factor is "
                      "E55-LOCKED: pre-markup subtotal 1654.2 x 1.20 = 1985.04 "
                      "(the sheet's shipped-config total) reproduces to the cent; "
                      "1.21 multiplicative would not. The tbc profile used 1.21 -- "
                      "the documented LOW-band delta vs this function",
        "rows": {}, "no_row_reason": "spec-pending:07§9-N4",
        "accepted": ("spec07-N2 rate-card landing", "2026-07-16"),
        "logged": None, "upgrade": None,
    },
    "cap_markup_ut": {
        "title": "US-TYPICAL-scenario markup (soft cost x contingency)",
        "tier": "constant", "status": "active",
        "value": 1.3923, "units": "factor", "band": None, "basis": "literature",
        "history": [("2026-07-16", 1.3923, "literature",
                     "spec07 N2 -- spec 04 §3.2 US-typical band")],
        "provenance": "US-typical markup = soft costs 1.17 x contingency 1.19 = "
                      "1.3923 (spec 04 §3.2, FTA early-stage practice; the tbc "
                      "profile's US-TYPICAL markup). Multiplicative here (vs the "
                      "additive LOW markup) per §3.2 and the tbc derivation",
        "rows": {}, "no_row_reason": "spec-pending:07§9-N4",
        "accepted": ("spec07-N2 rate-card landing", "2026-07-16"),
        "logged": None, "upgrade": "corridor-specific FTA risk assessment",
    },
    "cap_delivery_ut": {
        "title": "US-TYPICAL delivery-environment factor (viaduct + stations)",
        "tier": "constant", "status": "active",
        "value": 1.75, "units": "factor", "band": (1.5, 2.0), "basis": "literature",
        "history": [("2026-07-16", 1.75, "literature",
                     "spec07 N2 -- spec 04 §3.2 US-typical band")],
        "provenance": "delivery-environment multiplier on viaduct + stations for "
                      "the US-TYPICAL scenario (spec 04 §3.2: 1.5-2.0x, Transit "
                      "Costs Project US-elevated comps); the tbc profile's 1.75x. "
                      "Applied to cap_viaduct_km and cap_station only (civil "
                      "items), not to track/systems/rolling stock",
        "rows": {}, "no_row_reason": "spec-pending:07§9-N4",
        "accepted": ("spec07-N2 rate-card landing", "2026-07-16"),
        "logged": None, "upgrade": "named US-elevated comparator set (§3.2 x-check)",
    },
    "cap_crossing_low": {
        "title": "special-structures crossing rate (LOW / simple span)",
        "tier": "constant", "status": "active",
        "value": 30.0, "units": "$M/crossing", "band": (30.0, 80.0),
        "basis": "judgment",
        "history": [("2026-07-16", 30.0, "judgment",
                     "spec07 N2 -- spec 04 §3.3 special-structures placeholder")],
        "provenance": "per major crossing (freeway / river / railroad), LOW end = "
                      "simple channel span (spec 04 §3.3 band 30-80 $M, FLAGGED "
                      "placeholder for an engineering reference). capcost.capital "
                      "crossings arg x this default; overridable (parameterized)",
        "rows": {}, "no_row_reason": "spec-pending:07§9-N4",
        "accepted": ("spec07-N2 rate-card landing", "2026-07-16"),
        "logged": None, "upgrade": "engineering reference per crossing (spec 04 §3.3)",
    },
    "cap_crossing_ut": {
        "title": "special-structures crossing rate (US-TYPICAL / wide interchange)",
        "tier": "constant", "status": "active",
        "value": 65.0, "units": "$M/crossing", "band": (30.0, 80.0),
        "basis": "judgment",
        "history": [("2026-07-16", 65.0, "judgment",
                     "spec07 N2 -- spec 04 §3.3 special-structures placeholder")],
        "provenance": "per major crossing, US-TYPICAL point within the spec 04 "
                      "§3.3 30-80 $M band (high = wide freeway interchange under "
                      "traffic); the tbc profile's US-TYPICAL crossing rate. "
                      "FLAGGED placeholder pending an engineering reference",
        "rows": {}, "no_row_reason": "spec-pending:07§9-N4",
        "accepted": ("spec07-N2 rate-card landing", "2026-07-16"),
        "logged": None, "upgrade": "engineering reference per crossing (spec 04 §3.3)",
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
    # per-artifact rows those config values drive (or a disposition where the
    # config value has no own row). Harbor and streetcar anchors are SEPARATE
    # entries (spec 08 §3: "anchor -> low" means DIFFERENT assumptions per
    # corridor). A2b promoted the anchor_derivation structured keys (trend /
    # corr_share / uniformity), the 2013 backtest world (config/backtest_543.json),
    # and the visitor / bca config blocks -- each a resolvable structured-key
    # pointer (spec 08 §5 check 6: no prose-blob pointers).
    "harbor_anchor": {
        "title": "Harbor corridor anchor band (weekday boardings)",
        "tier": "config", "status": "active", "basis": "measured",
        "config_key": "config/harbor.json: anchor_low / anchor_high",
        "history": [("2026-07-11", (7650, 9650), "measured",
                     "spec08 A2 harvest -- config anchor_low/high")],
        "provenance": "543 + 43 FY2019 route totals x FY2019->FY2024 trend x "
                      "corridor share (anchor_from_apc.py / route43_share.py); "
                      "the trend + corr_share bands are now the structured "
                      "anchor_derivation keys (entries anchor_trend / corr_share), "
                      "cross-checked to give 7650/9650 within rounding-to-50; the "
                      "anchor_lo/anchor_hi sensitivity rows sweep the band",
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
    "anchor_trend": {
        "title": "Harbor anchor FY2019->FY2024 system trend band",
        "tier": "config", "status": "active", "basis": "measured",
        "config_key": "config/harbor.json: anchor_derivation.trend",
        "history": [("2026-07-14", (0.90, 0.99), "measured",
                     "spec08 A2b -- promoted from anchor_note prose")],
        "provenance": "the FY2019->FY2024 per-month system ridership ratio 0.94 "
                      "(range 0.90-0.99 covering route-share drift + COVID-window "
                      "bias), a factor of the forward Harbor anchor band; its "
                      "sensitivity is carried by the anchor_lo/anchor_hi sweep",
        "rows": {}, "no_row_reason": "covered-elsewhere:anchor_lo",
        "accepted": ("owner-directive 2026-07-11", "2026-07-11"),
        "logged": None, "upgrade": "APC records request",
    },
    "corr_share": {
        "title": "Route-43 corridor share (SHARED: forward anchor + 2013 backtest)",
        "tier": "config", "status": "active", "basis": "measured",
        "config_key": "config/harbor.json: anchor_derivation.corr_share",
        "history": [("2026-07-14", (0.75, 0.86), "measured",
                     "spec08 A2b -- promoted from prose; ONE entry, two derivations")],
        "provenance": "Route 43's boarding share inside the 12.1-mi corridor, "
                      "0.75 (LODES) - 0.86 (ACS), scripts/route43_share.py. The "
                      "SAME assumption in TWO derivations (spec 08 §2): the forward "
                      "Harbor anchor (543 + 43 x corr_share) AND the 2013 backtest "
                      "anchor (route43_total ~13,000 x corr_share -> 9,750-11,180, "
                      "backtest_543.py reads this key). Physically single-sourced "
                      "in config/harbor.json; the backtest reads it from the Harbor "
                      "corridor config, never duplicated. Sensitivity via anchor_lo",
        "rows": {}, "no_row_reason": "covered-elsewhere:anchor_lo",
        "accepted": ("owner-directive 2026-07-11", "2026-07-11"),
        "logged": None, "upgrade": "APC records request / on-board survey",
    },
    "streetcar_anchor_derivation": {
        "title": "OC Streetcar anchor derivation bands (uniformity + trend)",
        "tier": "config", "status": "active", "basis": "measured",
        "config_key": "config/streetcar.json: anchor_derivation "
                      "(uniformity / trend)",
        "history": [("2026-07-14", ((0.80, 1.10), (0.90, 0.99)), "measured",
                     "spec08 A2b -- promoted the clean band quantities from prose")],
        "provenance": "the along-route uniformity band 0.80-1.10 and the "
                      "FY2019->present trend 0.90-0.99 that scale the ~5,034 raw "
                      "composite-carrier corridor boardings (anchor_streetcar.py). "
                      "The per-carrier shape-shares (0.29/0.35/0.56/0.41) and the "
                      "~5,034 raw stay in prose -- measured shape overlaps, not a "
                      "clean band (spec 08 §2: document, do not invent). Cross-check "
                      "3600/5500 = 5034 x uniformity x trend within rounding-to-50; "
                      "sensitivity via the streetcar anchor_lo/anchor_hi sweep",
        "rows": {}, "no_row_reason": "covered-elsewhere:anchor_lo",
        "accepted": ("owner-directive 2026-07-11", "2026-07-11"),
        "logged": None, "upgrade": "APC records request",
    },
    "backtest_world": {
        "title": "2013 Bravo! 543 backtest world (promoted config file)",
        "tier": "config", "status": "active", "basis": "measured",
        "config_key": "config/backtest_543.json",
        "history": [("2026-07-14", "backtest_543", "measured",
                     "spec08 A2b -- 2013 world promoted out of backtest_543.py")],
        "provenance": "the June-2013 backtest scenario -- the 2013 local/rapid "
                      "services and the Route-43 route-total anchor LEAF (~13,000) "
                      "-- promoted from hardcoded backtest_543.py into config "
                      "(spec 08 §2: the last structured citation-drift nest). The "
                      "corridor share is NOT here (the shared corr_share entry); "
                      "the anchor band 9,750-11,180 is computed in code. The 2013 "
                      "services' sensitivities are the bt_* rows (owned by the "
                      "backtest_service_* entries)",
        "rows": {}, "no_row_reason": "covered-elsewhere:bt_flat15",
        "accepted": ("owner-directive 2026-07-11", "2026-07-11"),
        "logged": None, "upgrade": "APC records request",
    },
    "backtest_service_new": {
        "title": "2013 launch 543 service (backtest artifact)",
        "tier": "config", "status": "active", "basis": "measured",
        "config_key": "config/backtest_543.json: service_new",
        "history": [("2026-07-14", "service_new", "measured",
                     "spec08 A2b -- owns the 543-service backtest sensitivity rows")],
        "provenance": "the actual June-2013 launch service (15 mph, 10-min peak / "
                      "15-min off-peak, ~1-mi stops). Owns the backtest 543-service "
                      "sensitivity rows: bt_flat15 (old flat-15 spec), bt_20min "
                      "(20-min all day), bt_13mph (weaker TSP)",
        "rows": {"backtest": ["bt_flat15", "bt_20min", "bt_13mph"]},
        "no_row_reason": None, "accepted": None,
        "logged": None, "upgrade": "OCTA 2013 service records",
    },
    "backtest_service_base": {
        "title": "2013 Route 43 local base service (backtest artifact)",
        "tier": "config", "status": "active", "basis": "measured",
        "config_key": "config/backtest_543.json: services_base.local",
        "history": [("2026-07-14", "services_base", "measured",
                     "spec08 A2b -- owns the 43-base backtest sensitivity rows")],
        "provenance": "the 2013 Route 43 local (~12 mph, ~15-min, 1/4-mi stops); "
                      "the 2013 peak headway is unknown so the sensitivity rows "
                      "bt_base20 (flat 20-min) and bt_base_10_15 (10-min peak / "
                      "15 off) bracket it",
        "rows": {"backtest": ["bt_base20", "bt_base_10_15"]},
        "no_row_reason": None, "accepted": None,
        "logged": None, "upgrade": "OCTA 2013 service records",
    },
    "visitor_config": {
        "title": "visitor-market bin weights (corridor configs)",
        "tier": "config", "status": "active", "basis": "judgment",
        "config_key": "config/{harbor,streetcar}.json: visitor.bin_weights",
        "history": [("2026-07-14", "visitor.bin_weights", "judgment",
                     "spec08 A2b -- config-block pointer")],
        "provenance": "the resort/civic visitor market's distance-bin weights "
                      "(the load-bearing visitor config; visitor.share / visitor.S0 "
                      "mirror the phi / s0v priors and are consumed through them). "
                      "The whole visitor market's contribution is bounded by the "
                      "no_visitor toggle row; the 0-0.5-mi split by no_bin0",
        "rows": {}, "no_row_reason": "covered-elsewhere:no_visitor",
        "accepted": ("owner-directive 2026-07-11", "2026-07-11"),
        "logged": None, "upgrade": "resort/civic-market survey",
    },
    "bca_config": {
        "title": "BCA config block (routes removed + revenue vehicle-hours)",
        "tier": "config", "status": "active", "basis": "measured",
        "config_key": "config/{harbor,streetcar}.json: bca",
        "history": [("2026-07-14", "bca", "measured",
                     "spec08 A2b -- config-block pointer")],
        "provenance": "the fold/retain routes_removed sets and the weekday revenue "
                      "vehicle-hours (rev_hours_weekday, measured from OCTA GTFS) "
                      "that feed the avoided base O&M in the welfare BCA wrapper "
                      "(spec 06 §E4). The avoided-base-O&M channel's headline "
                      "sensitivity is the avoidable_marginal wrapper row -- the "
                      "avoidable-cost RATE (marginal vs fully-allocated $/rev-hr) "
                      "swept on exactly THESE oc-provided quantities. DUAL-NATURE "
                      "(spec 08 §9 Q7): the RATE lives in the TBCR RANGES, but the "
                      "swept QUANTITY (routes_removed x rev_hours) is oc's, so the "
                      "oc registry claims the row (om_lo/om_hi -- the NEW-line GoA4 "
                      "O&M, E5 -- stay engine-owned/exempt). LANDED 2026-07-15 "
                      "(spec 06 W1): flipped from spec-pending:06§E4 to a real "
                      "check-2 wrapper claim",
        "rows": {"wrapper": ["avoidable_marginal"]},
        "no_row_reason": None, "accepted": None,
        "logged": None, "upgrade": "OCTA service-calendar / cost model",
    },

    # ===== width-block owners (spec 08 §4; rows in the 'width' artifact) =====
    # The band-WIDTH knobs. A point() row is vacuously 0.0% (it pins fix_bins),
    # so these are exercised by the width_sensitivities block: full reruns under
    # x0.5/x2 scale factors (a scale over-key, NOT new priors). dirichlet_strength
    # now OWNS the four concentrations as a constant (single-sourced into run(),
    # spec 08 A2b addendum 0c); s0_se_width stays structural (its "value" is the
    # ACS delta-method SEs, data-derived, not a registry literal).
    "dirichlet_strength": {
        "title": "Dirichlet bin-shape concentrations (joint bin-shape trust)",
        "tier": "constant", "status": "active",
        "value": (300, 300, 100, 400),
        "units": "concentration (walk/transfer/visitor/car_frac)",
        "band": (0.5, 2.0), "basis": "judgment",
        "history": [("2026-07-11", "dirichlet_strength", "judgment",
                     "spec08 A2 harvest -- introduced spec02, structural"),
                    ("2026-07-14", (300, 300, 100, 400), "judgment",
                     "spec08 A2b addendum 0c -- tier structural->constant; four "
                     "concentrations single-sourced into run()")],
        "provenance": "the four Dirichlet concentrations -- walk-bin 300, "
                      "transfer-bin 300, visitor-bin 100, car-frac 400 -- encode "
                      "one 'how much do we trust the bin shapes' assumption, now "
                      "single-sourced (model.py DIR_WALK/DIR_XFER/DIR_VIS/DIR_CF). "
                      "The band (0.5, 2.0) is the JOINT x-scale range the width "
                      "block sweeps (NOT concentration bounds); its edges ARE the "
                      "dirichlet_half (x0.5) / dirichlet_double (x2) width rows "
                      "(spec 08 §4/§5 check 5 'band edges present as rows'). Claimed "
                      "PER-CORRIDOR (spec 06 W1): each corridor's width block is "
                      "scanned separately, closing the earlier union-collapse",
        "rows": {"width_harbor": ["dirichlet_half", "dirichlet_double"],
                 "width_streetcar": ["dirichlet_half", "dirichlet_double"]},
        "no_row_reason": None, "accepted": None,
        "logged": None, "upgrade": "on-board / APC bin-share observations",
    },
    "s0_se_width": {
        "title": "S0 base-share lognormal jitter width",
        "tier": "structural", "status": "active", "basis": "measured",
        "history": [("2026-07-11", "s0_se_width", "locally-calibrated",
                     "spec08 A2 harvest -- introduced spec02"),
                    ("2026-07-14", "s0_se_width", "measured",
                     "spec08 A2b addendum 0d -- basis measured (ACS delta-method SEs)")],
        "provenance": "the S0 base-share jitter is lognormal(0, cor.s0_se) with "
                      "cor.s0_se the ACS delta-method relative SEs (measured); the "
                      "width block scales that sigma x0.5/x2 (spec 08 §4). Claimed "
                      "PER-CORRIDOR (spec 06 W1): harbor / streetcar width blocks "
                      "scanned separately, closing the union-collapse",
        "rows": {"width_harbor": ["s0se_half", "s0se_double"],
                 "width_streetcar": ["s0se_half", "s0se_double"]},
        "no_row_reason": None, "accepted": None,
        "logged": None, "upgrade": "ACS refresh / observed base shares",
    },

    # ===== data tier (dataset vintages; NOT owned) ==========================
    # Names the dataset RELEASE the pipeline reads, not a code-owned literal --
    # data-tier entries carry no 'value' (spec 08 §2: NOT owned; code never
    # imports one). Basis "measured" throughout: each is a real published
    # dataset release; the ASSUMPTION being registered is the VINTAGE CHOICE
    # (which release, fetched/pulled when), not a judgment about the data
    # itself -- the vintage-choice risk is documented per-entry as a
    # provenance caveat instead (spec 08 A3 harvest, closing the §2/§7 gap:
    # this module previously had ZERO data-tier entries despite both sections
    # promising them).
    "lodes_2022": {
        "title": "LODES8 commute O-D vintage (ca_od_main_JT00_2022)",
        "tier": "data", "status": "active", "basis": "measured",
        "history": [("2026-07-14", "LODES8 ca_od_main_JT00_2022", "measured",
                     "spec08 A3 harvest -- introduced spec01/spec02, "
                     "scripts/build_derived.py")],
        "provenance": "US Census LEHD LODES8 CA commute O-D, block level, "
                      "aggregated to OC tract pairs (scripts/build_derived.py "
                      "reads ca_od_main_JT00_2022.csv.gz; scripts/download_data.py "
                      "is the fetch). The dataset itself is measured; the "
                      "ASSUMPTION is the VINTAGE CHOICE -- 2022 is the latest "
                      "LODES8 release at build time and proxies BOTH the 2013 "
                      "backtest market and the present-day forward corridors "
                      "with a post-COVID, WFH-reshaped commute SHAPE (spec 02 "
                      "§4.8; the vintage gap is also named in the ABC sigma "
                      "rationale, reweight_abc.py). Mandated sensitivity: "
                      "rebuild bins with pre-COVID LODES 2019 (spec 02 §4.8 "
                      "rebuilt-variant row), not yet landed -- hence the row "
                      "is spec-pending, not disposed",
        "rows": {}, "no_row_reason": "spec-pending:02§4.8",
        "accepted": ("owner-directive 2026-07-11", "2026-07-14"),
        "logged": None, "upgrade": "LODES 2019 rebuilt-variant row (spec 02 §4.8)",
    },
    "acs_2023": {
        "title": "ACS 2023 5-yr B08141 vintage (workers x vehicle availability x transit use)",
        "tier": "data", "status": "active", "basis": "measured",
        "history": [("2026-07-14", "ACS 2023 5-yr B08141", "measured",
                     "spec08 A3 harvest -- introduced spec01/spec02, "
                     "scripts/build_derived.py")],
        "provenance": "Census ACS 2023 5-yr B08141 table-based summary file, "
                      "tract level (scripts/build_derived.py reads "
                      "acsdt5y2023-b08141.dat; scripts/download_data.py is the "
                      "fetch). The dataset itself is measured; the ASSUMPTION "
                      "is the VINTAGE CHOICE -- the 2019-2023 pooled window "
                      "proxies the 2013 backtest market the same way the "
                      "LODES entry's caveat does (reweight_abc.py's ABC sigma "
                      "rationale bundles '2023 ACS proxying the 2013 market' "
                      "alongside the LODES commute-shape issue). UNLIKE "
                      "LODES, no spec section or rebuilt-variant mechanism "
                      "targets an alternate ACS vintage specifically, so "
                      "spec-pending:02§4.8 would overclaim a landing that "
                      "isn't scoped for ACS. LEAST-BAD DISPOSITION (spec 08 "
                      "A3 handoff, flagged for owner review): pointed at "
                      "anchor_lo/anchor_hi, since ACS's single most "
                      "consequential registry-visible role is the 0.86-ACS "
                      "reading of corr_share (vs 0.75-LODES), already swept "
                      "by that row (see the corr_share entry) -- but this "
                      "does NOT cover ACS's other role feeding S0 base-transit "
                      "shares directly into every draw (only the SE-WIDTH of "
                      "that role is swept, via s0_se_width, which stresses "
                      "the CURRENT vintage's own measurement uncertainty, not "
                      "a vintage SWAP). Recorded here as an imperfect fit, not "
                      "a clean covered-elsewhere claim",
        "rows": {}, "no_row_reason": "covered-elsewhere:anchor_lo",
        "accepted": ("owner-directive 2026-07-11", "2026-07-14"),
        "logged": None, "upgrade": "ACS vintage rebuilt-variant row (mechanism TBD)",
    },
    "gtfs_2026_07": {
        "title": "OCTA GTFS fetch vintage (2026-07)",
        "tier": "data", "status": "active", "basis": "measured",
        "history": [("2026-07-14", "OCTA GTFS 2026-07", "measured",
                     "spec08 A3 harvest -- introduced spec01/spec02, "
                     "scripts/download_data.py")],
        "provenance": "OCTA's published GTFS feed (octa.net/current/"
                      "google_transit.zip), fetched 2026-07 -- shapes, "
                      "headways, scheduled speeds (scripts/download_data.py; "
                      "consumed by build_corridor.py and the rapid_alt config "
                      "branch). The dataset itself is measured; the "
                      "ASSUMPTION is the FETCH-DATE vintage. The base-service "
                      "`rapid_gtfs` row (owned by harbor_service_new, 'rapid "
                      "base -> GTFS current') is a REAL, already-landed "
                      "sensitivity swapping the config's doc-value rapid base "
                      "(15 mph/24-min) for the current GTFS reading (12.8 "
                      "mph/20-min; README key provenance) -- it covers the "
                      "GTFS-vintage exposure for the harbor rapid base "
                      "specifically. It does NOT cover GTFS's other consumers "
                      "(corridor shape geometry / feeder crossings in "
                      "build_corridor.py, the street_cal_local/street_cal_rapid "
                      "calibration points, or the streetcar corridor, which "
                      "has no rapid base and so no rapid_gtfs row) -- a "
                      "partial, not full, coverage; flagged for owner review",
        "rows": {}, "no_row_reason": "covered-elsewhere:rapid_gtfs",
        "accepted": ("owner-directive 2026-07-11", "2026-07-14"),
        "logged": None, "upgrade": "GTFS refetch / periodic re-vintage",
    },
    "ntd_snapshot_2026_07": {
        "title": "NTD monthly-release snapshot vintage (2026-07, behind the UPT leaves)",
        "tier": "data", "status": "active", "basis": "measured",
        "history": [("2026-07-14", "NTD 90036 snapshot 2026-07", "measured",
                     "spec08 A3 harvest -- introduced spec02 s4.6 (R1), "
                     "reweight_abc.py")],
        "provenance": "the dual-source-verified 2026-07 pull of NTD ID 90036 "
                      "monthly-release data (Socrata 8bui-9xvu + the TS2.1 "
                      "2018-release Excel via Wayback, reweight_abc.py "
                      "docstring) behind the upt_fy2013_mb / upt_fy2014_mb / "
                      "upt_fy2017_mb / obs_543_fy2017 constant-tier leaves "
                      "(spec 08 §7: these landed as constant tier, not the "
                      "single data-tier entry originally planned, because "
                      "code imports their literal values -- see §7 note). "
                      "The dataset itself is measured; the ASSUMPTION is the "
                      "SNAPSHOT vintage (which NTD report-year reading to "
                      "trust). Its defensible alternate reading is exactly "
                      "the FY2013-vs-FY2014 back-trend spread those three "
                      "leaf entries already point at the 543_launch14_s500 "
                      "row for -- a genuine, already-owned covering row",
        "rows": {}, "no_row_reason": "covered-elsewhere:543_launch14_s500",
        "accepted": ("owner-directive 2026-07-11", "2026-07-14"),
        "logged": None, "upgrade": "NTD annual refresh",
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
    Priors return the (lo, hi, shape) 3-tuple. List/dict values are returned as
    a shallow copy so a consumer that mutates the result cannot corrupt the
    registry's single source (spec 08 A3 handoff)."""
    v = ASSUMPTIONS[assumption_id]["value"]
    if isinstance(v, (list, dict)):
        return v.copy()
    return v


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
    return GeneratedPriors((k, e["value"]) for k, e in priors)
