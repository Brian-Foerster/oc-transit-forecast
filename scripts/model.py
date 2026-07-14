"""
Monte-Carlo incremental pivot logit, nested within transit.

Structure (per market segment x distance bin x within-cell sub-rider):
  Each transit service s has utility
      V_s = bivt*IVT(d, speed_s) + bwait*(wait_s(headway) + walk_s(position))
            [+ asc for the NEW line]
  A rider's street position is uniform over one stop-grid period; every
  service's walk time is computed from that SAME position (K=8 quadrature,
  see subcell_walks), so the best-service choice is smooth at the cell level
  without any logsum "variety bonus". The pivot applies exp(dV) per sub-cell:
      S1 = S0*e^dV / (S0*e^dV + 1 - S0),   dV = V(new system) - V(base).
  In the retain scenario the new line's boardings are total x P(new|transit),
  derived from the same utilities. Fold removes the local, so short trips
  are charged the longer walk to rapid stops.

Markets: walk (both-ends LODES incl. 0-0.5-mi intra-tract bin), transfer
(one-end LODES via feeder crossings, pinned to tau share of base boardings),
visitor (resort market, pinned to phi share; random arrival so wait = h/2).
Non-work expansion via ws/kappa (optionally with a shorter-trip tilt).

Time of day: a service's headway may be scalar or {'peak','offpeak'};
per-period utilities are blended by a pkshare prior.

Wait: walk access uses eff_wait = min(h/2, w0 + lam*h) (arrival-strategy
closed form; visitors use h/2 -- no schedule adaptation); transfers use
min(h/2, xcap).

Uncertainty: behavioral params (bivt, ovt, asc) drawn triangular (peaked);
base shares jittered with ACS-published MOEs (delta-method SEs); bins
Dirichlet-resampled. NO baked-in filter: the headline is reported uncapped,
with the backtest-calibrated (ABC) treatment SIDE BY SIDE -- see
reweight_abc.py -- and the implied uplift printed against the reference
class. draw_params()/run(params=) provide common random numbers across
configurations.

usage: python model.py data/derived/corridor_harbor.json
"""
import copy, json, os, sys
import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

N = 40000
WALK_MPH = 3.0
SUBK = 8   # rider-position quadrature nodes; 8 is exact for 0.25/0.5/1.0-mi grids
DEFAULT_FARE = 2.00   # OCTA flat cash fare, $ (spec 06 D3; override via cfg["fare_base"])

# Reference classes are DISPLAY-ONLY (spec 05 §4): printed beside the
# forecast, never used to cap, reweight, or filter draws (standing user
# decision). Entries are basis-tagged -- regime {fold, retain, study} x
# horizon {launch, matured} -- because the old one-line string mixed three
# measurement bases (Cleveland matured fold vs Twin Cities launch retain vs
# a study average) and quoted only Cleveland's matured high end.
REFERENCE = {
    "uplift": [  # tier 0: bus->rapid corridor uplifts (arterial BRT analogs)
        {"name": "Twin Cities A Line", "pct": 30, "regime": "retain",
         "horizon": "launch", "note": "first-year, overlay on retained local"},
        {"name": "Cleveland HealthLine", "pct": 40, "regime": "fold",
         "horizon": "launch", "note": "launch year; $200M street-rebuild confound"},
        {"name": "Cleveland HealthLine", "pct": 78, "regime": "fold",
         "horizon": "matured", "note": "5-yr matured; rebuild + Univ Circle TOD confound"},
    ],
    "study": {"name": "UW BRT synthesis (2017)", "pct": 35,
              "note": "average across BRT corridors, mixed bases"},
    # tier 1: mode-matched grade-separated driverless metros -- absolute
    # ridership / forecast-accuracy analogs ONLY; no clean corridor-uplift
    # basis (new alignments, not same-street bus replacements). Do NOT back
    # out a pseudo-uplift from these.
    "alm_analogs": [
        {"name": "Vancouver Canada Line (2009)",
         "note": "beat ~100k/day target by 2010; 2019 ~150k vs 120k forecast "
                 "(optimism-confirming pole; embedded in a feeder network)"},
        {"name": "Montreal REM South Shore (2023)",
         "note": "~30k/day projected, early counts ~24k (cautionary launch "
                 "pole; opened as a standalone stub)"},
    ],
    # tier 2: rail-over-bus mode bonus -- empirical anchor for the ASC
    # premium bracket {1.0, 1.5, 2.0} (README issue 14)
    "mode_bonus": {"name": "Canada Line displacing the 98 B-Line",
                   "note": "rail replacing the busiest bus corridor; anchors "
                           "the rail-ASC premium bracket"},
    # tier 3: outside-view accuracy prior -- an annotation, never a filter
    "optimism": {"name": "Flyvbjerg, Holm & Buhl (2005), JAPA 71(2)",
                 "note": "9 of 10 rail forecasts overestimated; mean "
                         "overestimation ~106%; 84% off by more than +/-20%"},
}

# (lo, hi, shape): triangular = peaked at midpoint; uniform elsewhere
PRIORS = {
    "bivt":  (-0.035, -0.018, "tri"),  # in-vehicle time coef, util/min
    "ovt":   (1.6, 2.5, "tri"),        # wait & walk weight relative to IVT
    "asc":   (0.0, 0.40, "tri"),       # image/reliability constant (trimmed)
    "w0":    (4.0, 7.0, "uni"),        # scheduled-arrival platform wait, min
    "lam":   (0.10, 0.25, "uni"),      # schedule-delay slope
    "xcap":  (10.0, 15.0, "uni"),      # transfer-wait cap, min
    "tau":   (0.25, 0.40, "uni"),      # transfer share of base boardings
    "phi":   (0.05, 0.15, "uni"),      # visitor share of base boardings
    "s0v":   (0.10, 0.30, "uni"),      # visitor base transit share
    "ws":    (0.40, 0.60, "uni"),      # work share of boardings
    "kappa": (0.60, 1.00, "uni"),      # non-work responsiveness
    "pkshare": (0.45, 0.60, "uni"),    # peak share of boardings (TOD blend)
    # spec 06 D3/D7: appended LAST so draw_params consumes its rng stream in
    # insertion order and every pre-existing prior's draws stay bit-identical
    # (the append-last rule -- the repo was once bitten by rng reordering).
    "vot_behav": (10.0, 22.0, "tri"),  # $/hr, behavioral VOT (fare response)
    "pcar0":     (0.05, 0.25, "uni"),  # car-diversion prob, 0-vehicle segment
    "pcar1":     (0.35, 0.65, "uni"),  # 1-vehicle segment
    "pcar2":     (0.55, 0.85, "uni"),  # 2+-vehicle segment
    "pcarv":     (0.00, 0.30, "uni"),  # visitor market
    # pcar* are drawn and exported only (res["params"]); the BCA wrapper (B4)
    # prices them -- model code must NOT consume them anywhere.
    # spec 02 §4.9 (R6): grade-separated derived-speed priors, appended LAST
    # after pcarv (the same append-last rng discipline) so every pre-existing
    # prior's draws stay bit-identical. Consumed ONLY by the forward line's
    # derived_speed block; central (80 km/h, 25 s) reproduces ~30 mph at 1-mi
    # spacing. The measured base services keep their config scalar speeds.
    "v_cruise": (70.0, 90.0, "uni"),   # km/h, grade-separated cruise (ALM)
    "dwell":    (20.0, 30.0, "uni"),   # s, station dwell (ALM)
}
# cap treatments removed per user decision 2026-07: the headline is reported
# uncapped NEXT TO the backtest-calibrated (ABC) treatment -- see reweight_abc.py.
# The single-element list is retained deliberately: the (label, cap) loop
# structure lets a future analysis reintroduce a treatment in one line.
ENVELOPES = [("uncapped", None)]

