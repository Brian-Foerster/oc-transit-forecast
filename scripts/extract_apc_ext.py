"""Panel extension: extract additional route-year boardings + RVH from OCTA
'Bus Operations Performance Measurements Report' detailed reports published
on octa.legistar.com, into data/derived/route_boardings_ext.csv (long format:
route,fy,boardings,rvh). The committed route_boardings.csv and extract_apc.py
are NOT touched.

CONTAMINATION GUARD (absolute): the route-year BOARDINGS extracted here are
outcome data. This module extracts, validates, and emits them as a table and
nothing else -- it never regresses on them, never joins them to a predictor
matrix, and no predictor/fit module may read route_boardings_ext.csv until
phase 2b. The stage-1 power machinery keeps using only the committed v2.0
variance decomposition. test_extract_apc_ext.py enforces both directions.

SOURCES (all located 2026-07-20 via the Legistar web API,
webapi.legistar.com/v1/octa/matters, title filter 'Performance Measurements';
73 matters in the family, FY2009-10 .. FY2022-23; per-file provenance
sidecars are written next to each PDF in data/raw/apc_ext). The route-level
'OCTA Operating Statistics By Route' tables exist ONLY in the Q4 detailed
reports from FY2016-17 onward; every earlier report (Transit Division format,
FY2009-10..FY2015-16) is a systemwide-KPI document with no route table
(verified on the FY2012-13 Q4 A+B, FY2013-14 Q4, FY2014-15 Q4 attachments;
the FY2015-16 Q4 attachment is a text-free page scan). The task-provided Q2
links carry the SAME table headed 'Fiscal Year 20xx-yy' but their content is
fiscal-year-TO-DATE, not annual -- verified numerically: Q2-FY2021 route 060
boardings 721,810 vs 1,427,161 in the Q4 FY2021 report (ratio 0.51, 6 of 12
months) and Q2-FY2023 route 060 403,263 vs 1,613,660 (ratio 0.25; that
report's narrative says 'Through Q1'). The Q4 reports are therefore the
annual sources; the Q2 files are retained as monotonicity cross-checks.

  label   file (data/raw/apc_ext)              period          role
  fy2017  FY2017-Q4-Detailed-Report-Legistar   Jul16-Jun17     cross-check
  fy2019  FY2019-Q4-Detailed-Report-Legistar   Jul18-Jun19     cross-check
  fy2020  FY2020-Q4-Detailed-Report            Jul19-Jun20     NEW (emitted)
  fy2021  FY2021-Q4-Detailed-Report            Jul20-Jun21     NEW (emitted)
  fy2022  FY2022-Q4-Detailed-Report            Jul21-Jun22     NEW (emitted)
  fy2023  FY2023-Q4-Detailed-Report            Jul22-Jun23     NEW (emitted)
  fy2021h1  FY2021-Q2-Detailed-Report          Jul20-Dec20     check only
  fy2023q1  FY2023-Q2-Detailed-Report          Jul22-Sep22     check only

Search misses, documented (2026-07-20):
  * FY2013-FY2016: no route-level table exists in the report family (older
    'Transit Division' KPI format; see above). Not extractable from these
    board reports at all.
  * FY2018 (Jul17-Jun18): both Legistar copies of the Q4 FY2017-18 report
    (matters 2628 and 6506, 'Attachment A - Revised') embed the four table
    pages as raster image strips (5 strips of ~1047x250 px per Local page,
    ~300x693 per Express/Stationlink page) with no text layer -- same defect
    as the octa.net copy that extract_apc.py already skips. Unextractable
    without OCR; no OCR dependency is added.
  * FY2024 (Jul23-Jun24): the quarterly report family ends with the Q4
    FY2022-23 matter (Dec 2022). Its successor, the 'Bimonthly Transit
    Performance Report' (first matter Jun 2024), is a slide deck with no
    route-level operating statistics (verified on the Oct 2024 and Jun 2025
    issues). octa.net URL probes FY2024-Q2/Q4-Detailed-Report.pdf return 404.

Row layout and validation are inherited from extract_apc.py (17/18-token
full-row parse; optional FY2020+ Stationlink Submode token) with two
extensions seen in the newer PDFs: (a) parenthesized negatives, e.g.
'(0.4)%' farebox and '(0.07)' revenue per boarding on Q2-FY2021 route 079;
(b) rows may wrap across extracted text lines, so a short route-start line
is re-joined with following lines before parsing (line-regrouping; no
camelot/tabula). Every parsed row must reproduce the printed BoardVSH =
boardings/RVH to 2dp via the interval test imported from extract_apc
(rvh_check_ok); any non-whitelisted failure exits nonzero.

Source-defect whitelists (forensics in-line below):
  * KNOWN_BAD_RVH (imported): the three FY2017 rows (35/70/150) whose
    printed VSH contradicts BoardVSH by 25-35%%; they reappear identically
    in the Legistar copy of the same report; RVH treated as absent in the
    fy2017 cross-check.
  * KNOWN_DUP_RVH_EXT fy2022 route 560: the two sort-order tables of the
    FY2022 Q4 report print two variants of the whole row (farebox 9.6%% vs
    10.3%%, RVH 22,387 vs 22,382, boardings identical 395,079). Both rows
    pass the 2dp check and both satisfy the report's own cost identity
    (implied VSH 22,396 / 22,364 vs printed, within the +/-35 rounding
    envelope), so neither variant can be forensically preferred; boardings
    (agreeing) are kept and RVH is emitted BLANK, the KNOWN_BAD_RVH
    precedent for a datum the source itself prints inconsistently.

Cross-validation gates (all fatal unless stated):
  G1 2dp reproduction for every row of every file (whitelists above).
  G2 duplicate sort-order tables agree per route (whitelist above).
  G3 fy2017 + fy2019 Legistar copies reproduce the committed
     route_boardings.csv cells exactly (boardings and RVH, including the
     three blanked RVH cells). This anchors the parser to ground truth.
  G4 fy2020 full-year boardings >= committed fy2020q3 (9-mo YTD) per route.
     RVH is NOT gated: the Q4 FY2020 report revised six routes' annual RVH
     BELOW the 9-month print (150, 529, 53X, 560, 57X, 64X; -0.03%% to
     -3.6%%, boardings essentially unchanged -- COVID Express suspension
     true-up). Reported as source revisions, not failures.
  G5 Q2 partial files: FYTD boardings and RVH <= the same FY's annual
     values per route, and no route appears in a Q2 file but not the
     annual file.

Only the four NEW fiscal years are emitted. The fy2017/fy2019 full parses
also see routes the committed table excludes (Express 2xx/7xx, Stationlink
4xx, sub-100k locals); widening the committed FY2017/FY2019 universe stays
a spec/registry decision (see extract_apc.py LEGACY_MIN_BOARDINGS) and is
NOT smuggled in here.

usage: python extract_apc_ext.py   -> data/derived/route_boardings_ext.csv
       (downloads any missing source PDF from octa.legistar.com; octa.net
        mirrors need a browser User-Agent header, which is always sent and
        noted in the provenance sidecars)
"""
import datetime
import hashlib
import os
import re
import sys
import urllib.request

