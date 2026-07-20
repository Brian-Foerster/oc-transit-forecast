# -*- coding: utf-8 -*-
"""Build tidy OC tract CSVs from raw ACS summary files + crosswalk analysis.

Phase 2a (spec 01 §9): the tidy oc_* outputs are DERIVED tables, so they are
written to data/derived (committed) rather than the gitignored data/raw/acs
where the phase-1 acquisition first left them; the raw summary-file inputs
stay in data/raw/acs with their provenance sidecars."""
import csv, hashlib, io, os, time, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "..", "data", "raw", "acs")
DER = os.path.join(HERE, "..", "data", "derived")

def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def write_csv(fname, header, rows, source_desc):
    path = os.path.join(DER, fname)
    rows = sorted(rows, key=lambda r: r[0])
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    with open(path + ".provenance.txt", "w", encoding="utf-8") as f:
        f.write(f"filename: {fname}\nderived_from: {source_desc}\n"
                f"bytes: {os.path.getsize(path)}\nsha256: {sha256_file(path)}\n"
                f"created: {time.strftime('%Y-%m-%dT%H:%M:%S%z')}\n")
    print(f"{fname}: {len(rows)} rows")
    return path

# ---------- table-based .dat files (2019 prototype, 2023) ----------
def tidy_dat(vintage, table, keep_ids, fname):
    src = os.path.join(RAW, f"acsdt5y{vintage}-{table.lower()}.dat")
    cols = [f"{table}_E{i}" for i in keep_ids] + [f"{table}_M{i}" for i in keep_ids]
    # dat naming: B01003_E001 style already
    rows, county, state = [], None, None
    with open(src, encoding="utf-8-sig") as f:
        r = csv.reader(f, delimiter="|")
        hdr = next(r)
        idx = {h: i for i, h in enumerate(hdr)}
        gi = idx["GEO_ID"]
        want = [idx[c.replace("_E", "_E").replace("_M", "_M")] for c in cols]
        e001 = idx[f"{table}_E001"]
        for row in r:
            g = row[gi]
            if g.startswith("1400000US06059"):
                rows.append([g[-11:]] + [row[j] for j in want])
            elif g == "0500000US06059":
                county = int(row[e001])
            elif g == "0400000US06":
                state = int(row[e001])
    # interleave E/M per id to match existing convention (E block then M block, as oc_b08141.csv)
    path = write_csv(fname, ["GEOID"] + cols, rows,
                     f"data/raw/acs/acsdt5y{vintage}-{table.lower()}.dat "
                     f"(see its .provenance.txt there for URL/sha256); "
                     f"filtered to GEO_ID prefix 1400000US06059")
    tract_sum = sum(int(r[1]) for r in rows if r[1] not in ("", ".") and int(r[1]) >= 0)
    print(f"  sanity {vintage} {table}: tracts={len(rows)} tract_sum_E001={tract_sum} "
          f"county_E001={county} match={tract_sum == county} state_E001={state}")

B08141_IDS = ["001", "002", "003", "004", "005", "016", "017", "018", "019", "020"]
B25044_IDS = ["001", "003", "010"]
B01003_IDS = ["001"]

tidy_dat(2019, "B08141", B08141_IDS, "oc_b08141_2019.csv")
tidy_dat(2019, "B25044", B25044_IDS, "oc_b25044_2019.csv")
tidy_dat(2019, "B01003", B01003_IDS, "oc_b01003_2019.csv")
tidy_dat(2023, "B25044", B25044_IDS, "oc_b25044_2023.csv")
tidy_dat(2023, "B01003", B01003_IDS, "oc_b01003_2023.csv")

# ---------- 2017 sequence-based files ----------
# geography: g20175ca.csv -> LOGRECNO for OC tracts (sumlevel 140, county 059)
logrec = {}
with open(os.path.join(RAW, "g20175ca.csv"), encoding="latin-1") as f:
    for row in csv.reader(f):
        # FILEID,STUSAB,SUMLEVEL,COMPONENT,LOGRECNO,...; GEOID field starts '1400000US'
        if row[2] == "140" and row[3] == "00":
            geoid_full = next((x for x in row if x.startswith("14000US")), None)
            if geoid_full and geoid_full.startswith("14000US06059"):
                logrec[row[4]] = geoid_full[-11:]
print(f"g20175ca: {len(logrec)} OC tract logrecnos")

