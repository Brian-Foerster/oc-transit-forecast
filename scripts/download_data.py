"""Fetch raw inputs into data/raw (gitignored, ~180 MB total).
Everything the model needs is derivable from these four public sources."""
import os, sys, urllib.request, zipfile

RAW = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
os.makedirs(RAW, exist_ok=True)

SOURCES = {
    # LEHD LODES8: CA commute O-D, all jobs, block level (96 MB)
    "ca_od_main_JT00_2022.csv.gz":
        "https://lehd.ces.census.gov/data/lodes/LODES8/ca/od/ca_od_main_JT00_2022.csv.gz",
    # ACS 2023 5-yr B08141 table-based summary file, all US geos (71 MB)
    "acsdt5y2023-b08141.dat":
        "https://www2.census.gov/programs-surveys/acs/summary_file/2023/table-based-SF/data/5YRData/acsdt5y2023-b08141.dat",
    # CA census-tract centroids (2 MB)
    "gaz_tracts_06.txt":
        "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2023_Gazetteer/2023_gaz_tracts_06.txt",
    # OCTA GTFS (4 MB)
    "octa_gtfs.zip":
        "https://www.octa.net/current/google_transit.zip",
}

def main():
    for name, url in SOURCES.items():
        dest = os.path.join(RAW, name)
        if os.path.exists(dest) and os.path.getsize(dest) > 0:
            print(f"have {name}")
            continue
        print(f"fetching {name} ...")
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=300) as r, open(dest, "wb") as f:
            while True:
                b = r.read(1 << 20)
                if not b:
                    break
                f.write(b)
        print(f"  {os.path.getsize(dest):,} bytes")
    gdir = os.path.join(RAW, "gtfs")
    if not os.path.exists(os.path.join(gdir, "shapes.txt")):
        with zipfile.ZipFile(os.path.join(RAW, "octa_gtfs.zip")) as z:
            z.extractall(gdir)
        print("extracted GTFS")

if __name__ == "__main__":
    sys.exit(main())
