"""
Backtest: predict the Bravo! 543's own 2013 launch and compare to what
actually happened -- the corridor's natural experiment.

Setup (2013):
  base system : Route 43 local only -- ~12 mph, ~15-min headway, 1/4-mi stops
  build       : add 543 -- 15 mph, 10-min peak / 15-min off-peak (use 15),
                ~1-mi stops, Bravo branding (asc prior applies); 43 RETAINED
  anchor      : Route 43 ~13,000 route-total at launch x corridor share
                0.75-0.86 -> 9,750-11,180 corridor boardings

Observed outcome:
  543 carried ~3,900/day by 2017 (Streetsblog) and averaged ~3,500/day over
  its first six years (OCTA 2019 release). 543 runs only the corridor, so
  these are corridor-consistent numbers -- the cleanest observable.

Caveats: 2022 LODES / 2023 ACS proxy for 2013 markets; midday headways
represent all-day service; observed 543 boardings include riders diverted
from Route 43, which the retain scenario's new-line split does model.
"""
import copy, json, os, sys
import numpy as np
from model import Corridor, run, pct

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
OBS_543 = (3500, 3900)

cor = Corridor(os.path.join(HERE, "..", "data", "derived",
                            "corridor_harbor.json"))
cfg = copy.deepcopy(cor.cfg)
cfg["anchor_low"], cfg["anchor_high"] = 9750, 11180
cfg["services_base"] = {"local": {"speed": 12.0, "headway": 15.0,
                                  "spacing": 0.25}}
cfg["service_new"] = {"speed": 15.0, "headway": 15.0, "spacing": 1.0}
cor.cfg = cfg

res = run(cor)
new = res["uncapped"]["retain"]["newline"]
tot = res["uncapped"]["retain"]["total"]
up = [100 * (pct(res["ratio_retain"], q) - 1) for q in (10, 50, 90)]

print("=== BACKTEST: Bravo! 543 launch (June 2013) ===")
print(f"predicted 543 weekday boardings (P10/P50/P90): "
      f"{pct(new,10):,.0f} / {pct(new,50):,.0f} / {pct(new,90):,.0f}")
print(f"OBSERVED 543: ~{OBS_543[0]:,} - {OBS_543[1]:,} "
      f"(6-yr avg .. 2017)")
print(f"predicted corridor transit uplift: "
      f"{'/'.join(f'{u:+.0f}%' for u in up)}")
print(f"  (observed corridor uplift is confounded by OCTA's 2013-2017 "
      f"systemwide ridership decline; the 543-boardings comparison above "
      f"is the clean observable)")

# sensitivity of the prediction to the shakiest backtest assumptions
central = {"bivt": -0.0265, "ovt": 2.05, "asc": 0.20, "w0": 5.5, "lam": 0.175,
           "xcap": 12.5, "tau": 0.325, "phi": 0.10, "s0v": 0.20,
           "ws": 0.50, "kappa": 0.80, "fix_bins": 1}
b0 = pct(run(cor, n=4000, **central)["uncapped"]["retain"]["newline"], 50)
print(f"\ncentral 543 prediction: {b0:,.0f}")
for label, patch, kv in [
    ("no Bravo branding (asc=0)", None, {"asc": 0.0}),
    ("543 at 20-min all day", {"service_new": dict(cfg["service_new"],
                                                   headway=20.0)}, {}),
    ("543 at 13 mph (weaker TSP)", {"service_new": dict(cfg["service_new"],
                                                        speed=13.0)}, {}),
    ("43 base 20-min headway", {"services_base": {"local": {
        "speed": 12.0, "headway": 20.0, "spacing": 0.25}}}, {}),
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
