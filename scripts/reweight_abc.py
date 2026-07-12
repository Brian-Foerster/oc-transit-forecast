"""
Backtest-calibrated forecast (ABC reweighting), reported SIDE BY SIDE with
the uncalibrated answer -- never replacing it (no baked-in filter).

Mechanism: the SAME 40,000 parameter draws (common random numbers via
draw_params + shared seed) flow through (a) the 2013 Bravo! 543 backtest
configuration and (b) the forward Harbor forecast. Each draw is weighted by
how well its backtest prediction matches the target 543 outcome:

    w_i ~ exp(-0.5 * ((pred_i - MU) / SIGMA)^2)

LAUNCH-EQUIVALENT TARGET (spec 02 §4.6; closes README known issue 15).
The earliest 543 measurement (FY2017 = 4,615/wd, anchor_from_apc.py) is four
years post-launch, after systemwide decline had begun; the model's backtest
predicts the LAUNCH response (its world is anchored to the June-2013 Route 43
level ~13,000/day), so a matured target under-states what the model predicts
and drags the ASC posterior down. We convert the FY2017 measurement to a
launch-equivalent level via OCTA's own measured FY2013/FY2017 system
back-trend:

    MU_LAUNCH = 4,615 x (FY2013 bus UPT / FY2017 bus UPT) = 4,615 x 1.28678
              ~ 5,938/wd  (central kernel: 543_launch_s500)

The old matured six-year average (mu=4,200) is RETAINED as a sensitivity row
(543_matured_s500), not deleted -- its output must reproduce the pre-retarget
central bit-for-bit under common random numbers (the regression gate).

Measured back-trend (dual-source verified 2026-07-11 -- Socrata monthly
module 8bui-9xvu summed Jul-Jun AND the TS2.1 2018-release annual Excel via
Wayback agree exactly; NTD report year proven = OCTA fiscal year by exact
monthly-sum matches for RY2015-2017):

  OCTA (NTD ID 90036) annual bus UPT, motorbus (MB, DO+PT):
    FY2012 52,530,933   FY2013 51,067,292   FY2014 48,561,206
    FY2015 46,696,936   FY2016 42,968,439   FY2017 39,686,125
    FY2018 39,055,987
  MB+CB (bus family): FY2013 51,419,189   FY2017 39,954,846

  back-trend FY2013/FY2017:  MB 1.28678  |  MB+CB 1.28693  (delta 0.01% --
    mode-choice immaterial; MB used).
  cross-check: NTD FY2017 MB 39,686,125 vs the repo's quarterly-report FY2017
    system boardings 38,677,431 -> +2.61% (NTD UPT is APC/sampling-adjusted
    and MB includes all contracted fixed-route service; within tolerance).

Why FY2013 is the CENTRAL ratio and FY2014 a ROW: the backtest world is
anchored to the June-2013 (FY2013-era) Route 43 level, so the observation
must be scaled to the SAME system vintage the model's anchor carries -- that
is FY2013. The FY2014 ratio (the 543's first full operating year, 1.22363 ->
mu ~5,647) is the defensible alternative reading of "launch-equivalent" and
differs by ~5%; it is exposed as its own kernel (543_launch14_s500), not
silently chosen against.

Sources (dual-source verified; do not "clean up" the ratio -- it is measured):
- https://data.transportation.gov/resource/8bui-9xvu.json  (Complete Monthly
  Ridership with Adjustments and Estimates; ntd_id='90036', Jul2012-Jun2017
  window, 420 rows, aggregated to Jul-Jun fiscal years)
- https://data.transportation.gov/resource/npsm-38gk.json  (2024 TS2.1 by
  Mode; validation RY2015-2017)
- TS2.1 2018-release Excel via Wayback (transit.dot.gov blocks scripts),
  UPT sheet, NTD ID 90036 -- FY2012-FY2018 full history.

SIGMA reasoning (updated, not re-derived): 500 central retains the ~400
structural-error floor (post-COVID 2022 LODES commute SHAPE and 2023 ACS
proxying the 2013 market, the 2013 Route 43's unknown peak headway) plus
observation-side spread that now includes back-trend VINTAGE uncertainty --
the FY2013-vs-FY2014 spread is itself visible as the 543_launch14_s500 row.
350/800 remain the width sensitivities.

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
SEED = 42

# NTD back-trend (data table + sources in the module docstring). Do NOT round
# the ratio -- it is a measured quantity carried at full precision.
UPT_FY2013_MB = 51_067_292
UPT_FY2014_MB = 48_561_206
UPT_FY2017_MB = 39_686_125
OBS_543_FY2017 = 4615.0                            # earliest measured 543 wd
BACKTREND_13 = UPT_FY2013_MB / UPT_FY2017_MB       # 1.28678
BACKTREND_14 = UPT_FY2014_MB / UPT_FY2017_MB       # 1.22363
MU_LAUNCH = OBS_543_FY2017 * BACKTREND_13          # ~5,938.5  central
MU_LAUNCH14 = OBS_543_FY2017 * BACKTREND_14        # ~5,647    FY2014-vintage row
MU_MATURED = 4200.0                                # old six-year avg (row)

# Five kernels: (label, mu, sigma, tag), CENTRAL FIRST. This is the single
# source of truth -- bca_export, make_charts and the tests import get_kernels()
# / central_label() instead of hardcoding labels, so the spec 02 §4.4 joint
# multi-experiment kernel can join later by appending rows here (abc_weights'
# signature does not change -- that is B4's design). Label = experiment +
# target flavor + sigma; two kernels now share sigma=500, which is why the
# JSON is keyed by label rather than by bare sigma.
KERNELS = [
    ("543_launch_s500",   MU_LAUNCH,   500.0, "central"),
    ("543_launch_s350",   MU_LAUNCH,   350.0, "sensitivity"),
    ("543_launch_s800",   MU_LAUNCH,   800.0, "sensitivity"),
    ("543_launch14_s500", MU_LAUNCH14, 500.0, "sensitivity"),   # FY2014 vintage
    ("543_matured_s500",  MU_MATURED,  500.0, "sensitivity"),   # spec 02 §4.6
]


def get_kernels():
    """(label, mu, sigma) triples for abc_weights, central first -- the single
    source of truth the downstream exporters import instead of hardcoding
    labels/sigmas."""
    return [(lbl, mu, sig) for lbl, mu, sig, _ in KERNELS]


def central_label():
    """Label of the tag=='central' kernel (the launch-equivalent one)."""
    return next(lbl for lbl, _, _, tag in KERNELS if tag == "central")


def _tag_of(label):
    return next(t for lbl, _, _, t in KERNELS if lbl == label)


def abc_weights(pred, kernels):
    """pred: (n,) backtest predictions; kernels: [(label, mu, sigma), ...]
    -> {label: normalized (n,) weights}.

    Each draw is weighted by a Gaussian kernel on its backtest prediction
    against the target mu; the weights are normalized to sum 1. `pred` is
    computed ONCE by the caller and reused across kernels (common random
    numbers), so adding kernels is free. The spec 02 §4.4 joint
    multi-experiment kernel joins by appending entries -- this signature does
    not change."""
    out = {}
    for label, mu, sigma in kernels:
        w = np.exp(-0.5 * ((pred - mu) / sigma) ** 2)
        w /= w.sum()
        out[label] = w
    return out


def main(path):
    cor = Corridor(path)
    params = draw_params(N, SEED)
    back = run(backtest_corridor(), params=params, seed=SEED)
    fwd = run(cor, params=params, seed=SEED)
    pred = back["uncapped"]["retain"]["newline"]     # per-draw 543 prediction
    kernels = get_kernels()
    weights = abc_weights(pred, kernels)
    p50_pred = pct(pred, 50)

    out = {
        "observed_543": list(OBS_543),
        "backtrend": {
            "upt_fy2013_mb": UPT_FY2013_MB,
            "upt_fy2017_mb": UPT_FY2017_MB,
            "ratio": BACKTREND_13,
            "source": "NTD 90036, see reweight_abc.py docstring",
        },
        "kernels": {},
    }

    print(f"=== ABC calibration vs Bravo! 543 launch "
          f"(observed ~{OBS_543[0]:,}-{OBS_543[1]:,}; launch-equivalent "
          f"mu={MU_LAUNCH:,.0f} = {OBS_543_FY2017:,.0f} x {BACKTREND_13:.5f} "
          f"NTD back-trend) ===")
    print(f"backtest per-draw prediction P10/P50/P90: "
          f"{pct(pred,10):,.0f} / {p50_pred:,.0f} / {pct(pred,90):,.0f}")
    resid = 100.0 * (p50_pred - MU_LAUNCH) / MU_LAUNCH
    resid_mat = 100.0 * (p50_pred - MU_MATURED) / MU_MATURED
    print(f"central residual: backtest P50 {p50_pred:,.0f} vs launch-eq mu "
          f"{MU_LAUNCH:,.0f} -> {resid:+.1f}%  "
          f"(was {resid_mat:+.1f}% at matured {MU_MATURED:,.0f} -- retarget "
          f"shrinks the one-sided residual)")

    for label, mu, sigma in kernels:
        w = weights[label]
        ess = 1.0 / np.sum(w ** 2)
        tag = _tag_of(label)
        d = {"mu": float(mu), "sigma": float(sigma), "ess": float(ess),
             "tag": tag, "forecast": {}, "posterior": {}}
        if ess < 1000:
            print(f"  WARNING {label}: ESS={ess:,.0f} < 1,000 -- kernel too "
                  f"tight; widen sigma rather than filter")
        for scen in ("fold", "retain"):
            x = fwd["uncapped"][scen]["newline"]
            d["forecast"][scen] = [wpct(x, w, q) for q in (10, 50, 90)]
        b = fwd["uncapped"]["blend"]
        d["forecast"]["blend"] = [wpct(b, w, q) for q in (10, 50, 90)]
        for k in ("asc", "bivt", "ovt"):
            d["posterior"][k] = [wpct(fwd["params"][k], w, q)
                                 for q in (10, 50, 90)]
        out["kernels"][label] = d

    # central table (uncapped | ABC side by side), then posterior, then one
    # line per sensitivity kernel.
    clbl = central_label()
    cd = out["kernels"][clbl]
    b = fwd["uncapped"]["blend"]
    ub = [pct(b, q) for q in (10, 50, 90)]
    cb = cd["forecast"]["blend"]
    print(f"\n{'treatment':>28} | {'P10':>7} {'P50':>7} {'P90':>7}")
    print(f"{'uncapped (headline)':>28} | "
          f"{ub[0]:7,.0f} {ub[1]:7,.0f} {ub[2]:7,.0f}")
    print(f"{'backtest-calibrated (ABC)':>28} | "
          f"{cb[0]:7,.0f} {cb[1]:7,.0f} {cb[2]:7,.0f}"
          f"   ({clbl}, ESS={cd['ess']:,.0f})")
    print(f"\nposterior vs prior (P10/P50/P90):")
    for k in ("asc", "bivt", "ovt"):
        pr = [pct(fwd["params"][k], q) for q in (10, 50, 90)]
        po = cd["posterior"][k]
        print(f"  {k:5s} prior {pr[0]:+.3f}/{pr[1]:+.3f}/{pr[2]:+.3f}"
              f"  ->  posterior {po[0]:+.3f}/{po[1]:+.3f}/{po[2]:+.3f}")
    print(f"\nsensitivity kernels (blend P10/P50/P90):")
    for label, mu, sigma in kernels:
        if label == clbl:
            continue
        dd = out["kernels"][label]
        cbk = dd["forecast"]["blend"]
        print(f"  {label:20s} mu={mu:6,.0f} sig={sigma:5.0f}: "
              f"{cbk[0]:,.0f} / {cbk[1]:,.0f} / {cbk[2]:,.0f} "
              f"(ESS={dd['ess']:,.0f})")

    # seed-robustness check: fresh draws, same central launch kernel
    c_mu, c_sig = next((mu, sig) for lbl, mu, sig in kernels if lbl == clbl)
    p2 = draw_params(N, SEED + 1)
    b2 = run(backtest_corridor(), params=p2, seed=SEED + 1)
    f2 = run(cor, params=p2, seed=SEED + 1)
    w2 = abc_weights(b2["uncapped"]["retain"]["newline"],
                     [(clbl, c_mu, c_sig)])[clbl]
    alt = wpct(f2["uncapped"]["blend"], w2, 50)
    ref = cd["forecast"]["blend"][1]
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
