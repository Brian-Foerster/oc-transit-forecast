"""
Backtest: predict the Bravo! 543's own 2013 launch and compare to what
actually happened -- the corridor's natural experiment.

Setup (2013):
  base system : Route 43 local only -- ~12 mph, ~15-min headway, 1/4-mi stops
  build       : add 543 -- 15 mph, 10-min peak / 15-min off-peak (actual
                launch service), ~1-mi stops, Bravo branding (asc prior
                applies); 43 RETAINED
  anchor      : Route 43 ~13,000 route-total at launch x corridor share
                0.75-0.86 -> 9,750-11,180 corridor boardings

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


def backtest_corridor():
    """The June-2013 configuration (shared with reweight_abc.py)."""
    cor = Corridor(os.path.join(HERE, "..", "data", "derived",
                                "corridor_harbor.json"))
    cfg = copy.deepcopy(cor.cfg)
    cfg["anchor_low"], cfg["anchor_high"] = 9750, 11180
    cfg["services_base"] = {"local": {"speed": 12.0, "headway": 15.0,
                                      "spacing": 0.25}}
    cfg["service_new"] = {"speed": 15.0,
                          "headway": {"peak": 10.0, "offpeak": 15.0},
                          "spacing": 1.0}   # actual June-2013 launch service
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
    b0 = pct(run(cor, n=4000, **central)["uncapped"]["retain"]["newline"], 50)
    print(f"\ncentral 543 prediction: {b0:,.0f}")
    for label, patch, kv in [
        ("no Bravo branding (asc=0)", None, {"asc": 0.0}),
        ("543 flat 15-min (old spec)", {"service_new": dict(
            cfg["service_new"], headway=15.0)}, {}),
        ("543 at 20-min all day", {"service_new": dict(
            cfg["service_new"], headway=20.0)}, {}),
        ("543 at 13 mph (weaker TSP)", {"service_new": dict(
            cfg["service_new"], speed=13.0)}, {}),
        ("43 base 20-min headway", {"services_base": {"local": {
            "speed": 12.0, "headway": 20.0, "spacing": 0.25}}}, {}),
        ("43 base 10-min pk/15 off", {"services_base": {"local": {
            "speed": 12.0, "headway": {"peak": 10.0, "offpeak": 15.0},
            "spacing": 0.25}}}, {}),
    ]:
        d = dict(central); d.update(kv)
        v = pct(run(cor, n=4000, cfg_patch=patch, **d)
                ["uncapped"]["retain"]["newline"], 50)
        print(f"  {label:28s}: {v:8,.0f}  ({100*(v-b0)/b0:+.1f}%)")

    out = {"predicted_543": [pct(new, 10), pct(new, 50), pct(new, 90)],
           "observed_543": list(OBS_543), "uplift_pct": up}
    with open(os.path.join(HERE, "..", "outputs", "backtest_543.json"), "w",
              encoding="utf-8") as f:
        json.dump(out, f, indent=2)


if __name__ == "__main__":
    main()