# ---- derived average speed (spec 02 §4.9, R6) ---------------------------
# TCQSM-style decomposition: average speed falls OUT of cruise speed, station
# dwell, and the accel/decel time lost at each stop, so `speed` and `spacing`
# are no longer independent config knobs. Mode decision 2026-07-08 splits it in
# two: the forward elevated automated light-metro line uses the grade-separated
# variant (no signal delay); the street variant, calibrated in code from two
# measured OCTA bus points, stays for the bus backtest/calibration experiments.
A_COMFORT = 1.0          # m/s^2, REM-class comfortable accel(=decel): sets the
                         # per-stop time lost vs cruising, grade-separated only
J_COMFORT = 0.75         # m/s^3, service jerk limit (spec 02 §4.9b). Passenger
                         # comfort standards band the sustained jerk at
                         # ~0.5-1.0 (EN 13452 family); 0.75 central, the band
                         # edges are sensitivity rows. j->inf recovers R6's
                         # trapezoid (the accel/decel time lost is v/a, no jerk
                         # ramp), retained as the regression row.
KMH_PER_MPH = 1.609344   # exact
MPS_PER_KMH = 1000.0 / 3600.0
M_PER_MI = KMH_PER_MPH * 1000.0   # 1609.344 m, exact
# Two measured points on the shared Harbor street (avg mph, stop spacing mi):
# Route 43 local and Route 543 rapid, both in this repo's GTFS/anchor
# provenance. Two equations identify the street variant's per-stop penalty and
# no-stop street speed; MEASURED STAYS MEASURED, so the base services keep
# their own config scalar speeds and this curve only prices hypothetical bus
# designs (sensitivity rows / future experiments).
STREET_CAL_POINTS = ((11.4, 0.25), (12.8, 1.0))
TSP_SPEEDUP = 0.075      # 2024 OCTA TSP study ~7-8% corridor speed-up would
                         # raise v_street; informational only, no consumer yet


def s_curve_phase_time(dv_mps, accel=A_COMFORT, jerk=J_COMFORT):
    """Time (s) for one jerk-limited (S-curve) speed change of magnitude
    dv_mps at service accel `accel` and jerk limit `jerk`, elementwise.

    If the change is large enough that acceleration saturates at `accel`
    (dv >= accel^2/jerk), the profile is jerk-up / hold / jerk-down and takes
    dv/accel + accel/jerk (the extra accel/jerk over the trapezoid dv/accel is
    the two jerk ramps). Otherwise acceleration never reaches `accel` and the
    triangular-accel profile takes 2*sqrt(dv/jerk). At these speeds
    accel^2/jerk is only 1-2 m/s so the saturated branch always binds, but
    the sub-saturated branch is implemented for correctness (j->inf makes the
    ramp term vanish, recovering the R6 trapezoid dv/accel)."""
    dv = np.asarray(dv_mps, float)
    a_sq_over_j = accel * accel / jerk
    saturated = dv / accel + accel / jerk
    triangle = 2.0 * np.sqrt(np.maximum(dv, 0.0) / jerk)
    return np.where(dv >= a_sq_over_j, saturated, triangle)


def stop_run_time(d_m, v_cruise_mps, accel=A_COMFORT, jerk=J_COMFORT):
    """Stop-to-stop run time (s) over distance d_m aiming for cruise speed
    v_cruise_mps, jerk-limited S-curve, elementwise over draws (v may be an
    (n,) array; d/accel/jerk broadcast).

    Antisymmetry identity (the non-obvious step): a jerk-limited phase from 0
    to v is antisymmetric about its midpoint, so it covers exactly
    v*t_phase/2 -- i.e. an accel+decel with no cruise covers v*t_phase. Hence
    cruise is REACHABLE within d iff v*t_phase(v) <= d; then the run is
    d/v + t_phase (pure-cruise time plus one full phase-time of excess:
    accel and decel each waste t_phase/2 vs cruising the same distance).
    When d is too short to reach v (the reachability cap, materially new at
    tight spacings), the train peaks at v_p < v where a bare accel+decel just
    fills d: v_p^2/accel + v_p*accel/jerk = d, whose positive root is the
    quadratic below; the run is then two phases, 2*t_phase(v_p)."""
    v = np.asarray(v_cruise_mps, float)
    d = np.asarray(d_m, float)
    tph = s_curve_phase_time(v, accel, jerk)
    reachable = v * tph <= d
    t_reach = d / v + tph
    # peak speed when v is unreachable within d (depends only on d, accel,
    # jerk -- not on the target v). Positive root of the phase-distance
    # quadratic; valid while v_p >= accel^2/jerk (the fully-jerk-limited
    # triangle sub-case does not bind at these d -- asserted below).
    v_p = (-accel * accel / jerk
           + np.sqrt(accel**4 / jerk**2 + 4.0 * accel * d)) / 2.0
    capped = ~reachable
    if np.any(capped):
        vp_b = np.broadcast_to(v_p, capped.shape)
        assert np.all(vp_b[capped] >= accel * accel / jerk), (
            "v_p below accel^2/jerk: the jerk-limited triangle sub-case "
            "binds and the quadratic root is invalid at this spacing")
    t_cap = 2.0 * s_curve_phase_time(v_p, accel, jerk)
    return np.where(reachable, t_reach, t_cap)