import pypdf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from extract_apc import KNOWN_BAD_RVH, rvh_check_ok  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

EXT = os.path.join(HERE, "..", "data", "raw", "apc_ext")
DER = os.path.join(HERE, "..", "data", "derived")
UA = "Mozilla/5.0"          # octa.net/legistar reject bare urllib UAs

# label -> (file, url, fiscal-year header on the table pages, role, note)
# role: "new" = emitted; "xcheck" = committed-table anchor; "partial" = FYTD
SOURCES = {
    "fy2017": ("FY2017-Q4-Detailed-Report-Legistar.pdf",
               "https://octa.legistar1.com/octa/attachments/"
               "450966b7-67eb-431e-8823-5a82cf039e9f.pdf",
               "2016-17", "xcheck",
               "Legistar matter 2107 (Q4 FY2016-17, 2017-10-16) Attachment A;"
               " same report as the committed octa.net copy"),
    "fy2019": ("FY2019-Q4-Detailed-Report-Legistar.pdf",
               "https://octa.legistar1.com/octa/attachments/"
               "eb162bfe-2201-4cb0-9488-aa800127c5bc.pdf",
               "2018-19", "xcheck",
               "Legistar matter 8165 (Q4 FY2018-19, 2019-10-07) Attachment A;"
               " same report as the committed octa.net copy"),
    "fy2020": ("FY2020-Q4-Detailed-Report.pdf",
               "https://octa.legistar1.com/octa/attachments/"
               "7a861a48-28aa-4523-a887-84a82fc2450f.pdf",
               "2019-20", "new",
               "Legistar matter 8978 (Q4 FY2019-20, 2020-10-05) Attachment A;"
               " full-year incl. COVID Q4; committed fy2020q3 is its 9-mo"
               " subset"),
    "fy2021": ("FY2021-Q4-Detailed-Report.pdf",
               "https://octa.legistar1.com/octa/attachments/"
               "933682c5-b40f-49bf-b7be-a7ef1ea98bb6.pdf",
               "2020-21", "new",
               "Legistar matter 9063 (Q4 FY2020-21) Attachment A; octa.net"
               " mirror /pdf/FY2021-Q4-Detailed-Report.pdf (browser UA"
               " required)"),
    "fy2022": ("FY2022-Q4-Detailed-Report.pdf",
               "https://octa.legistar1.com/octa/attachments/"
               "08344afe-3811-41d8-b002-410222cb9ca8.pdf",
               "2021-22", "new",
               "Legistar matter 10055 (Q4 FY2021-22) Attachment A"),
    "fy2023": ("FY2023-Q4-Detailed-Report.pdf",
               "https://octa.legistar1.com/octa/attachments/"
               "fdfe2302-7786-4a33-94a4-b1aefef13adc.pdf",
               "2022-23", "new",
               "Legistar matter 10647 (Q4 FY2022-23) Attachment A"),
    # task-provided Q2 links -- fiscal-year-to-date tables, checks only
    "fy2021h1": ("FY2021-Q2-Detailed-Report.pdf",
                 "https://octa.legistar.com/View.ashx?M=F&ID=9225001&"
                 "GUID=4905F492-AEEF-4D37-9286-988E19602C9E",
                 "2020-21", "partial",
                 "Legistar matter 9312 (Q2 FY2020-21, 2021-03-16) Attachment"
                 " A; table is Jul-Dec 2020 FYTD despite the annual-looking"
                 " header; octa.net mirror /pdf/FY2021-Q2-Detailed-Report.pdf"
                 " (browser UA required)"),
    "fy2023q1": ("FY2023-Q2-Detailed-Report.pdf",
                 "https://octa.legistar.com/View.ashx?GUID=9A687273-4CFF-"
                 "4993-B70A-5AE81F684795&ID=11559747&M=F",
                 "2022-23", "partial",
                 "Legistar matter 10629 (Q2 FY2022-23, 2022-12-19) Attachment"
                 " A; narrative covers 'Through Q1', table is Jul-Sep 2022"
                 " FYTD despite the annual-looking header"),
}
PARTIAL_OF = {"fy2021h1": "fy2021", "fy2023q1": "fy2023"}  # G5 pairs

