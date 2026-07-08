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
REFERENCE = "Twin Cities +33% | UW +35% | Cleveland HealthLine +78%"

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
}
# cap treatments removed per user decision 2026-07: the headline is reported
# uncapped NEXT TO the backtest-calibrated (ABC) treatment -- see reweight_abc.py
ENVELOPES = [("uncapped", None)]


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

    def util(svc, market, dists, walks, is_new, period):
        """(n, cells) utility of one service; walks[id(svc)] is the
        per-cell walk distance (mi) for this service."""
        h, v = hdw(svc, period), svc["speed"]
        walk_min = walks[id(svc)] / WALK_MPH * 60.0
        u = (p["bivt"][:, None] * dists[None, :] * (60.0 / v)
             + bwait[:, None] * (wait_of(svc, market, h)[:, None]
                                 + walk_min[None, :]))
        if is_new:
            u = u + p["asc"][:, None]
        return u

    base_svcs = [(s, False) for s in cfg["services_base"].values()]
    systems = {
        "fold":   [(cfg["service_new"], True)],
        "retain": [(cfg["service_new"], True),
                   (cfg["services_base"]["local"], False)],
    }
    union = list(cfg["services_base"].values()) + [cfg["service_new"]]

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

    def combine(svcs, market, dists, walks, period):
        """Each sub-rider takes their best available service (near-perfect
        substitutes on one street earn no logsum 'variety bonus' -- the
        red-bus/blue-bus correction). variety_logsum=True restores a
        theta=1 logsum as a sensitivity toggle."""
        us = np.stack([util(s, market, dists, walks, isn, period)
                       for s, isn in svcs])
        if over.get("variety_logsum"):
            m = us.max(axis=0)
            ls = m + np.log(np.exp(us - m).sum(axis=0))
            pnew = np.exp(us[0] - ls) if svcs[0][1] else None
            return ls, pnew
        best = us.max(axis=0)
        pnew = (us[0] >= best - 1e-12).astype(float) if svcs[0][1] else None
        return best, pnew

    def market_terms(market, dists, wts, period):
        legs = 1 if market == "transfer" else 2
        walks, subw = subcell_walks(legs)
        Q = len(subw)
        dists_e = np.repeat(dists, Q)                        # (bins*Q,)
        walks_e = {k: np.tile(v, len(dists)) for k, v in walks.items()}
        wts_e = (wts[:, :, None] * subw[None, None, :]).reshape(n, -1)
        ls0, _ = combine(base_svcs, market, dists_e, walks_e, period)
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
            out[scen] = ((P * S1).sum(axis=(1, 2)),
                         (P * S1 * pn).sum(axis=(1, 2)))
            den = (P * S0).sum(axis=(1, 2))
        return out, den

    # periods: single pass unless any service has {'peak','offpeak'} headways;
    # den/fx/fv are utility-free, so only the numerators vary by period and
    # blending numerators at common den == blending per-period ratios.
    tod = any(isinstance(s["headway"], dict) for s in union)
    periods = ([("peak", p["pkshare"]), ("offpeak", 1.0 - p["pkshare"])]
               if tod else [(None, 1.0)])

    def system_response(wwA, xwA, vwA):
        num = {scen: 0.0 for scen in systems}
        num_new = {scen: 0.0 for scen in systems}
        den = fx = fv = None
        for period, wgt in periods:
            mk_w, den_w = market_terms("walk", cor.wd, wwA, period)
            mk_x, den_x = market_terms("transfer", cor.xd, xwA, period)
            mk_v, den_v = market_terms("visitor", cor.wd, vwA, period)
            if den is None:   # utility-free, identical across periods
                fx = (0.0 if no_transfer
                      else p["tau"] * den_w / ((1 - p["tau"]) * den_x))
                fv = (0.0 if no_visitor
                      else p["phi"] * den_w / ((1 - p["phi"]) * den_v))
                den = den_w + fx * den_x + fv * den_v
            for scen in systems:
                num[scen] = num[scen] + wgt * (
                    mk_w[scen][0] + fx * mk_x[scen][0] + fv * mk_v[scen][0])
                num_new[scen] = num_new[scen] + wgt * (
                    mk_w[scen][1] + fx * mk_x[scen][1] + fv * mk_v[scen][1])
        return num, num_new, den

    num, num_new, den = system_response(ww, xw, vw)
    rshort = None
    if over.get("nonwork_short"):
        # sensitivity probe: LODES is commute-only, so the non-work market
        # inherits the work O-D shape; this tilts it toward shorter trips
        # (exp weight, L = 4 mi) for the non-work response only
        L = 4.0
        def tilt(w, d):
            t = w * np.exp(-d / L)[None, :]
            return t / t.sum(axis=1, keepdims=True)
        numS, _, denS = system_response(tilt(ww, cor.wd), tilt(xw, cor.xd), vw)
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
    print(f"=== {cfg['title']} : {sn['speed']:.0f} mph / {hstr}"
          f" / {sn['spacing']:.2f}-mi stops ===")

    res = run(cor)
    summary = {}
    for key in ("ratio_fold", "ratio_retain"):
        u = [100 * (pct(res[key], q) - 1) for q in (10, 50, 90)]
        summary[key] = u
        print(f"implied corridor uplift, {key[6:]:>6}: "
              f"{'/'.join(f'{x:+.0f}%' for x in u)}")
    print(f"reference class: {REFERENCE}")
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
    sens("rapid base -> GTFS current",
         cfg_patch={"services_base": {"rapid": dict(
             cfg["services_base"]["rapid"], **cfg["rapid_alt"])}})
    sens("new line 25 mph",
         cfg_patch={"service_new": dict(sn, speed=25.0)})
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

    # ---- design sweep (h = peak headway; off-peak = 2x) --------------------
    print("\n--- design sweep: central expected-blend P50 (uncapped; "
          "h = peak, off-peak = 2x) ---")
    speeds, heads = [20, 25, 30, 35], [5, 10, 15]
    sweep = {}
    print("        " + "".join(f"  h={h:>2}min" for h in heads))
    for v in speeds:
        vals = [point(cfg_patch={"service_new": dict(
                    sn, speed=float(v),
                    headway={"peak": float(h), "offpeak": 2.0 * h})})
                for h in heads]
        sweep[v] = vals
        print(f"  {v} mph" + "".join(f"  {x:7,.0f}" for x in vals))

    dest = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "..", "outputs", f"results_{cor.name}.json")
    with open(dest, "w", encoding="utf-8") as f:
        json.dump({"config": cfg, "summary": summary,
                   "sensitivity": [{"label": l, "value": v, "pct": d}
                                   for l, v, d in rows],
                   "sweep": {str(v): sweep[v] for v in speeds},
                   "central_blend": base}, f, indent=2)
    print(f"\n-> {dest}")


if __name__ == "__main__":
    main(sys.argv[1])
