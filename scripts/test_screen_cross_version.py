"""Cross-version stage-1 screen tests (consolidation item 2).

The three screen generations (v2.0 tract, v2.1 block, v2.2 productivity) share
their catchment predictor machinery in a way that WAS asserted in prose but
never machine-checked across versions. These tests close that gap:

  XV1  ONE compute_predictors per geographic frame, single-sourced on BOTH the
       fit side and the scan side, in EVERY version -- by object identity:
         * v2.0 fit (screen_fit.sc) and scan (screen_scan.sc) reference the
           SAME screen_common.compute_predictors;
         * v2.1 fit (screen_fit_v21.sv) and scan (screen_scan_v21.sv) reference
           the SAME screen_common_v21.compute_predictors_v21;
         * v2.2 fit (screen_fit_v22.sv) and scan (screen_scan_v22.sv) reference
           the SAME screen_common_v21.compute_predictors_v21;
         * and v2.1 and v2.2 reference the SAME block function OBJECT (there is
           no screen_common_v22 -- the block predictor is shared verbatim).
       This is the D6 "fit predictors come from the same shared function as the
       scan" guarantee, VERIFIED (not asserted) and now enforced across
       versions -- a future v2.4 that re-forks compute_predictors trips XV1.

  XV2  fit==scan predictor RUNTIME identity for the BLOCK versions on a live
       route (the block analogue of test_screen.py D1 / Route 43): the
       full-shape window [0, L] computed on the fit side equals a FRESH
       scan-side computation through the same compute_predictors_v21.
       Data-gated (house Q6 pattern).

  XV3  BYTE-IDENTITY GATE: each version's build_artifact(), run in-process at
       the FULL registry B, reproduces its committed artifact byte-for-byte
       (b88f9b65 / 83aeb032 / 3b1d5526). This is the manual D21 dual-generation
       gate promoted to a runnable, cross-version check. It NEVER writes to
       outputs/. It is slow (~3-4 min for all three at B=2000), so it is OFF by
       default and runs only when SCREEN_XV_BYTE=1 is set in the environment.

(Per-version in-process double-run determinism is already covered by
test_screen.py D4, test_screen_v21_fit.py W5, test_screen_v22_fit.py V5.)

    python -X utf8 scripts/test_screen_cross_version.py
    SCREEN_XV_BYTE=1 python -X utf8 scripts/test_screen_cross_version.py   # + XV3
"""
import hashlib
import json
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "outputs")
RAW = os.path.join(HERE, "..", "data", "raw")

from assumptions import val                                       # noqa: E402

HAVE_TRACT = os.path.exists(os.path.join(RAW, "gtfs", "trips.txt"))
HAVE_BLOCK = (HAVE_TRACT
              and os.path.exists(os.path.join(RAW, "gtfs_archive",
                                              "octa_gtfs_fy2017_20170201.zip"))
              and os.path.exists(os.path.join(HERE, "..", "data", "derived",
                                              "oc_blocks.csv")))

# (module name, committed artifact, sha prefix) for the byte-identity gate
VERSIONS = (
    ("screen_scan",     "screen_results.json",     "b88f9b65"),
    ("screen_scan_v21", "screen_results_v21.json", "83aeb032"),
    ("screen_scan_v22", "screen_results_v22.json", "3b1d5526"),
)


def test_xv1_compute_predictors_single_source():
    """ONE compute_predictors per frame, single-sourced on fit AND scan in
    every version -- by object identity (no data needed)."""
    import screen_common as sc
    import screen_common_v21 as sv
    import screen_fit as sf20
    import screen_scan as ss20
    import screen_fit_v21 as sf21
    import screen_scan_v21 as ss21
    import screen_fit_v22 as sf22
    import screen_scan_v22 as ss22

    # v2.0 (tract frame): both sides are screen_common.compute_predictors
    assert sf20.sc is sc and ss20.sc is sc, "v2.0 fit/scan not on screen_common"
    assert sf20.sc.compute_predictors is ss20.sc.compute_predictors \
        is sc.compute_predictors, "v2.0 fit/scan compute_predictors diverged"

    # v2.1 (block frame): both sides are compute_predictors_v21
    assert sf21.sv is sv and ss21.sv is sv, "v2.1 fit/scan not on common_v21"
    assert sf21.sv.compute_predictors_v21 is ss21.sv.compute_predictors_v21 \
        is sv.compute_predictors_v21, "v2.1 fit/scan predictor diverged"

    # v2.2 (block frame, productivity): both sides are compute_predictors_v21
    assert sf22.sv is sv and ss22.sv is sv, "v2.2 fit/scan not on common_v21"
    assert sf22.sv.compute_predictors_v21 is ss22.sv.compute_predictors_v21 \
        is sv.compute_predictors_v21, "v2.2 fit/scan predictor diverged"

    # cross-version: v2.1 and v2.2 share the SAME block function object -- the
    # block predictor is consolidated verbatim (no screen_common_v22 exists)
    assert sf21.sv.compute_predictors_v21 is sf22.sv.compute_predictors_v21, \
        "v2.1 and v2.2 block compute_predictors are not the same object"
    assert not os.path.exists(os.path.join(HERE, "screen_common_v22.py")), \
        "a screen_common_v22 fork exists -- the block predictor must stay one"

    # the two frames are DISTINCT functions (tract vs block are not the same)
    assert sc.compute_predictors is not sv.compute_predictors_v21
    print("  XV1 OK  compute_predictors single-sourced fit==scan in v2.0/v2.1/"
          "v2.2; v2.1 and v2.2 share ONE block function object; two frames "
          "(tract, block) are two functions")


