"""
Streetcar anchor derivation (spec 05 §3.3) -- the cold-start's hard part.

Pattern: measured route-level boardings (data/derived/route_boardings.csv,
from extract_apc.py) x each route's SHAPE SHARE inside the streetcar
corridor buffer (0.9 mi, matching build_corridor.py). Routes running
substantially ALONG the corridor are base carriers and sum into the anchor;
routes that merely cross enter the model via the transfer market (tau) and
are excluded here to avoid double-counting.

Known weaknesses, stated up front (they are why the interval is wider than
Harbor's):
- No single parallel local traces the Pacific Electric ROW diagonal -- the
  anchor is a composite of partial overlaps, unlike Harbor's clean 43/543
  co-located pair.
- Boardings are assumed uniform along each route (the shape-share step);
  downtown segments may be more or less productive than route average.
- SARTC rail transfers (Metrolink/Amtrak) are NOT in the anchor -- OCTA
  GTFS only; they enter (partially) via tau. Genuinely new access from the
  greenfield ROW is out of scope by construction: upside risk.

usage: python anchor_streetcar.py     (reads config/streetcar.json)
"""
import json, math, os, sys
import numpy as np
import pandas as pd
from build_corridor import Line, load_gtfs, main_shape_xy, route_headways, \
    MI_LAT, MI_LON, BUFFER_MI

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
WEEKDAY_EQUIV = 318      # 7-day annual -> weekday (Sa ~0.65, Su+hol ~0.5)
PARALLEL_MIN_SHARE = 0.20  # below this a route is a crossing feeder, not a carrier
TREND = (0.90, 0.99)     # FY2019 -> FY2024+ system per-month ratio (anchor_from_apc.py)
UNIFORMITY = (0.80, 1.10)  # boardings-not-uniform-along-route spread


def main():
    cfg = json.load(open(os.path.join(HERE, "..", "config", "streetcar.json"),
                         encoding="utf-8"))
    wp = np.array(cfg["corridor_waypoints"], float)
    line = Line(wp[:, 1] * MI_LON, wp[:, 0] * MI_LAT)
    print(f"corridor: {line.L:.2f} mi, buffer {BUFFER_MI} mi")

    bd = pd.read_csv(os.path.join(HERE, "..", "data", "derived",
                                  "route_boardings.csv"), dtype={"route": str})
    fy19 = dict(zip(bd["route"], bd["fy2019"]))

    trips, shapes, st, wk = load_gtfs()
    routes = pd.read_csv(os.path.join(HERE, "..", "data", "raw", "gtfs",
                                      "routes.txt"), dtype=str)
    rows = []
    for rid in routes["route_id"]:
        res, fl = main_shape_xy(trips, shapes, wk, rid)
        if res is None or fl < 1.0:
            continue
        fx, fy = res
        step = max(1, len(fx) // 300)
        fx, fy = fx[::step], fy[::step]
        inside = 0
        for i in range(len(fx)):
            off, pos = line.project(fx[i], fy[i])
            if abs(off) <= BUFFER_MI and 0 <= pos <= line.L:
                inside += 1
        share = inside / len(fx)
        ann = fy19.get(rid.lstrip("0") or rid)
        if share > 0.02 and ann and not math.isnan(float(ann)):
            wd = float(ann) / WEEKDAY_EQUIV
            rows.append((rid, share, wd, share * wd))
    rows.sort(key=lambda r: -r[3])
    print(f"\n{'route':>6} {'shape-share':>11} {'FY2019 wd':>10} {'contrib':>9}")
    for rid, share, wd, contrib in rows[:14]:
        tag = "PARALLEL" if share >= PARALLEL_MIN_SHARE else "crossing (-> tau)"
        print(f"{rid:>6} {share:11.2f} {wd:10,.0f} {contrib:9,.0f}  {tag}")

    par = [(rid, share, wd, c) for rid, share, wd, c in rows
           if share >= PARALLEL_MIN_SHARE]
    base = sum(c for *_ , c in par)
    lo = base * UNIFORMITY[0] * TREND[0]
    hi = base * UNIFORMITY[1] * TREND[1]
    print(f"\nparallel carriers: {[r[0] for r in par]}")
    print(f"raw corridor boardings (FY2019): {base:,.0f}")
    print(f"anchor after uniformity {UNIFORMITY} x trend {TREND}: "
          f"{lo:,.0f} - {hi:,.0f}  -> round to 50")
    print("\nmeasured headways of parallel carriers (for services_base):")
    for rid, *_ in par:
        print(f"  route {rid}: {route_headways(trips, st, wk, rid)}")
    print("\nNOT in the anchor: SARTC Metrolink/Amtrak transfers (no OCTA "
          "GTFS), greenfield new access (out of scope; upside risk). "
          "Crossing routes enter via tau.")


if __name__ == "__main__":
    main()
