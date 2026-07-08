"""Estimate the share of Route 43's boardings that occur within the 12.1-mi
FTC->MacArthur corridor (the 543's extent). Route 43 runs ~18 mi to Costa
Mesa, so quoting its full-route boardings as a corridor anchor overstates.
Share is proxied two ways over Route 43's 0.9-mi buffer:
  * ACS transit-riding workers within the corridor window vs full route
  * LODES O-D flows (both ends in the Route 43 buffer, >=0.5 mi) with both
    ends inside the corridor window vs all
"""
import os
import numpy as np
import pandas as pd
from build_corridor import load_gtfs, main_shape_xy, Line, MI_LAT, MI_LON, DER

BUFFER = 0.9

trips, shapes, st, wk = load_gtfs()
(sx, sy), _ = main_shape_xy(trips, shapes, wk, "43")
line43 = Line(sx, sy)
(rx, ry), _ = main_shape_xy(trips, shapes, wk, "543")
line543 = Line(rx, ry)
print(f"Route 43 shape: {line43.L:.1f} mi; 543 (corridor): {line543.L:.1f} mi")

tr = pd.read_csv(os.path.join(DER, "oc_tracts.csv"), dtype={"GEOID": str})
o43 = np.empty(len(tr)); p43 = np.empty(len(tr)); o5 = np.empty(len(tr))
for i, r in enumerate(tr.itertuples()):
    o43[i], p43[i] = line43.project(r.lon * MI_LON, r.lat * MI_LAT)
    o5[i], _ = line543.project(r.lon * MI_LON, r.lat * MI_LAT)
in43 = np.abs(o43) <= BUFFER
incorr = in43 & (np.abs(o5) <= BUFFER)   # within corridor extent too
g43 = set(tr["GEOID"][in43]); gc = set(tr["GEOID"][incorr])
print(f"Route 43 buffer tracts: {len(g43)}; of those in corridor window: {len(gc)}")

acs = pd.read_csv(os.path.join(DER, "oc_b08141.csv"), dtype={"GEOID": str})
tw_all = acs[acs["GEOID"].isin(g43)]["B08141_E016"].sum()
tw_cor = acs[acs["GEOID"].isin(gc)]["B08141_E016"].sum()
print(f"ACS transit workers: corridor {tw_cor:,} / route {tw_all:,} "
      f"= {tw_cor/tw_all:.3f}")

od = pd.read_csv(os.path.join(DER, "oc_tract_od.csv.gz"), dtype={"h": str, "w": str})
pos = dict(zip(tr["GEOID"], p43))
m = od[od["h"].isin(g43) & od["w"].isin(g43)].copy()
m["d"] = (m["h"].map(pos) - m["w"].map(pos)).abs()
m = m[m["d"] >= 0.5]
j_all = m["n"].sum()
j_cor = m[m["h"].isin(gc) & m["w"].isin(gc)]["n"].sum()
print(f"LODES O-D jobs: corridor {j_cor:,} / route {j_all:,} = {j_cor/j_all:.3f}")