def grade_sep_min_per_mile(v_cruise_kmh, dwell_s, spacing_mi,
                           accel=A_COMFORT, jerk=J_COMFORT):
    """Grade-separated running time (min/mi), elementwise over draws. No signal
    delay; the per-stop excess over cruising is the jerk-limited S-curve phase
    time (spec 02 §4.9b), and the reached speed is capped to v_p when the stop
    spacing is too short to attain v_cruise. j->inf with the cap retained is
    R6's trapezoid (the regression row)."""
    v_mps = np.asarray(v_cruise_kmh, float) * MPS_PER_KMH
    d_m = spacing_mi * M_PER_MI
    t_run = stop_run_time(d_m, v_mps, accel, jerk)
    return (t_run + dwell_s) / 60.0 / spacing_mi


def calibrate_street(points=STREET_CAL_POINTS):
    """Solve two measured (avg mph, spacing) points for the street variant's
    (per-stop penalty min, no-stop street speed mph): min/mi = 60/v_street +
    p_stop/spacing, two equations / two unknowns. Solved symbolically from the
    named constants so the ~0.19 min-per-stop / ~13.3 mph result MOVES if the
    calibration points are ever revised -- never hardcode the solved values."""
    (v1, s1), (v2, s2) = points
    m1, m2 = 60.0 / v1, 60.0 / v2                    # measured min/mi
    p_stop = (m1 - m2) / (1.0 / s1 - 1.0 / s2)       # min per stop
    v_street = 60.0 / (m2 - p_stop / s2)             # no-stop street speed, mph
    return p_stop, v_street


def street_min_per_mile(spacing_mi, cal=None):
    """Street running time (min/mi) at a given stop spacing, from the calibrated
    (p_stop, v_street). Reproduces the two measured points by construction."""
    p_stop, v_street = cal if cal is not None else calibrate_street()
    return 60.0 / v_street + p_stop / spacing_mi


def derived_speed_mph(svc, p, variant=None):
    """Average speed (mph) for a service carrying a derived_speed block.
    Grade-separated -> per-draw (n,) array (v_cruise/dwell are priors in `p`);
    street -> scalar (calibrated constants only)."""
    ds = svc["derived_speed"]
    variant = variant or ds["variant"]
    if variant == "grade_separated":
        # optional accel/jerk override keys default to the module constants
        # (spec 02 §4.9b) -- the sensitivity-row / future-variant mechanism.
        mpm = grade_sep_min_per_mile(p["v_cruise"], p["dwell"], svc["spacing"],
                                     accel=ds.get("accel", A_COMFORT),
                                     jerk=ds.get("jerk", J_COMFORT))
    elif variant == "street":
        mpm = street_min_per_mile(svc["spacing"])
    else:
        raise ValueError(f"unknown derived_speed variant {variant!r}")
    return 60.0 / mpm


def draw_params(n, seed=42, over=None):
    """Draw the prior vector on its own child stream. ALWAYS consumes the
    rng for every key, so pinning one prior no longer shifts the draws of
    the others; the same (n, seed) gives common random numbers across
    configurations (backtest vs forward) for ABC reweighting."""
    rng = np.random.default_rng(np.random.SeedSequence(seed).spawn(2)[0])
    p = {}
    for k, (lo, hi, shape) in PRIORS.items():
        p[k] = (rng.triangular(lo, (lo + hi) / 2, hi, n) if shape == "tri"
                else rng.uniform(lo, hi, n))
    for k, v in (over or {}).items():
        if k in p:
            p[k] = np.full(n, float(v))
    return p


class Corridor:
    def __init__(self, path):
        j = json.load(open(path, encoding="utf-8"))
        self.cfg = j["config"]
        self.name = self.cfg["name"]
        seg = j["segments"]
        self.cf = np.array(seg["car_frac"])
        self.s0 = np.array(seg["S0_by_car"])
        self.s0_se = np.array(seg.get("S0_se_rel", [0.10, 0.10, 0.10]))
        self.wd = np.array(j["walk_bins"]["centers"])
        self.ww = np.array(j["walk_bins"]["weights"])
        self.xd = np.array(j["transfer_bins"]["centers"])
        self.xw = np.array(j["transfer_bins"]["weights"])
        # spec 06 D7: full-O-D (straight-line centroid-to-centroid) distance
        # per transfer bin, for the cm_seg_fullod bound; falls back to the
        # corridor-leg centers on derived files built before this field
        # existed.
        self.xd_od = np.array(j["transfer_bins"].get("centers_od", j["transfer_bins"]["centers"]))
        nv = len(self.cfg["visitor"]["bin_weights"])
        assert nv == len(self.wd), (
            f"visitor bin_weights has {nv} entries but walk_bins has "
            f"{len(self.wd)} -- update the config to match")


