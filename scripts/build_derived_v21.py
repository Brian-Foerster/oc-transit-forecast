"""v2.1 block-resolution derived tables (spec 01 §9 / phase 2a).

Compresses the phase-1 acquisition raws (data/raw, untracked -- provenance
sidecars alongside each file) into the committed block-level tables the §9
predictor machinery (screen_common_v21.py) reads:

  oc_blocks.csv               OC 2020 tabulation blocks: GEOID20, internal
                              point (INTPTLAT20/INTPTLON20, raw TIGER strings),
                              ALAND20 (m^2), pop2020 (PL 94-171 P1/P0010001)
  oc_block_od_{2017,2019,2022}.csv.gz
                              LODES8 OC-to-OC block-pair job counts (h, w, n
                              = S000); ALL LODES8 years are enumerated on 2020
                              blocks (LODESTechDoc8.3 'Geography Vintage'), so
                              the three vintages share one block frame
  oc_block_wac_{2017,2019,2022}.csv
                              LODES8 WAC for OC blocks: GEOID20, C000, CNS15
                              (NAICS 61 edu), CNS16 (62 health), CNS17 (71
                              arts/rec), CNS18 (72 accommodation/food) -- the
                              §9.1 b4 generator-jobs columns (TechDoc8.3 map)
  oc_tract10_to_tract20.csv   OC 2010-tract -> 2020-tract apportionment
                              shares (pop-land overlap estimator, see
                              share_t10_to_t20 below): bridges the 2013-17 /
                              2015-19 ACS tidies (2010-tract geography) onto
                              the 2020-block frame

Deterministic: rows sorted on their key columns, LF newlines, utf-8, fixed
float format, gzip mtime pinned to 0 -- byte-identical on rerun.

The ACS tidy tables (oc_b25044_* / oc_b01003_* / oc_b08141_*) are built by
scripts/acs_vintage_build.py directly into data/derived (phase 2a moved them
out of the gitignored data/raw).

INPUT-SIDE ONLY (pre-registration hold, spec 01 §9): nothing here reads
boardings or fits anything.

    python -X utf8 scripts/build_derived_v21.py
"""
import gzip
import io
import os
import struct
import zipfile

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "..", "data", "raw")
DER = os.path.join(HERE, "..", "data", "derived")
os.makedirs(DER, exist_ok=True)

TIGER_ZIP = os.path.join(RAW, "tiger2020", "tl_2020_06059_tabblock20.zip")
BLOCK_POP = os.path.join(RAW, "census2020", "oc_2020_p1_block_pop.csv")
CROSSWALK = os.path.join(RAW, "acs", "tab20_tract20_tract10_natl.txt")
LODES8 = os.path.join(RAW, "lodes8")
OD_FILES = {  # 2022 OD was acquired earlier at the data/raw root (v2.0 build)
    "2017": os.path.join(LODES8, "ca_od_main_JT00_2017.csv.gz"),
    "2019": os.path.join(LODES8, "ca_od_main_JT00_2019.csv.gz"),
    "2022": os.path.join(RAW, "ca_od_main_JT00_2022.csv.gz"),
}
WAC_FILES = {y: os.path.join(LODES8, f"ca_wac_S000_JT00_{y}.csv.gz")
             for y in ("2017", "2019", "2022")}
WAC_COLS = ["C000", "CNS15", "CNS16", "CNS17", "CNS18"]


def _write_lf(path, text):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def _write_gz(path, text):
    """Deterministic gzip: mtime pinned to 0, no embedded filename."""
    with open(path, "wb") as f:
        with gzip.GzipFile(fileobj=f, mode="wb", compresslevel=9,
                           mtime=0) as g:
            g.write(text.encode("utf-8"))


