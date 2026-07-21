"""Design-stage power-check tests (spec 01 §9, owner item 3 2026-07-20).

G1/G2 are the STANDING CONTAMINATION GUARD required by the pre-registration
hold: the power module may build v2.1 predictor matrices input-side and
generate synthetic outcomes from injected coefficients, but it may NEVER
regress real boardings on v2.1 predictors -- no estimator in
screen_power.py may see a real outcome value.

  G1  source guard (pure): screen_power.py imports no fit module and no
      estimator package; the boardings CSV is referenced ONLY in/above
      load_rvh (mask + RVH extraction); the guard marker is present
  G2  load_rvh returns route/fy/rvh ONLY -- no boardings-shaped column
      leaves the loader (data-gated)
  G3  simulation exactness (pure): the Gram-sum bootstrap delta equals the
      OLS refit on the concatenated resampled rows (the reduction is the
      EXACT criterion-1 refit, not an approximation); same-seed
      determinism of simulate_deltas
  G4  power arithmetic (pure): power_curves sign-fraction thresholding and
      required_at interpolation on hand-built deltas
  W2  registry variance-decomposition pin (screen_v20_resid_decomp) ==
      recompute from the COMMITTED v2.0 fit (data-gated)
  W3  artifact schema + loyo resolution + small-B check + in-process
      double-run byte-identity at reduced S (data-gated)

    python -X utf8 scripts/test_screen_power.py
"""
import json
import os
import sys

import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "outputs")
RAW = os.path.join(HERE, "..", "data", "raw")

import screen_power as sp                                      # noqa: E402
from assumptions import val                                    # noqa: E402

HAVE_DATA = os.path.exists(os.path.join(RAW, "gtfs", "trips.txt"))
ARTIFACT = os.path.join(OUT, "screen_power_check.json")
SRC = os.path.join(HERE, "screen_power.py")


def test_g1_source_guard():
    with open(SRC, encoding="utf-8") as f:
        src = f.read()
    # no fit module, no estimator package, no fit-frame y column
    for banned in ("import screen_fit", "from screen_fit", "statsmodels",
                   "log_b", "import screen_scan", "from screen_scan"):
        assert banned not in src, \
            f"screen_power.py contains {banned!r} -- the contamination " \
            "guard bars every path to a real-boardings regression"
    # the boardings CSV appears only in the module docstring + load_rvh
    # (both precede fit_universe); nothing downstream may re-open it
    head, tail = src.split("def fit_universe", 1)
    assert "route_boardings" in head, "load_rvh moved -- update this guard"
    assert "route_boardings" not in tail, \
        "route_boardings referenced beyond load_rvh -- guard violation"
    assert "CONTAMINATION GUARD" in src, "guard statement missing"
    print("  G1 OK  source guard (no fit imports; boardings CSV confined "
          "to load_rvh)")


def test_g2_load_rvh_boardings_free():
    if not HAVE_DATA:
        print("  G2 SKIP  (data/raw absent)")
        return
    rvh = sp.load_rvh()
    assert list(rvh.columns) == ["route", "fy", "rvh"], list(rvh.columns)
    assert not any("board" in c.lower() for c in rvh.columns)
    assert (rvh["rvh"] > 0).all()
    assert set(rvh["fy"]) <= set(sp.FYS)
    print(f"  G2 OK  load_rvh boardings-free ({len(rvh)} fittable "
          "route-years; columns route/fy/rvh only)")


def _toy_design(rng):
    """5 clusters x 3 rows, 4 columns (const + 3 covariates)."""
    nR, k = 5, 4
    routes = [f"r{i}" for i in range(nR)]
    X = np.column_stack([np.ones(nR * 3),
                         rng.standard_normal((nR * 3, k - 1))])
    clusters = np.repeat(routes, 3)
    return {"X": X, "clusters": clusters, "fys": ["fy2017"] * (nR * 3),
            "names": ["const", "b1_flows", "b2_zveh", "b5_len"],
            "route_list": routes}


def test_g3_simulation_exactness():
    design = _toy_design(np.random.default_rng(5))
    X, clusters = design["X"], design["clusters"]
    routes = design["route_list"]
    nR = len(routes)
    ridx = {r: i for i, r in enumerate(routes)}
    row_route = np.array([ridx[c] for c in clusters])
    S, B = 2, 6
    sig2_r, sig2_e = 0.04, 0.01
    D1, D2 = sp.simulate_deltas(design, sig2_r, sig2_e, S, B,
                                np.random.default_rng(3))
    # replay the identical rng stream and refit each replicate the long
    # way: OLS on the CONCATENATED resampled rows (row order is
    # irrelevant to least squares) -- the Gram-sum delta must match
    rng = np.random.default_rng(3)
    j1 = design["names"].index("b1_flows")
    j2 = design["names"].index("b2_zveh")
    for s in range(S):
        u = (np.sqrt(sig2_r) * rng.standard_normal(nR))[row_route] \
            + np.sqrt(sig2_e) * rng.standard_normal(len(X))
        draws = rng.integers(0, nR, (B, nR))
        for b in range(B):
            sel = np.concatenate([np.flatnonzero(row_route == i)
                                  for i in draws[b]])
            beta = np.linalg.lstsq(X[sel], u[sel], rcond=None)[0]
            assert abs(beta[j1] - D1[s, b]) < 1e-10, (s, b)
            assert abs(beta[j2] - D2[s, b]) < 1e-10, (s, b)
    # same-seed determinism
    E1, E2 = sp.simulate_deltas(design, sig2_r, sig2_e, S, B,
                                np.random.default_rng(3))
    assert np.array_equal(D1, E1) and np.array_equal(D2, E2)
    print("  G3 OK  Gram-sum bootstrap == concatenated-row OLS refit "
          f"({S}x{B} replicates); same-seed deterministic")


