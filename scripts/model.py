"""
Monte-Carlo incremental pivot logit, nested within transit.

Structure (per market segment x distance bin):
  Each transit service s has utility
      V_s = bivt*IVT(d, speed_s) + bwait*wait_s(headway) + bwalk*walk(spacing_s)
            [+ asc for the NEW line]
  The rider's transit utility is the theta-logsum over available services;
  the pivot applies exp(dV) to base shares, where
      dV = logsum(new system) - logsum(base system).
  In the retain scenario the new line's boardings are total x P(new | transit),
  from the same logsum -- this replaces the old invented "retained share" and
  the fold/retain coin flip with mechanism. Fold removes the local, so short
  trips are charged the longer walk to rapid stops.

Markets: walk (both-ends LODES), transfer (one-end LODES via feeder crossings,
pinned to tau share of base boardings), visitor (resort market, pinned to phi
share; random arrival so wait = h/2). Non-work expansion via ws/kappa.

Wait: walk/visitor access uses eff_wait = min(h/2, w0 + lam*h) (arrival-
strategy closed form; visitors use h/2 -- no schedule adaptation); transfers
use min(h/2, xcap).

Uncertainty: behavioral params (bivt, ovt, asc) drawn triangular (peaked);
base shares jittered with ACS-published MOEs (delta-method SEs); bins
Dirichlet-resampled. NO envelope filter: implied uplift is reported against
the reference class and the headline shown uncapped / cap +80% / cap +55%.

usage: python model.py data/derived/corridor_harbor.json
"""
import copy, json, os, sys
import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

N = 40000
WALK_MPH = 3.0
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
}
ENVELOPES = [("uncapped", None), ("cap +80%", 0.80), ("cap +55%", 0.55)]


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