# fy2022 route 560: the report's two sort-order tables print two variants of
# the row (see module docstring for the forensics). Boardings agree; RVH is
# emitted blank rather than choosing between 22,387 and 22,382.
KNOWN_DUP_RVH_EXT = frozenset({("fy2022", "560")})

ROUTE_RE = re.compile(r"^\d{2,3}X?$")
ZONES = frozenset("NCS")
SUBMODE_RE = re.compile(r"^[A-Z]{2,4}$")     # FY2020+ Stationlink "RCL"
# parenthesized negatives occur in the COVID-era tables (route 079 farebox
# "(0.4)%", revenue "(0.07)" in the Q2-FY2021 file)
PCT_RE = re.compile(r"^\(?\d{1,3}\.\d\)?%$")
MONEY_RE = re.compile(r"^\(?\d{1,3}(,\d{3})*\.\d{2}\)?$")
COUNT_RE = re.compile(r"^\d{1,3}(,\d{3})*$")
BUS_RE = re.compile(r"^(-|\d{1,3})$")
FY_HDR_RE = re.compile(r"Fiscal Year\s*(\d{4}-\d{2})")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch_all():
    os.makedirs(EXT, exist_ok=True)
    for label, (fname, url, _fy, _role, note) in SOURCES.items():
        dest = os.path.join(EXT, fname)
        if not (os.path.exists(dest) and os.path.getsize(dest) > 0):
            print(f"fetching {fname} ...")
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=300) as r, \
                    open(dest, "wb") as f:
                while True:
                    b = r.read(1 << 20)
                    if not b:
                        break
                    f.write(b)
        prov = dest + ".provenance.txt"
        if not os.path.exists(prov):
            with open(prov, "w", encoding="utf-8", newline="\n") as f:
                f.write(f"filename: {fname}\n"
                        f"source_url: {url}\n"
                        f"size_bytes: {os.path.getsize(dest)}\n"
                        f"sha256: {sha256(dest)}\n"
                        f"fetched: {datetime.datetime.now().isoformat(timespec='seconds')}\n"
                        f"notes: {note}. Fetched with User-Agent '{UA}'"
                        " (bare-urllib UAs are rejected by octa.net; header"
                        " noted per house provenance rule). OCTA Operating"
                        " Statistics By Route table, Fiscal Year"
                        f" {SOURCES[label][2]}.\n")


