"""
Backtest-calibrated forecast (ABC reweighting), reported SIDE BY SIDE with
the uncalibrated answer -- never replacing it (no baked-in filter).

Mechanism: the SAME 40,000 parameter draws (common random numbers via
draw_params + shared seed) flow through (a) the 2013 Bravo! 543 backtest
configuration and (b) the forward Harbor forecast. Each draw is weighted by
how well its backtest prediction matches the observed 543 outcome:

    w_i ~ exp(-0.5 * ((pred_i - MU) / SIGMA)^2)

MU = 3,700 (center of the observed 3,500-3,900 range). SIGMA combines the
observation spread (~200: six-year average vs 2017 figure) with structural
error the draws do not carry (~450: 2022 LODES / 2023 ACS proxying 2013
markets, the 2013 Route 43's unknown peak headway, the anchor derivation
being inference) -> 500 central, reported at 350/800 as sensitivities.

This calibrates against the corridor's own natural experiment (local data),
which is categorically different from the rejected literature-envelope
filter; per user decision 2026-07 it REPLACES the old cap +80%/+55% columns
as the companion treatment to the uncapped headline.

usage: python reweight_abc.py [data/derived/corridor_harbor.json]
"""
import json, os, sys
import numpy as np
from model import Corridor, run, draw_params, pct, wpct, N
from backtest_543 import backtest_corridor, OBS_543

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
MU = 3700.0
SIGMAS = [500.0, 350.0, 800.0]          # central first, then sensitivities
SEED = 42


def main(path):
    cor = Corridor(path)
    params = draw_params(N, SEED)
    back = run(backtest_corridor(), params=params, seed=SEED)
    fwd = run(cor, params=params, seed=SEED)
    pred = back["uncapped"]["retain"]["newline"]     # per-draw 543 prediction

    out = {"mu": MU, "observed_543": list(OBS_543), "sigmas": {}}
    print(f"=== ABC calibration vs Bravo! 543 launch "
          f"(observed ~{OBS_543[0]:,}-{OBS_543[1]:,}; kernel mu={MU:,.0f}) ===")
    print(f"backtest per-draw prediction P10/P50/P90: "
          f"{pct(pred,10):,.0f} / {pct(pred,50):,.0f} / {pct(pred,90):,.0f}")

    for sigma in SIGMAS:
        w = np.exp(-0.5 * ((pred - MU) / sigma) ** 2)
        w /= w.sum()
        ess = 1.0 / np.sum(w ** 2)
        tag = "central" if sigma == SIGMAS[0] else "sensitivity"
        d = {"ess": float(ess), "tag": tag, "forecast": {}, "posterior": {}}
        if ess < 1000:
            print(f"  WARNING sigma={sigma:.0f}: ESS={ess:,.0f} < 1,000 -- "
                  f"kernel too tight; widen sigma rather than filter")
        for scen in ("fold", "retain"):
            x = fwd["uncapped"][scen]["newline"]
            d["forecast"][scen] = [wpct(x, w, q) for q in (10, 50, 90)]
        b = fwd["uncapped"]["blend"]
        d["forecast"]["blend"] = [wpct(b, w, q) for q in (10, 50, 90)]
        for k in ("asc", "bivt", "ovt"):
            d["posterior"][k] = [wpct(fwd["params"][k], w, q)
                                 for q in (10, 50, 90)]
        out["sigmas"][f"{sigma:.0f}"] = d

        if sigma == SIGMAS[0]:
            ub = [pct(b, q) for q in (10, 50, 90)]
            cb = d["forecast"]["blend"]
            print(f"\n{'treatment':>26} | {'P10':>7} {'P50':>7} {'P90':>7}")
            print(f"{'uncapped (headline)':>26} | "
                  f"{ub[0]:7,.0f} {ub[1]:7,.0f} {ub[2]:7,.0f}")
            print(f"{'backtest-calibrated (ABC)':>26} | "
                  f"{cb[0]:7,.0f} {cb[1]:7,.0f} {cb[2]:7,.0f}"
                  f"   (sigma={sigma:.0f}, ESS={ess:,.0f})")
            print(f"\nposterior vs prior (P10/P50/P90):")
            for k in ("asc", "bivt", "ovt"):
                pr = [pct(fwd["params"][k], q) for q in (10, 50, 90)]
                po = d["posterior"][k]
                print(f"  {k:5s} prior {pr[0]:+.3f}/{pr[1]:+.3f}/{pr[2]:+.3f}"
                      f"  ->  posterior {po[0]:+.3f}/{po[1]:+.3f}/{po[2]:+.3f}")
        else:
            cb = d["forecast"]["blend"]
            print(f"  sigma={sigma:3.0f}: blend "
                  f"{cb[0]:,.0f} / {cb[1]:,.0f} / {cb[2]:,.0f} "
                  f"(ESS={ess:,.0f})")

    # seed-robustness check: fresh draws, same kernel
    p2 = draw_params(N, SEED + 1)
    b2 = run(backtest_corridor(), params=p2, seed=SEED + 1)
    f2 = run(cor, params=p2, seed=SEED + 1)
    w2 = np.exp(-0.5 * ((b2["uncapped"]["retain"]["newline"] - MU)
                        / SIGMAS[0]) ** 2)
    w2 /= w2.sum()
    alt = wpct(f2["uncapped"]["blend"], w2, 50)
    ref = out["sigmas"][f"{SIGMAS[0]:.0f}"]["forecast"]["blend"][1]
    drift = 100 * (alt - ref) / ref
    out["seed_check_p50"] = [ref, alt]
    print(f"\nseed-robustness: calibrated blend P50 {ref:,.0f} (seed {SEED}) "
          f"vs {alt:,.0f} (seed {SEED+1}) -- drift {drift:+.1f}%")

    dest = os.path.join(HERE, "..", "outputs", f"abc_{cor.name}.json")
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print(f"-> {dest}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else
         os.path.join(HERE, "..", "data", "derived", "corridor_harbor.json"))
