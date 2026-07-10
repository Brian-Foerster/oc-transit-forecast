"""Extract route-level annual boardings from the OCTA quarterly performance
report PDFs (data/raw/apc, fetched by download_data.py) into a committed
table. Serves the streetcar anchor derivation (spec 05 §3.3), the stage-1
DRM screen (spec 01), and the service-change panel (spec 02 §4.4).

Row format in the PDFs: `043 N 20.4% $3.79 ... 1,515,585 ...` -- route id,
zone letter, farebox %, dollar columns, then annual boardings as the first
7+-digit comma number. FY2018's PDF extracts unparseably and is skipped.

usage: python extract_apc.py   -> data/derived/route_boardings.csv
"""
import os, re, sys
import pypdf

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
APC = os.path.join(HERE, "..", "data", "raw", "apc")
DER = os.path.join(HERE, "..", "data", "derived")

FILES = {  # column label -> (file, period note)
    "fy2017": "FY2017-Q4-Detailed-Report-PM.pdf",     # Jul16-Jun17, full yr
    "fy2019": "FY-2019-Q4-Detailed-Report-PM.pdf",    # Jul18-Jun19, full yr
    "fy2020q3": "FY2020-Q3-Detailed-Report.pdf",      # Jul19-Mar20, 9 mo YTD
}
PAT = re.compile(r"^(\d{2,3}X?)\s+[NCS]\s+[\d.]+%.*?([\d,]{7,})")


def route_boardings(path):
    r = pypdf.PdfReader(path)
    routes = {}
    for pg in r.pages:
        t = (pg.extract_text() or "").replace(chr(0x202F), " ")
        for ln in t.splitlines():
            m = PAT.match(ln.strip())
            if m:
                routes.setdefault(m.group(1).lstrip("0") or "0",
                                  int(m.group(2).replace(",", "")))
    return routes


def main():
    cols = {}
    for label, fname in FILES.items():
        path = os.path.join(APC, fname)
        if not os.path.exists(path):
            print(f"missing {fname} -- run download_data.py first")
            return 1
        cols[label] = route_boardings(path)
        print(f"{label}: {len(cols[label])} routes, "
              f"total {sum(cols[label].values()):,}")
    allroutes = sorted(set().union(*cols.values()),
                       key=lambda r: (len(r), r))
    dest = os.path.join(DER, "route_boardings.csv")
    with open(dest, "w", encoding="utf-8") as f:
        f.write("route," + ",".join(FILES) + "\n")
        for rt in allroutes:
            f.write(rt + "," + ",".join(str(cols[c].get(rt, ""))
                                        for c in FILES) + "\n")
    print(f"-> {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