def test_g4_power_arithmetic():
    # hand-built deltas: sim 0 noise -0.1 (passes once g > 0.1 exactly at
    # threshold), sim 1 noise +0.2 (always positive at g >= 0)
    D = np.array([[-0.1] * 10, [0.2] * 10])
    grid = [0.0, 0.05, 0.15]
    pw = sp.power_curves(D, D, grid, 0.841, 10)
    # g=0: sim0 frac 0 fail, sim1 frac 1 pass -> 0.5; g=0.05 same;
    # g=0.15: sim0 0.15-0.1>0 frac 1 -> both pass
    assert pw["b1"] == [0.5, 0.5, 1.0]
    assert pw["joint"] == [0.5, 0.5, 1.0]
    # strictness: g exactly at -delta gives 0 + ... > 0 FALSE
    pw0 = sp.power_curves(np.array([[0.0] * 4]), np.array([[0.0] * 4]),
                          [0.0], 0.841, 4)
    assert pw0["b1"] == [0.0], "sign fraction must be STRICTLY positive"
    # required_at: linear interpolation between bracketing grid points
    req = sp.required_at([0.0, 0.1, 0.2], [0.0, 0.5, 1.0], 0.8)
    assert abs(req - 0.16) < 1e-12, req
    assert sp.required_at([0.0, 0.1], [0.1, 0.2], 0.8) is None
    assert sp.required_at([0.0, 0.1], [0.9, 1.0], 0.8) == 0.0
    print("  G4 OK  power_curves thresholding + required_at interpolation")


def test_w2_registry_decomposition_pin():
    if not HAVE_DATA:
        print("  W2 SKIP  (data/raw absent)")
        return
    import screen_fit as sf
    pinned = val("screen_v20_resid_decomp")
    rec = sf.resid_decomposition()
    for k in ("sig2_route", "sig2_resid"):
        assert abs(pinned[k] - rec[k]) < 5e-7, \
            (k, pinned[k], rec[k], "registry pin drifted from the " \
             "committed v2.0 fit recompute")
    assert rec["n_routes"] == 41 and rec["n_route_years"] == 115
    print(f"  W2 OK  registry pin == v2.0 recompute (sig2_route "
          f"{rec['sig2_route']:.6f}, sig2_resid {rec['sig2_resid']:.6f}, "
          f"{rec['n_routes']} routes / {rec['n_route_years']} route-years)")


def test_w3_artifact_and_determinism():
    if not HAVE_DATA:
        print("  W3 SKIP  (data/raw absent)")
        return
    if os.path.exists(ARTIFACT):
        a = json.load(open(ARTIFACT, encoding="utf-8"))
        for k in ("run_id", "schema", "seed", "n_sims", "n_boot",
                  "n_boot_check", "disclaimer", "assumptions_manifest",
                  "criterion", "beta_grid", "x_variation",
                  "loyo_resolution", "variance_matching", "designs",
                  "reentrant_stylization", "stylizations",
                  "literature_comparison", "verdict", "no_contamination"):
            assert k in a, f"missing top-level key {k}"
        assert a["schema"] == "01-P1"
        cfg = val("screen_power_check")
        assert a["seed"] == cfg["seed"] and a["n_boot"] == cfg["n_boot"]
        assert a["criterion"]["pos_frac_min"] == val("screen_pos_frac_min")
        # LOYO resolution recorded on the measured input-side fact
        lo = a["loyo_resolution"]
        assert isinstance(lo["loyo_in_battery"], bool)
        assert set(lo["shares"]) == {"l_flows", "l_zveh_hh", "l_genjobs"}
        # l_len must be EXACTLY time-invariant under the current-shape
        # stylization (the max-min>0 test, not the 1-ulp std)
        assert a["x_variation"]["l_len"]["share_routes_varying"] == 0.0
        for lbl in ("clusters_41", "clusters_47"):
            d = a["designs"][lbl]
            chk = d["small_b_check"]
            assert chk["pass"] is True, (lbl, chk)
            assert max(chk["abs_diff"].values()) <= chk["tolerance"]
            for k in ("b1", "b2", "joint"):
                assert len(d["power"][k]) == len(a["beta_grid"])
                assert all(0.0 <= p <= 1.0 for p in d["power"][k])
        assert a["designs"]["clusters_47"]["n_clusters"] == \
            a["designs"]["clusters_41"]["n_clusters"] + 6
        assert a["verdict"]["overall"] in ("adequately-powered", "marginal",
                                           "underpowered")
        print(f"  W3a OK  artifact schema (verdict {a['verdict']['overall']}; "
              f"loyo_in {lo['loyo_in_battery']})")
    else:
        print("  W3a SKIP  (outputs/screen_power_check.json absent)")
    # in-process double-run determinism at reduced S
    a1 = sp.build_power_artifact(n_sims=8, quiet=True)
    a2 = sp.build_power_artifact(n_sims=8, quiet=True)
    s1 = json.dumps(sp._canon(a1), sort_keys=True, indent=2)
    s2 = json.dumps(sp._canon(a2), sort_keys=True, indent=2)
    assert s1 == s2, "power artifact not byte-identical on in-process rerun"
    print(f"  W3b OK  in-process double-run byte-identity (S=8, "
          f"{len(s1):,} bytes)")


if __name__ == "__main__":
    test_g1_source_guard()
    test_g2_load_rvh_boardings_free()
    test_g3_simulation_exactness()
    test_g4_power_arithmetic()
    test_w2_registry_decomposition_pin()
    test_w3_artifact_and_determinism()
    print("ALL SCREEN POWER TESTS PASS")