def tidy_seq(seq, table, start, cell_offsets, fname):
    """start = 1-based field position of table cell 1; cell_offsets = 0-based offsets of wanted cells."""
    zpath = os.path.join(RAW, f"20175ca{seq}000.zip")
    data = {}
    with zipfile.ZipFile(zpath) as z:
        for kind in ("e", "m"):
            name = f"{kind}20175ca{seq}000.txt"
            with z.open(name) as fh:
                for row in csv.reader(io.TextIOWrapper(fh, encoding="latin-1")):
                    lr = row[5]
                    if lr in logrec:
                        vals = [row[start - 1 + o] for o in cell_offsets]
                        data.setdefault(lr, {})[kind] = vals
    ids = [f"{table}_{'E'}{i}" for i in cell_ids] + [f"{table}_{'M'}{i}" for i in cell_ids]
    rows = []
    for lr, d in data.items():
        rows.append([logrec[lr]] + d["e"] + d["m"])
    path = write_csv(fname, ["GEOID"] + ids, rows,
                     f"data/raw/acs/20175ca{seq}000.zip e/m20175ca{seq}000.txt "
                     f"+ data/raw/acs/g20175ca.csv (see their .provenance.txt "
                     f"there); table {table} start position {start}, "
                     f"lookup data/raw/acs/ACS_5yr_Seq_Table_Number_Lookup.txt")
    tract_sum = sum(int(r[1]) for r in rows if r[1] not in ("", "."))
    print(f"  sanity 2017 {table}: tracts={len(rows)} tract_sum_E001={tract_sum}")

# B08141 seq 0028, start 40, cells 1-5 and 16-20
cell_ids = B08141_IDS
tidy_seq("0028", "B08141", 40, [0, 1, 2, 3, 4, 15, 16, 17, 18, 19], "oc_b08141_2017.csv")
# B25044 seq 0105, start 114, cells 1 (total), 3 (owner 0veh), 10 (renter 0veh)
cell_ids = B25044_IDS
tidy_seq("0105", "B25044", 114, [0, 2, 9], "oc_b25044_2017.csv")
# B01003 seq 0003, start 130, cell 1
cell_ids = B01003_IDS
tidy_seq("0003", "B01003", 130, [0], "oc_b01003_2017.csv")

# ---------- crosswalk analysis ----------
pairs = []
with open(os.path.join(RAW, "tab20_tract20_tract10_natl.txt"), encoding="utf-8-sig") as f:
    r = csv.reader(f, delimiter="|")
    hdr = next(r)
    i20 = hdr.index("GEOID_TRACT_20"); i10 = hdr.index("GEOID_TRACT_10")
    iap = hdr.index("AREALAND_PART"); ia10 = hdr.index("AREALAND_TRACT_10")
    for row in r:
        if row[i20].startswith("06059") or row[i10].startswith("06059"):
            pairs.append((row[i10], row[i20], int(row[iap] or 0), int(row[ia10] or 0)))

# raw graph
from collections import defaultdict
t10_to_20 = defaultdict(set); t20_to_10 = defaultdict(set)
for g10, g20, ap, a10 in pairs:
    if g10 and g20:
        t10_to_20[g10].add(g20); t20_to_10[g20].add(g10)

def classify(t10_to_20, t20_to_10):
    one2one = split = merge = complex_ = 0
    kinds = {}
    for g10, s20 in t10_to_20.items():
        if len(s20) == 1:
            g20 = next(iter(s20))
            if len(t20_to_10[g20]) == 1:
                kinds[g10] = "1:1"; one2one += 1
            else:
                kinds[g10] = "merge"; merge += 1   # several 2010 -> one 2020
        else:
            if all(len(t20_to_10[g20]) == 1 for g20 in s20):
                kinds[g10] = "split"; split += 1   # one 2010 -> several 2020
            else:
                kinds[g10] = "complex"; complex_ += 1
    return kinds, one2one, split, merge, complex_

kinds_raw, o_r, s_r, m_r, c_r = classify(t10_to_20, t20_to_10)

# sliver-filtered: drop parts <2% of the 2010 tract's land area
t10f = defaultdict(set); t20f = defaultdict(set)
for g10, g20, ap, a10 in pairs:
    if g10 and g20 and (a10 == 0 or ap / a10 >= 0.02):
        t10f[g10].add(g20); t20f[g20].add(g10)
# rebuild t20f from surviving pairs only (both directions consistent)
kinds_f, o_f, s_f, m_f, c_f = classify(t10f, t20f)

# population share (2019 B01003 on 2010 tracts) in non-1:1 relationships
pop = {}
with open(os.path.join(DER, "oc_b01003_2019.csv"), encoding="utf-8") as f:
    rr = csv.reader(f); next(rr)
    for row in rr:
        pop[row[0]] = int(row[1])
tot = sum(pop.values())
non11_raw = sum(pop.get(g, 0) for g, k in kinds_raw.items() if k != "1:1")
non11_f = sum(pop.get(g, 0) for g, k in kinds_f.items() if k != "1:1")
n10 = len([g for g in t10_to_20 if g.startswith("06059")])
n20 = len([g for g in t20_to_10 if g.startswith("06059")])
print(f"crosswalk: OC 2010 tracts={n10}, 2020 tracts={n20}, overlap pairs={len(pairs)}")
print(f"raw:      1:1={o_r} split={s_r} merge={m_r} complex={c_r}; "
      f"pop in non-1:1 = {non11_raw}/{tot} = {non11_raw/tot:.1%}")
print(f"filtered (part>=2% of 2010 land): 1:1={o_f} split={s_f} merge={m_f} complex={c_f}; "
      f"pop in non-1:1 = {non11_f}/{tot} = {non11_f/tot:.1%}")