def parse_row_ext(tokens):
    """17/18-token full-row parse (see extract_apc.parse_row), extended for
    parenthesized negatives. Returns (route, boardings, rvh, printed_b_per_
    rvh), None for a non-row line, or the string "short" when the line
    starts like a data row but has too few tokens (wrapped line -- caller
    regroups). Raises ValueError on a route-like line that misfits."""
    if (len(tokens) < 2 or not ROUTE_RE.match(tokens[0])
            or tokens[1] not in ZONES):
        return None
    body = tokens[2:]
    if body and SUBMODE_RE.match(body[0]) and not body[0].endswith("%"):
        body = body[1:]
    body = [t.rstrip("$") for t in body]
    if len(body) < 15:
        return "short"
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


def parse_text_rows(text):
    """One table page's extracted text -> list of (route, boardings, rvh,
    printed_b_per_rvh). Regroups rows that wrap across text lines (the
    recon's out-of-order/pypdf warning); a route-like line that never
    completes the 17/18-token shape raises (ValueError from the shape
    check on overshoot, AssertionError on dangling tokens at page end)."""
    rows, pending = [], []
    for ln in text.splitlines():
        new = ln.split()
        if pending and not new:              # blank line inside a wrap
            continue
        tokens = pending + new
        parsed = parse_row_ext(tokens)
        if parsed == "short":                # wrapped row: join next line
            pending = tokens                 # bounded: the 15-token shape
            continue                         # check errors on overshoot
        pending = []
        if parsed is not None:
            rows.append(parsed)
    assert not pending, f"dangling wrapped tokens: {pending}"
    return rows


def route_stats_ext(label, path):
    """Parse one detailed report -> {route: (boardings, rvh_or_None)}.
    Scans only 'OCTA Operating Statistics By Route' pages, asserts their
    fiscal-year header matches SOURCES, regroups wrapped lines, applies the
    2dp gate (G1) and the duplicate-table gate (G2)."""
    expect_fy = SOURCES[label][2]
    r = pypdf.PdfReader(path)
    routes, failures = {}, []
    for pg in r.pages:
        t = (pg.extract_text() or "").replace(chr(0x202F), " ") \
                                     .replace(chr(0xA0), " ")
        if "Operating Statistics By Route" not in t:
            continue
        hdr = FY_HDR_RE.search(t)
        assert hdr and hdr.group(1) == expect_fy, (
            f"{os.path.basename(path)}: table page headed "
            f"{hdr.group(1) if hdr else 'NO FY'!r}, expected {expect_fy!r}")
        for route, boardings, rvh, printed in parse_text_rows(t):
            if not rvh_check_ok(boardings, rvh, printed):
                if (label, route) in KNOWN_BAD_RVH:
                    rvh = None       # documented FY2017 source defect
                else:
                    failures.append(
                        f"{os.path.basename(path)} route {route}: "
                        f"{boardings}/{rvh} = {boardings / rvh:.4f} "
                        f"!= printed {printed}")
            if route not in routes:
                routes[route] = (boardings, rvh)
            elif routes[route] != (boardings, rvh):
                if (label, route) in KNOWN_DUP_RVH_EXT and \
                        routes[route][0] == boardings:
                    routes[route] = (boardings, None)   # RVH inconsistent
                else:
                    failures.append(
                        f"{os.path.basename(path)} route {route}: sort-order "
                        f"tables disagree: {routes[route]} vs "
                        f"{(boardings, rvh)}")
    if failures:
        for f in sorted(set(failures)):
            print("VALIDATION FAIL:", f)
        sys.exit(1)
    return routes


def load_committed():
    """Committed route_boardings.csv -> {route: {col: int_or_None}}."""
    path = os.path.join(DER, "route_boardings.csv")
    with open(path, encoding="utf-8") as f:
        header = f.readline().strip().split(",")
        table = {}
        for ln in f:
            cells = ln.strip().split(",")
            row = dict(zip(header, cells))
            table[row["route"]] = {c: (int(row[c]) if row[c] else None)
                                   for c in header[1:]}
    return table


