"""
Backtest: predict the Bravo! 543's own 2013 launch and compare to what
actually happened -- the corridor's natural experiment.

Setup (2013) -- the world now lives in config/backtest_543.json (spec 08 A2b):
  base system : Route 43 local only -- ~12 mph, ~15-min headway, 1/4-mi stops
  build       : add 543 -- 15 mph, 10-min peak / 15-min off-peak (actual
                launch service), ~1-mi stops, Bravo branding (asc prior
                applies); 43 RETAINED
  anchor      : Route 43 ~13,000 route-total at launch (config leaf) x the
                SHARED corridor share 0.75-0.86 (config/harbor.json
                anchor_derivation.corr_share, cited by the forward anchor too)
                -> 9,750-11,180 corridor boardings, computed in code

Observed outcome (MEASURED, 2026-07 -- OCTA quarterly performance reports,
scripts/anchor_from_apc.py): 543 weekday boardings FY2017 = 4,615,
FY2019 = 3,739, FY2020-YTD = 3,376; six-year cumulative 6.4M (OCTA 2019
release) ~ 4,250/wd average. The old press figures (~3,500-3,900) were low.
543 runs only the corridor, so these are corridor-consistent numbers --
the cleanest observable. Launch-era target for calibration: ~4,200.

Caveats: 2022 LODES / 2023 ACS proxy for 2013 markets; the 2013 Route 43's
peak headway is unknown (flat 15 assumed; sensitivity row covers 10/15);
observed 543 boardings include riders diverted from Route 43, which the
retain scenario's new-line split does model. The per-draw prediction is
also the ABC calibration target -- see reweight_abc.py.
"""
import copy, json, os, sys
import numpy as np
from model import Corridor, run, pct, PRIORS
from assumptions import val

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
OBS_543 = val("obs_543")   # measured FY2019 wd .. FY2017 wd (anchor_from_apc.py)
SENS_N = val("sens_n")     # point-sensitivity draw count (unified with model.py)
BT_CONFIG = os.path.join(HERE, "..", "config", "backtest_543.json")


def backtest_corridor():
    """The June-2013 configuration (shared with reweight_abc.py). The 2013 world
    -- the local/rapid services and the Route-43 route-total anchor LEAF -- lives
    in config/backtest_543.json (spec 08 A2b: the last structured citation-drift
    nest, promoted out of this module). The corridor SHARE is not duplicated
    here: it is the SAME corr_share the forward Harbor anchor derivation cites,
    read from the Harbor corridor config this function already loads (one
    assumption, two citing derivations -- spec 08 §2). The anchor band is
    COMPUTED (route43_total x corr_share = 9,750-11,180)."""
    cor = Corridor(os.path.join(HERE, "..", "data", "derived",
                                "corridor_harbor.json"))
    bt = json.load(open(BT_CONFIG, encoding="utf-8"))
    cfg = copy.deepcopy(cor.cfg)
    corr_share = cfg["anchor_derivation"]["corr_share"]     # SHARED w/ forward
    total = bt["anchor"]["route43_total"]                   # ~13,000 (2013 leaf)
    lo, hi = total * corr_share[0], total * corr_share[1]
    assert (lo, hi) == (9750.0, 11180.0), (lo, hi)          # byte-identity guard
    cfg["anchor_low"], cfg["anchor_high"] = lo, hi
    cfg["services_base"] = bt["services_base"]
    cfg["service_new"] = bt["service_new"]
    cor.cfg = cfg
    return cor


