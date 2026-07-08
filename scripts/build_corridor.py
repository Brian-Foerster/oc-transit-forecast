"""
Corridor config -> model inputs json.

For a corridor defined by a GTFS route shape (optionally windowed):
  * corridor tracts (centroid within 0.9 mi), positions along the line
  * ACS market segments (worker mix + base transit share by vehicle avail.)
  * walk market: both-ends-in-corridor LODES flows -> distance bins
  * feeder crossings: other OCTA routes that genuinely cross the corridor
    (points near the line AND on both sides), with crossing position
  * transfer market: one-end-in-corridor LODES flows whose other end is
    within 0.9 mi of a crossing feeder -> on-line distance bins.
    Feeder access cost is common to base and build, so it cancels in the
    pivot; the feeder gates only *whether* access exists.

usage: python build_corridor.py config/harbor.json
"""
import json, math, os, sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "..", "data", "raw")
DER = os.path.join(HERE, "..", "data", "derived")
GTFS = os.path.join(RAW, "gtfs")

BUFFER_MI, XFER_BUFFER_MI = 0.9, 0.9
CROSS_NEAR, CROSS_FAR = 0.25, 1.0     # crossing test thresholds (mi)
MIN_TRIP_MI = 0.5
EDGES = np.array([0.5, 2.5, 4.75, 7.5, 10.25, 12.6])

MI_LAT = 69.05
MI_LON = 69.17 * math.cos(math.radians(33.77))


def load_gtfs():
    trips = pd.read_csv(os.path.join(GTFS, "trips.txt"), dtype=str)
    cal = pd.read_csv(os.path.join(GTFS, "calendar.txt"), dtype=str)
    shapes = pd.read_csv(os.path.join(GTFS, "shapes.txt"), dtype={"shape_id": str})
    st = pd.read_csv(os.path.join(GTFS, "stop_times.txt"), dtype=str,
                     usecols=["trip_id", "departure_time"])
    wk = set(cal[cal["monday"] == "1"]["service_id"])
    return trips, shapes, st, wk


def main_shape_xy(trips, shapes, wk, route):
    t = trips[(trips["route_id"] == route) & trips["service_id"].isin(wk)]
    best, bl = None, -1.0
    for sid in t["shape_id"].dropna().unique():
        s = shapes[shapes["shape_id"] == sid].sort_values("shape_pt_sequence")
        x = s["shape_pt_lon"].to_numpy() * MI_LON
        y = s["shape_pt_lat"].to_numpy() * MI_LAT
        L = float(np.sum(np.hypot(np.diff(x), np.diff(y))))
        if L > bl:
            best, bl = (x, y), L
    return best, bl


def midday_headway(trips, st, wk, route):
    t = trips[(trips["route_id"] == route) & trips["service_id"].isin(wk)]
    if len(t) == 0:
        return None
    d0 = t[t["direction_id"] == "0"] if (t["direction_id"] == "0").any() else t
    tt = st[st["trip_id"].isin(set(d0["trip_id"]))]
    starts = (tt.groupby("trip_id")["departure_time"].min()
                .map(lambda x: int(x[:2]) * 60 + int(x[3:5])).sort_values())
    mid = starts[(starts >= 9 * 60) & (starts <= 15 * 60)].to_numpy()
    if len(mid) < 3:
        return None
    return float(np.median(np.diff(mid)))


