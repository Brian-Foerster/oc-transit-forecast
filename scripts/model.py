"""
Monte-Carlo incremental pivot logit with:
  * arrival-strategy wait structure   eff_wait(h) = min(h/2, w0 + lam*h)
  * transfer market                    xfer_wait(h) = min(h/2, xcap),
    pinned to an on-board-survey transfer share of base boardings (tau)
  * non-work expansion                 ratio = ws*r_work + (1-ws)*(1+kappa*(r_work-1))
  * NO baked-in empirical-envelope filter: the implied corridor uplift is
    reported against reference-class benchmarks, and headline numbers are
    shown under each envelope treatment (none / cap +80% / cap +55%).
    Every structural knob appears in the one-at-a-time sensitivity table.

usage: python model.py data/derived/corridor_harbor.json
"""
import json, os, sys
import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

N = 40000
REFERENCE = "Twin Cities +33% | UW +35% | Cleveland HealthLine +78%"

# Monte-Carlo parameter ranges (uniform unless noted). Central = midpoint.
PRIORS = {
    "bivt":  (-0.035, -0.018),  # in-vehicle time coef, util/min (literature)
    "ovt":   (1.6, 2.5),        # wait weight relative to IVT
    "asc":   (0.0, 0.40),       # image/reliability constant (trimmed; was 0-0.55
                                #   before the explicit schedule-delay term)
    "w0":    (4.0, 7.0),        # scheduled-arrival platform wait, min
    "lam":   (0.10, 0.25),      # schedule-delay slope (per headway-min)
    "xcap":  (10.0, 15.0),      # transfer-wait cap (schedule coordination), min
    "tau":   (0.25, 0.40),      # transfer share of base boardings (survey range)
    "ws":    (0.40, 0.60),      # work share of boardings
    "kappa": (0.60, 1.00),      # non-work responsiveness vs work
    "ret":   (0.25, 0.40),      # riders staying on retained local
}
ENVELOPES = [("uncapped", None), ("cap +80%", 0.80), ("cap +55%", 0.55)]


def eff_wait(h, w0, lam):
    return np.minimum(h / 2.0, w0 + lam * h)


def xfer_wait(h, xcap):
    return np.minimum(h / 2.0, xcap)


class Corridor:
    def __init__(self, path):
        j = json.load(open(path, encoding="utf-8"))
        self.cfg = j["config"]
        self.name = self.cfg["name"]
        seg = j["segments"]
        self.cf = np.array(seg["car_frac"])
        self.s0 = np.array(seg["S0_by_car"])
        self.wd = np.array(j["walk_bins"]["centers"])
        self.ww = np.array(j["walk_bins"]["weights"])
        self.xd = np.array(j["transfer_bins"]["centers"])
        self.xw = np.array(j["transfer_bins"]["weights"])


def run(cor, n=N, seed=42, linear_wait=False, no_transfer=False, **over):
    """Vectorized MC. `over` pins any PRIORS key or service param to a value."""
    rng = np.random.default_rng(seed)
    cfg = cor.cfg

    def draw(key):
        if key in over:
            return np.full(n, float(over[key]))
        lo, hi = PRIORS[key]
        return rng.uniform(lo, hi, n)

    p = {k: draw(k) for k in PRIORS}
    anchor = (np.full(n, float(over["anchor"])) if "anchor" in over
              else rng.uniform(cfg["anchor_low"], cfg["anchor_high"], n))
    v0 = float(over.get("speed_exist", cfg["speed_exist_mph"]))
    h0 = float(over.get("headway_exist", cfg["headway_exist_min"]))
    v1 = float(over.get("speed_new", cfg["speed_new_mph"]))
    h1 = float(over.get("headway_new", cfg["headway_new_min"]))

    bwait = p["bivt"] * p["ovt"]
    if linear_wait:
        dW_walk = (h1 - h0) / 2.0 * np.ones(n)
    else:
        dW_walk = eff_wait(h1, p["w0"], p["lam"]) - eff_wait(h0, p["w0"], p["lam"])
    dW_xfer = xfer_wait(h1, p["xcap"]) - xfer_wait(h0, p["xcap"])
    ivt_per_mi = 60.0 / v1 - 60.0 / v0

    # per-draw input jitter: bin weights (Dirichlet), S0 (lognormal), car mix
    ww = (np.tile(cor.ww, (n, 1)) if "fix_bins" in over
          else rng.dirichlet(cor.ww * 300, n))
    xw = (np.tile(cor.xw, (n, 1)) if "fix_bins" in over
          else rng.dirichlet(cor.xw * 300, n))
    s0 = cor.s0[None, :] * (1.0 if "fix_bins" in over
                            else rng.lognormal(0.0, 0.10, (n, 3)))
    cf = (np.tile(cor.cf, (n, 1)) if "fix_bins" in over
          else rng.dirichlet(cor.cf * 400, n))

    def market(dists, wts, dwait):
        dv = (p["bivt"][:, None] * dists[None, :] * ivt_per_mi
              + (bwait * dwait)[:, None] + p["asc"][:, None])       # (n, bins)
        e = np.exp(dv)[:, :, None]                                   # (n,bins,1)
        S0 = np.clip(s0, 1e-6, 0.95)[:, None, :]                     # (n,1,3)
        S1 = S0 * e / (S0 * e + (1 - S0))
        P = wts[:, :, None] * cf[:, None, :]
        return (P * S1).sum(axis=(1, 2)), (P * S0).sum(axis=(1, 2))

    num_w, den_w = market(cor.wd, ww, dW_walk)
    if no_transfer:
        num, den = num_w, den_w
    else:
        num_x, den_x = market(cor.xd, xw, dW_xfer)
        f = p["tau"] * den_w / ((1 - p["tau"]) * den_x)   # pins base xfer share
        num, den = num_w + f * num_x, den_w + f * den_x

    r_work = num / den
    ratio = p["ws"] * r_work + (1 - p["ws"]) * (1 + p["kappa"] * (r_work - 1))

    out = {}
    for label, cap in ENVELOPES:
        r = ratio if cap is None else np.minimum(ratio, 1 + cap)
        total = anchor * r
        retained = total * (1 - p["ret"])
        # mixture blend: carries the fold/retain design uncertainty in the band
        blend = np.where(rng.random(n) < 0.5, total, retained)
        # expected blend: deterministic per draw, for sensitivities/sweeps
        blend_ev = 0.5 * (total + retained)
        out[label] = {"total": total, "retained": retained,
                      "blend": blend, "blend_ev": blend_ev}
    out["ratio"] = ratio
    return out