def test_xv2_fit_scan_runtime_identity_block():
    """Block versions: the fit-side full-shape predictors equal a FRESH
    scan-side computation through compute_predictors_v21 (D1 analogue)."""
    if not HAVE_BLOCK:
        print("  XV2 SKIP  (block data absent)")
        return
    import screen_common_v21 as sv
    import screen_fit_v21 as sf
    # the full vintage set build_fit_rows needs across the 6-FY panel (main())
    data = sv.load_data_v21(acs_vintages=("2017", "2019", "2021", "2023"),
                            lodes_vintages=("2017", "2019", "2021", "2022"))
    cns = sf.load_cns_by_block(data, ("2017", "2019", "2021", "2022"))
    fit = sf.build_fit_rows(data, cns, val("buffer_mi"))
    rows = fit["rows"]
    # pick a route-year present in the fit frame, rebuild its catchment fresh
    rec = rows.iloc[0]
    r, fy = rec["route"], rec["fy"]
    projs = sf.build_fit_projs(data, quiet=True)["proj_cache"]
    proj = projs[(r, fy)]
    fresh = sv.compute_predictors_v21(data, proj, 0.0, proj.L, fy,
                                      rvh=float(rec["rvh"]),
                                      buffer_mi=val("buffer_mi"))
    assert abs(fresh["flows"] - float(rec["flows"])) < 1e-9
    assert abs(fresh["zveh_hh"] - float(rec["zveh"])) < 1e-9
    assert abs(fresh["genjobs"] - float(rec["genjobs"])) < 1e-9
    assert int(fresh["gen_dummy"]) == int(rec["gen_dummy"])
    print(f"  XV2 OK  block fit==scan predictor identity on {r}@{fy} "
          f"(flows {fresh['flows']:.0f}, zveh {fresh['zveh_hh']:.0f}, "
          f"genjobs {fresh['genjobs']:.0f})")


def test_xv3_byte_identity_full_B():
    """FULL-B byte-identity gate: each version's build_artifact reproduces its
    committed artifact byte-for-byte. Off unless SCREEN_XV_BYTE=1 (slow)."""
    if os.environ.get("SCREEN_XV_BYTE") != "1":
        print("  XV3 SKIP  (set SCREEN_XV_BYTE=1 to run the full-B "
              "committed-bytes gate; ~3-4 min)")
        return
    if not HAVE_BLOCK:
        print("  XV3 SKIP  (data absent)")
        return
    import importlib
    for modname, fname, sha in VERSIONS:
        mod = importlib.import_module(modname)
        art = mod.build_artifact(quiet=True)          # full registry B
        blob = (json.dumps(mod._canon(art), sort_keys=True, indent=2)
                + "\n").encode("utf-8")
        committed = open(os.path.join(OUT, fname), "rb").read()
        h = hashlib.sha256(blob).hexdigest()
        assert blob == committed, (
            f"{modname} regen != committed {fname} "
            f"(regen {h[:8]}, want {sha})")
        assert h.startswith(sha), f"{fname} sha {h[:8]} != {sha}"
        print(f"  XV3 .. {modname} -> {fname} byte-identical (sha {sha})")
    print("  XV3 OK  all three artifacts reproduce byte-identically at full B")


if __name__ == "__main__":
    test_xv1_compute_predictors_single_source()
    test_xv2_fit_scan_runtime_identity_block()
    test_xv3_byte_identity_full_B()
    print("ALL CROSS-VERSION SCREEN TESTS PASS")