# ---------------------------------------------------------------------------
# TIGER DBF (minimal dBase-III reader -- no geo dependency needed: the §9.2
# catchment rule uses block INTERNAL POINTS, which live in the DBF attributes)
# ---------------------------------------------------------------------------
def read_dbf(fileobj):
    """-> (fieldnames, iterator of dict rows). Values are stripped strings."""
    hdr = fileobj.read(32)
    n_rec, hdr_len, rec_len = struct.unpack("<IHH", hdr[4:12])
    fields = []
    while True:
        fd = fileobj.read(32)
        if fd[0:1] == b"\x0d":
            break
        name = fd[:11].split(b"\x00")[0].decode("ascii")
        length = fd[16]
        fields.append((name, length))
    fileobj.seek(hdr_len)
    rows = []
    for _ in range(n_rec):
        rec = fileobj.read(rec_len)
        if rec[0:1] == b"*":                       # deleted record
            continue
        pos, row = 1, {}
        for name, length in fields:
            row[name] = rec[pos:pos + length].decode("latin-1").strip()
            pos += length
        rows.append(row)
    return [f[0] for f in fields], rows


def build_blocks():
    with zipfile.ZipFile(TIGER_ZIP) as z:
        with z.open("tl_2020_06059_tabblock20.dbf") as f:
            names, rows = read_dbf(io.BytesIO(f.read()))
    pop = pd.read_csv(BLOCK_POP, dtype={"GEOID20": str})
    popmap = dict(zip(pop["GEOID20"], pop["P1_001N"].astype(int)))
    assert len(popmap) == len(pop), "duplicate GEOID20 in PL block pop"
    recs = []
    for r in rows:
        g = r["GEOID20"]
        assert g in popmap, f"block {g} missing from PL 94-171 pop table"
        recs.append((g, r["INTPTLAT20"], r["INTPTLON20"],
                     int(r["ALAND20"]), popmap[g]))
    assert len(recs) == len(popmap), \
        f"TIGER blocks {len(recs)} != PL pop rows {len(popmap)}"
    recs.sort(key=lambda t: t[0])
    lines = ["GEOID20,INTPTLAT20,INTPTLON20,ALAND20,pop2020"]
    lines += [f"{g},{la},{lo},{al},{p}" for g, la, lo, al, p in recs]
    _write_lf(os.path.join(DER, "oc_blocks.csv"), "\n".join(lines) + "\n")
    tot = sum(r[4] for r in recs)
    print(f"oc_blocks.csv: {len(recs)} blocks, pop2020 total {tot:,}")
    return {g: g[:11] for g, *_ in recs}, \
        {g[:11]: 0 for g, *_ in recs} | _tract20_pop(recs)


def _tract20_pop(recs):
    tp = {}
    for g, _la, _lo, _al, p in recs:
        tp[g[:11]] = tp.get(g[:11], 0) + p
    return tp


# ---------------------------------------------------------------------------
# LODES8 OD / WAC (2020-block geography for ALL years, LODESTechDoc8.3)
# ---------------------------------------------------------------------------
def build_od(year, path):
    parts = []
    reader = pd.read_csv(path, chunksize=2_000_000,
                         usecols=["w_geocode", "h_geocode", "S000"],
                         dtype={"w_geocode": str, "h_geocode": str,
                                "S000": np.int64})
    for chunk in reader:
        sel = (chunk["h_geocode"].str.startswith("06059")
               & chunk["w_geocode"].str.startswith("06059"))
        if sel.any():
            parts.append(chunk.loc[sel, ["h_geocode", "w_geocode", "S000"]])
    od = (pd.concat(parts)
          .rename(columns={"h_geocode": "h", "w_geocode": "w", "S000": "n"})
          .groupby(["h", "w"], as_index=False)["n"].sum()
          .sort_values(["h", "w"], kind="mergesort"))
    text = "h,w,n\n" + "".join(f"{h},{w},{n}\n" for h, w, n
                               in od.itertuples(index=False))
    out = os.path.join(DER, f"oc_block_od_{year}.csv.gz")
    _write_gz(out, text)
    print(f"oc_block_od_{year}.csv.gz: {len(od):,} block pairs, "
          f"{od['n'].sum():,} jobs, {os.path.getsize(out):,} bytes gz")