def pct(x, q):
    return float(np.percentile(x, q))


def summarize(res):
    row = {}
    for label, _ in ENVELOPES:
        b = res[label]["blend"]; t = res[label]["total"]
        row[label] = {
            "blend": [pct(b, 10), pct(b, 50), pct(b, 90)],
            "total": [pct(t, 10), pct(t, 50), pct(t, 90)],
        }
    r = res["ratio"]
    row["uplift_pct"] = [100 * (pct(r, q) - 1) for q in (10, 50, 90)]
    return row


def main(path):
    cor = Corridor(path)
    cfg = cor.cfg
    print(f"=== {cfg['title']} : {cfg['speed_new_mph']:.0f} mph / "
          f"{cfg['headway_new_min']:.0f}-min new line ===")

    res = run(cor)
    s = summarize(res)
    print(f"\nimplied corridor uplift (P10/P50/P90): "
          f"{'/'.join(f'{u:+.0f}%' for u in s['uplift_pct'])}")
    print(f"reference class: {REFERENCE}")
    print(f"\n{'envelope':>10} | {'blend P10':>9} {'P50':>7} {'P90':>7} | "
          f"{'total P50':>9}")
    for label, _ in ENVELOPES:
        b = s[label]["blend"]; t = s[label]["total"]
        print(f"{label:>10} | {b[0]:9,.0f} {b[1]:7,.0f} {b[2]:7,.0f} | "
              f"{t[1]:9,.0f}")

    # ---- one-at-a-time sensitivity (uncapped blend P50) --------------------
    central = {k: (lo + hi) / 2 for k, (lo, hi) in PRIORS.items()}
    central["fix_bins"] = 1
    base = pct(run(cor, n=4000, **central)["uncapped"]["blend_ev"], 50)
    rows = []
    def sens(label, **kv):
        d = dict(central); d.update(kv)
        v = pct(run(cor, n=4000, **d)["uncapped"]["blend_ev"], 50)
        rows.append((label, v, 100 * (v - base) / base))
    sens("anchor -> low",  anchor=cfg["anchor_low"])
    sens("anchor -> high", anchor=cfg["anchor_high"])
    for k in ("bivt", "ovt", "asc", "w0", "lam", "xcap", "tau", "ws", "kappa"):
        lo, hi = PRIORS[k]
        sens(f"{k} -> {lo}", **{k: lo})
        sens(f"{k} -> {hi}", **{k: hi})
    sens("asc -> 0.55 (untrimmed)", asc=0.55)
    sens("linear h/2 wait (old spec)", linear_wait=True)
    sens("no transfer market (old spec)", no_transfer=True)
    sens("exist svc -> GTFS current",
         speed_exist=cfg["speed_exist_alt"], headway_exist=cfg["headway_exist_alt"])
    sens("new line 25 mph", speed_new=25.0)
    sens("new line 10-min headway", headway_new=10.0)

    print(f"\n--- one-at-a-time sensitivity (central={base:,.0f}, uncapped blend) ---")
    for label, v, d in sorted(rows, key=lambda r: -abs(r[2])):
        print(f"  {label:32s}: {v:8,.0f}  ({d:+.1f}%)")

    # ---- design sweep (central values, uncapped) ---------------------------
    print("\n--- design sweep: central blend P50 (uncapped) ---")
    speeds, heads = [20, 25, 30, 35], [5, 10, 15]
    print("        " + "".join(f"  h={h:>2}min" for h in heads))
    sweep = {}
    for v in speeds:
        vals = [pct(run(cor, n=4000, speed_new=v, headway_new=h,
                        **central)["uncapped"]["blend_ev"], 50) for h in heads]
        sweep[v] = vals
        print(f"  {v} mph" + "".join(f"  {x:7,.0f}" for x in vals))

    dest = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "..", "outputs", f"results_{cor.name}.json")
    with open(dest, "w", encoding="utf-8") as f:
        json.dump({"config": cfg, "summary": s,
                   "sensitivity": [{"label": l, "value": v, "pct": d}
                                   for l, v, d in rows],
                   "sweep": {str(v): sweep[v] for v in speeds},
                   "central_blend": base}, f, indent=2)
    print(f"\n-> {dest}")


if __name__ == "__main__":
    main(sys.argv[1])