def main():
    cor = backtest_corridor()
    cfg = cor.cfg

    res = run(cor)
    new = res["uncapped"]["retain"]["newline"]
    up = [100 * (pct(res["ratio_retain"], q) - 1) for q in (10, 50, 90)]

    print("=== BACKTEST: Bravo! 543 launch (June 2013) ===")
    print(f"predicted 543 weekday boardings (P10/P50/P90): "
          f"{pct(new,10):,.0f} / {pct(new,50):,.0f} / {pct(new,90):,.0f}")
    print(f"OBSERVED 543: ~{OBS_543[0]:,} - {OBS_543[1]:,} "
          f"(measured FY2019 wd .. FY2017 wd; 6-yr avg ~4,250)")
    print(f"predicted corridor transit uplift: "
          f"{'/'.join(f'{u:+.0f}%' for u in up)}")
    print(f"  (observed corridor uplift is confounded by OCTA's 2013-2017 "
          f"systemwide ridership decline; the 543-boardings comparison above "
          f"is the clean observable)")

    # sensitivity of the prediction to the shakiest backtest assumptions.
    # Prior-central pins are the PRIORS midpoints (spec 08: was a hardcoded dict
    # duplicating the 12 pre-D3 midpoints -- a live citation-drift instance;
    # now computed from PRIORS like model.py's central). Pinning the post-D3
    # priors (vot_behav, pcar*, v_cruise, dwell) is a no-op for this 2013 bus
    # backtest -- it sets no fares and no derived_speed block -- so the
    # prediction is unchanged (inside the byte-identical gate).
    central = {k: (lo + hi) / 2 for k, (lo, hi, _) in PRIORS.items()}
    central["fix_bins"] = 1
    b0 = pct(run(cor, n=SENS_N, **central)["uncapped"]["retain"]["newline"], 50)
    print(f"\ncentral 543 prediction: {b0:,.0f}")
    # spec 08 A2b: the six backtest sensitivity rows now carry a stable machine
    # `id` and are WRITTEN into backtest_543.json (a `sensitivity` block, pct vs
    # the central prediction) -- they were stdout-only and unverifiable before,
    # so the registry could not claim them (spec 08 §5 check 2). Additive: the
    # predicted/observed/uplift values are byte-unchanged.
    # NOTE (spec 08 A3, saves the next reviewer a re-derivation): bt_flat15
    # and bt_base_10_15 land BYTE-IDENTICAL values (confirmed in
    # outputs/backtest_543.json -- same value/pct to full float precision).
    # This is not a bug. The 2013 default world already has base 43 at flat
    # 15-min and 543 at 10-min peak/15-min off-peak (config/backtest_543.json).
    # bt_flat15 patches ONLY 543's headway to flat 15 (so 43=flat15, 543=flat15
    # -- equal headway, both lines, both TOD periods); bt_base_10_15 patches
    # ONLY 43's headway to 10/15 (so 43=10/15, 543=10/15 -- equal headway
    # again, just the other split). Speed and spacing for both lines are
    # untouched in both patches. Whenever the two lines share the SAME
    # headway in every TOD period, the wait term is identical for both
    # choices and cancels out of the 43-vs-543 utility DIFFERENCE -- so the
    # split is driven entirely by the (here, identical) non-wait terms,
    # regardless of what the shared headway value actually is (flat 15 vs a
    # 10/15 split). That is why these two differently-motivated patches
    # collapse to the same predicted value.
    sens_rows = []
    for sid, label, patch, kv in [
        ("bt_asc0", "no Bravo branding (asc=0)", None, {"asc": 0.0}),
        ("bt_flat15", "543 flat 15-min (old spec)", {"service_new": dict(
            cfg["service_new"], headway=15.0)}, {}),
        ("bt_20min", "543 at 20-min all day", {"service_new": dict(
            cfg["service_new"], headway=20.0)}, {}),
        ("bt_13mph", "543 at 13 mph (weaker TSP)", {"service_new": dict(
            cfg["service_new"], speed=13.0)}, {}),
        ("bt_base20", "43 base 20-min headway", {"services_base": {"local": {
            "speed": 12.0, "headway": 20.0, "spacing": 0.25}}}, {}),
        ("bt_base_10_15", "43 base 10-min pk/15 off", {"services_base": {"local": {
            "speed": 12.0, "headway": {"peak": 10.0, "offpeak": 15.0},
            "spacing": 0.25}}}, {}),
    ]:
        d = dict(central); d.update(kv)
        v = pct(run(cor, n=SENS_N, cfg_patch=patch, **d)
                ["uncapped"]["retain"]["newline"], 50)
        sens_rows.append({"id": sid, "label": label, "value": v,
                          "pct": 100 * (v - b0) / b0})
        print(f"  {label:28s}: {v:8,.0f}  ({100*(v-b0)/b0:+.1f}%)")

    out = {"predicted_543": [pct(new, 10), pct(new, 50), pct(new, 90)],
           "observed_543": list(OBS_543), "uplift_pct": up,
           "sensitivity_central": b0, "sensitivity": sens_rows}
    with open(os.path.join(HERE, "..", "outputs", "backtest_543.json"), "w",
              encoding="utf-8") as f:
        json.dump(out, f, indent=2)


if __name__ == "__main__":
    main()
