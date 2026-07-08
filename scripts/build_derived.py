"""Compress data/raw into the small committed tables in data/derived:
  oc_tracts.csv        OC tract centroids (GEOID, lat, lon)
  oc_b08141.csv        ACS B08141 estimates for OC tracts (workers/transit
                       by vehicle availability)
  oc_tract_od.csv.gz   LODES commute flows aggregated to OC tract pairs
These three files (plus GTFS-derived corridor jsons) fully determine the model."""
import os
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "..", "data", "raw")
DER = os.path.join(HERE, "..", "data", "derived")
os.makedirs(DER, exist_ok=True)

# tract centroids
gaz = pd.read_csv(os.path.join(RAW, "gaz_tracts_06.txt"), sep="\t")
gaz.columns = [c.strip() for c in gaz.columns]
gaz["GEOID"] = gaz["GEOID"].astype(str).str.zfill(11)
oc = gaz[gaz["GEOID"].str.startswith("06059")]
oc[["GEOID", "INTPTLAT", "INTPTLONG"]].rename(
    columns={"INTPTLAT": "lat", "INTPTLONG": "lon"}).to_csv(
    os.path.join(DER, "oc_tracts.csv"), index=False)
print(f"oc_tracts.csv: {len(oc)} tracts")

# ACS B08141 estimates, OC tracts only
acs = pd.read_csv(os.path.join(RAW, "acsdt5y2023-b08141.dat"), sep="|",
                  dtype={"GEO_ID": str})
acs = acs[acs["GEO_ID"].str.startswith("1400000US06059", na=False)].copy()
acs["GEOID"] = acs["GEO_ID"].str[-11:]
keep = ["GEOID"] + [f"B08141_E{i:03d}" for i in list(range(1, 6)) + list(range(16, 21))]
acs[keep].to_csv(os.path.join(DER, "oc_b08141.csv"), index=False)
print(f"oc_b08141.csv: {len(acs)} tracts")

# LODES -> OC tract pairs
rows = []
reader = pd.read_csv(os.path.join(RAW, "ca_od_main_JT00_2022.csv.gz"),
                     chunksize=2_000_000,
                     usecols=["w_geocode", "h_geocode", "S000"],
                     dtype={"w_geocode": str, "h_geocode": str, "S000": np.int32})
for chunk in reader:
    ht = chunk["h_geocode"].str[:11]
    wt = chunk["w_geocode"].str[:11]
    sel = ht.str.startswith("06059") & wt.str.startswith("06059")
    if sel.any():
        rows.append(pd.DataFrame({"h": ht[sel], "w": wt[sel],
                                  "n": chunk.loc[sel, "S000"].to_numpy()}))
od = pd.concat(rows).groupby(["h", "w"], as_index=False)["n"].sum()
od.to_csv(os.path.join(DER, "oc_tract_od.csv.gz"), index=False, compression="gzip")
print(f"oc_tract_od.csv.gz: {len(od):,} pairs, {od['n'].sum():,} jobs")