class Line:
    """Polyline with signed-offset projection."""
    def __init__(self, x, y):
        self.x, self.y = x, y
        self.seg = np.hypot(np.diff(x), np.diff(y))
        self.cum = np.concatenate([[0.0], np.cumsum(self.seg)])
        self.L = self.cum[-1]
        self.ax, self.ay = x[:-1], y[:-1]
        self.dx, self.dy = np.diff(x), np.diff(y)
        self.L2 = np.where(self.seg == 0, 1.0, self.seg ** 2)

    def project(self, px, py):
        """-> (signed offset mi, position mi). Sign: + left of travel dir."""
        t = np.clip(((px - self.ax) * self.dx + (py - self.ay) * self.dy) / self.L2, 0, 1)
        qx, qy = self.ax + t * self.dx, self.ay + t * self.dy
        d = np.hypot(px - qx, py - qy)
        i = int(np.argmin(d))
        cross = self.dx[i] * (py - qy[i]) - self.dy[i] * (px - qx[i])
        return math.copysign(d[i], cross if cross != 0 else 1.0), \
               float(self.cum[i] + t[i] * self.seg[i])


def bin_flows(dists, weights):
    idx = np.digitize(dists, EDGES) - 1
    counts = np.zeros(len(EDGES) - 1)
    sums = np.zeros(len(EDGES) - 1)
    ok = (idx >= 0) & (idx < len(counts))
    np.add.at(counts, idx[ok], weights[ok])
    np.add.at(sums, idx[ok], (weights * dists)[ok])
    w = counts / counts.sum() if counts.sum() > 0 else counts
    centers = np.where(counts > 0, sums / np.maximum(counts, 1e-9),
                       0.5 * (EDGES[:-1] + EDGES[1:]))
    return w, centers, counts


