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
    status    active | superseded | superseded-kept-as-row | retired
              (plain `superseded`: replaced by a successor entry named in
              the final history element; kept for the append-only record)
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
        "logged": None,
        "upgrade": "APC time-of-day boardings -- records-request item 2 "
                   "time-of-day APC is the evidence gate for any band change "
                   "(post-2020 flattening challenge, external review "
                   "2026-07-17)",
    },
    "vot_behav": {
        "title": "behavioral value of time (fare response)",
        "tier": "prior", "status": "active",
        "value": (10.0, 22.0, "tri"), "order": 12, "units": "$/hr",
        "basis": "literature",
        "history": [("2026-07-11", (10.0, 22.0, "tri"), "literature",
                     "spec08 A1 harvest -- introduced spec06 D3"),
                    ("2026-07-19", (10.0, 22.0, "tri"), "literature",
                     "FB batch: per-draw vot_behav draws now EXPORTED as the "
                     "15th bca_export stream, un-blocking the wrapper's "
                     "vot_wedge row (pre-registered engine-owned in the "
                     "check_assumptions wrapper scan, the roh/fare_sweep "
                     "precedent); band unchanged")],
        "provenance": "behavioral VOT band for the fare-response utility term "
                      "(spec 06 D3); money is never monetized through it. Baked "
                      "into the exported utility, so its wrapper rows "
                      "(vot_behav_lo/vot_behav_hi) read 0.0% at flat fare and need "
                      "a stage-2 re-export to sweep -- exposed regardless (spec 06 "
                      "W1 / rule 2). FB batch 2026-07-19: the per-draw draws "
                      "ship as the bca_export vot_behav stream ($/hr), feeding "
                      "the tbc vot_wedge tornado row (minutes re-priced by THIS "
                      "prior instead of the engine welfare VOT) -- vot_wedge is "
                      "ENGINE-OWNED per the spec 08 s9 Q7 tie-break as written: "
                      "the swept knob is the wrapper's PRICING RULE, not this "
                      "band (the roh/fare_sweep/no_asc_cs precedent -- engine-"
                      "side re-pricings of oc streams stay engine-owned even "
                      "when the price is an oc prior); this entry keeps the "
                      "band-edge claims and this pointer",
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
        "title": "grade-separated cruise speed (ALM; pinned owner design value)",
        "tier": "prior", "status": "active",
        "value": (96.56064, 96.56064, "uni"), "order": 17, "units": "km/h",
        "basis": "judgment",
        "history": [("2026-07-11", (70.0, 90.0, "uni"), "literature",
                     "spec08 A1 harvest -- introduced spec02 s4.9 R6, 23c6cca"),
                    ("2026-07-17", (90.0, 103.2, "uni"), "judgment",
                     "owner decision: design top speed 60 mph; band = "
                     "delivery/degraded-ops uncertainty around the design value"),
                    ("2026-07-18", "(96.56064, 96.56064, uni) — pinned at "
                     "60.000 mph exactly", "judgment",
                     "owner decision 2026-07-18: no cruise-speed variability; "
                     "degenerate uniform preserves rng streams + prior "
                     "fingerprint; supersedes the 90-103.2 band from the "
                     "2026-07-17 60-mph design change")],
        "provenance": "REM-class automated-light-metro cruise speed; owner design "
                      "decision 2026-07-18 PINS the cruise speed at 60.000 mph "
                      "exactly (96.56064 km/h = 60 x 1.609344) with ZERO "
                      "variability -- a degenerate uniform (lo == hi) kept in the "
                      "prior tier so the rng stream ordering and the committed "
                      "prior-order fingerprint are preserved; the lo/hi "
                      "sensitivity rows are expected 0.0%; derived average speed "
                      "(spec 02 s4.9 R6)",
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
                      "average speed (spec 02 s4.9 R6). Anchor-station "
                      "asymmetric tail (external review 2026-07-17): the "
                      "20-30 s range is achievable with PSDs/level boarding "
                      "at the light stations but OPTIMISTIC at the "
                      "Disneyland-area anchor, where surge boardings push the "
                      "tail right; station-level dwell is stage-3 territory "
                      "-- the corridor-uniform draw stands until then",
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
    "asc_calibrated_launch": {
        "title": "launch-equivalent ABC posterior ASC (spec 02 s4.5c premium base)",
        "tier": "constant", "status": "active",
        "value": 0.189, "units": "util", "band": (0.189, 0.378),
        "basis": "locally-calibrated",
        "history": [("2026-07-20", 0.189, "locally-calibrated",
                     "R2 batch (spec02 s4.5c) -- abc_harbor central-kernel "
                     "(543_launch_s500) asc posterior P50 0.18875, rounded to "
                     "the 3dp display convention (asc_calibrated precedent)")],
        "provenance": "the LAUNCH-EQUIVALENT ABC posterior ASC central from the "
                      "bus 543 experiment (abc_harbor.json 543_launch_s500 asc "
                      "P50 = 0.18875 -> 0.189), the base of the spec 02 s4.5c "
                      "ASC-transportability premium rows: forward ASC = "
                      "calibrated ASC x premium, premium in {1.0, 1.5, 2.0} "
                      "(bracket sharpened by the 2026-07-08 elevated-ALM mode "
                      "decision -- the calibration experiments are BUS overlays, "
                      "the forward line is rail-class, so transporting the 543's "
                      "premium at x1.0 is the conservative current assumption; "
                      "README issue 14). The band is the swept bracket span "
                      "(0.189-0.378 = x1.0-x2.0); x1.5 is the interior probe "
                      "row. DISTINCT from asc_calibrated (0.109): that is the "
                      "MATURED-era posterior kept frozen as the streetcar "
                      "display anchor; this entry is the launch-equivalent "
                      "value the s4.5c rows sweep in BOTH corridor tables",
        "rows": {"harbor": ["asc_premium_10", "asc_premium_15",
                            "asc_premium_20"],
                 "streetcar": ["asc_premium_10", "asc_premium_15",
                               "asc_premium_20"]},
        "no_row_reason": None, "accepted": None,
        "logged": "README known-issue 14",
        "upgrade": "post-launch rail-class APC (streetcar ~2027) -- the first "
                   "measured rail-over-bus premium replaces the bracket",
    },
    "induced_eps": {
        "title": "induced-demand elasticity band (side column, spec 02 s4.5b)",
        "tier": "constant", "status": "active",
        "value": (0.1, 0.3), "units": "elasticity (demand w.r.t. transit "
                                      "generalized cost)", "band": (0.1, 0.3),
        "basis": "literature",
        "history": [("2026-07-20", (0.1, 0.3), "literature",
                     "R2 batch (spec02 s4.5b) -- prior U(0.1, 0.3) per the "
                     "spec; side column + band-edge rows, never the headline")],
        "provenance": "total-demand elasticity to the accessibility change "
                      "(spec 02 s4.5b): the 'with induced demand' SIDE COLUMN "
                      "applies a per-cell multiplier (GC1/GC0)^-eps to the "
                      "post-pivot transit mass, GC measured by the transit "
                      "choice-model utility (ls1/ls0 -- bivt cancels, so the "
                      "ratio is a generalized-cost ratio); eps ~ U(0.1, 0.3) "
                      "drawn per draw on a THIRD SeedSequence child stream "
                      "(consumes no existing rng; not a PRIORS key, so the "
                      "prior-order fingerprint and every committed draw are "
                      "untouched). Market creation is OUT OF SCOPE of the "
                      "pivot by construction (spec 02 s1), so this column is "
                      "clearly labeled, NEVER the headline and NEVER a gate "
                      "criterion; the induced_lo/induced_hi rows pin eps at "
                      "the band edges and report the induced-inclusive "
                      "expected blend vs the headline base",
        "rows": {"harbor": ["induced_lo", "induced_hi"],
                 "streetcar": ["induced_lo", "induced_hi"]},
        "no_row_reason": None, "accepted": None,
        "logged": None,
        "upgrade": "STOPS total-demand response / observed post-launch "
                   "corridor totals",
    },
    "induced_gc_clip": {
        "title": "induced-column GC-ratio clip (numerical guard)",
        "tier": "constant", "status": "active",
        "value": (0.05, 20.0), "units": "ratio", "band": None,
        "basis": "judgment",
        "history": [("2026-07-20", (0.05, 20.0), "judgment",
                     "R2 review fix -- was a bare literal in model.py's new "
                     "induced-column path; registry-owned per house rule")],
        "provenance": "np.clip on GC1/GC0 (= ls1/ls0, transit choice-model "
                      "logsums) before the (GC1/GC0)^-eps induced multiplier "
                      "(spec 02 s4.5b): a numerical guard against a "
                      "vanishing/blowing-up logsum ratio, not an assumption "
                      "doing work at central (GC ratios sit near 1; the clip "
                      "never binds on the shipped draws) -- the s0_pivot_clip "
                      "idiom applied to the induced side column; rowless via "
                      "the non-binding disposition like s0_pivot_clip, NOT "
                      "laundered as definitional",
        "rows": {}, "no_row_reason": "non-binding:review-2026-07-20",
        "accepted": ("R2 review fix 2026-07-20", "2026-07-20"),
        "logged": None, "upgrade": None,
    },

    # ---- reweight_abc.py -------------------------------------------------
    "upt_fy2013_mb": {
        "title": "OCTA annual bus UPT, motorbus, FY2013 (NTD 90036)",
        "tier": "constant", "status": "active",
        "value": 51_067_292, "units": "unlinked trips/yr", "band": None,
        "basis": "measured",
        "history": [("2026-07-11", 51_067_292, "measured",
                     "spec08 A1 harvest -- introduced spec02 s4.6 (R1), 0e710db"),
                    ("2026-07-20", 51_067_292, "measured",
                     "R2 batch: value unchanged; entry gains the "
                     "543_launch_bt_s507 back-trend-BAND kernel row (the "
                     "standing README-issue-13 promise that the vintage "
                     "factor's uncertainty be carried explicitly, not only "
                     "as the discrete FY2014 alternative)")],
        "provenance": "NTD ID 90036 annual bus UPT (MB, DO+PT), FY2013; "
                      "dual-source verified (Socrata 8bui-9xvu + TS2.1 2018 "
                      "Excel); the central back-trend numerator (feeds the CENTRAL "
                      "kernel 543_launch_s500, which is not a sensitivity row). "
                      "Owns the 543_launch_bt_s507 ABC kernel row: the back-trend "
                      "factor treated as UNCERTAIN, B ~ U(FY2014 ratio 1.2236, "
                      "FY2013 ratio 1.2868) -- the 543 launched June 2013, "
                      "exactly the FY2013/FY2014 fiscal boundary, so the two "
                      "annual readings bracket the launch instant -- "
                      "marginalized into the Gaussian kernel form the ABC "
                      "machinery uses: mu = 4,615 x mid(B) ~ 5,793, sigma = "
                      "sqrt(500^2 + (4,615 x (B13-B14))^2 / 12) ~ 507 (the "
                      "Gaussian approximation of the exact uniform-convolution "
                      "is sub-0.1% here since the uniform half-width ~146 << "
                      "sigma 500). REJECTED ALTERNATIVE: a second mu-shifted "
                      "discrete kernel -- redundant, the FY2014-anchored "
                      "reading already exists as 543_launch14_s500 "
                      "(upt_fy2014_mb). The tbc welfare-BCA wrapper stays on "
                      "the CENTRAL kernel (543_launch_s500) -- this kernel is "
                      "an oc-side sensitivity only, deliberately NOT a wrapper "
                      "tornado row (the abc_s350/abc_s800 wrapper rows remain "
                      "the wrapper's ABC-width exposure). The FY2013-vs-FY2014 "
                      "vintage CHOICE sensitivity remains 543_launch14_s500",
        "rows": {"abc": ["543_launch_bt_s507"]},
        "no_row_reason": None,
        "accepted": ("owner-directive 2026-07-11", "2026-07-11"),
        "logged": "README known-issue 13", "upgrade": "NTD annual refresh",
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
        "title": "corridor tract inclusion buffer (SHARED: stage-2 corridors "
                 "+ stage-1 screen)",
        "tier": "constant", "status": "active",
        "value": 0.9, "units": "mi", "band": (0.5, 1.25), "basis": "judgment",
        "history": [("2026-07-11", 0.9, "definitional",
                     "spec08 A1 harvest -- introduced spec01/spec02"),
                    ("2026-07-18", 0.9, "judgment",
                     "spec01 Q1 + external challenge 2026-07-17 -- basis "
                     "definitional->judgment (a catchment radius with a "
                     "defensible 0.5 alternative is a judgment, not a "
                     "definition); band (0.5, 1.25); the rowless quality-knob "
                     "disposition is superseded by screen rows "
                     "buffer_lo/buffer_hi (panel D13)"),
                    ("2026-07-19", 0.9, "judgment",
                     "FB batch: the QUEUED stage-2 rebuilt-variant rows "
                     "LANDED -- buffer_0p5/buffer_0p75 in BOTH corridor "
                     "results (build_corridor --variant buffer_0p5/buffer_"
                     "0p75, the intra_tract_alt mechanism on the buffer "
                     "axis); closes the 2026-07-18 'queued, not landed' "
                     "promise; value unchanged"),
                    ("2026-07-20", 0.9, "judgment",
                     "spec01 §9.2 pre-registration (phase 2a) -- THIRD "
                     "consumer: the v2.1 block-resolution catchment "
                     "(screen_common_v21) applies the SAME entry to block "
                     "internal points, the tract rule verbatim; the "
                     "centroid-test approximation of buffer-polygon "
                     "intersection is stated in-spec. Value, band and the "
                     "buffer_lo/buffer_hi rescan rows unchanged -- they "
                     "carry over to the phase-2b rebuilt scan")],
        "provenance": "centroid-within distance for corridor tract membership; "
                      "ONE entry, TWO consumers (the corr_share precedent, "
                      "spec 08 §2): build_corridor.py's stage-2 corridors AND "
                      "the spec 01 screen's shared compute_predictors "
                      "catchment cite the same id, so drift is machine-"
                      "visible. The value is under EXTERNAL CHALLENGE as a "
                      "stage-2 constant (2026-07-17), which raises -- not "
                      "lowers -- the bar for its stage-1 reuse: the screen "
                      "sweeps BOTH band edges as full-rescan rows (buffer_lo "
                      "= 0.5 / buffer_hi = 1.25); the stage-2 corridor-"
                      "membership rebuilt-variant rows LANDED 2026-07-19 (FB "
                      "batch): buffer_0p5 / buffer_0p75 in BOTH corridor "
                      "results (build_corridor --variant, the intra_tract_alt "
                      "mechanism on the buffer axis) -- the empirical answer "
                      "to the reviewer's '0.9-mi tail is doing real work' "
                      "challenge. Challenge + unification logged (README "
                      "known-issue 30)",
        "rows": {"screen": ["buffer_lo", "buffer_hi"],
                 "harbor": ["buffer_0p5", "buffer_0p75"],
                 "streetcar": ["buffer_0p5", "buffer_0p75"]},
        "no_row_reason": None,
        "accepted": None,
        "logged": "README known-issue 30",
        "upgrade": "post-launch observed access-distance distribution "
                   "(on-board survey / APC stop-level boardings)",
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
    # map into feeder_headway), so they are RULE-BEARING, not documentation.
    # spec 07 §9 N4 CONVERTED these from spec-pending to network-artifact CLAIMS:
    # each declares a row in outputs/network_sequence.json's assumptions_manifest
    # (check_assumptions' network scan). Their §8i/§10 G7 sensitivity rows
    # (uniform-along-line + walk-bin-mass omega, exclusive-tract, peak-mapped
    # feeder headway) live in that artifact's sensitivity block, harness-internal
    # (engine-owned, exempt). NO new priors (constant tier only; the prior-order
    # fingerprint is untouched).
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
        "rows": {"network": ["omega_allocation"]},
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
        "rows": {"network": ["omega_stop_materialization"]},
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
        "rows": {"network": ["feeder_headway_map"]},
        "accepted": ("spec07-N1a network-mechanics landing", "2026-07-16"),
        "logged": None, "upgrade": "committed-line published service plan",
    },

    # ---- sequence_network.py knobs (spec 07 N1b sequencing harness) -------
    # The three harness-level knobs the greedy loop introduces. CONSTANT tier
    # (NOT priors -- none is consumed by draw_params, so the prior-order
    # fingerprint is untouched, exactly as N1a promised). Each carries a band so
    # its lo/hi (or cap 1/3) sensitivity rows can source their edges. spec 07 §9
    # N4 CONVERTED these from spec-pending to network-artifact CLAIMS: check_-
    # assumptions now scans outputs/network_sequence.json, and each knob claims
    # its assumptions_manifest row there (its G7 lo/hi sensitivity rows are
    # harness-internal / engine-owned in the scan). cycle_gap is §11 Q1's exposed
    # knob (prior U(4,8) yr as a CONCEPT -- but a harness constant, not a
    # draw_params prior).
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
        "rows": {"network": ["cycle_gap"]},
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
        "rows": {"network": ["network_budget"]},
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
        "rows": {"network": ["depth_cap"]},
        "accepted": ("spec07-N1b sequencing-harness landing", "2026-07-16"),
        "logged": None, "upgrade": "adopted provenance-governance threshold",
    },

    # ---- capcost.py (spec 04 capital rate card as code, spec 07 N2) -------
    # PRE-markup line-item leaves (2026 US$M) from costs/metro_cost_model.xlsx
    # §2 / spec 04 §2. capcost.capital() DERIVES the markup-inclusive
    # coefficients (Fixed 183.6 / 23.4 route-km / 27.6 elevated / 33.96 station
    # / 7.44 car) from these leaves x cap_markup_low (E55-locked). spec 07 §9 N4
    # CONVERTED these from spec-pending to network-artifact CLAIMS: each rate-card
    # leaf is declared in outputs/network_sequence.json's assumptions_manifest
    # (the harness/capcost CONSUME it -> the capital bands + the run_id values-
    # hash), and the registry claims that declaration (check_assumptions' network
    # scan). The capital G7 rows (fixed_cost_share {1,0.5,0}) live in that
    # artifact's sensitivity block, harness-internal. NO tbc-wrapper capital rows
    # exist to claim. NO new priors (constant tier only).
    "cap_occ": {
        "title": "operations control centre (fixed capital)",
        "tier": "constant", "status": "active",
        "value": 28.0, "units": "$M", "band": None, "basis": "measured",
        "history": [("2026-07-16", 28.0, "measured",
                     "spec07 N2 -- spec 04 §2 rate card as code")],
        "provenance": "OCC fixed capital, REM-calibrated rate card "
                      "(costs/metro_cost_model.xlsx §2, spec 04 §2). Part of the "
                      "fixed term (OCC + depot) the §8j fixed_cost_share knob scales",
        "rows": {"network": ["cap_occ"]},
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
        "rows": {"network": ["cap_depot"]},
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
        "rows": {"network": ["cap_route_km"]},
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
        "rows": {"network": ["cap_viaduct_km"]},
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
        "rows": {"network": ["cap_station"]},
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
        "rows": {"network": ["cap_car"]},
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
        "rows": {"network": ["cap_markup_low"]},
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
        "rows": {"network": ["cap_markup_ut"]},
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
        "rows": {"network": ["cap_delivery_ut"]},
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
        "rows": {"network": ["cap_crossing_low"]},
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
        "rows": {"network": ["cap_crossing_ut"]},
        "accepted": ("spec07-N2 rate-card landing", "2026-07-16"),
        "logged": None, "upgrade": "engineering reference per crossing (spec 04 §3.3)",
    },

    # ---- stage-1 DRM screen constants (spec 01 §5b; S2 landing) -----------
    # Stage-1 materiality convention (spec 01 §4): a `screen` sensitivity
    # row's pct = 100 * (1 - Spearman rho of the full window ranking vs
    # headline) -- rank churn, never a ridership delta (stage-1 scores are
    # ordinal only, spec 00 §1; there is no ridership headline to move).
    # ALL screen row ids are oc-registry-owned: the screen has no engine, so
    # no engine-owned exemption set applies to the check_assumptions
    # `screen` artifact scan (spec 01 §5b; unlike wrapper/network).
    "screen_window_mi": {
        "title": "screen window length (stage-1 county-wide scan)",
        "tier": "constant", "status": "active",
        "value": 12.5, "units": "mi", "band": (10.0, 15.0), "basis": "judgment",
        "history": [("2026-07-18", 12.5, "judgment",
                     "spec01 S2 -- panel D5: FIXED window length (a swept "
                     "length makes windows of different lengths incomparable "
                     "within one scan); 12.5 = the 13-arterial prototype's "
                     "best-window length")],
        "provenance": "fixed sliding-window length for the mechanical scan "
                      "universe (spec 01 §3.2): every weekday GTFS route "
                      "shape with main-shape length >= this. Measured counts: "
                      "53 weekday shapes; ~612 windows at 12.5 mi (846 at 10, "
                      "430 at 15). Judgment resting on the prototype "
                      "precedent -- the near-circularity of leaning on the "
                      "prototype is logged (README known-issue 31). Both band "
                      "edges are full-rescan sensitivity rows",
        "rows": {"screen": ["window_10", "window_15"]},
        "no_row_reason": None, "accepted": None,
        "logged": "README known-issue 31",
        "upgrade": "ALM line-length economics study (spec 04)",
    },
    "screen_step_mi": {
        "title": "screen window slide step",
        "tier": "constant", "status": "active",
        "value": 0.5, "units": "mi", "band": None, "basis": "judgment",
        "history": [("2026-07-18", 0.5, "judgment",
                     "spec01 S2 -- panel D5 window semantics; w0 = k*0.5 "
                     "exactly (integer k, never accumulated floats)")],
        "provenance": "window slide step for the scan (spec 01 §3.2); a "
                      "resolution knob -- a finer step adds near-duplicate "
                      "windows the overlap grouping collapses, it does not "
                      "reorder distinct corridors",
        "rows": {}, "no_row_reason": "quality-knob",
        "accepted": ("spec01 panel adjudication 2026-07-18", "2026-07-18"),
        "logged": None, "upgrade": "finer-step rescan",
    },
    "screen_overlap_threshold": {
        "title": "screen overlap-grouping threshold (shared catchment tracts)",
        "tier": "constant", "status": "active",
        "value": 0.30, "units": "share", "band": (0.2, 0.4), "basis": "judgment",
        "history": [("2026-07-18", 0.30, "judgment",
                     "spec01 S2 -- panel D17; connected components over "
                     "windows sharing > threshold of catchment tracts")],
        "provenance": "windows sharing more than this fraction of catchment "
                      "tracts are grouped by connected components "
                      "(deterministic group ids = lexicographically smallest "
                      "member window_id) so gate 1 cannot double-count "
                      "central Santa Ana demand (spec 01 §3.3). Grouping "
                      "addresses double-counted DEMAND; correlated errors "
                      "across windows are the joint bootstrap's job (§3.4). "
                      "Both band edges are regrouping sensitivity rows. "
                      "MEASURED DEGENERACY (review 2026-07-19): the "
                      "components collapse to ONE county-wide group at 0.30 "
                      "(one at 0.2, two at 0.4) -- single-linkage "
                      "transitivity defeats the dedup purpose; gate 1 uses "
                      "the artifact's overlap_diagnostics (best window per "
                      "host shape + per-pair shares) instead. A non-chaining "
                      "regrouping is an open owner decision (spec 01 §3.3 "
                      "caveat)",
        "rows": {"screen": ["overlap_lo", "overlap_hi"]},
        "no_row_reason": None, "accepted": None,
        "logged": "README known issue 34",
        "upgrade": "non-chaining grouping (complete-linkage or "
                   "host-shape-scoped) -- owner decision",
    },
    "screen_svc_std": {
        "title": "standardized service level (median FY2019 RVH per route-mile)",
        "tier": "constant", "status": "active",
        "value": 1577.65, "units": "rev-hr/route-mi/yr",
        "band": (1119.07, 2773.07), "basis": "measured",
        "history": [("2026-07-18", 1577.65, "measured",
                     "spec01 S2 -- panel D8: computed from route_boardings.csv "
                     "rvh_fy2019 / GTFS main-shape miles over the 41 fitted "
                     "routes (S2 derivation)"),
                    ("2026-07-19", 1577.65, "measured",
                     "SC batch (external critique): value unchanged; the "
                     "index NORMALIZATION built on this entry is REBASED to "
                     "same-exposure -- baseline 100 = median over fitted "
                     "host routes of each route's own BEST 12.5-mi-window "
                     "prediction at svc_std, replacing the median fitted "
                     "route AT ITS OWN LENGTH (a length artifact: with "
                     "b3+b5 = +0.917 per log-mile and 12.5-mi windows vs an "
                     "~18-mi median route, no window could mechanically "
                     "exceed ~72). Positive scalar multiple -- ranks "
                     "unchanged, asserted by a standing test (README "
                     "known-issue 36)")],
        "provenance": "svc_std = median over the 41 fitted routes (the "
                      "route_boardings.csv x 2026-07 GTFS weekday-shape "
                      "intersection; the 6 discontinued routes 24/53X/57X/"
                      "64X/82/153 drop out) of FY2019 annual revenue hours "
                      "per main-shape route-mile: rvh_fy2019 (extract_apc.py, "
                      "b/RVH-validated to 2dp) / build_corridor.main_shape_xy "
                      "length. Median 1577.65 (Route 30's 32,134 / 20.368 mi; "
                      "Route 43 reads 3,739.0); the band records the "
                      "distribution's p25 1119.07 (Route 33) / p75 2773.07 "
                      "(Route 55) = the svc_p25/svc_p75 probe rows. Windows "
                      "are scored at svc_std x window length -- a "
                      "PRESENTATION convention, not an identification fix "
                      "(spec 01 §1/§3.2): a single additive b3 term shifts "
                      "every window's log-score by the same constant, so the "
                      "probes are expected rank-inert; the rows PROVE that "
                      "rather than asserting it. The index-normalization "
                      "choice built on top is logged (README known-issue 33); "
                      "its 2026-07-19 same-exposure rebase (best "
                      "12.5-mi-window-per-fitted-route baseline; old ceiling "
                      "~72 was mechanical) is known-issue 36",
        "rows": {"screen": ["svc_p25", "svc_p75"]},
        "no_row_reason": None, "accepted": None,
        "logged": "README known-issue 36 (same-exposure rebase; the "
                  "normalization choice itself = known-issue 33)",
        "upgrade": "records request items 1a/1b (post-FY2021 RVH refresh)",
    },
    "screen_n_boot": {
        "title": "screen route-cluster bootstrap replicate count",
        "tier": "constant", "status": "active",
        "value": 2000, "units": "replicates", "band": None, "basis": "judgment",
        "history": [("2026-07-18", 2000, "judgment",
                     "spec01 S2 -- panel D9 route-cluster bootstrap")],
        "provenance": "B replicates: resample ROUTES with replacement, refit, "
                      "rescore ALL windows jointly per replicate (spec 01 "
                      "§3.4; cross-window correlation captured for free). A "
                      "convergence/resolution knob for the p10/p90, rank_ci "
                      "and tie_with_cutoff outputs, not a rank-affecting "
                      "choice",
        "rows": {}, "no_row_reason": "quality-knob",
        "accepted": ("spec01 panel adjudication 2026-07-18", "2026-07-18"),
        "logged": None, "upgrade": "convergence study",
    },
    "screen_seed": {
        "title": "screen bootstrap RNG seed",
        "tier": "constant", "status": "active",
        "value": 7, "units": "seed", "band": None, "basis": "definitional",
        "history": [("2026-07-18", 7, "definitional",
                     "spec01 S2 -- panel D9; single seeded default_rng, "
                     "determinism checklist item 5")],
        "provenance": "the single numpy default_rng seed behind the screen's "
                      "route-cluster bootstrap + within-replicate ACS MOE "
                      "perturbation (spec 01 §3.4); part of the "
                      "dual-generation byte-identity gate (spec 01 §6)",
        "rows": {}, "no_row_reason": "quality-knob",
        "accepted": ("spec01 panel adjudication 2026-07-18", "2026-07-18"),
        "logged": None, "upgrade": None,
    },
    "screen_loo_rho": {
        "title": "screen LOO-route rank-stability floor (leverage screen)",
        "tier": "constant", "status": "active",
        "value": 0.9, "units": "Spearman rho", "band": None, "basis": "judgment",
        "history": [("2026-07-18", 0.9, "judgment",
                     "spec01 S2 -- review 2026-07-08 comment 16 threshold, "
                     "DEMOTED by panel D12 from primary gate to leverage "
                     "screen (single-route deletion barely moves a 41-route "
                     "fit)")],
        "provenance": "leave-one-ROUTE-out Spearman rho floor (spec 01 §5) -- "
                      "a leverage screen only; the PRIMARY gate is the "
                      "rank-stability battery whose perturbations are the "
                      "screen artifact's sensitivity rows. An acceptance-"
                      "threshold knob, not a swept model quantity",
        "rows": {}, "no_row_reason": "quality-knob",
        "accepted": ("spec01 panel adjudication 2026-07-18", "2026-07-18"),
        "logged": None, "upgrade": "post-records-request panel extension",
    },
    "screen_male": {
        "title": "screen LOO median-absolute-log-error ceiling (secondary)",
        "tier": "constant", "status": "active",
        "value": 0.35, "units": "log points", "band": None, "basis": "judgment",
        "history": [("2026-07-18", 0.35, "judgment",
                     "spec01 S2 -- review 2026-07-08 comment 16, retained as "
                     "a secondary diagnostic by panel D12")],
        "provenance": "LOO median absolute log error ceiling (~±40% on a "
                      "held-out route); secondary diagnostic, worst-5 routes "
                      "named in fit_diagnostics (spec 01 §5). An acceptance-"
                      "threshold knob, not a swept model quantity",
        "rows": {}, "no_row_reason": "quality-knob",
        "accepted": ("spec01 panel adjudication 2026-07-18", "2026-07-18"),
        "logged": None, "upgrade": "post-records-request panel extension",
    },
    # -- decision tripwire v2 (owner review 2026-07-20 of the SC-batch
    # pre-registration). Criterion 1 REVISED AND RATIFIED as a signed
    # bootstrap fraction (screen_pos_frac_min; screen_t_min superseded);
    # criterion 2 keeps its statistic with a PROVISIONAL value pending the
    # owner's decision on the shortlist-stability report; criterion 3's
    # statistic is REBUILT as margin-defined tie-set churn with NO value
    # yet (screen_top8_churn_max superseded; the successor threshold entry
    # lands when the owner sets it). ordinal_ok requires all criteria to
    # pass and an unset threshold cannot pass -> false-by-construction
    # until the owner sets 2/3 (the intended fail-safe). Mechanized in
    # screen_scan.py's decision_output block; live ids consumed via val()
    # (the check_assumptions screen scan verifies the consumption
    # declaration). Acceptance-threshold knobs -> rowless quality-knob.
    "screen_t_min": {
        "title": "screen tripwire: per-demand-coefficient minimum |t| "
                 "(cluster-robust) -- SUPERSEDED by screen_pos_frac_min",
        "tier": "constant", "status": "superseded",
        "value": 1.0, "units": "|t|", "band": None, "basis": "judgment",
        "history": [("2026-07-19", 1.0, "judgment",
                     "SC batch -- external critique 2026-07-19: the screen's "
                     "primary gate was thresholdless (no pre-registered "
                     "pass/fail); tripwire criterion (i)"),
                    ("2026-07-20", 1.0, "judgment",
                     "owner review 2026-07-20: NOT ratified as written -- "
                     "criterion 1 REVISED to the signed bootstrap-fraction "
                     "form (successor: screen_pos_frac_min = 0.841 = "
                     "Phi(1)). Cluster-robust analytic SEs are "
                     "downward-biased at ~41 clusters (the bias runs toward "
                     "pass), so the analytic |t| is demoted to a reported "
                     "diagnostic (decision_output.diagnostics"
                     ".min_abs_t_demand) and this entry is SUPERSEDED")],
        "provenance": "SUPERSEDED (owner review 2026-07-20) by "
                      "screen_pos_frac_min -- the signed bootstrap-fraction "
                      "form of criterion 1; the analytic cluster-robust |t| "
                      "survives only as a decision_output diagnostic. "
                      "Original: criterion (i) of the pre-registered "
                      "tripwire (spec 01 §5): every demand-block coefficient "
                      "(b1, b2) must have cluster-robust |t| >= this for "
                      "the ordinal ranking to be decision-grade. Measured "
                      "at landing: min |t| = 0.81 (b2_e002) -> FAILS",
        "rows": {}, "no_row_reason": "quality-knob",
        "accepted": ("superseded by owner review (revised criterion 1: "
                     "signed bootstrap-fraction)", "2026-07-20"),
        "logged": "README known-issue 38 (opened as 35)",
        "upgrade": None,
    },
    "screen_pos_frac_min": {
        "title": "screen tripwire criterion 1 (revised, ratified): minimum "
                 "demand-coefficient bootstrap positive-sign fraction",
        "tier": "constant", "status": "active",
        "value": 0.841, "units": "fraction of replicates", "band": None,
        "basis": "judgment",
        "history": [("2026-07-20", 0.841, "judgment",
                     "owner review 2026-07-20 -- REVISED criterion 1, "
                     "ratified: replaces screen_t_min's analytic "
                     "cluster-robust |t| >= 1.0 (superseded entry points "
                     "forward here)")],
        "provenance": "criterion 1 of the decision tripwire (spec 01 §5, "
                      "revised and RATIFIED 2026-07-20): for EACH "
                      "demand-block coefficient -- the demand block is "
                      "{b1_lodes, b2_e002}; b4 is OUTSIDE it per the "
                      "artifact's own grouped decomposition (its wrong-sign "
                      "risk is priced by the b4_off battery row and v2.1 "
                      "replaces the dummy with measured WAC generator jobs; "
                      "b4's per-replicate sign IS still reported as a "
                      "diagnostic) -- the fraction of the B=2000 "
                      "route-cluster bootstrap replicates with a STRICTLY "
                      "POSITIVE coefficient must be >= this. Basis: 0.841 = "
                      "Phi(1), the one-sided translation of |t| >= 1 with "
                      "the sign requirement added; t = 1 is the threshold "
                      "at which a regressor improves adjusted R-squared and "
                      "out-of-sample prediction error -- the "
                      "decision-theoretic minimum for carrying a variable "
                      "at all. The bootstrap-fraction form replaces the "
                      "analytic cluster-SE t because cluster-robust SEs are "
                      "downward-biased at ~41 clusters (bias toward pass); "
                      "the analytic |t| values stay as reported "
                      "diagnostics. Signs are recorded in the EXISTING "
                      "headline bootstrap (no new compute); pos_frac "
                      "recomputable from the artifact's replicate_signs "
                      "strings (test_screen.py D6). Measured at "
                      "ratification (v2.0 build): b1_pos_frac 0.8115, "
                      "b2_pos_frac 0.7435 -> FAILS",
        "rows": {}, "no_row_reason": "quality-knob",
        "accepted": ("owner-ratified (revised criterion 1: signed "
                     "bootstrap-fraction)", "2026-07-20"),
        "logged": "README known-issue 38",
        "upgrade": "v2.1 rebuilt fit (spec 01 §9)",
    },
    "screen_battery_rho_min": {
        "title": "screen tripwire criterion 2: battery minimum Spearman rho "
                 "(value provisional)",
        "tier": "constant", "status": "active",
        "value": 0.7, "units": "Spearman rho", "band": None,
        "basis": "judgment",
        "history": [("2026-07-19", 0.7, "judgment",
                     "SC batch -- external critique 2026-07-19: tripwire "
                     "criterion (ii)"),
                    ("2026-07-20", 0.7, "judgment",
                     "owner review 2026-07-20: statistic KEPT (battery min "
                     "Spearman rho, LOYO excluded); the 0.7 value is "
                     "PROVISIONAL pending the owner's decision on the "
                     "shortlist-stability report. RETRACTION recorded: any "
                     "e016-anchored calibration story for 0.7 is RETRACTED "
                     "-- it tuned the bar to an observed value (e016_swap's "
                     "measured rho 0.746) and that example fails criterion "
                     "3 anyway (top-8 churn 8); no such story may be cited "
                     "as this entry's basis")],
        "provenance": "criterion 2 of the decision tripwire (spec 01 §5): "
                      "the minimum Spearman rho over the pre-registered "
                      "battery perturbations (the FROZEN screen_battery_rows "
                      "list; the leave-one-year-out consistency check is "
                      "EXCLUDED -- mechanically near-1 with time-invariant "
                      "X) must be >= this. Value PROVISIONAL (owner sets it "
                      "after the shortlist-stability report). Measured at "
                      "landing: min rho = 0.39 (buffer_lo) -> FAILS",
        "rows": {}, "no_row_reason": "quality-knob",
        "accepted": ("statistic owner-ratified 2026-07-20; VALUE provisional "
                     "pending owner post-report", "2026-07-20"),
        "logged": "README known-issue 38 (opened as 35)",
        "upgrade": "owner post-report value decision; v2.1 rebuilt fit",
    },
    "screen_top8_churn_max": {
        "title": "screen tripwire: max top-8 membership changes per "
                 "perturbation -- SUPERSEDED (statistic rebuilt as "
                 "margin-defined tie-set churn)",
        "tier": "constant", "status": "superseded",
        "value": 2, "units": "windows", "band": None, "basis": "judgment",
        "history": [("2026-07-19", 2, "judgment",
                     "SC batch -- external critique 2026-07-19: tripwire "
                     "criterion (iii)"),
                    ("2026-07-20", 2, "judgment",
                     "owner review 2026-07-20: criterion 3's statistic "
                     "REBUILT as margin-defined tie-set churn (max "
                     "tie_churn_frac across battery rows, artifact "
                     "shortlist_stability block); hard-top-8 churn is "
                     "demoted to a per-row diagnostic column with an "
                     "explicit unit field ('window_id'; 'host_shape' for "
                     "window_10/window_15). NO successor threshold value "
                     "yet -- the owner sets it after the "
                     "shortlist-stability report; until then "
                     "decision_output.criteria.tie_churn carries threshold "
                     "null / pass null (an unset threshold cannot pass -- "
                     "fail-safe)"),
                    ("2026-07-20", 2, "judgment",
                     "criterion-3 UNIT FIX (owner blocking item, same-day "
                     "follow-up): the successor statistic's max scans "
                     "WINDOW-UNIT rows ONLY -- window_10/window_15 change "
                     "the window UNIVERSE, so their churn is measured in "
                     "host-shape units (denominator 14 vs 46 at the "
                     "review build; one flip reads 7.1% vs 2.2%), a "
                     "3.3x-coarser lossy proxy, and cross-universe "
                     "membership churn is a category mismatch a scalar "
                     "threshold cannot compare. The two rows remain fully "
                     "in criterion 2's min-rho (best-per-shape rankings, "
                     "unit-consistent) and in the shortlist_stability "
                     "report; the aggregate names them in "
                     "criterion3_excluded_rows. IMPLEMENTED, PENDING "
                     "OWNER RATIFICATION with the criterion-2/3 threshold "
                     "values (spec 01 §5)")],
        "provenance": "SUPERSEDED (owner review 2026-07-20): the hard "
                      "rank-8 cut measured churn against an arbitrary "
                      "boundary while the decision object is the "
                      "MARGIN-DEFINED tie set; the rebuilt criterion-3 "
                      "statistic is max tie-set churn across battery rows "
                      "(shortlist_stability.aggregate.max_tie_churn_frac) "
                      "and its threshold entry lands when the owner sets "
                      "it. Original: criterion (iii) -- top-8 membership "
                      "changes under every battery perturbation <= this. "
                      "Measured at landing: max churn = 8 (buffer_lo) -> "
                      "FAILS",
        "rows": {}, "no_row_reason": "quality-knob",
        "accepted": ("superseded by owner review (criterion-3 statistic "
                     "rebuild; value deferred)", "2026-07-20"),
        "logged": "README known-issue 38 (opened as 35)",
        "upgrade": None,
    },
    "screen_battery_rows": {
        "title": "screen battery: FROZEN perturbation row list (structural "
                 "governance)",
        "tier": "constant", "status": "active",
        "value": ["buffer_lo", "buffer_hi", "window_10", "window_15",
                  "drop_fy2020", "drop_rh", "e016_swap", "b4_off",
                  "gen_leave_class_out", "nb_estimator", "svc_p25",
                  "svc_p75", "offset_variant", "overlap_lo", "overlap_hi",
                  "year_fe_vs_pooled"],
        "units": "battery row ids", "band": None, "basis": "definitional",
        "history": [("2026-07-20", "16 frozen battery row ids",
                     "definitional",
                     "owner review 2026-07-20 -- battery FROZEN: the "
                     "battery criterion is a MIN, so adding a row can only "
                     "lower it and deleting a row can only raise it; "
                     "adding or dropping a row is therefore an "
                     "owner-approved spec amendment (spec 01 §5/§9), never "
                     "a build patch")],
        "provenance": "the exact sensitivity row ids constituting the §5 "
                      "battery (LOYO excluded as a consistency check). "
                      "STRUCTURAL-GOVERNANCE entry carried at constant "
                      "tier: the registry's structural tier is "
                      "machine-checked to own enumerated-alternative rows "
                      "(check 5) and this entry instead freezes a LIST, "
                      "consumed via val() by screen_scan.py (battery order "
                      "+ shortlist_stability) and asserted row-for-row "
                      "against the artifact by test_screen.py. Declared in "
                      "the screen artifact's assumptions_manifest (check-2 "
                      "consumption declaration, tripwire pattern)",
        "rows": {}, "no_row_reason": "definitional",
        "accepted": ("owner-directed battery freeze (criteria 2/3 "
                     "statistics rebuild)", "2026-07-20"),
        "logged": "README known-issue 38",
        "upgrade": None,
    },
    "screen_battery_rows_v21": {
        "title": "v2.1 screen battery: CLOSED perturbation row list for "
                 "the phase-2b verdict (frozen pre-fit)",
        "tier": "constant", "status": "active",
        "value": ["buffer_lo", "buffer_hi", "window_10", "window_15",
                  "drop_fy2020", "drop_rh", "e016_swap", "e002_swap",
                  "popden_swap", "genjobs_off", "genjobs_leave_class_out",
                  "gen_dummy_swap", "nb_estimator", "svc_p25", "svc_p75",
                  "offset_variant", "overlap_lo", "overlap_hi",
                  "year_fe_vs_pooled", "loyo"],
        "units": "battery row ids", "band": None, "basis": "definitional",
        "history": [("2026-07-20", "20 frozen v2.1 battery row ids",
                     "definitional",
                     "owner item 2 2026-07-20 -- v2.1 battery FROZEN NOW, "
                     "on ACQUISITION FACTS ONLY (before any v2.1 input is "
                     "fitted; the owner's criterion-2/3 threshold values "
                     "attach to THIS list for the phase-2b verdict). "
                     "Composition: the 14 v2.0 window-unit rows carried "
                     "over WITH the two generator rows REDEFINED against "
                     "§9.1's continuous WAC term (b4_off -> genjobs_off = "
                     "drop l_genjobs; gen_leave_class_out -> "
                     "genjobs_leave_class_out = drop ONE NAICS sector "
                     "from the CNS15-18 sum, class-max aggregation "
                     "carried over); PLUS the §9.1 swaps popden_swap / "
                     "e002_swap / gen_dummy_swap; PLUS window_10/"
                     "window_15 (CRITERION-2-ONLY, flagged -- the §5 "
                     "criterion-3 unit fix excludes their host-shape-unit "
                     "churn from the tie-churn max); MINUS sld_swap, "
                     "EXCLUDED because the EPA SLD was NOT acquired in "
                     "phase 1 (§9.1 made the row conditional on "
                     "acquisition -- decided on that acquisition fact, "
                     "never on fit results); PLUS loyo, RETURNED per the "
                     "§9.3 condition resolved IN THIS BATCH on the "
                     "measured input-side fact (screen_power_check "
                     "artifact x_variation: every vintage-matched "
                     "predictor -- l_flows / l_zveh_hh / l_genjobs -- has "
                     "nonzero within-route across-year variance for "
                     "share 1.0 of the 41 fitted routes)")],
        "provenance": "the CLOSED battery for the spec 01 §9.5 phase-2b "
                      "verdict: criterion 2's min-rho runs over ALL 20 "
                      "rows; criterion 3's tie-churn max runs over the "
                      "WINDOW-UNIT rows only (window_10/window_15 "
                      "excluded per the §5 unit fix). Freezing NOW -- "
                      "before the rebuilt fit exists -- is the point: the "
                      "battery criterion is a MIN, so membership edits "
                      "after seeing v2.1 numbers would be a tunable bar "
                      "(screen_battery_rows precedent). loyo = leave-one-"
                      "year-out rank stability, min Spearman rho over the "
                      "three year-dropped refits vs the v2.1 headline "
                      "ranking (restored from its v2.0 demotion because "
                      "vintage-matched X varies within route across "
                      "years; note the fy2017 drop leaves a single-"
                      "vintage X pair -- stated, not hidden). The v2.0 "
                      "16-row battery (screen_battery_rows) remains the "
                      "PUBLISHED current-artifact report; this list is "
                      "consumed via val() by the phase-2b rebuild when it "
                      "runs (test D2 pattern extends to the v2.1 "
                      "artifact)",
        "rows": {}, "no_row_reason": "definitional",
        "accepted": ("owner item 2 2026-07-20 (pre-fit freeze on "
                     "acquisition facts)", "2026-07-20"),
        "logged": "README known-issue 38",
        "upgrade": "phase 2b rebuilt artifact (rows go live; test asserts "
                   "artifact == this list, order included)",
    },
    # -- v2.1 rebuild constants (spec 01 §9 pre-registration; phase 2a) -----
    "gen_jobs_naics": {
        "title": "v2.1 generator-jobs NAICS column set (LODES WAC CNS15-18)",
        "tier": "constant", "status": "active",
        "value": ["CNS15", "CNS16", "CNS17", "CNS18"],
        "units": "LODES WAC columns", "band": None, "basis": "judgment",
        "history": [("2026-07-20",
                     ["CNS15", "CNS16", "CNS17", "CNS18"], "judgment",
                     "spec01 §9.1 pre-registration -- b4 measured generator "
                     "jobs (education + health + arts/rec + accommodation-"
                     "food) REPLACE the saturated hand-coded binary dummy; "
                     "the set is fixed BEFORE any v2.1 input is fitted")],
        "provenance": "the WAC columns summed into the §9.1 b4 predictor: "
                      "CNS15 = NAICS 61 Educational Services, CNS16 = 62 "
                      "Health Care and Social Assistance, CNS17 = 71 Arts, "
                      "Entertainment, and Recreation, CNS18 = 72 "
                      "Accommodation and Food Services (LODESTechDoc8.3 "
                      "column map; sector choice mirrors the v2.0 special-"
                      "generator classes resort/college/medical, measured "
                      "instead of hand-flagged). Consumed via val() by "
                      "screen_common_v21.load_data_v21 -- no literal in "
                      "code. The enumerated alternative (the legacy binary "
                      "dummy) is the pre-registered gen_dummy_swap battery "
                      "row, owned by screen_v21_swap_rows and pending the "
                      "phase-2b rebuilt artifact",
        "rows": {}, "no_row_reason": "covered-elsewhere:gen_dummy_swap",
        "accepted": ("spec01 §9 pre-registration 2026-07-20", "2026-07-20"),
        "logged": None,
        "upgrade": "phase 2b rebuilt fit (the swap row goes live)",
    },
    "screen_power_check": {
        "title": "v2.1 design-stage power check: simulation design knobs "
                 "(owner item 3, 2026-07-20)",
        "tier": "constant", "status": "active",
        "value": {"beta_grid_max": 0.8, "beta_grid_step": 0.05,
                  "n_sims": 200, "n_boot": 500, "n_boot_check": 2000,
                  "check_beta": 0.4, "seed": 11, "power_target": 0.8,
                  "tol_small_b": 0.05, "verdict_se_mult": 2.0},
        "units": "simulation design dict", "band": None, "basis": "judgment",
        "history": [("2026-07-20",
                     "grid [0,0.8] step 0.05; S=200; B=500 (checked vs "
                     "2000); seed 11; 80% power target", "judgment",
                     "owner review 2026-07-20 item 3 -- DESIGN-STAGE power "
                     "check for tripwire criterion 1 under the v2.1 "
                     "rebuild, run BEFORE the v2.1 fit (which stays "
                     "unrun)"),
                    ("2026-07-20",
                     "grid [0,0.8] step 0.05; S=200; B=500 (checked vs "
                     "2000); seed 11; 80% power target", "judgment",
                     "spec01 §9.9 panel extension (owner directive 'extend "
                     "the panel') -- SAME design knobs re-run on the "
                     "EXTENDED panel: the artifact gains a panel_ext block "
                     "(schema 01-P1 -> 01-P2) with the union-presence "
                     "extended designs (current-shape 41->50; with-replicas "
                     "47->63), vintage-matched X per §9.9.2 across the "
                     "6-FY set screen_panel_ext_fys, the SAME committed "
                     "v2.0 variance decomposition (screen_v20_resid_decomp; "
                     "no variance re-estimated from new data), a BEFORE/"
                     "AFTER required-elasticity table, and the verdict "
                     "recomputed under this same pre-stated rule. The "
                     "committed 3-year clusters_41/clusters_47 blocks are "
                     "regenerated bit-identically (same seed stream, drawn "
                     "first)")],
        "provenance": "scripts/screen_power.py consumes this dict via "
                      "val(): what true demand elasticities (b1, b2) would "
                      "clear criterion 1's bootstrap sign fraction >= "
                      "screen_pos_frac_min with ~41/47 route clusters? "
                      "Synthetic log-boardings = X_v21 * beta_true + route "
                      "effect + noise (variances from "
                      "screen_v20_resid_decomp); the EXACT criterion-1 "
                      "statistic (route-cluster bootstrap sign fraction) "
                      "per simulated dataset. NO-CONTAMINATION NOTE "
                      "(binding, spec 01 §9 pre-registration hold): the "
                      "module builds v2.1 predictor matrices INPUT-SIDE "
                      "only (screen_common_v21), never joins them to real "
                      "boardings, and never runs the v2.1 fit -- standing "
                      "guard test test_screen_power.py G1/G2. Artifact: "
                      "outputs/screen_power_check.json (+ .png), "
                      "deterministic (seeded, dual-run byte-identical)",
        "rows": {}, "no_row_reason": "non-binding: design-stage power "
                                     "analysis informing the owner's "
                                     "criterion-2/3 threshold decision; "
                                     "binds no pipeline output and feeds "
                                     "no artifact the registry scans",
        "accepted": ("owner review 2026-07-20 item 3 (design-stage, "
                     "pre-fit)", "2026-07-20"),
        "logged": "README known-issue 38",
        "upgrade": "phase 2b rebuilt fit (the measured pos_frac supersedes "
                   "the simulated power read)",
    },
    "screen_v20_resid_decomp": {
        "title": "committed v2.0 screen fit: route-effect / residual "
                 "variance decomposition (power-check variance matching)",
        "tier": "constant", "status": "active",
        "value": {"sig2_route": 0.025261, "sig2_resid": 0.003352},
        "units": "log-boardings variance components", "band": None,
        "basis": "measured",
        "history": [("2026-07-20",
                     "sig2_route 0.025261 / sig2_resid 0.003352 "
                     "(41 routes, 115 route-years)", "measured",
                     "owner item 3 2026-07-20 -- extracted from the "
                     "COMMITTED v2.0 headline fit by "
                     "screen_fit.resid_decomposition (method of moments "
                     "on the log-OLS residuals grouped by route)")],
        "provenance": "the cluster variance decomposition the design-stage "
                      "power check injects into synthetic log-boardings "
                      "(spec 01 §9 owner item 3): pooled within-route "
                      "residual variance sig2_resid = sum_r sum_y (e_ry - "
                      "ebar_r)^2 / sum_r (n_r - 1); between-route "
                      "sig2_route = var_b(ebar_r) - sig2_resid * "
                      "mean_r(1/n_r) floored at 0 -- method of moments on "
                      "the committed v2.0 log-OLS (BASE_CFG) residuals, "
                      "screen_fit.resid_decomposition. Pinned HERE so "
                      "scripts/screen_power.py consumes val() and never "
                      "reads a boardings value (contamination guard); "
                      "test_screen_power.py W2 asserts these values equal "
                      "the recompute from the committed fit (5e-7 "
                      "tolerance, values stored at the artifact's 6-dp "
                      "canon)",
        "rows": {}, "no_row_reason": "non-binding: variance-matching input "
                                     "to the design-stage power check "
                                     "only; the v2.0 fit it summarizes is "
                                     "already the committed public "
                                     "artifact",
        "accepted": ("owner review 2026-07-20 item 3 (design-stage, "
                     "pre-fit)", "2026-07-20"),
        "logged": "README known-issue 38",
        "upgrade": "phase 2b rebuilt fit (v2.1's own decomposition "
                   "supersedes this matching)",
    },
    "screen_panel_ext_fys": {
        "title": "v2.1 EXTENDED fit-panel fiscal-year set (owner directive "
                 "2026-07-20 'extend the panel'; frozen on availability "
                 "facts, pre-fit)",
        "tier": "constant", "status": "active",
        "value": ["fy2017", "fy2019", "fy2020", "fy2021", "fy2022",
                  "fy2023"],
        "units": "boardings fiscal-year labels", "band": None,
        "basis": "definitional",
        "history": [("2026-07-20",
                     ["fy2017", "fy2019", "fy2020", "fy2021", "fy2022",
                      "fy2023"], "definitional",
                     "owner directive 2026-07-20 'extend the panel' "
                     "(spec 01 §9.9 addendum) -- FROZEN on availability "
                     "facts ALONE, before any v2.1 fit exists: the "
                     "extraction (scripts/extract_apc_ext.py, Legistar "
                     "board-record Q4 detailed reports) landed EXACTLY "
                     "four new FYs with passing validation -- fy2020 "
                     "(full year, 61 routes), fy2021 (50), fy2022 (53), "
                     "fy2023 (54), 218 route-year rows in "
                     "data/derived/route_boardings_ext.csv (apc_ext_fy20_23) "
                     "-- UNION the two surviving committed years fy2017/"
                     "fy2019. fy2020 full-year SUPERSEDES the committed "
                     "9-month fy2020q3 (the two never co-enter a fit; "
                     "§9.9.1). NOT landed, on record: FY2013-16 (older "
                     "Transit Division format, no route-level table), "
                     "FY2018 (raster image strips, no text layer), FY2024+ "
                     "(successor bimonthly deck carries no route-level "
                     "statistics) -- so the §9.9.2 pre-2017 vintage clause "
                     "is MOOT")],
        "provenance": "the CLOSED fiscal-year set for the spec 01 §9.9 "
                      "extended panel, consumed via val() by "
                      "scripts/screen_power.py (load_rvh_ext + the panel_ext "
                      "block; NO literal in code). Ordered fy2017 first so "
                      "fys[1:] are the year-FE dummies (base year fy2017; "
                      "5 FE + intercept + 5 §9.1 slopes = 11 columns). "
                      "Freezing the year set NOW -- before the rebuilt fit "
                      "exists -- is the governance point (screen_battery_"
                      "rows_v21 precedent): the extension is a MIN-changing "
                      "design edit, so year-set edits after seeing v2.1 "
                      "numbers would be a tunable bar. Adding a FY here is "
                      "an owner-approved §9.5 spec amendment, never a "
                      "data-file side effect -- load_rvh_ext RAISES if "
                      "route_boardings_ext.csv carries any FY label outside "
                      "this set. CONTAMINATION GUARD (§9.9.5): the boardings "
                      "VALUES behind these FYs are outcome data barred from "
                      "any predictor matrix until phase 2b; only the "
                      "route-year PRESENCE mask and the validated b3 RVH "
                      "passthrough leave the guarded loader (test_screen_"
                      "power.py G1/G2e)",
        "rows": {}, "no_row_reason": "definitional",
        "accepted": ("owner directive 2026-07-20 'extend the panel' "
                     "(pre-fit freeze on availability facts)", "2026-07-20"),
        "logged": "README known-issue 39",
        "upgrade": "phase 2b rebuilt fit on the extended panel (the year "
                   "set goes live as the fit's row universe; a landed "
                   "archived-GTFS token would also unlock fit-side "
                   "per-year shapes, §9.9.3)",
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
    "gamma_t": {
        "title": "linear-in-time utility (nonlinear-time damping rows, spec 02 s4.5a)",
        "tier": "structural", "status": "active", "basis": "judgment",
        "history": [("2026-07-20", "gamma_t (headline 1.0 = linear)", "judgment",
                     "R2 batch (spec02 s4.5a) -- gamma bracket {0.7, 0.8, 0.9}, "
                     "0.7 added per the 2026-07-08 review (0.8/0.9 alone too "
                     "mild to reveal whether nonlinearity matters)")],
        "provenance": "headline utility is LINEAR in in-vehicle time (bivt*t). "
                      "The gamma_07/gamma_08/gamma_09 rows damp it to "
                      "bivt*t^gamma (IVT minutes only; walk/wait keep the ovt "
                      "weighting) via the gamma_t over-key -- the spec 02 s4.5a "
                      "structural risk-pricing bracket. The default path is "
                      "byte-identical (the damped expression is a separate "
                      "branch, entered only when the key is set)",
        "rows": {"harbor": ["gamma_07", "gamma_08", "gamma_09"],
                 "streetcar": ["gamma_07", "gamma_08", "gamma_09"]},
        "no_row_reason": None, "accepted": None,
        "logged": None, "upgrade": "spec 02 s7 known limitation closes when a "
                                   "local time-of-day elasticity lands",
    },
    "softmax_theta": {
        "title": "choice-structure middle bracket (small-theta softmax rows, "
                 "spec 02 s4.5d)",
        "tier": "structural", "status": "active", "basis": "judgment",
        "history": [("2026-07-20", "softmax_theta (headline = hard max)",
                     "judgment",
                     "R2 batch (spec02 s4.5d) -- theta {0.1, 0.2} rows, the "
                     "principled middle between the hard max and the theta=1 "
                     "variety logsum (2026-07-08 review comment 7)")],
        "provenance": "the hard max (headline) and the theta=1 logsum "
                      "(variety_logsum row, -37%) bracket the truth; the "
                      "theta_01/theta_02 rows are a smoothed max -- genuine "
                      "idiosyncratic taste WITHOUT the full variety bonus "
                      "(ls = m + theta*log(sum(exp((u-m)/theta)))). Registered "
                      "expectation (spec 02 s4.5d): with typical inter-service "
                      "utility gaps >= 0.3, small-theta lands within a few "
                      "percent of the max -- showing that (or failing to) is "
                      "the point. The existing walk_spread row perturbs walk "
                      "DISTANCE, not choice-level taste, and is not a "
                      "substitute (spec text). Default path byte-identical "
                      "(separate branch)",
        "rows": {"harbor": ["theta_01", "theta_02"],
                 "streetcar": ["theta_01", "theta_02"]},
        "no_row_reason": None, "accepted": None,
        "logged": None, "upgrade": None,
    },

    # ---- stage-1 screen structural choices (spec 01 §5b; S2 landing) -------
    # Screen structural entries satisfy materiality (check 5) by enumerating
    # every alternative code path as a `screen` sensitivity row; row pct is
    # the stage-1 rank-churn convention (see the screen-constants block).
    "estimator_screen": {
        "title": "screen estimator choice (log-OLS primary / NB2 always-fitted)",
        "tier": "structural", "status": "active", "basis": "judgment",
        "history": [("2026-07-18", "log-OLS primary, NB2 permanent robustness",
                     "judgment",
                     "spec01 S2 -- panel D1 estimator flip; no silent "
                     "fallback branch")],
        "provenance": "PRIMARY = log-OLS on log(annual boardings) with "
                      "cluster-by-route SEs; NB2 (statsmodels, "
                      "loglike_method='nb2', fixed start_params/maxiter) is a "
                      "PERMANENT robustness row -- BOTH estimators are always "
                      "fitted, and the nb_estimator row reports Spearman rho "
                      "of the full window ranking + top-8 set churn vs "
                      "primary (spec 01 §3.1). Rationale: at annual boardings "
                      "1e5-1e6 the NB2 variance is effectively alpha*mu^2 -- "
                      "pure multiplicative error, log-OLS territory -- and NB "
                      "adds convergence fragility at n_eff~41. The always-"
                      "fitted row replaces any conditional fallback: an "
                      "estimator switch can never happen silently",
        "rows": {"screen": ["nb_estimator"]},
        "no_row_reason": None, "accepted": None,
        "logged": None,
        "upgrade": "post-records-request panel (more routes/years)",
    },
    "screen_fy2020_clip": {
        "title": "screen FY2020-Q3 COVID clip (March-in, 9-month YTD)",
        "tier": "structural", "status": "active", "basis": "judgment",
        "history": [("2026-07-18", "March-in (9-mo YTD)", "judgment",
                     "spec01 S2 -- panel D11: the draft 'Jul-Feb only if "
                     "March distorts' clause is DELETED (unimplementable from "
                     "the on-disk YTD PDF); mandatory drop_fy2020 row "
                     "instead")],
        "provenance": "FY2020-Q3 rows are kept with March 2020 (COVID onset) "
                      "included: the on-disk PDF prints a 9-month YTD total "
                      "and a monthly cut would need a network fetch. "
                      "Handling: year FE, plus an explicit months_observed=9 "
                      "exposure adjustment on the fit side only if trivially "
                      "cleaner (spec 01 §3.1). The pre-registered drop_fy2020 "
                      "row is the honest handle; it is SHARED with "
                      "x_vintage_mismatch and apc_fy17_19_20, which point at "
                      "it (covered-elsewhere style) rather than "
                      "double-claiming",
        "rows": {"screen": ["drop_fy2020"]},
        "no_row_reason": None, "accepted": None,
        "logged": None,
        "upgrade": "records request item 1b (post-FY2021 route-level data "
                   "de-confounds the COVID clip)",
    },
    "x_vintage_mismatch": {
        "title": "screen X-vs-y vintage mismatch (2022 LODES / 2023 ACS X on "
                 "FY2017-20 y)",
        "tier": "structural", "status": "active", "basis": "judgment",
        "history": [("2026-07-18", "pooled years with year FE", "judgment",
                     "spec01 S2 -- panel D16: the temporal X-vs-y mismatch is "
                     "a structural assumption of the fit, not a footnote"),
                    ("2026-07-20", "pooled years with year FE", "judgment",
                     "spec01 §9.3 pre-registration (phase 2a) -- "
                     "SUPERSESSION QUEUED: the v2.1 rebuild vintage-matches "
                     "X (FY2017 rows read 2017 LODES / 2013-17 ACS; FY2019 "
                     "+ FY2020-Q3 read 2019 / 2015-19; the scan keeps "
                     "2022/2023), removing the single-cross-section "
                     "mismatch this entry registers. The supersession "
                     "LANDS with the phase-2b rebuilt artifact; until then "
                     "the v2.0 claim stands unchanged"),
                    ("2026-07-20", "pooled years with year FE", "judgment",
                     "spec01 §9.9 panel extension (owner directive 'extend "
                     "the panel') -- the vintage-match dispatch now also "
                     "covers the four new fit-panel years: FY2020 (full) "
                     "reads 2019 LODES / 2015-19 ACS; FY2021 reads 2021 "
                     "LODES / 2017-21 ACS (both acquired this batch, "
                     "lodes_od_2021 / lodes_wac / acs_2021_5yr); FY2022 and "
                     "FY2023 read 2022 LODES / 2019-23 ACS (§9.9.2). Every "
                     "extended route-year is vintage-matched, so the "
                     "single-cross-section mismatch this entry registers "
                     "still resolves at the phase-2b rebuild -- now over "
                     "the extended panel")],
        "provenance": "the screen regresses FY2017/FY2019/FY2020-Q3 boardings "
                      "on 2022 LODES / 2019-2023 ACS predictors -- a "
                      "post-COVID, WFH-reshaped commute shape explaining "
                      "pre-COVID ridership (2026-07 GTFS alignments also "
                      "differ from the service that generated the boardings; "
                      "spec 01 §2/§7). Rows: year_fe_vs_pooled (year-FE vs "
                      "pooled fit); the SHARED drop_fy2020 row (owned by "
                      "screen_fy2020_clip) probes the most COVID-contaminated "
                      "y year. A pre-COVID-X refit row is QUEUED on the "
                      "spec 02 §4.8 LODES-2019 rebuilt-variant mechanism when "
                      "it lands (see lodes_2022)",
        "rows": {"screen": ["year_fe_vs_pooled"]},
        "no_row_reason": None, "accepted": None,
        "logged": None,
        "upgrade": "phase 2b v2.1 rebuilt fit (spec 01 §9.3 vintage-matched "
                   "X supersedes this entry's mismatch; §9.4 archived-GTFS "
                   "fit-side shapes are the remaining input, BLOCKED on the "
                   "owner's Mobility Database token -- no archived-GTFS "
                   "data-tier entries exist until that acquisition lands). "
                   "Stage-2 side: LODES 2019 rebuilt-variant refit "
                   "(spec 02 §4.8 mechanism)",
    },
    "screen_endog_controls": {
        "title": "screen endogenous-controls choice (RH control kept; E016 out)",
        "tier": "structural", "status": "active", "basis": "judgment",
        "history": [("2026-07-18",
                     "b3 RVH allocation control kept; E016 -> E002 swap",
                     "judgment",
                     "spec01 S2 -- panel D14 endogeneity firewall, "
                     "mechanized")],
        "provenance": "BOTH revenue hours and ACS B08141 E016 transit workers "
                      "are reclassified endogenous-to-service (spec 01 §1): "
                      "b3 log(RVH) stays as an allocation CONTROL, never "
                      "causal; E016 is REMOVED from the predictor set "
                      "(replaced by E002 zero-vehicle workers -- E016 is also "
                      "mostly noise: 39% zero tracts, median MOE/estimate "
                      "1.26). Enforcement is mechanized, not prose: drop_rh "
                      "(fit without RH) and e016_swap (E016 back in) are "
                      "always-run battery rows, and standing tests forbid any "
                      "published prediction at a counterfactual service "
                      "level. The standardized-service dilemma is logged "
                      "(README known-issue 29)",
        "rows": {"screen": ["drop_rh", "e016_swap"]},
        "no_row_reason": None, "accepted": None,
        "logged": "README known-issue 29",
        "upgrade": "exogenous transit-propensity instrument / post-records-"
                   "request panel",
    },
    "screen_scale_term": {
        "title": "screen scale-term choice (b5 free elasticity vs offset)",
        "tier": "structural", "status": "active", "basis": "judgment",
        "history": [("2026-07-18", "b5 log(length) free elasticity", "judgment",
                     "spec01 S2 -- panel D3/Q8 length-scale confound fix")],
        "provenance": "fit and scan share an exposure footing through b5 = "
                      "log(route/window length mi) as a FREE elasticity: "
                      "without a scale term, coefficients fitted on "
                      "3.3-46.9-mi whole-route catchments are incomparable "
                      "with fixed 12.5-mi windows (spec 01 §3.1). The "
                      "enumerated alternative -- offset log(length) with the "
                      "coefficient pinned to 1 -- is the offset_variant row",
        "rows": {"screen": ["offset_variant"]},
        "no_row_reason": None, "accepted": None,
        "logged": None, "upgrade": None,
    },
    "screen_v21_swap_rows": {
        "title": "v2.1 pre-registered predictor swaps (spec 01 §9.1)",
        "tier": "structural", "status": "active", "basis": "judgment",
        "history": [("2026-07-20",
                     "popden_swap / e002_swap / gen_dummy_swap "
                     "(+ conditional sld_swap, not claimed)", "judgment",
                     "spec01 §9 pre-registration (phase 2a landing) -- the "
                     "swap set is fixed BEFORE any v2.1 input is fitted; "
                     "claims point at the PENDING v2.1 rebuilt artifact")],
        "provenance": "the §9.1 swap table, sensitivity battery only, never "
                      "headline: the v2.1 b2 headline becomes B25044 "
                      "zero-vehicle HOUSEHOLDS -- e002_swap restores the "
                      "v2.0 B08141 E002 zero-vehicle-workers headline (the "
                      "e016_swap row carries over unchanged, still owned by "
                      "screen_endog_controls); popden_swap replaces b1 with "
                      "log1p(B01003 population / ALAND density); "
                      "gen_dummy_swap restores the legacy binary special-"
                      "generator dummy in place of the b4 generator-jobs "
                      "magnitude (gen_jobs_naics + special_generators point "
                      "here for their alternatives). sld_swap (EPA SLD "
                      "D-index) is pre-registered CONDITIONAL on acquiring "
                      "the SLD and drops silently otherwise -- NOT claimed. "
                      "Rows live in the v2.1 rebuilt artifact (artifact key "
                      "`screen_v21`), generated by phase 2b; until then "
                      "these claims sit as check-2 pending warnings by "
                      "design (spec 01 §9.7 registry-landing pattern, "
                      "'entries land with the build branch')",
        "rows": {"screen_v21": ["popden_swap", "e002_swap",
                                "gen_dummy_swap"]},
        "no_row_reason": None, "accepted": None,
        "logged": None,
        "upgrade": "phase 2b rebuilt fit + battery (gated on the archived-"
                   "GTFS acquisition, itself blocked on the owner's "
                   "Mobility Database token)",
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
                      "sub-5-min 3.5/7 & 2.5/5 headway plans (owner 2026-07-17, "
                      "GoA4 sub-5-min frequency test), 0.5/1.5-mi spacing "
                      "(spec 08 §3 -- one owner per artifact)",
        "rows": {"harbor": ["grid_phase_half", "rapid_gtfs", "headway_10_20",
                            "headway_flat5", "headway_35_7", "headway_25_5",
                            "spacing_05", "spacing_15"]},
        "no_row_reason": None, "accepted": None,
        "logged": None, "upgrade": "OCTA project design docs",
    },
    "candidate_crossings": {
        "title": "major-crossing counts per candidate (special-structures capital)",
        "tier": "config", "status": "active", "basis": "judgment",
        "config_key": "config/candidates.json: <candidate>.crossings",
        "history": [("2026-07-18", "harbor=4, streetcar=0", "judgment",
                     "N5 review fix -- harness capital was priced at crossings=0; "
                     "harbor's 4 per spec 04 s3.3's named set (I-5, SR-22, Santa "
                     "Ana River channel, BNSF Fullerton)")],
        "provenance": "the count of grade-separation special structures priced "
                      "at the spec 04 s3.3 30-80 $M/crossing band; harbor = 4 "
                      "named structures (physical facts; the JUDGMENT is what "
                      "counts as major); streetcar = 0 (at-grade PE-ROW, no "
                      "priced grade separations -- basis note in candidates.json)",
        "rows": {"network": ["crossing_count"]},
        "no_row_reason": None, "accepted": None,
        "logged": None, "upgrade": "preliminary-engineering structure list",
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
    "special_generators": {
        "title": "special-generator flag list (resort / college / medical)",
        "tier": "config", "status": "active", "basis": "judgment",
        "config_key": "config/special_generators.json",
        "history": [("2026-07-18", "13 generators (3 resort / 6 college / 4 "
                     "medical)", "judgment",
                     "spec01 S2 -- panel D15 initial hand-coding; an "
                     "append-only history entry is REQUIRED per list edit"),
                    ("2026-07-19", "13 generators (3 resort / 6 college / 4 "
                     "medical)", "judgment",
                     "review fix batch -- Kaiser Anaheim corrected to the "
                     "verified 3440 E La Palma Ave campus (33.8545, "
                     "-117.8440); the initial coordinate sat ~2.8 mi east "
                     "near Weir Canyon, outside any 0.9-mi catchment of the "
                     "actual site")],
        "provenance": "the hand-coded special-generator list ({name, type in "
                      "{resort, college, medical}, lat, lon to 4dp}) behind "
                      "the screen's b4 dummy. Judgment data, NOT regenerable "
                      "-- hence config/, not data/derived (repo rule 4). The "
                      "dummy is derived GEOMETRICALLY on BOTH fit and scan "
                      "sides inside the shared compute_predictors (any "
                      "flagged generator within the buffer of the catchment "
                      "window, spec 01 §3.2), so fit/score consistency is "
                      "structural. b4 is high-leverage from a handful of "
                      "routes and the flagged routes are also the highest-"
                      "boardings ones: rows b4_off (drop the dummy, report "
                      "churn) + gen_leave_class_out (leave one class out); "
                      "fit-side dfbetas and Harbor-area with/without-b4 "
                      "scores are mandatory fit_diagnostics. Initial "
                      "hand-coding logged (README known-issue 32)",
        "rows": {"screen": ["b4_off", "gen_leave_class_out"]},
        "no_row_reason": None, "accepted": None,
        "logged": "README known-issue 32",
        "upgrade": "measured magnitudes (enrollment / attendance / LEHD "
                   "workplace counts) replacing judgment flags",
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
                     "scripts/build_derived.py"),
                    ("2026-07-20", "LODES8 ca_od_main_JT00_2022", "measured",
                     "phase 2a (spec01 §9) consolidation -- geography fact "
                     "recorded: ALL LODES8 years are enumerated on 2020 "
                     "tabulation blocks (LODESTechDoc8.3 'Geography "
                     "Vintage'), so the 2017/2019/2022 OD vintages share "
                     "one block frame; the §9.6 manifest's LODES7/2010-"
                     "block plan was superseded at acquisition. Same raw "
                     "now also feeds the v2.1 SCAN-side block table "
                     "data/derived/oc_block_od_2022.csv.gz (858,534 pairs; "
                     "jobs total 945,997 == the tract table exactly)"),
                    ("2026-07-20", "LODES8 ca_od_main_JT00_2022", "measured",
                     "spec01 §9.9 panel extension (owner directive 'extend "
                     "the panel') -- this 2022 vintage now ALSO backs the "
                     "FY2022 and FY2023 fit-panel rows (§9.9.2 nearest-"
                     "vintage). STALE-PREMISE CORRECTION: the earlier "
                     "'2022 is the latest LODES8 release' claim is stale -- "
                     "LODES8 now ships 2023 (CA od+wac 2023 raws STAGED "
                     "with sidecars in data/raw/lodes8, no derived tables "
                     "built). STATED §9.9.2 DECISION: FY2023 rows are "
                     "FROZEN on the 2022 vintage for this design; "
                     "re-vintaging FY2023 to LODES 2023 is a governed "
                     "later amendment, not a silent swap")],
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
                      "is spec-pending, not disposed. SCREEN-SCOPED CAVEAT "
                      "(spec 01 §2, S2): the same 2022 vintage is the "
                      "stage-1 screen's X side (both-ends-in catchment "
                      "flows), regressed on FY2017-FY2020-Q3 boardings -- "
                      "that temporal X-vs-y mismatch is registered as its own "
                      "structural entry (x_vintage_mismatch, rows "
                      "year_fe_vs_pooled + the shared drop_fy2020); the "
                      "screen's pre-COVID-X refit row REUSES this entry's "
                      "§4.8 rebuilt-variant mechanism when it lands",
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
                      "a clean covered-elsewhere claim. SCREEN-SCOPED CAVEAT "
                      "(spec 01 §2, S2): the screen consumes B08141 E002 "
                      "zero-vehicle workers (+MOEs, propagated inside each "
                      "bootstrap replicate as MOE/1.645 normal perturbations) "
                      "as predictor b2; the 2019-2023 pooled window vs "
                      "FY2017-20 outcomes exposure is registered at "
                      "x_vintage_mismatch, and the rejected E016 transit-"
                      "workers alternative is the e016_swap row (owned by "
                      "screen_endog_controls)",
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
                      "partial, not full, coverage; flagged for owner review. "
                      "SCREEN-SCOPED CAVEAT (spec 01 §2, S2): the stage-1 "
                      "screen's scan universe AND fit-side route shapes are "
                      "this 2026-07 snapshot while the outcomes are "
                      "FY2017-FY2020-Q3; six APC routes (24, 53X, 57X, 64X, "
                      "82, 153) were discontinued and have no 2026 weekday "
                      "shape, so they cannot be fitted -- a SURVIVORSHIP-"
                      "biased drop (systematically low performers; the model "
                      "never sees fundamentals-poor failures and the "
                      "underservice logic is correspondingly flattered, "
                      "spec 01 §7). Accepted as a survivorship disposition; "
                      "screen_fit.py prints the dropped list by name; the "
                      "broader alignment-vintage exposure is registered at "
                      "x_vintage_mismatch",
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
    "apc_fy17_19_20": {
        "title": "APC route-level boardings+RVH extraction vintage "
                 "(FY2017 / FY2019 / FY2020-Q3)",
        "tier": "data", "status": "active", "basis": "measured",
        "history": [("2026-07-18",
                     "OCTA Bus Operations Performance Measurements "
                     "FY2017/FY2019/FY2020-Q3 PDFs",
                     "measured",
                     "spec01 S2 -- panel D16; extract_apc.py full-row parse "
                     "(S0), boardings/RVH validated against the printed "
                     "b/RVH column to 2dp for every row"),
                    ("2026-07-20",
                     "FY2017/FY2019/FY2020-Q3 (committed) -- UNCHANGED; "
                     "panel extended in a NEW entry", "measured",
                     "spec01 §9.9 panel extension (owner directive 'extend "
                     "the panel'): this committed table is untouched; the "
                     "four new FYs (FY2020 full / FY2021-23) land in "
                     "apc_ext_fy20_23 as data/derived/route_boardings_ext"
                     ".csv, and the extended fit-panel year set is frozen "
                     "in screen_panel_ext_fys. The LEGACY_MIN_BOARDINGS "
                     "floor this entry owns stays on the FY2017/FY2019 "
                     "universe; the new FYs carry NO floor (§9.9.1) -- the "
                     "asymmetry is stated, and widening THIS entry's "
                     "committed-year universe remains a separate governed "
                     "edit here, not an extraction default")],
        "provenance": "the y-side vintage of the stage-1 screen: route-level "
                      "annual boardings + revenue hours extracted from the "
                      "on-disk OCTA quarterly performance PDFs (data/raw/apc "
                      "via scripts/extract_apc.py -> "
                      "data/derived/route_boardings.csv; 68/63/61 rows "
                      "parsed+validated; three FY2017 RVH cells blanked as "
                      "internally inconsistent with the printed BoardVSH -- "
                      "the KNOWN_BAD_RVH whitelist, routes 35/70/150). The "
                      "dataset itself is measured; the ASSUMPTION is the "
                      "VINTAGE CHOICE: FY2017-FY2020-Q3 are the only "
                      "route-level years public on octa.net, and the most "
                      "COVID-contaminated year already carries the "
                      "drop_fy2020 row (owned by screen_fy2020_clip) -- "
                      "pointed there as the vintage choice's one registry-"
                      "visible sensitivity, an imperfect fit recorded "
                      "honestly (the acs_2023 least-bad-disposition "
                      "precedent). This entry also owns the committed-"
                      "universe floor frozen in extract_apc.py as "
                      "LEGACY_MIN_BOARDINGS (boardings >= 100,000 -- the old "
                      "regex's implicit selection, kept so the 47-route/132-"
                      "cell fit universe is unchanged); widening the "
                      "universe is an edit HERE, not an extraction default",
        "rows": {}, "no_row_reason": "covered-elsewhere:drop_fy2020",
        "accepted": ("spec01 panel adjudication 2026-07-18", "2026-07-18"),
        "logged": None,
        "upgrade": "records request items 1a/1b (FY2014-16 + post-FY2021 "
                   "route-level; widened item 2 = systemwide stop-level APC)",
    },
    "apc_ext_fy20_23": {
        "title": "APC route-level boardings+RVH panel EXTENSION "
                 "(FY2020 full / FY2021 / FY2022 / FY2023)",
        "tier": "data", "status": "active", "basis": "measured",
        "history": [("2026-07-20",
                     "OCTA Q4 detailed reports FY2020/FY2021/FY2022/FY2023 "
                     "(Legistar board-record PDFs)", "measured",
                     "spec01 §9.9 panel extension (owner directive 'extend "
                     "the panel') -- scripts/extract_apc_ext.py -> "
                     "data/derived/route_boardings_ext.csv, 218 route-year "
                     "rows, every row's boardings/RVH validated against the "
                     "printed Board/VSH column to 2dp (the extract_apc.py "
                     "house protocol)")],
        "provenance": "the EXTENDED y-side vintage of the stage-1 screen: "
                      "route-level annual boardings + revenue hours "
                      "extracted from the OCTA quarterly performance 'Q4 "
                      "detailed report' family, located via the Legistar "
                      "web API (webapi.legistar.com/v1/octa; per-FY matter "
                      "ids 8978/9063/10055/10647; provenance sidecars -- "
                      "URL, bytes, sha256, matter id -- under "
                      "data/raw/apc_ext/, gitignored like data/raw/apc). "
                      "SOURCE CORRECTION on record: the two Q2 reports the "
                      "recon cited carry fiscal-year-TO-DATE data under "
                      "annual-looking headers, NOT annual tables; the "
                      "annual 'Operating Statistics By Route' tables live "
                      "in the Q4 reports (exactly how committed FY2017/"
                      "FY2019 were sourced) and the Q2 files are kept as "
                      "FYTD<=annual cross-checks (gate G5). The dataset is "
                      "measured; the ASSUMPTION is the §9.9.1 FROZEN "
                      "YEAR-SET CHOICE (screen_panel_ext_fys): exactly the "
                      "four FYs that landed with passing validation -- "
                      "fy2020 (61 routes, 30,617,349 boardings; full-year "
                      "SUPERSEDES the committed 9-month fy2020q3), fy2021 "
                      "(50; deepest-COVID year), fy2022 (53), fy2023 (54; "
                      "strongest post-COVID). CROSS-VALIDATION: the same "
                      "parser on the Legistar FY2017/FY2019 Q4 copies "
                      "reproduces EVERY committed route_boardings.csv cell "
                      "exactly (all boardings, all RVH, incl. the three "
                      "KNOWN_BAD_RVH blanks). ONE new defect, frozen: route "
                      "560/fy2022 RVH blanked (KNOWN_DUP_RVH_EXT -- two "
                      "sort-order tables print RVH 22,387/22,382 with "
                      "boardings agreeing; neither forensically preferable; "
                      "the KNOWN_BAD_RVH precedent). NO boardings floor is "
                      "applied to the new FYs (§9.9.1) -- unlike the "
                      "committed years' LEGACY_MIN_BOARDINGS floor "
                      "(apc_fy17_19_20); the asymmetry is an availability "
                      "fact of the two tables, pre-stated to close it as a "
                      "post-fit tuning knob. CONTAMINATION GUARD (§9.9.5): "
                      "these boardings are outcome data barred from any "
                      "predictor matrix until phase 2b; test_extract_apc_"
                      "ext.py T7 blanket-bans every predictor/fit module "
                      "from route_boardings_ext with the single "
                      "screen_power.py presence+RVH carve-out",
        "rows": {}, "no_row_reason": "covered-elsewhere:drop_fy2020",
        "accepted": ("owner directive 2026-07-20 'extend the panel'",
                     "2026-07-20"),
        "logged": "README known-issue 39",
        "upgrade": "phase 2b rebuilt fit on the extended panel; a landed "
                   "OCR pass would recover FY2018 (raster-strip tables); "
                   "no route-level FY2013-16 / FY2024+ source exists in "
                   "OCTA's public board record",
    },

    # ---- v2.1 acquisition vintages (spec 01 §9.6; phase 2a consolidation) --
    # Everything phase 1 acquired for the pre-registered rebuild. Sensitivity
    # rows for these vintages are generated by the phase-2b rebuilt artifact
    # (the §9.1 battery), so the predictor-feeding entries here are
    # spec-pending:01§9 dispositions -- counted warnings until 2b lands.
    # Provenance sidecars (URL + sha256 per file) sit next to each raw under
    # data/raw/ (untracked); the committed derived tables are built by
    # scripts/build_derived_v21.py + scripts/acs_vintage_build.py.
    "lodes_od_2017": {
        "title": "LODES8 commute O-D 2017 vintage (v2.1 fit-side b1, FY2017)",
        "tier": "data", "status": "active", "basis": "measured",
        "history": [("2026-07-20", "LODES8 ca_od_main_JT00_2017", "measured",
                     "spec01 §9.6 acquisition (phase 1) + phase 2a derived "
                     "table oc_block_od_2017.csv.gz")],
        "provenance": "US Census LEHD LODES8 CA O-D main JT00 2017, "
                      "block level (data/raw/lodes8/ca_od_main_JT00_2017"
                      ".csv.gz + sidecar; OC-to-OC block pairs compressed to "
                      "data/derived/oc_block_od_2017.csv.gz, 854,800 pairs / "
                      "945,769 jobs, scripts/build_derived_v21.py). The "
                      "ASSUMPTION is the §9.3 VINTAGE MATCH: FY2017 boardings "
                      "rows read THIS vintage for b1 both-ends-in flows. "
                      "Enumerated on 2020 tabulation blocks like every "
                      "LODES8 year (LODESTechDoc8.3 'Geography Vintage') -- "
                      "the §9.6 manifest's LODES7/2010-block plan was "
                      "superseded at acquisition by LODES8-on-2020-blocks, "
                      "which shares one block frame across 2017/2019/2022",
        "rows": {}, "no_row_reason": "spec-pending:01§9",
        "accepted": ("spec01 §9 pre-registration 2026-07-20", "2026-07-20"),
        "logged": None,
        "upgrade": "phase 2b rebuilt fit (vintage-matched battery rows)",
    },
    "lodes_od_2019": {
        "title": "LODES8 commute O-D 2019 vintage (v2.1 fit-side b1, "
                 "FY2019 + FY2020-Q3)",
        "tier": "data", "status": "active", "basis": "measured",
        "history": [("2026-07-20", "LODES8 ca_od_main_JT00_2019", "measured",
                     "spec01 §9.6 acquisition (phase 1) + phase 2a derived "
                     "table oc_block_od_2019.csv.gz")],
        "provenance": "US Census LEHD LODES8 CA O-D main JT00 2019, block "
                      "level (data/raw/lodes8 sidecar; OC-to-OC pairs -> "
                      "data/derived/oc_block_od_2019.csv.gz, 870,558 pairs / "
                      "964,854 jobs). §9.3 vintage match: BOTH FY2019 and "
                      "FY2020-Q3 boardings rows read this vintage (2019 is "
                      "the last pre-COVID enumeration; 2020 LODES reflects "
                      "the shock, not the fundamentals the screen ranks). "
                      "2020-block geography per LODESTechDoc8.3",
        "rows": {}, "no_row_reason": "spec-pending:01§9",
        "accepted": ("spec01 §9 pre-registration 2026-07-20", "2026-07-20"),
        "logged": None,
        "upgrade": "phase 2b rebuilt fit (vintage-matched battery rows)",
    },
    "lodes_od_2021": {
        "title": "LODES8 commute O-D 2021 vintage (v2.1 fit-side b1, FY2021; "
                 "panel extension)",
        "tier": "data", "status": "active", "basis": "measured",
        "history": [("2026-07-20", "LODES8 ca_od_main_JT00_2021", "measured",
                     "spec01 §9.9 panel-extension acquisition (owner "
                     "directive 'extend the panel') + derived table "
                     "oc_block_od_2021.csv.gz")],
        "provenance": "US Census LEHD LODES8 CA O-D main JT00 2021, block "
                      "level (data/raw/lodes8/ca_od_main_JT00_2021.csv.gz + "
                      "sidecar; OC-to-OC block pairs -> data/derived/"
                      "oc_block_od_2021.csv.gz, 813,561 pairs / 888,980 "
                      "jobs, scripts/build_derived_v21.py). The ASSUMPTION "
                      "is the §9.9.2 VINTAGE MATCH: FY2021 boardings rows "
                      "read THIS vintage for b1 both-ends-in flows (the "
                      "newly extracted panel year, apc_ext_fy20_23). "
                      "Enumerated on 2020 tabulation blocks like every "
                      "LODES8 year (LODESTechDoc8.3 'Geography Vintage'), "
                      "one block frame with 2017/2019/2022. The 2021 dip "
                      "(od jobs 964,854 in 2019 -> 888,980 in 2021 -> "
                      "945,997 in 2022) is the coherent COVID trough, an "
                      "availability fact recorded, not smoothed",
        "rows": {}, "no_row_reason": "spec-pending:01§9",
        "accepted": ("owner directive 2026-07-20 'extend the panel'",
                     "2026-07-20"),
        "logged": None,
        "upgrade": "phase 2b rebuilt fit (vintage-matched battery rows)",
    },
    "lodes_wac": {
        "title": "LODES8 WAC vintages 2017/2019/2021/2022 (v2.1 b4 "
                 "generator jobs, CNS15-18)",
        "tier": "data", "status": "active", "basis": "measured",
        "history": [("2026-07-20",
                     "LODES8 ca_wac_S000_JT00_{2017,2019,2022}", "measured",
                     "spec01 §9.6 acquisition (phase 1) + phase 2a derived "
                     "tables oc_block_wac_{2017,2019,2022}.csv"),
                    ("2026-07-20",
                     "LODES8 ca_wac_S000_JT00_{2017,2019,2021,2022}",
                     "measured",
                     "spec01 §9.9 panel extension (owner directive 'extend "
                     "the panel') -- 2021 vintage ADDED for the FY2021 "
                     "panel rows: derived table oc_block_wac_2021.csv "
                     "(16,015 blocks, C000 1,579,269, CNS15-18 477,808, == "
                     "independent raw recount). The 2021 C000 (2019 "
                     "1,685,277 -> 2021 1,579,269 -> 2022 1,697,325) is the "
                     "coherent COVID trough")],
        "provenance": "US Census LEHD LODES8 CA WAC S000 JT00, block level, "
                      "FOUR vintages (data/raw/lodes8 sidecars; OC blocks "
                      "-> data/derived/oc_block_wac_{2017,2019,2021,2022}"
                      ".csv). Feeds the §9.1 b4 generator-jobs predictor as "
                      "the sum of the gen_jobs_naics columns -- CNS15 = "
                      "NAICS 61 edu, CNS16 = 62 health, CNS17 = 71 "
                      "arts/rec, CNS18 = 72 accommodation/food "
                      "(LODESTechDoc8.3 column map, recorded in each "
                      "sidecar). Vintage match: 2017 -> FY2017 rows, 2019 "
                      "-> FY2019/FY2020-Q3/FY2020 rows (§9.3 + §9.9.2 -- "
                      "2019 is the last pre-shock enumeration), 2021 -> "
                      "FY2021 rows (§9.9.2), 2022 -> FY2022/FY2023 rows + "
                      "the scan side. 2020-block geography for all years "
                      "(TechDoc8.3)",
        "rows": {}, "no_row_reason": "spec-pending:01§9",
        "accepted": ("spec01 §9 pre-registration 2026-07-20", "2026-07-20"),
        "logged": None,
        "upgrade": "phase 2b rebuilt fit (b4 goes live; gen_dummy_swap row)",
    },
    "tiger2020pl_blocks": {
        "title": "TIGER/Line 2020 PL tabulation blocks, OC (v2.1 catchment "
                 "frame)",
        "tier": "data", "status": "active", "basis": "measured",
        "history": [("2026-07-20", "tl_2020_06059_tabblock20 (TIGER2020PL)",
                     "measured",
                     "spec01 §9.6 acquisition (phase 1) + phase 2a derived "
                     "table oc_blocks.csv")],
        "provenance": "Census TIGER/Line 2020 PL-94-171-vintage tabulation "
                      "blocks for Orange County (data/raw/tiger2020/"
                      "tl_2020_06059_tabblock20.zip + sidecar; DBF "
                      "attributes -> data/derived/oc_blocks.csv, 26,734 "
                      "blocks: GEOID20, internal point INTPTLAT20/"
                      "INTPTLON20, ALAND20). The §9.2 catchment rule runs "
                      "on the block INTERNAL POINTS (|offset| <= buffer_mi "
                      "AND position in-window) -- the centroid-test "
                      "approximation of buffer-polygon intersection is a "
                      "stated property of the rule, not hidden. ALAND20 "
                      "also denominates the popden_swap density",
        "rows": {}, "no_row_reason": "spec-pending:01§9",
        "accepted": ("spec01 §9 pre-registration 2026-07-20", "2026-07-20"),
        "logged": None,
        "upgrade": "phase 2b rebuilt scan on the block frame",
    },
    "pl94171_block_pop": {
        "title": "2020 PL 94-171 block population (v2.1 apportionment "
                 "weights)",
        "tier": "data", "status": "active", "basis": "measured",
        "history": [("2026-07-20",
                     "ca2020.pl.zip P0010001 (== API P1_001N)", "measured",
                     "spec01 §9.6 acquisition (phase 1; legacy summary file "
                     "because api.census.gov now requires a key) + phase 2a "
                     "join into oc_blocks.csv pop2020")],
        "provenance": "2020 Decennial PL 94-171 legacy summary file, "
                      "California (data/raw/census2020/ca2020.pl.zip + "
                      "sidecar; SUMLEV 750 GEOCODE 06059* P0010001 -> "
                      "data/raw/census2020/oc_2020_p1_block_pop.csv -> "
                      "oc_blocks.csv pop2020; OC total 3,186,989). These "
                      "are the tract->block APPORTIONMENT WEIGHTS for every "
                      "ACS-vintage predictor (screen_common_v21 docstring "
                      "states the approximation honestly: 2020 weights are "
                      "used for ALL vintages, zero-population tracts split "
                      "equally, tract totals conserved), and the pop-land "
                      "overlap estimator behind oc_tract10_to_tract20.csv",
        "rows": {}, "no_row_reason": "spec-pending:01§9",
        "accepted": ("spec01 §9 pre-registration 2026-07-20", "2026-07-20"),
        "logged": None,
        "upgrade": "block-level ACS-period population if ever published",
    },
    "acs_2017_5yr": {
        "title": "ACS 2013-2017 5-yr vintage (v2.1 FY2017 X: B25044 / "
                 "B01003 / B08141)",
        "tier": "data", "status": "active", "basis": "measured",
        "history": [("2026-07-20",
                     "ACS 2017 5-yr summary-file sequences 0003/0028/0105",
                     "measured",
                     "spec01 §9.6 acquisition (phase 1) + phase 2a move of "
                     "the tidy tables into data/derived (committed)")],
        "provenance": "Census ACS 2013-2017 5-yr summary file, CA tract "
                      "sequences (data/raw/acs/20175ca{0003,0028,0105}000"
                      ".zip + g20175ca.csv + lookup, sidecars there; "
                      "scripts/acs_vintage_build.py -> data/derived/"
                      "oc_{b01003,b08141,b25044}_2017.csv, 583 tracts each, "
                      "tract-sum sanity printed). §9.3 vintage match: "
                      "FY2017 boardings rows read these for b2 zero-vehicle "
                      "households (B25044 E003+E010), popden_swap (B01003/"
                      "ALAND) and the e002/e016 swap inputs. Published on "
                      "2010 TRACT geography -- bridged to the 2020 block "
                      "frame via oc_tract10_to_tract20.csv (pop-land "
                      "overlap estimator) then pop-weight apportioned; the "
                      "two-stage approximation is documented in "
                      "screen_common_v21",
        "rows": {}, "no_row_reason": "spec-pending:01§9",
        "accepted": ("spec01 §9 pre-registration 2026-07-20", "2026-07-20"),
        "logged": None,
        "upgrade": "phase 2b rebuilt fit (vintage-matched battery rows)",
    },
    "acs_2019_5yr": {
        "title": "ACS 2015-2019 5-yr vintage (v2.1 FY2019/FY2020-Q3 X: "
                 "B25044 / B01003 / B08141)",
        "tier": "data", "status": "active", "basis": "measured",
        "history": [("2026-07-20",
                     "ACS 2019 5-yr prototype table-based files", "measured",
                     "spec01 §9.6 acquisition (phase 1) + phase 2a move of "
                     "the tidy tables into data/derived (committed)")],
        "provenance": "Census ACS 2015-2019 5-yr prototype table-based "
                      "summary files (data/raw/acs/acsdt5y2019-{b01003,"
                      "b08141,b25044}.dat + sidecars; acs_vintage_build.py "
                      "-> data/derived/oc_*_2019.csv, 583 tracts, tract-sum "
                      "== county sanity TRUE for all three). §9.3 vintage "
                      "match: FY2019 AND FY2020-Q3 boardings rows read "
                      "these. 2010 tract geography, bridged + apportioned "
                      "like acs_2017_5yr. The 2019-2023 scan-side tables "
                      "stay under the existing acs_2023 entry (B08141) and "
                      "the phase-1 oc_{b25044,b01003}_2023.csv tidies",
        "rows": {}, "no_row_reason": "spec-pending:01§9",
        "accepted": ("spec01 §9 pre-registration 2026-07-20", "2026-07-20"),
        "logged": None,
        "upgrade": "phase 2b rebuilt fit (vintage-matched battery rows)",
    },
    "acs_2021_5yr": {
        "title": "ACS 2017-2021 5-yr vintage (v2.1 FY2021 X: B25044 / "
                 "B01003 / B08141; panel extension)",
        "tier": "data", "status": "active", "basis": "measured",
        "history": [("2026-07-20",
                     "ACS 2017-2021 5-yr table-based summary file "
                     "(B25044 / B01003 / B08141)", "measured",
                     "spec01 §9.9 panel-extension acquisition (owner "
                     "directive 'extend the panel') -> tidy tables in "
                     "data/derived (committed)")],
        "provenance": "Census ACS 2017-2021 5-yr TABLE-BASED summary file, "
                      "CA tract (data/raw/acs/acsdt5y2021-{b01003,b08141,"
                      "b25044}.dat + sidecars; the table-based-SF/data/"
                      "5YRData path -- the prototype/ and sequence-based "
                      "paths 404 for 2021, probed and recorded in "
                      "scripts/acs_vintage_build.py; -> data/derived/"
                      "oc_{b01003,b08141,b25044}_2021.csv, 614 tracts each, "
                      "tract-sum == county TRUE for all three: E001 "
                      "1,555,720 / zveh 1,057,592 / pop 3,182,923). §9.9.2 "
                      "vintage match: FY2021 boardings rows read these for "
                      "b2 zero-vehicle households (B25044 E003+E010), "
                      "popden_swap (B01003/ALAND) and the e002/e016 swap "
                      "inputs. DISTINGUISHING GEOGRAPHY FACT: 2017-2021 is "
                      "the FIRST 5-yr vintage published on 2020 TRACTS -- "
                      "same frame as acs_2023, so NO oc_tract10_to_tract20 "
                      "bridge is applied for FY2021 rows (unlike "
                      "acs_2017_5yr / acs_2019_5yr, which are 2010-tract "
                      "and bridged); screen_common_v21._ACS_FILES tags the "
                      "2021 vintage 't20', pop-weight apportioned to blocks "
                      "directly",
        "rows": {}, "no_row_reason": "spec-pending:01§9",
        "accepted": ("owner directive 2026-07-20 'extend the panel'",
                     "2026-07-20"),
        "logged": None,
        "upgrade": "phase 2b rebuilt fit (vintage-matched battery rows)",
    },
    "ipeds_fall2023": {
        "title": "IPEDS fall-2023 enrollment + HD2024 directory (generator "
                 "context)",
        "tier": "data", "status": "active", "basis": "measured",
        "history": [("2026-07-20", "HD2024.zip + DRVEF2023.zip", "measured",
                     "spec01 §9.6 acquisition row 8 (phase 1) -- context / "
                     "b4 cross-check ONLY, never a predictor (§9.7)")],
        "provenance": "NCES IPEDS institutional directory 2024 + derived "
                      "fall-2023 enrollment (data/raw/generators/HD2024.zip "
                      "/ DRVEF2023.zip -> ipeds_enrollment.csv, 8 target OC "
                      "colleges with ENRTOT/FTE + lat/lon; sidecars there). "
                      "§9.7 is binding: enters fit diagnostics as LOGGED "
                      "CONTEXT or a b4 cross-check only -- never a "
                      "predictor, so no sensitivity row will ever exist",
        "rows": {},
        "no_row_reason": "non-binding:context-only (spec01 §9.7 -- never a "
                         "predictor)",
        "accepted": ("spec01 §9 pre-registration 2026-07-20", "2026-07-20"),
        "logged": None, "upgrade": "EF2024A when NCES releases it",
    },
    "hcai_util_2024": {
        "title": "HCAI hospital utilization CY2024 (generator context)",
        "tier": "data", "status": "active", "basis": "measured",
        "history": [("2026-07-20", "hosp24_util_data_final.xlsx (Oct 2025 "
                     "release)", "measured",
                     "spec01 §9.6 acquisition row 8 (phase 1) -- context / "
                     "b4 cross-check ONLY, never a predictor (§9.7)")],
        "provenance": "HCAI Hospital Annual Utilization CY2024 FINAL via "
                      "the CHHS open-data portal (data/raw/generators/"
                      "hosp24_util_data_final.xlsx -> hcai_beds.csv, all 37 "
                      "OC hospitals, licensed beds + lat/lon; sidecars "
                      "there). §9.7 binding: logged context / b4 "
                      "cross-check only, never a predictor",
        "rows": {},
        "no_row_reason": "non-binding:context-only (spec01 §9.7 -- never a "
                         "predictor)",
        "accepted": ("spec01 §9 pre-registration 2026-07-20", "2026-07-20"),
        "logged": None, "upgrade": "CY2025 release",
    },
    "cde_enroll_2425": {
        "title": "CDE 2024-25 school enrollment + directory (generator "
                 "context)",
        "tier": "data", "status": "active", "basis": "measured",
        "history": [("2026-07-20", "cenroll2425.txt + pubschls.txt",
                     "measured",
                     "spec01 §9.6 acquisition row 8 (phase 1) -- context / "
                     "b4 cross-check ONLY, never a predictor (§9.7)")],
        "provenance": "CDE 2024-25 cumulative-enrollment download + public-"
                      "schools directory (data/raw/generators/cenroll2425"
                      ".txt + pubschls.txt -> cde_enrollment_oc.csv, 665 OC "
                      "schools joined to lat/lon, 27 without coordinates; "
                      "sidecars there). §9.7 binding: enrollment enters "
                      "only as logged context / b4 cross-check -- the "
                      "non-commute demand model v2.1 explicitly does NOT "
                      "build",
        "rows": {},
        "no_row_reason": "non-binding:context-only (spec01 §9.7 -- never a "
                         "predictor)",
        "accepted": ("spec01 §9 pre-registration 2026-07-20", "2026-07-20"),
        "logged": None, "upgrade": "2025-26 files",
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