def run(cor, n=N, seed=42, linear_wait=False, no_transfer=False,
        no_visitor=False, cfg_patch=None, smooth_k=SUBK, params=None, **over):
    """Vectorized MC. `over` pins any PRIORS key / 'anchor'; `cfg_patch`
    deep-merges into the corridor config (service definitions etc.).
    smooth_k: sub-cell quadrature nodes for within-cell rider position
    (0 = old knife-edge point value spacing/4).
    params: pre-drawn prior dict from draw_params() -- pass the SAME dict
    to two run() calls for common random numbers (ABC); anchor and input
    jitters use a second child stream, so run(params=draw_params(n, s),
    seed=s) is identical to run(seed=s)."""
    rng = np.random.default_rng(np.random.SeedSequence(seed).spawn(2)[1])
    cfg = copy.deepcopy(cor.cfg)
    if cfg_patch:
        for k, v in cfg_patch.items():
            if isinstance(v, dict) and isinstance(cfg.get(k), dict):
                cfg[k].update(v)
            else:
                cfg[k] = v

    if params is None:
        p = draw_params(n, seed, over)
    else:   # pins still apply on top of shared draws
        p = {k: (np.full(n, float(over[k])) if k in over else v)
             for k, v in params.items()}
    anchor = (np.full(n, float(over["anchor"])) if "anchor" in over
              else rng.uniform(cfg["anchor_low"], cfg["anchor_high"], n))
    bwait = p["bivt"] * p["ovt"]   # also the walk weight
    # spec 06 D3: base fare each service falls back to; per-service override
    # via svc["fare"]. At today's flat fare every fare term is exactly 0.
    fare_base = cfg.get("fare_base", DEFAULT_FARE)

    fixed = "fix_bins" in over
    ww = np.tile(cor.ww, (n, 1)) if fixed else rng.dirichlet(cor.ww * 300, n)
    xw = np.tile(cor.xw, (n, 1)) if fixed else rng.dirichlet(cor.xw * 300, n)
    vw_base = np.array(cfg["visitor"]["bin_weights"], float)
    vw_base = vw_base / vw_base.sum()
    vw = (np.tile(vw_base, (n, 1)) if fixed
          else rng.dirichlet(np.maximum(vw_base, 1e-3) * 100, n))
    s0 = cor.s0[None, :] * (1.0 if fixed
                            else rng.lognormal(0.0, cor.s0_se, (n, 3)))
    cf = np.tile(cor.cf, (n, 1)) if fixed else rng.dirichlet(cor.cf * 400, n)
    if over.get("no_bin0"):        # drop the 0-0.5-mi bin (old market defn)
        for arr in (ww, xw, vw):
            arr[:, 0] = 0.0
            arr /= arr.sum(axis=1, keepdims=True)

    def hdw(svc, period):
        """Headway may be scalar (uniform) or {'peak': h, 'offpeak': h}."""
        h = svc["headway"]
        return h[period] if isinstance(h, dict) else h

    def wait_of(svc, market, h):
        if market == "transfer":
            return np.minimum(h / 2.0, p["xcap"])
        if market == "visitor":
            return np.full(n, h / 2.0)
        if linear_wait:
            return np.full(n, h / 2.0)
        return np.minimum(h / 2.0, p["w0"] + p["lam"] * h)

    def util(svc, market, dists, walks, is_new, period, asc_scale=1.0,
             fare_scale=1.0):
        """(n, cells) utility of one service; walks[id(svc)] is the
        per-cell walk distance (mi) for this service. asc_scale scales the
        new line's ASC (0 = no-ASC counterfactual, spec 06 D1); fare_scale
        scales the fare term (0 = fare-free utility for the welfare passes,
        spec 06 D3). Both 1.0 defaults are numerical no-ops, so the ridership
        path is unchanged."""
        h = hdw(svc, period)
        walk_min = walks[id(svc)] / WALK_MPH * 60.0
        # inv_v[id(svc)] is 60/speed in min/mi, pre-shaped to broadcast against
        # (n, cells): a python scalar for exogenous services (old path, bitwise
        # unchanged) or an (n, 1) per-draw column where speed is derived.
        u = (p["bivt"][:, None] * dists[None, :] * inv_v[id(svc)]
             + bwait[:, None] * (wait_of(svc, market, h)[:, None]
                                 + walk_min[None, :]))
        if is_new:
            u = u + asc_scale * p["asc"][:, None]
        # spec 06 D3: fare enters BEHAVIOR here (bcost = utils per $, negative)
        # but the MONEY is never monetized through VOT -- welfare uses the
        # fare-free variant (fare_scale=0) and the dollar burden is a separate
        # stream. At flat fares svc_fare == fare_base, so this term is exactly
        # 0.0 and u is bitwise unchanged.
        bcost = p["bivt"] * 60.0 / p["vot_behav"]        # utils per $ (negative)
        u = u + fare_scale * bcost[:, None] * (svc.get("fare", fare_base)
                                               - fare_base)
        return u

    base_svcs = [(s, False) for s in cfg["services_base"].values()]
    systems = {
        "fold":   [(cfg["service_new"], True)],
        "retain": [(cfg["service_new"], True),
                   (cfg["services_base"]["local"], False)],
    }
    union = list(cfg["services_base"].values()) + [cfg["service_new"]]

    def inv_speed(svc):
        """60/speed (min/mi), pre-shaped for the util() broadcast. A service
        carrying a derived_speed block gets its average speed DERIVED per draw
        (spec 02 §4.9) -> (n, 1) column; otherwise (or under the exogenous_speed
        governance toggle) it stays the config scalar speed, so the exogenous
        ridership path is bitwise unchanged (measured stays measured)."""
        if "derived_speed" in svc and not over.get("exogenous_speed"):
            f = 60.0 / derived_speed_mph(svc, p)
            return f[:, None] if np.ndim(f) else f
        return 60.0 / svc["speed"]
    inv_v = {id(s): inv_speed(s) for s in union}

    def subcell_walks(legs):
        """Within-cell rider-position quadrature. A rider's absolute street
        position x is uniform over one grid period P = max(spacing); every
        service's per-leg walk distance is min(x mod sp, sp - x mod sp)
        from the SAME x -- heterogeneity lives in the rider, so services
        stay perfectly correlated and no variety bonus can arise. Identical
        joint columns are merged (aligned grids collapse K^2 -> ~7).
        Returns ({id(svc): (Q,) walk mi}, (Q,) weights)."""
        if not smooth_k:
            return ({id(s): np.array([legs * s["spacing"] / 4.0])
                     for s in union}, np.array([1.0]))
        x = (np.arange(smooth_k) + 0.5) / smooth_k * \
            max(s["spacing"] for s in union)
        def d(s):
            r = (x - s.get("grid_phase", 0.0)) % s["spacing"]
            return np.minimum(r, s["spacing"] - r)
        W = np.stack([d(s) for s in union])                  # (S, K)
        if legs == 2:
            W = (W[:, :, None] + W[:, None, :]).reshape(len(union), -1)
        uniq, inv = np.unique(np.round(W, 9).T, axis=0, return_inverse=True)
        subw = np.zeros(len(uniq))
        np.add.at(subw, inv, 1.0 / W.shape[1])
        W = uniq.T                                           # (S, Q)
        if over.get("walk_spread"):   # +/-15% walk-taste axis (sensitivity)
            t, tw = np.array([0.85, 1.0, 1.15]), np.array([0.25, 0.5, 0.25])
            W = (W[:, :, None] * t[None, None, :]).reshape(len(union), -1)
            subw = (subw[:, None] * tw[None, :]).ravel()
        return {id(s): W[i] for i, s in enumerate(union)}, subw

    def combine(svcs, market, dists, walks, period, asc_scale=1.0,
                fare_scale=1.0):
        """Each sub-rider takes their best available service (near-perfect
        substitutes on one street earn no logsum 'variety bonus' -- the
        red-bus/blue-bus correction). variety_logsum=True restores a
        theta=1 logsum as a sensitivity toggle. asc_scale/fare_scale thread
        to util() for the no-ASC / fare-free welfare passes (spec 06 D1/D3)."""
        us = np.stack([util(s, market, dists, walks, isn, period, asc_scale,
                            fare_scale) for s, isn in svcs])
        if over.get("variety_logsum"):
            m = us.max(axis=0)
            ls = m + np.log(np.exp(us - m).sum(axis=0))
            pnew = np.exp(us[0] - ls) if svcs[0][1] else None
            return ls, pnew
        best = us.max(axis=0)
        pnew = (us[0] >= best - 1e-12).astype(float) if svcs[0][1] else None
        return best, pnew

    def um_split(dv, e, S0, P):
        """Exact per-sub-cell binary-logit consumer surplus in utils (spec 06
        D10): CS/capita = ln(1 + S0*(e - 1)) with e = clipped exp(dv) reused
        from the pivot. Returns (infra, margin): um_infra = sum P*S0*dv (the
        existing-rider component, ramped separately per D6), um_margin =
        um_total - um_infra. Consumes NO rng."""
        cs = np.log1p(S0 * (e - 1.0))                        # (n, C, seg)
        infra = (P * S0 * dv[:, :, None]).sum(axis=(1, 2))
        return infra, (P * cs).sum(axis=(1, 2)) - infra

    def market_terms(market, dists, wts, period, dists_od=None):
        legs = 1 if market == "transfer" else 2
        walks, subw = subcell_walks(legs)
        Q = len(subw)
        dists_e = np.repeat(dists, Q)                        # (bins*Q,)
        # spec 06 B2/D7: full-O-D distance variant (transfer market only;
        # None elsewhere, so dcm_od below just reuses dcm).
        distsod_e = None if dists_od is None else np.repeat(dists_od, Q)
        walks_e = {k: np.tile(v, len(dists)) for k, v in walks.items()}
        wts_e = (wts[:, :, None] * subw[None, None, :]).reshape(n, -1)
        ls0, _ = combine(base_svcs, market, dists_e, walks_e, period)
        # spec 06 D3: fare-free base logsum for the welfare passes (fare term
        # zeroed); at flat fares it equals ls0 bitwise. base_svcs has no new
        # line, so asc_scale is irrelevant here -- only fare_scale=0 matters.
        ls0_ff = combine(base_svcs, market, dists_e, walks_e, period,
                         fare_scale=0.0)[0]
        out = {}
        for scen, svcs in systems.items():
            ls1, pnew = combine(svcs, market, dists_e, walks_e, period)
            dv = ls1 - ls0                                   # (n, bins*Q)
            e = np.exp(np.clip(dv, -20, 20))[:, :, None]
            if market == "visitor":
                S0 = np.clip(p["s0v"], 1e-6, 0.95)[:, None, None]
                P = wts_e[:, :, None]
            else:
                S0 = np.clip(s0, 1e-6, 0.95)[:, None, :]
                P = wts_e[:, :, None] * cf[:, None, :]
            S1 = S0 * e / (S0 * e + (1 - S0))                # pivot per sub-cell
            pn = 1.0 if pnew is None else pnew[:, :, None]
            # spec 06 B1+D3: welfare accumulators on the FARE-FREE utility
            # variant (fare_scale=0) -- fare money is NEVER monetized through
            # VOT (D3 blocking-finding fix); the dollar burden below is the
            # separate money-metric stream. NOT multiplied by pnew -- benefits
            # accrue to all corridor transit riders; pnew only splits
            # boardings. Signed dv (fold short trips can lose) flows unclipped.
            # At flat fares dv_ff == dv bitwise, so B1's values are unchanged.
            ls1_ff = combine(svcs, market, dists_e, walks_e, period,
                             1.0, 0.0)[0]
            dv_ff = ls1_ff - ls0_ff
            e_ff = np.exp(np.clip(dv_ff, -20, 20))[:, :, None]
            um_infra, um_margin = um_split(dv_ff, e_ff, S0, P)
            # no-ASC AND fare-free counterfactual (spec 06 D1/D3): re-combine
            # with the new line's ASC and the fare term BOTH zeroed, against
            # the fare-free base -- for monetization only.
            dv0 = combine(svcs, market, dists_e, walks_e, period,
                          0.0, 0.0)[0] - ls0_ff
            e0 = np.exp(np.clip(dv0, -20, 20))[:, :, None]
            um0_infra, um0_margin = um_split(dv0, e0, S0, P)
            # spec 06 B2/D7: signed diverted-car-trip-mile mass per
            # car-ownership segment, off the HEADLINE pivot only (no no-ASC
            # variant for car-miles), NOT scaled by pnew (a diverted car trip
            # stays diverted regardless of which service captures the rider),
            # unfloored (a fold short-trip loss is a real negative mass). The
            # transfer market's dists_e is the corridor-leg (access) distance
            # -- an undercount of the diverted VMT, since the car trip covers
            # the full O-D; dcm_od swaps in the full-O-D distance for the
            # SAME choice-probability mass (dS unchanged, only the mile
            # multiplier differs). Visitor has no car segments -- squeeze to
            # (n,) so it accumulates into cm_visitor, not cm_seg.
            dS = S1 - S0
            dcm = (P * dS * dists_e[None, :, None]).sum(axis=1)
            dcm_od = dcm if distsod_e is None else (
                P * dS * distsod_e[None, :, None]).sum(axis=1)
            if market == "visitor":
                dcm, dcm_od = dcm.sum(axis=1), dcm_od.sum(axis=1)
            # spec 06 D3: money-metric fare-burden mass (dollars). The fare
            # changed BEHAVIOR via the full-utility pivot above (S1, dS); here
            # the MONEY is booked separately -- rule-of-half on the margin,
            # (S0 + 0.5*dS), the full-utility choice pnew picking each rider's
            # fare (fold: all-new; retain: new-vs-local split). Base-service
            # fares == fare_base assumed; extend fare_chosen_0 if a config ever
            # sets base-service fares. Exactly 0 at flat fares (Dfare == 0).
            # I3 guard: the rule-of-half books the "before" fare as fare_base
            # for EVERY rider, so a base service quoting its own fare would
            # silently corrupt the dollar stream (fare_chosen_0, the pre-change
            # fare, is hardwired to fare_base). A crash beats a wrong money-
            # metric stream -- extend fare_chosen_0 before setting a base fare.
            assert all(s.get("fare", fare_base) == fare_base
                       for s in cfg["services_base"].values()), (
                "a base service sets a non-default 'fare'; fare_burden assumes "
                "base fares == fare_base -- extend fare_chosen_0 (the pre-change "
                "fare) to carry per-service base fares")
            fare_new = svcs[0][0].get("fare", fare_base)
            fare_local = svcs[-1][0].get("fare", fare_base)   # retain fallback
            fare_chosen = pn * fare_new + (1 - pn) * fare_local
            fb = (P * (S0 + 0.5 * dS)
                  * (fare_chosen - fare_base)).sum(axis=(1, 2))
            out[scen] = ((P * S1).sum(axis=(1, 2)),
                         (P * S1 * pn).sum(axis=(1, 2)),
                         um_infra, um_margin, um0_infra, um0_margin,
                         dcm, dcm_od, fb)
            den = (P * S0).sum(axis=(1, 2))
        return out, den

    # periods: single pass unless any service has {'peak','offpeak'} headways;
    # den/fx/fv are utility-free, so only the numerators vary by period and
    # blending numerators at common den == blending per-period ratios.
    tod = any(isinstance(s["headway"], dict) for s in union)
    periods = ([("peak", p["pkshare"]), ("offpeak", 1.0 - p["pkshare"])]
               if tod else [(None, 1.0)])

    def _col(x):
        """x as-is if a python-scalar weight (the tod=False wgt=1.0 literal or
        the no_transfer fx=0.0 literal -- broadcasts fine against any shape),
        else reshaped to (n, 1) so it lines up with the (n, seg) car-mile
        accumulators. In the normal case wgt (=pkshare) and fx (built from tau)
        are prior DRAWS, hence (n,) arrays -- not only when pinned via `over`."""
        return x if np.isscalar(x) else x[:, None]

    def system_response(wwA, xwA, vwA):
        num = {scen: 0.0 for scen in systems}
        num_new = {scen: 0.0 for scen in systems}
        # spec 06 B1: welfare numerators [um_infra, um_margin, um0_infra,
        # um0_margin] blended by wgt and combined with fx/fv exactly like num.
        um = {scen: [0.0, 0.0, 0.0, 0.0] for scen in systems}
        # spec 06 B2: diverted-trip-mile numerators [cm_seg, cm_visitor,
        # cm_seg_fullod], same TOD blend. cm_seg/cm_seg_fullod are (n, seg)
        # (walk + fx*transfer, no visitor -- visitor has no car segments);
        # cm_visitor is (n,) (fv*visitor only).
        cm = {scen: [0.0, 0.0, 0.0] for scen in systems}
        # spec 06 D3: money-metric fare-burden numerator ($), (n,) like num --
        # same wgt/fx/fv blend across all three markets (visitor pays fares
        # too). Zero at flat fares.
        fb = {scen: 0.0 for scen in systems}
        den = fx = fv = None
        for period, wgt in periods:
            mk_w, den_w = market_terms("walk", cor.wd, wwA, period)
            mk_x, den_x = market_terms("transfer", cor.xd, xwA, period, cor.xd_od)
            mk_v, den_v = market_terms("visitor", cor.wd, vwA, period)
            if den is None:   # utility-free, identical across periods
                fx = (0.0 if no_transfer
                      else p["tau"] * den_w / ((1 - p["tau"]) * den_x))
                fv = (0.0 if no_visitor
                      else p["phi"] * den_w / ((1 - p["phi"]) * den_v))
                den = den_w + fx * den_x + fv * den_v
            wgt_c, fx_c = _col(wgt), _col(fx)
            for scen in systems:
                num[scen] = num[scen] + wgt * (
                    mk_w[scen][0] + fx * mk_x[scen][0] + fv * mk_v[scen][0])
                num_new[scen] = num_new[scen] + wgt * (
                    mk_w[scen][1] + fx * mk_x[scen][1] + fv * mk_v[scen][1])
                for j in range(4):
                    um[scen][j] = um[scen][j] + wgt * (
                        mk_w[scen][j + 2] + fx * mk_x[scen][j + 2]
                        + fv * mk_v[scen][j + 2])
                cm[scen][0] = cm[scen][0] + wgt_c * (
                    mk_w[scen][6] + fx_c * mk_x[scen][6])
                cm[scen][1] = cm[scen][1] + wgt * (fv * mk_v[scen][6])
                cm[scen][2] = cm[scen][2] + wgt_c * (
                    mk_w[scen][7] + fx_c * mk_x[scen][7])
                fb[scen] = fb[scen] + wgt * (
                    mk_w[scen][8] + fx * mk_x[scen][8] + fv * mk_v[scen][8])
        return num, num_new, den, um, cm, fb

    num, num_new, den, um, cm, fb = system_response(ww, xw, vw)
    rshort = None
    if over.get("nonwork_short"):
        # sensitivity probe: LODES is commute-only, so the non-work market
        # inherits the work O-D shape; this tilts it toward shorter trips
        # (exp weight, L = 4 mi) for the non-work response only
        L = 4.0
        def tilt(w, d):
            t = w * np.exp(-d / L)[None, :]
            return t / t.sum(axis=1, keepdims=True)
        # welfare/car-mile/fare-burden exports are main-path only (B1/B2/D3);
        # the tilted umS/cmS/fbS are a future export design point (D8), dropped.
        numS, _, denS, _, _, _ = system_response(
            tilt(ww, cor.wd), tilt(xw, cor.xd), vw)
        rshort = {scen: numS[scen] / denS for scen in systems}

    out = {}
    for scen in systems:
        r_work = num[scen] / den
        r_nw = r_work if rshort is None else rshort[scen]
        ratio = p["ws"] * r_work + (1 - p["ws"]) * (1 + p["kappa"] * (r_nw - 1))
        newshare = num_new[scen] / num[scen]
        out[scen] = {"ratio": ratio, "newshare": newshare}

    res = {}
    for label, cap in ENVELOPES:
        d = {}
        for scen in systems:
            r = out[scen]["ratio"]
            rc = r if cap is None else np.minimum(r, 1 + cap)
            total = anchor * rc
            d[scen] = {"total": total,
                       "newline": total * out[scen]["newshare"]}
            # spec 06 B1: per-draw user benefit in equivalent IVT minutes,
            # person-scaled by the anchor and normalized like the ratio
            # (um/den), utils->minutes via |bivt|. WORK-SHAPED and PRE-BLEND
            # (spec 06 D8): the ws/kappa non-work expansion is ridership-only;
            # the BCA wrapper applies the benefits blend. total = infra +
            # margin, so totals are not returned.
            um_infra, um_margin, um0_infra, um0_margin = um[scen]
            for key, u_x in (("um_infra", um_infra), ("um_margin", um_margin),
                             ("um0_infra", um0_infra), ("um0_margin", um0_margin)):
                d[scen][key] = anchor * (u_x / den) / np.abs(p["bivt"])
            # spec 06 B2: diverted-trip-mile masses, per car-ownership
            # segment (cm_seg (n,3): walk+transfer, corridor-leg distance for
            # transfer -- documented undercount; cm_seg_fullod (n,3): same
            # but the transfer leg is the full O-D straight-line distance,
            # a D7 bound on that undercount). cm_visitor (n,): visitor market
            # has no car segments. Miles, not utils -- no /|bivt|.
            cm_seg, cm_visitor, cm_seg_fullod = cm[scen]
            d[scen]["cm_seg"] = anchor[:, None] * (cm_seg / den[:, None])
            d[scen]["cm_visitor"] = anchor * (cm_visitor / den)
            d[scen]["cm_seg_fullod"] = anchor[:, None] * (cm_seg_fullod / den[:, None])
            # spec 06 D3: fare-burden in DOLLARS -- person-scaled like the
            # ratio (fb/den), NO /|bivt| (this is money, not utils). The BCA
            # engine nets it against fare revenue at exactly $1. Work-shaped,
            # PRE-BLEND (like um/cm). Zero at flat fares.
            d[scen]["fare_burden"] = anchor * (fb[scen] / den)
        blend_ev = 0.5 * (d["fold"]["newline"] + d["retain"]["newline"])
        blend = np.where(rng.random(n) < 0.5,
                         d["fold"]["newline"], d["retain"]["newline"])
        d["blend"], d["blend_ev"] = blend, blend_ev
        res[label] = d
    res["ratio_fold"] = out["fold"]["ratio"]
    res["ratio_retain"] = out["retain"]["ratio"]
    res["newshare_retain"] = out["retain"]["newshare"]
    res["params"], res["anchor"] = p, anchor
    return res