def main(cfg_path):
    cfg = json.load(open(cfg_path, encoding="utf-8"))
    trips, shapes, st, wk = load_gtfs()
    (sx, sy), L = main_shape_xy(trips, shapes, wk, cfg["corridor_route"])
    line = Line(sx, sy)
    w0, w1 = cfg["window_mi"] or [0.0, line.L]
    print(f"{cfg['name']}: shape {line.L:.1f} mi, window {w0:.2f}-{w1:.2f}")

    tr = pd.read_csv(os.path.join(DER, "oc_tracts.csv"), dtype={"GEOID": str})
    off = np.empty(len(tr)); pos = np.empty(len(tr))
    for i, r in enumerate(tr.itertuples()):
        off[i], pos[i] = line.project(r.lon * MI_LON, r.lat * MI_LAT)
    tr["off"], tr["pos"] = off, pos
    corr = tr[(np.abs(tr["off"]) <= BUFFER_MI) & tr["pos"].between(w0, w1)]
    posmap = dict(zip(corr["GEOID"], corr["pos"]))
    cset = set(posmap)
    print(f"  corridor tracts: {len(cset)}")

    # ---- ACS segments ----------------------------------------------------
    acs = pd.read_csv(os.path.join(DER, "oc_b08141.csv"), dtype={"GEOID": str})
    m = acs[acs["GEOID"].isin(cset)]
    def c(i): return f"B08141_E{i:03d}"
    wk0, wk1 = m[c(2)].sum(), m[c(3)].sum()
    wk2 = m[c(4)].sum() + m[c(5)].sum()
    t0, t1 = m[c(17)].sum(), m[c(18)].sum()
    t2 = m[c(19)].sum() + m[c(20)].sum()
    W = wk0 + wk1 + wk2
    segments = {
        "car_frac": [round(wk0 / W, 4), round(wk1 / W, 4), round(wk2 / W, 4)],
        "S0_by_car": [round(t0 / max(wk0, 1), 4), round(t1 / max(wk1, 1), 4),
                      round(t2 / max(wk2, 1), 4)],
        "S0_overall": round(m[c(16)].sum() / m[c(1)].sum(), 4),
        "workers_total": int(m[c(1)].sum()),
    }

    # ---- LODES walk + transfer flows --------------------------------------
    od = pd.read_csv(os.path.join(DER, "oc_tract_od.csv.gz"),
                     dtype={"h": str, "w": str})
    hin = od["h"].isin(cset); win = od["w"].isin(cset)

    both = od[hin & win].copy()
    d = (both["h"].map(posmap) - both["w"].map(posmap)).abs()
    wwts, wctr, wcnt = bin_flows(d.to_numpy(), both["n"].to_numpy(float))

    # feeder crossings
    routes = pd.read_csv(os.path.join(GTFS, "routes.txt"), dtype=str)
    feeders = []
    for rid in routes["route_id"]:
        if rid in cfg["excluded_feeders"]:
            continue
        res, fl = main_shape_xy(trips, shapes, wk, rid)
        if res is None or fl < 1.0:
            continue
        fx, fy = res
        step = max(1, len(fx) // 250)
        fx, fy = fx[::step], fy[::step]
        offs = np.empty(len(fx)); poss = np.empty(len(fx))
        for i in range(len(fx)):
            offs[i], poss[i] = line.project(fx[i], fy[i])
        near = np.abs(offs) < CROSS_NEAR
        if not (near.any() and (offs > CROSS_FAR).any() and (offs < -CROSS_FAR).any()):
            continue
        j = int(np.argmin(np.abs(offs)))
        npos = poss[j]
        if not (w0 <= npos <= w1):
            continue
        hw = midday_headway(trips, st, wk, rid)
        feeders.append({"route": rid, "node_pos": round(float(npos), 2),
                        "headway": hw, "x": fx, "y": fy})
    print(f"  crossing feeders: {len(feeders)} "
          f"({[f['route'] for f in feeders]})")

    # nearest crossing feeder for every non-corridor tract
    out_tr = tr[~tr["GEOID"].isin(cset)]
    node_of = {}
    OX = out_tr["lon"].to_numpy() * MI_LON
    OY = out_tr["lat"].to_numpy() * MI_LAT
    bestd = np.full(len(out_tr), np.inf)
    bestn = np.full(len(out_tr), np.nan)
    for f in feeders:
        dmat = np.hypot(OX[:, None] - f["x"][None, :],
                        OY[:, None] - f["y"][None, :]).min(axis=1)
        upd = dmat < np.minimum(bestd, XFER_BUFFER_MI)
        bestd[upd] = dmat[upd]
        bestn[upd] = f["node_pos"]
    for g, nd, bd in zip(out_tr["GEOID"], bestn, bestd):
        if not np.isnan(nd):
            node_of[g] = float(nd)
    print(f"  feeder-served outside tracts: {len(node_of)} of {len(out_tr)}")

    one = pd.concat([
        od[hin & ~win].assign(cend=lambda x: x["h"], oend=lambda x: x["w"]),
        od[~hin & win].assign(cend=lambda x: x["w"], oend=lambda x: x["h"]),
    ])
    one["node"] = one["oend"].map(node_of)
    one = one.dropna(subset=["node"])
    one["d"] = (one["cend"].map(posmap) - one["node"]).abs()
    xwts, xctr, xcnt = bin_flows(one["d"].to_numpy(), one["n"].to_numpy(float))

    out = {
        "config": cfg,
        "segments": segments,
        "walk_bins": {"weights": [round(x, 4) for x in wwts],
                      "centers": [round(x, 2) for x in wctr],
                      "jobs": int(wcnt.sum())},
        "transfer_bins": {"weights": [round(x, 4) for x in xwts],
                          "centers": [round(x, 2) for x in xctr],
                          "jobs": int(xcnt.sum())},
        "feeders": [{k: f[k] for k in ("route", "node_pos", "headway")}
                    for f in feeders],
        "one_end_jobs_total": int(od[hin ^ win]["n"].sum()),
    }
    dest = os.path.join(DER, f"corridor_{cfg['name']}.json")
    with open(dest, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    print(f"  walk market: {out['walk_bins']['jobs']:,} jobs, "
          f"bins {out['walk_bins']['weights']}")
    print(f"  transfer market: {out['transfer_bins']['jobs']:,} of "
          f"{out['one_end_jobs_total']:,} one-end jobs, "
          f"bins {out['transfer_bins']['weights']}")
    print(f"  -> {dest}")


if __name__ == "__main__":
    main(sys.argv[1])