def cross_validate(stats, committed):
    """Gates G3-G5. Returns list of fatal messages (empty = pass) and a list
    of informational source-revision notes."""
    fatal, notes = [], []
    # G3: fy2017/fy2019 equality on every committed cell
    for lab in ("fy2017", "fy2019"):
        ext = stats[lab]
        for rt, row in committed.items():
            cb, crv = row[lab], row["rvh_" + lab]
            if cb is None:
                continue
            if rt not in ext:
                fatal.append(f"G3 {lab} route {rt}: in committed table but "
                             "not parsed from the Legistar copy")
                continue
            eb, erv = ext[rt]
            if eb != cb:
                fatal.append(f"G3 {lab} route {rt}: boardings {eb} != "
                             f"committed {cb}")
            if erv != crv:
                fatal.append(f"G3 {lab} route {rt}: rvh {erv} != committed "
                             f"{crv}")
    # G4: fy2020 full year vs committed fy2020q3 (boardings monotone; RVH
    # revisions reported only)
    for rt, row in committed.items():
        q3b, q3r = row["fy2020q3"], row["rvh_fy2020q3"]
        if q3b is None and q3r is None:
            continue
        if rt not in stats["fy2020"]:
            fatal.append(f"G4 route {rt}: has fy2020q3 data but missing "
                         "from the full-year FY2020 table")
            continue
        fb, fr = stats["fy2020"][rt]
        if q3b is not None and fb < q3b:
            fatal.append(f"G4 route {rt}: full-year boardings {fb} < "
                         f"9-mo YTD {q3b}")
        if q3r is not None and fr is not None and fr < q3r:
            notes.append(f"G4 note route {rt}: full-year RVH {fr} printed "
                         f"below the 9-mo YTD {q3r} (Q4-report true-up, "
                         f"boardings {fb} vs YTD {q3b})")
    # G5: FYTD <= annual for the task-provided Q2 files
    for plab, alab in PARTIAL_OF.items():
        for rt, (pb, pr) in stats[plab].items():
            if rt not in stats[alab]:
                fatal.append(f"G5 {plab} route {rt}: absent from the "
                             f"{alab} annual table")
                continue
            ab, ar = stats[alab][rt]
            if pb > ab:
                fatal.append(f"G5 {plab} route {rt}: FYTD boardings {pb} > "
                             f"annual {ab}")
            if pr is not None and ar is not None and pr > ar:
                fatal.append(f"G5 {plab} route {rt}: FYTD RVH {pr} > "
                             f"annual {ar}")
    return fatal, notes


def main():
    fetch_all()
    stats = {}
    for label, (fname, _url, _fy, role, _note) in SOURCES.items():
        path = os.path.join(EXT, fname)
        stats[label] = route_stats_ext(label, path)
        nb = sum(v[0] for v in stats[label].values())
        nr = sum(1 for v in stats[label].values() if v[1] is None)
        print(f"{label} ({role}): {len(stats[label])} routes parsed+validated"
              f" (b/RVH == printed to 2dp), boardings total {nb:,}"
              + (f", {nr} RVH cell(s) blanked" if nr else ""))
    committed = load_committed()
    fatal, notes = cross_validate(stats, committed)
    for n in notes:
        print(n)
    if fatal:
        for f in fatal:
            print("VALIDATION FAIL:", f)
        return 1
    print("cross-validation: G3 committed-cell equality, G4 fy2020q3 "
          "monotonicity, G5 FYTD<=annual -- all pass")
    new_labels = [lab for lab, s in SOURCES.items() if s[3] == "new"]
    dest = os.path.join(DER, "route_boardings_ext.csv")
    with open(dest, "w", encoding="utf-8", newline="\n") as f:
        f.write("route,fy,boardings,rvh\n")
        for lab in new_labels:                    # dict order = FY order
            for rt in sorted(stats[lab], key=lambda r: (len(r), r)):
                b, rvh = stats[lab][rt]
                f.write(f"{rt},{lab},{b},{'' if rvh is None else rvh}\n")
    n = sum(len(stats[lab]) for lab in new_labels)
    print(f"-> {dest} ({n} route-year rows, FYs: {', '.join(new_labels)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