def pct(x, q):
    return float(np.percentile(x, q))


def wpct(x, w, q):
    """Weighted percentile (cumulative-weight interpolation)."""
    i = np.argsort(x)
    cw = np.cumsum(w[i])
    return float(np.interp(q / 100.0, cw / cw[-1], x[i]))


def main(path):
    cor = Corridor(path)
    cfg = cor.cfg
    sn = cfg["service_new"]
    h = sn["headway"]
    hstr = (f"{h['peak']:.0f}/{h['offpeak']:.0f}-min pk/off"
            if isinstance(h, dict) else f"{h:.0f}-min")
    # spec 02 §4.9: with a derived_speed block the average speed is DERIVED from
    # the prior-central cruise/dwell and this spacing, not the config scalar.
    vc_c = sum(PRIORS["v_cruise"][:2]) / 2.0     # central grade-sep cruise, km/h
    dw_c = sum(PRIORS["dwell"][:2]) / 2.0        # central station dwell, s
    if "derived_speed" in sn:
        # float(): grade_sep_min_per_mile now returns a 0-d array for scalar
        # inputs (np.where in the jerk-limited stop_run_time), so coerce before
        # formatting -- the per-draw util path stays (n,) via inv_speed.
        spd = 60.0 / float(grade_sep_min_per_mile(vc_c, dw_c, sn["spacing"]))
        sstr = (f"{spd:.1f} mph derived ({vc_c:.0f} km/h cruise / {dw_c:.0f}s "
                f"dwell)")
    else:
        sstr = f"{sn['speed']:.0f} mph"
    print(f"=== {cfg['title']} : {sstr} / {hstr}"
          f" / {sn['spacing']:.2f}-mi stops ===")

    res = run(cor)
    summary = {}
    bands = {}
    for key in ("ratio_fold", "ratio_retain"):
        u = [100 * (pct(res[key], q) - 1) for q in (10, 50, 90)]
        summary[key] = u
        bands[key.split("_")[1]] = (u[0], u[2])
        print(f"implied corridor uplift, {key[6:]:>6}: "
              f"{'/'.join(f'{x:+.0f}%' for x in u)}")
    # reference classes: display-only, basis-tagged (spec 05 §4); the
    # in-band flag compares each analog to the MATCHING scenario's P10-P90
    print("reference analogs (display-only; regime x horizon):")
    for e in REFERENCE["uplift"]:
        lo, hi = bands[e["regime"]]
        flag = "inside" if lo <= e["pct"] <= hi else "outside"
        print(f"  {e['name']:24s} +{e['pct']}%  [{e['regime']}/{e['horizon']}]"
              f"  {flag} model P10-P90 vs {e['regime']} -- {e['note']}")
    s = REFERENCE["study"]
    print(f"  study average: {s['name']} +{s['pct']}% -- {s['note']}")
    for e in REFERENCE["alm_analogs"]:
        print(f"  ALM analog (absolute/accuracy only): {e['name']} -- {e['note']}")
    print(f"  mode bonus: {REFERENCE['mode_bonus']['name']} -- "
          f"{REFERENCE['mode_bonus']['note']}")
    print(f"retained-local share of corridor transit (P50): "
          f"{100 * (1 - pct(res['newshare_retain'], 50)):.0f}% "
          f"(was an invented 25-40% prior; now mechanistic)")

    print(f"\n{'envelope':>10} | {'newline fold P50':>16} {'retain P50':>10} | "
          f"{'blend P10':>9} {'P50':>7} {'P90':>7}")
    for label, _ in ENVELOPES:
        d = res[label]
        b = d["blend"]
        summary[label] = {
            "fold": [pct(d["fold"]["newline"], q) for q in (10, 50, 90)],
            "retain": [pct(d["retain"]["newline"], q) for q in (10, 50, 90)],
            "blend": [pct(b, 10), pct(b, 50), pct(b, 90)],
            "total_fold": [pct(d["fold"]["total"], q) for q in (10, 50, 90)],
        }
        print(f"{label:>10} | {pct(d['fold']['newline'], 50):16,.0f} "
              f"{pct(d['retain']['newline'], 50):10,.0f} | "
              f"{pct(b, 10):9,.0f} {pct(b, 50):7,.0f} {pct(b, 90):7,.0f}")
    o = REFERENCE["optimism"]
    print(f"outside-view accuracy prior (annotation, never a filter): "
          f"{o['name']} -- {o['note']}")
    if cfg.get("cross_check"):
        cc = cfg["cross_check"]
        print(f"cross-check: {cc['note']}: {cc['lo']:,}-{cc['hi']:,}/day "
              f"(a pivot result far outside this band is a finding to "
              f"report -- anchor or ASC mis-set -- not to force)")

    # ---- one-at-a-time sensitivity (uncapped expected blend P50) ----------
    central = {k: (lo + hi) / 2 for k, (lo, hi, _) in PRIORS.items()}
    central["fix_bins"] = 1
    def point(**kv):
        kv2 = dict(central); kv2.update({k: v for k, v in kv.items()
                                         if k not in ("cfg_patch",)})
        return pct(run(cor, n=4000, cfg_patch=kv.get("cfg_patch"),
                       linear_wait=kv.get("linear_wait", False),
                       no_transfer=kv.get("no_transfer", False),
                       no_visitor=kv.get("no_visitor", False),
                       **{k: v for k, v in kv2.items()
                          if k not in ("linear_wait", "no_transfer",
                                       "no_visitor")})["uncapped"]["blend_ev"], 50)
    base = point()
    rows = []
    def sens(label, **kv):
        v = point(**kv)
        rows.append((label, v, 100 * (v - base) / base))
    sens("anchor -> low", anchor=cfg["anchor_low"])
    sens("anchor -> high", anchor=cfg["anchor_high"])
    for k in PRIORS:
        lo, hi, _ = PRIORS[k]
        sens(f"{k} -> {lo}", **{k: lo})
        sens(f"{k} -> {hi}", **{k: hi})
    sens("asc -> 0.55 (untrimmed)", asc=0.55)
    sens("logsum variety bonus (rejected)", variety_logsum=True)
    sens("linear h/2 wait (old spec)", linear_wait=True)
    sens("no transfer market", no_transfer=True)
    sens("no visitor market", no_visitor=True)
    sens("no sub-half-mile bin (old defn)", no_bin0=1)
    sens("non-work trips shorter (4-mi tilt)", nonwork_short=1)
    sens("knife-edge choice (old spec)", smooth_k=0)
    sens("walk-taste spread +/-15%", walk_spread=1)
    sens("new-line stops offset 0.5 mi",
         cfg_patch={"service_new": dict(sn, grid_phase=0.5)})
    if "rapid" in cfg["services_base"] and cfg.get("rapid_alt"):
        sens("rapid base -> GTFS current",
             cfg_patch={"services_base": {"rapid": dict(
                 cfg["services_base"]["rapid"], **cfg["rapid_alt"])}})
    # spec 02 §4.9 governance toggle: restore the old scalar-speed path (uses
    # the config's exogenous fallback speed) -- should reproduce the pre-R6
    # headline, since central derived speed ~= the 30-mph fallback.
    sens("exogenous speed (old spec)", exogenous_speed=1)
    # spec 02 §4.9b jerk-kinematics rows (grade-separated services only): the
    # accel/jerk override keys on the derived_speed block. The comfort band is
    # ~0.5-1.0 m/s^3; the trapezoid row (j->inf, cap retained) is the R6
    # regression and should reproduce the pre-JK central to float precision.
    if "derived_speed" in sn:
        ds = sn["derived_speed"]
        sens("jerk 0.5 (comfort floor)",
             cfg_patch={"service_new": dict(sn,
                        derived_speed=dict(ds, jerk=0.5))})
        sens("jerk 1.0 (comfort ceiling)",
             cfg_patch={"service_new": dict(sn,
                        derived_speed=dict(ds, jerk=1.0))})
        sens("accel 1.3 (performance)",
             cfg_patch={"service_new": dict(sn,
                        derived_speed=dict(ds, accel=1.3))})
        sens("trapezoid kinematics (R6)",
             cfg_patch={"service_new": dict(sn,
                        derived_speed=dict(ds, jerk=1e9))})
    sens("new line 10/20-min headway",
         cfg_patch={"service_new": dict(sn, headway={"peak": 10.0,
                                                     "offpeak": 20.0})})
    sens("flat 5-min all day (old spec)",
         cfg_patch={"service_new": dict(sn, headway=5.0)})
    sens("new stop spacing 0.5 mi",
         cfg_patch={"service_new": dict(sn, spacing=0.5)})
    sens("new stop spacing 1.5 mi",
         cfg_patch={"service_new": dict(sn, spacing=1.5)})

    print(f"\n--- one-at-a-time sensitivity (central={base:,.0f}, "
          f"uncapped expected blend) ---")
    for label, v, d in sorted(rows, key=lambda r: -abs(r[2])):
        print(f"  {label:32s}: {v:8,.0f}  ({d:+.1f}%)")

    # rail-ASC premium bracket (spec 05 §3.4): central points at the
    # ABC-calibrated ASC x each premium multiplier. Reported as a band,
    # not a point -- the constant has the least local support of any
    # parameter for a rail-class product calibrated on bus experiments.
    if cfg.get("asc_bracket"):
        a0 = cfg.get("asc_calibrated", 0.109)
        print(f"\n--- rail-ASC premium bracket (calibrated asc={a0:.3f} "
              f"from the BUS 543 experiment; bracket borrowed from the "
              f"metro scenario -- README issue 14) ---")
        for m in cfg["asc_bracket"]:
            v = point(asc=a0 * m)
            print(f"  asc x {m:.2f} = {a0*m:.3f}: {v:8,.0f}")

    # ---- design sweep (off-peak = 2x peak) ---------------------------------
    heads = [5, 10, 15]
    sweep = {}
    if "derived_speed" in sn:
        # spec 02 §4.9: the speed axis IS the grade-separated cruise axis now;
        # derived average speed responds to spacing everywhere (mph in parens
        # at central dwell/spacing so the km/h cells stay readable).
        print("\n--- design sweep: central expected-blend P50 (uncapped; "
              "grade-sep cruise x peak headway, off-peak = 2x) ---")
        axis, keys = "grade_separated_cruise_kmh", [60, 70, 80, 90]
        print("               " + "".join(f"  h={hh:>2}min" for hh in heads))
        for vc in keys:
            mph = 60.0 / float(grade_sep_min_per_mile(float(vc), dw_c,
                                                       sn["spacing"]))
            sweep[vc] = [point(v_cruise=float(vc), cfg_patch={"service_new": dict(
                            sn, headway={"peak": float(hh), "offpeak": 2.0 * hh})})
                         for hh in heads]
            print(f"  {vc} km/h (~{mph:4.1f}mph)"
                  + "".join(f"  {x:7,.0f}" for x in sweep[vc]))
    else:
        # exogenous-speed corridors (e.g. the at-grade OC Streetcar, decision 5)
        # keep the measured-speed axis.
        print("\n--- design sweep: central expected-blend P50 (uncapped; "
              "h = peak, off-peak = 2x) ---")
        axis, keys = "exogenous_speed_mph", [20, 25, 30, 35]
        print("        " + "".join(f"  h={hh:>2}min" for hh in heads))
        for v in keys:
            sweep[v] = [point(cfg_patch={"service_new": dict(
                            sn, speed=float(v),
                            headway={"peak": float(hh), "offpeak": 2.0 * hh})})
                        for hh in heads]
            print(f"  {v} mph" + "".join(f"  {x:7,.0f}" for x in sweep[v]))

    dest = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "..", "outputs", f"results_{cor.name}.json")
    with open(dest, "w", encoding="utf-8") as f:
        json.dump({"config": cfg, "summary": summary,
                   "reference": REFERENCE,
                   "sensitivity": [{"label": l, "value": v, "pct": d}
                                   for l, v, d in rows],
                   "sweep": {str(k): sweep[k] for k in keys},
                   "sweep_axis": axis,
                   "central_blend": base}, f, indent=2)
    print(f"\n-> {dest}")


if __name__ == "__main__":
    main(sys.argv[1])