def build_wac(year, path):
    w = pd.read_csv(path, dtype={"w_geocode": str})
    w = w[w["w_geocode"].str.startswith("06059")]
    w = (w[["w_geocode"] + WAC_COLS]
         .rename(columns={"w_geocode": "GEOID20"})
         .sort_values("GEOID20", kind="mergesort"))
    lines = ["GEOID20," + ",".join(WAC_COLS)]
    lines += [",".join(str(v) for v in row)
              for row in w.itertuples(index=False)]
    _write_lf(os.path.join(DER, f"oc_block_wac_{year}.csv"),
              "\n".join(lines) + "\n")
    gen = int(w[["CNS15", "CNS16", "CNS17", "CNS18"]].to_numpy().sum())
    print(f"oc_block_wac_{year}.csv: {len(w):,} blocks with jobs, "
          f"C000 {int(w['C000'].sum()):,}, CNS15-18 {gen:,}")


# ---------------------------------------------------------------------------
# 2010-tract -> 2020-tract apportionment shares (for the 2013-17 / 2015-19
# ACS tidies, which the Census publishes on 2010 tract geography)
# ---------------------------------------------------------------------------
def share_t10_to_t20(parts, pop20):
    """parts: [(t10, t20, aland_part, aland_t20)]; pop20: {t20: 2020 pop}.
    Share of tract10's value assigned to each overlapping tract20 =
    estimated population overlap, pop20(t20) * aland_part / aland_t20
    (uniform-density-within-2020-tract estimator; EXACT for 1:1 tracts and
    pure splits, where the 2020 tract lies wholly inside the 2010 tract).
    Fallbacks when the estimate is degenerate for a tract10: land-part
    shares, then equal split. Returns {t10: [(t20, share)]}, shares > 0
    summing to 1 per t10."""
    by10 = {}
    for t10, t20, ap, a20 in parts:
        by10.setdefault(t10, []).append((t20, ap, a20))
    out = {}
    for t10, lst in sorted(by10.items()):
        w = [pop20.get(t20, 0) * (ap / a20 if a20 > 0 else 0.0)
             for t20, ap, a20 in lst]
        if sum(w) <= 0:
            w = [float(ap) for _t20, ap, _a20 in lst]
        if sum(w) <= 0:
            w = [1.0] * len(lst)
        tot = sum(w)
        out[t10] = sorted((t20, wi / tot) for (t20, _ap, _a20), wi
                          in zip(lst, w) if wi > 0)
    return out


def build_tract_bridge(tract20_pop):
    parts = []
    with open(CROSSWALK, encoding="utf-8-sig") as f:
        hdr = f.readline().rstrip("\n").split("|")
        i20 = hdr.index("GEOID_TRACT_20")
        i10 = hdr.index("GEOID_TRACT_10")
        iap = hdr.index("AREALAND_PART")
        ia20 = hdr.index("AREALAND_TRACT_20")
        for line in f:
            row = line.rstrip("\n").split("|")
            if row[i10].startswith("06059") and row[i20].startswith("06059"):
                parts.append((row[i10], row[i20],
                              int(row[iap] or 0), int(row[ia20] or 0)))
    shares = share_t10_to_t20(parts, tract20_pop)
    lines = ["tract10,tract20,share"]
    for t10 in sorted(shares):
        for t20, s in shares[t10]:
            lines.append(f"{t10},{t20},{s:.8f}")
    _write_lf(os.path.join(DER, "oc_tract10_to_tract20.csv"),
              "\n".join(lines) + "\n")
    n10 = len(shares)
    n20 = len({t20 for lst in shares.values() for t20, _ in lst})
    npairs = sum(len(lst) for lst in shares.values())
    print(f"oc_tract10_to_tract20.csv: {npairs} pairs, {n10} 2010 tracts -> "
          f"{n20} 2020 tracts")


if __name__ == "__main__":
    _b2t, t20pop = build_blocks()
    build_tract_bridge(t20pop)
    for y in ("2017", "2019", "2022"):
        build_wac(y, WAC_FILES[y])
    for y in ("2017", "2019", "2022"):
        build_od(y, OD_FILES[y])
