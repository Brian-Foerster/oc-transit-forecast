"""Extract route-level annual boardings AND annual revenue vehicle hours from
the OCTA quarterly performance report PDFs (data/raw/apc, fetched by
download_data.py) into a committed table. Serves the streetcar anchor
derivation (spec 05 §3.3), the stage-1 DRM screen (spec 01, D24), and the
service-change panel (spec 02 §4.4).

Row format in the PDFs (full-row parse, replacing the old "first 7+-digit
comma number" heuristic): 17 whitespace-separated tokens

    route zone farebox% | subsidy direct indirect capital revenue |
    boardings | CostVSH DirectCostVSH CostVSM BoardVSH | VSH | 3 bus counts

e.g. FY2017 route 43:
    043 N 26.3% 3.23 2.02 0.96 0.25 1.06 2,190,951 132.86 84.42 12.83 32.93
    66,539 13 - -
where 2,190,951 is annual boardings, 66,539 is annual revenue vehicle hours
(VSH; the report itself calls the quantity RVH in its footnotes), and 32.93
is the printed boardings-per-RVH column. Every parsed row is validated:
boardings/RVH must reproduce the printed BoardVSH to 2 decimal places —
allowing for the PDF's own integer rounding of the RVH column (BoardVSH is
computed there from unrounded RVH, so the check is interval overlap of
[b/(rvh+0.5), b/(rvh-0.5)] with printed +/- 0.005; binding at small RVH,
e.g. FY2017 Stationlink 411: 5,837/863 = 6.7636 printed as 6.77). Any row
failing this check exits the script nonzero, EXCEPT the three known
source-inconsistent rows in KNOWN_BAD_RVH (see below), whose RVH is emitted
blank rather than trusted.

FY2020-Q3 layout drift (handled explicitly, verified against the extracted
text 2026-07-18):
  * The Stationlink table gains a Submode column ("463 C RCL 3.5% ...", 18
    tokens); Local and Express tables do not. The submode token is optional
    in the parser.
  * The Local sorted-by-SUBSIDY table (page 17) extracts as blank text under
    pypdf; FY2020-Q3 Local rows therefore appear exactly once (page 19,
    sorted by boardings) and get no duplicate-table cross-check. FY2017 and
    FY2019 rows appear in two sort orders and are asserted identical.

FY2018's PDF extracts unparseably and is skipped (unchanged).

Output compatibility (spec 01 build brief D24 + D2): the committed
route_boardings.csv keeps its boardings columns byte-for-byte — the same 47
routes and the same 132 non-blank route-year cells the old heuristic
selected. That heuristic's selection effect was "boardings >= 100,000"
(a 7+-character comma number); it is frozen here as LEGACY_MIN_BOARDINGS so
the D2 fit universe (47 routes x 3 FYs, 132 route-years) is unchanged.
Rows the full parse now additionally reads (sub-100k routes 21/76/87/177,
Express 2xx/7xx, Stationlink 4xx, FY2020-only 862/123) are validated and
counted but NOT emitted; widening the universe is a spec/registry decision
(S2, data-tier entry apc_fy17_19_20), not an extraction default.
rvh_* columns ARE emitted for every validated cell of the 47 committed
routes, including the 7 cells whose boardings fall under the legacy floor
(82/85/178 fy2019+fy2020q3, 153 fy2020q3): RVH is new data with no
byte-compat constraint, so nothing parseable is dropped.

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

# Rows where the source PDF is internally inconsistent: the printed VSH
# column disagrees with the printed BoardVSH by 25-35%. Forensics (2026-07-18)
# via the report's own cost identity, VSH ~= boardings*(subsidy/b + revenue/b
# - capital/b) / CostVSH: FY2017 route 35 -> 48,495 vs BoardVSH-implied
# 48,466 vs printed 36,931; route 70 -> 54,317 vs 53,461 vs printed 42,238;
# route 150 -> 13,120 vs 13,258 vs printed 9,949. BoardVSH/CostVSH/subsidy
# columns mutually agree, so the printed VSH is the corrupt datum for these
# three FY2017 rows (their FY2019/FY2020-Q3 rows validate clean). RVH is
# emitted BLANK for these cells; imputing boardings/BoardVSH instead is a
# registry-level decision (apc_fy17_19_20 entry), not an extraction default.
KNOWN_BAD_RVH = frozenset({("fy2017", "35"), ("fy2017", "70"),
                           ("fy2017", "150")})

# Frozen legacy compatibility floor, NOT an analytic constant: the old
# "first 7+-digit comma number" regex only matched boardings >= 100,000, and
# the committed boardings columns / D2 fit universe (47 routes, 132
# route-years) are defined by that selection. Registry ownership of this
# datum belongs to the apc_fy17_19_20 data-tier entry (S2); do not tune here.
LEGACY_MIN_BOARDINGS = 100_000

ROUTE_RE = re.compile(r"^\d{2,3}X?$")
ZONES = frozenset("NCS")
SUBMODE_RE = re.compile(r"^[A-Z]{2,4}$")     # FY2020-Q3 Stationlink "RCL"
PCT_RE = re.compile(r"^\d{1,2}\.\d%$")
MONEY_RE = re.compile(r"^\d{1,3}(,\d{3})*\.\d{2}$")
COUNT_RE = re.compile(r"^\d{1,3}(,\d{3})*$")
BUS_RE = re.compile(r"^(-|\d{1,3})$")


def parse_row(tokens):
    """Full-row parse. Returns (route, boardings, rvh, printed_b_per_rvh)
    or None if the line is not a data row. Raises ValueError on a line that
    starts like a data row but does not fit the 17/18-token layout."""
    if len(tokens) < 3 or not ROUTE_RE.match(tokens[0]) or tokens[1] not in ZONES:
        return None
    body = tokens[2:]
    if body and SUBMODE_RE.match(body[0]) and not body[0].endswith("%"):
        body = body[1:]                      # FY2020-Q3 Stationlink Submode
    body = [t.rstrip("$") for t in body]     # first table row carries $ signs
    # farebox% | 5 money | boardings | 4 ratios | VSH | 3 bus counts = 15
    if (len(body) != 15
            or not PCT_RE.match(body[0])
            or not all(MONEY_RE.match(t) for t in body[1:6])
            or not COUNT_RE.match(body[6])
            or not all(MONEY_RE.match(t) for t in body[7:11])
            or not COUNT_RE.match(body[11])
            or not all(BUS_RE.match(t) for t in body[12:15])):
        raise ValueError("route-like line does not fit the 17/18-token "
                         "layout: " + " ".join(tokens))
    route = tokens[0].lstrip("0") or "0"
    boardings = int(body[6].replace(",", ""))
    b_per_rvh = float(body[10])              # printed BoardVSH column
    rvh = int(body[11].replace(",", ""))
    return route, boardings, rvh, b_per_rvh


def rvh_check_ok(boardings, rvh, printed):
    """boardings/RVH reproduces the printed BoardVSH to 2dp, allowing for
    the PDF's integer rounding of RVH: overlap of [b/(rvh+0.5), b/(rvh-0.5)]
    with [printed-0.005, printed+0.005]."""
    eps = 1e-9
    ratio_lo = boardings / (rvh + 0.5)
    ratio_hi = boardings / (rvh - 0.5)
    return (ratio_lo - eps <= printed + 0.005
            and ratio_hi + eps >= printed - 0.005)


def route_stats(label, path):
    """Parse one report PDF -> {route: (boardings, rvh_or_None)}; validates
    every row against the printed boardings-per-RVH column and asserts the
    two sort-order tables agree wherever a route appears twice."""
    r = pypdf.PdfReader(path)
    routes, failures = {}, []
    for pg in r.pages:
        t = (pg.extract_text() or "").replace(chr(0x202F), " ")
        for ln in t.splitlines():
            parsed = parse_row(ln.split())
            if parsed is None:
                continue
            route, boardings, rvh, printed = parsed
            if not rvh_check_ok(boardings, rvh, printed):
                if (label, route) in KNOWN_BAD_RVH:
                    rvh = None      # documented source defect: emit blank
                else:
                    failures.append(
                        f"{os.path.basename(path)} route {route}: "
                        f"{boardings}/{rvh} = {boardings / rvh:.4f} "
                        f"!= printed {printed}")
            prev = routes.setdefault(route, (boardings, rvh))
            assert prev == (boardings, rvh), (
                f"{os.path.basename(path)} route {route}: sort-order tables "
                f"disagree: {prev} vs {(boardings, rvh)}")
    if failures:
        for f in sorted(set(failures)):
            print("VALIDATION FAIL:", f)
        sys.exit(1)
    return routes


def main():
    stats = {}
    for label, fname in FILES.items():
        path = os.path.join(APC, fname)
        if not os.path.exists(path):
            print(f"missing {fname} -- run download_data.py first")
            return 1
        stats[label] = route_stats(label, path)
        kept = {rt: v for rt, v in stats[label].items()
                if v[0] >= LEGACY_MIN_BOARDINGS}
        nbad = sum(1 for rt, v in stats[label].items() if v[1] is None)
        print(f"{label}: {len(stats[label])} rows parsed+validated "
              f"(b/RVH == printed to 2dp), {nbad} known-bad RVH blanked, "
              f"{len(kept)} at legacy floor, "
              f"boardings total {sum(v[0] for v in kept.values()):,}, "
              f"RVH total {sum(v[1] for v in kept.values() if v[1]):,}")
    # Committed universe (D2): routes with >= 1 FY at the legacy floor.
    allroutes = sorted(
        {rt for col in stats.values() for rt, v in col.items()
         if v[0] >= LEGACY_MIN_BOARDINGS},
        key=lambda r: (len(r), r))
    dest = os.path.join(DER, "route_boardings.csv")
    with open(dest, "w", encoding="utf-8", newline="\n") as f:
        f.write("route," + ",".join(FILES)
                + "," + ",".join("rvh_" + c for c in FILES) + "\n")
        for rt in allroutes:
            board = [str(stats[c][rt][0])
                     if rt in stats[c] and stats[c][rt][0] >= LEGACY_MIN_BOARDINGS
                     else "" for c in FILES]
            rvh = [str(stats[c][rt][1])
                   if rt in stats[c] and stats[c][rt][1] is not None
                   else "" for c in FILES]
            f.write(rt + "," + ",".join(board + rvh) + "\n")
    print(f"-> {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