def run(cor, n=N, seed=42, linear_wait=False, no_transfer=False,
        no_visitor=False, cfg_patch=None, **over):
    """Vectorized MC. `over` pins any PRIORS key / 'anchor'; `cfg_patch`
    deep-merges into the corridor config (service definitions etc.)."""
    rng = np.random.default_rng(seed)
    cfg = copy.deepcopy(cor.cfg)
    if cfg_patch:
        for k, v in cfg_patch.items():
            if isinstance(v, dict) and isinstance(cfg.get(k), dict):
                cfg[k].update(v)
            else:
                cfg[k] = v

    def draw(key):
        if key in over:
            return np.full(n, float(over[key]))
        lo, hi, shape = PRIORS[key]
        if shape == "tri":
            return rng.triangular(lo, (lo + hi) / 2, hi, n)
        return rng.uniform(lo, hi, n)

    p = {k: draw(k) for k in PRIORS}
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

    def wait_of(svc, market, h):
        if market == "transfer":
            return np.minimum(h / 2.0, p["xcap"])
        if market == "visitor":
            return np.full(n, h / 2.0)
        if linear_wait:
            return np.full(n, h / 2.0)
        return np.minimum(h / 2.0, p["w0"] + p["lam"] * h)

    def util(svc, market, dists, is_new):
        """(n, bins) utility of one service for one market."""
        h, v, sp = svc["headway"], svc["speed"], svc["spacing"]
        legs = 1 if market == "transfer" else 2
        walk_min = legs * (sp / 4.0) / WALK_MPH * 60.0
        u = (p["bivt"][:, None] * dists[None, :] * (60.0 / v)
             + (bwait * (wait_of(svc, market, h) + walk_min))[:, None])
        if is_new:
            u = u + p["asc"][:, None]
        return u

    base_svcs = [(s, False) for s in cfg["services_base"].values()]
    systems = {
        "fold":   [(cfg["service_new"], True)],
        "retain": [(cfg["service_new"], True),
                   (cfg["services_base"]["local"], False)],
    }

    def combine(svcs, market, dists):
        """Each segment takes its best available service (near-perfect
        substitutes on one street earn no logsum 'variety bonus' -- the
        red-bus/blue-bus correction). variety_logsum=True restores a
        theta=1 logsum as a sensitivity toggle."""
        us = np.stack([util(s, market, dists, isn) for s, isn in svcs])
        if over.get("variety_logsum"):
            m = us.max(axis=0)
            ls = m + np.log(np.exp(us - m).sum(axis=0))
            pnew = np.exp(us[0] - ls) if svcs[0][1] else None
            return ls, pnew
        best = us.max(axis=0)
        pnew = (us[0] >= best - 1e-12).astype(float) if svcs[0][1] else None
        return best, pnew

    def market_terms(market, dists, wts):
        ls0, _ = combine(base_svcs, market, dists)
        out = {}
        for scen, svcs in systems.items():
            ls1, pnew = combine(svcs, market, dists)
            dv = ls1 - ls0                                   # (n, bins)
            e = np.exp(np.clip(dv, -20, 20))[:, :, None]
            if market == "visitor":
                S0 = np.clip(p["s0v"], 1e-6, 0.95)[:, None, None]
                P = wts[:, :, None]
            else:
                S0 = np.clip(s0, 1e-6, 0.95)[:, None, :]
                P = wts[:, :, None] * cf[:, None, :]
            S1 = S0 * e / (S0 * e + (1 - S0))
            pn = 1.0 if pnew is None else pnew[:, :, None]
            out[scen] = ((P * S1).sum(axis=(1, 2)),
                         (P * S1 * pn).sum(axis=(1, 2)))
            den = (P * S0).sum(axis=(1, 2))
        return out, den

    mk_w, den_w = market_terms("walk", cor.wd, ww)
    mk_x, den_x = market_terms("transfer", cor.xd, xw)
    mk_v, den_v = market_terms("visitor", cor.wd, vw)

    fx = 0.0 if no_transfer else p["tau"] * den_w / ((1 - p["tau"]) * den_x)
    fv = 0.0 if no_visitor else p["phi"] * den_w / ((1 - p["phi"]) * den_v)
    den = den_w + fx * den_x + fv * den_v

    out = {}
    for scen in systems:
        num = mk_w[scen][0] + fx * mk_x[scen][0] + fv * mk_v[scen][0]
        num_new = mk_w[scen][1] + fx * mk_x[scen][1] + fv * mk_v[scen][1]
        r_work = num / den
        ratio = p["ws"] * r_work + (1 - p["ws"]) * (1 + p["kappa"] * (r_work - 1))
        newshare = num_new / num
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
    return res


def pct(x, q):
    return float(np.percentile(x, q))


def main(path):
    cor = Corridor(path)
    cfg = cor.cfg
    sn = cfg["service_new"]
    print(f"=== {cfg['title']} : {sn['speed']:.0f} mph / {sn['headway']:.0f}-min"
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
    sens("rapid base -> GTFS current",
         cfg_patch={"services_base": {"rapid": dict(
             cfg["services_base"]["rapid"], **cfg["rapid_alt"])}})
    sens("new line 25 mph",
         cfg_patch={"service_new": dict(sn, speed=25.0)})
    sens("new line 10-min headway",
         cfg_patch={"service_new": dict(sn, headway=10.0)})
    sens("new stop spacing 0.5 mi",
         cfg_patch={"service_new": dict(sn, spacing=0.5)})
    sens("new stop spacing 1.5 mi",
         cfg_patch={"service_new": dict(sn, spacing=1.5)})

    print(f"\n--- one-at-a-time sensitivity (central={base:,.0f}, "
          f"uncapped expected blend) ---")
    for label, v, d in sorted(rows, key=lambda r: -abs(r[2])):
        print(f"  {label:32s}: {v:8,.0f}  ({d:+.1f}%)")

    # ---- design sweep -------------------------------------------------------
    print("\n--- design sweep: central expected-blend P50 (uncapped) ---")
    speeds, heads = [20, 25, 30, 35], [5, 10, 15]
    sweep = {}
    print("        " + "".join(f"  h={h:>2}min" for h in heads))
    for v in speeds:
        vals = [point(cfg_patch={"service_new": dict(sn, speed=float(v),
                                                     headway=float(h))})
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
