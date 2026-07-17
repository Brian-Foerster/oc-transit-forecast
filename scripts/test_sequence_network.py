"""
Gates for the spec 07 N1b sequencing harness (scripts/sequence_network.py) and
the three N1a reviewer wiring notes. Runs the small pieces at reduced n; G1
runs the ONE cycle-1 harbor single at full N=40,000 to assert byte-identity
against the committed standalone results.

    python test_sequence_network.py

  G1  single-line degeneracy: cycle-1 harbor-vs-EMPTY reproduces the committed
      standalone run() outputs byte-identically (results_harbor summary values).
  G2b substitution family: a synthetic PARALLEL committed line scores below
      standalone WITH anchor_add active, across omega x {0.5, 1.5}.
  G3  complementarity sanity: the streetcar (terminus on Harbor Blvd) scores
      ABOVE standalone after a Harbor commitment (pre-stated positive; the actual
      % is reported).
  G4  CRN rank stability: seed-drift on the committed-order objective <= 2% and
      the committed ORDER exactly stable on a seed+1 rerun.
  G6  primary-artifact reproducibility: the artifact is byte-identical on rerun.
  G7  rule-2 knob gate: the sensitivity block carries the N1b-scope knob rows
      (cycle_gap lo/hi, budget lo/hi, omega x {0.5,1.5}, uniform, depth-cap 1/3)
      and names the spec-pending N4/N5 rows.
  W1  omega passes REAL worker masses (non-uniform), not the silent uniform
      fallback. W2 omega uses the WINDOWED H shape. W3 feeder injection is
      SCREENED by the dependency predicate.
"""
import json
import os
import sys

import numpy as np

import sequence_network as sn
from model import Corridor, run, draw_params, pct, N
from assumptions import val
import network_mechanics as nm

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "outputs")
DER = os.path.join(HERE, "..", "data", "derived")
SEED = val("seed")
NS = 2500                       # sequence-test draw count (fast; G4 checked here)

_GTFS = sn._Gtfs()
_TRACTS = sn._tract_table()
_CANDS, _HS, _SUBST = sn.load_candidates(
    os.path.join(HERE, "..", "config", "candidates.json"), _GTFS, _TRACTS)
_BYID = {c["id"]: c for c in _CANDS}


def _seq(seed=SEED, n=NS, **kw):
    return sn.sequence(_CANDS, _HS, _SUBST, seed=seed, n=n, quiet=True,
                       gtfs=_GTFS, tracts=_TRACTS, **kw)


# ---------------------------------------------------------------------------
def test_g1_single_line_degeneracy():
    """G1: cycle-1 harbor evaluated against the EMPTY network reproduces the
    committed standalone run() outputs byte-identically (spec 07 §10 G1). The
    harness passes the committed derived FILE verbatim (empty-network rule) and
    anchor_add=None, so run() is bit-for-bit the standalone call."""
    params, weights, _ess = sn._cycle_weights(N, SEED, sn.central_label())
    rec = sn.evaluate(dict(_BYID["harbor"], scenario="fold"), [], params, SEED,
                      weights, _GTFS, _TRACTS, N, sn.bc.RUN_DIR)
    ref = json.load(open(os.path.join(OUT, "results_harbor.json")))["summary"]
    res = rec["res"]
    # results_harbor summary uncapped[scen] is the NEWLINE (fold: newline==total
    # since the local is removed); total_fold is the fold TOTAL. Pin every one.
    for scen in ("fold", "retain"):
        got = [pct(res["uncapped"][scen]["newline"], q) for q in (10, 50, 90)]
        assert got == ref["uncapped"][scen], (scen, "newline", got,
                                              ref["uncapped"][scen])
    tf = [pct(res["uncapped"]["fold"]["total"], q) for q in (10, 50, 90)]
    assert tf == ref["uncapped"]["total_fold"], (tf, ref["uncapped"]["total_fold"])
    for key in ("ratio_fold", "ratio_retain"):
        u = [100.0 * (pct(res[key], q) - 1) for q in (10, 50, 90)]
        assert u == ref[key], (key, u, ref[key])
    assert rec["anchor_add"] is None, "empty network must be anchor_add=None"
    assert rec["injected"] == [] and rec["excluded"] == []
    assert rec["depth"] == 1, ("empty-network eval depth is 1", rec["depth"])
    print(f"  G1 OK  harbor|EMPTY reproduces committed results byte-identically: "
          f"newline fold P50 {ref['uncapped']['fold'][1]:,.4f}, retain P50 "
          f"{ref['uncapped']['retain'][1]:,.4f}, total_fold + both ratios")


def test_g2b_substitution_with_anchor_add():
    """G2b: a synthetic PARALLEL committed line (co-located persistent base
    service) scores BELOW standalone WITH the margin-only anchor_add active,
    across omega x {0.5, 1.5} (spec 07 §10 G2b). The double-count failure this
    catches would use GROSS newline and inflate the parallel candidate above
    standalone; the margin-only rule keeps it below. Metric = the new line's own
    newline forecast (the substituted quantity)."""
    cor = Corridor(os.path.join(DER, "corridor_harbor.json"))
    n = 3000
    # a persistent parallel twin of the new line (fast service on the same street)
    sn_svc = cor.cfg["service_new"]
    twin = dict(sn_svc); twin.pop("derived_speed", None)
    twin["speed"] = 30.0; twin["persistent"] = True
    standalone = float(np.median(run(cor, n=n)["uncapped"]["fold"]["newline"]))
    # margin-only anchor_add: H's per-draw MARGIN (new riders) apportioned by
    # omega. Use a synthetic positive margin ~ 2,500 wd riders; base omega 0.5
    # (parallel overlap is high), swept x {0.5, 1.5}.
    margin = np.full(n, 2500.0)
    base_omega = 0.5
    results = {}
    for scale in (0.5, 1.5):
        om = base_omega * scale
        add = nm.anchor_adjustment(om, margin, 0.0)     # omega*margin - fold_sub
        par = float(np.median(
            run(cor, n=n, cfg_patch={"services_base": {"twin": twin}},
                anchor_add=add)["uncapped"]["fold"]["newline"]))
        results[scale] = par
        assert par < standalone, (f"omega x {scale}: parallel {par:,.0f} not "
                                  f"below standalone {standalone:,.0f} -- "
                                  "double-count guard failed")
    print(f"  G2b OK  standalone newline {standalone:,.0f}; parallel+anchor_add "
          f"omega x0.5 {results[0.5]:,.0f} / x1.5 {results[1.5]:,.0f} "
          "(both below -- margin-only, no double count)")


def test_g3_complementarity_sanity():
    """G3: the streetcar (western terminus on Harbor Blvd) scores ABOVE standalone
    after a Harbor commitment (spec 07 §10 G3). Pre-stated POSITIVE; a null reads
    as the tau limitation (§8a), a negative is a bug. The actual % is reported --
    the real geometry SHARES the downtown Santa Ana catchment (omega ~ 0.18), so
    the effect flows through the anchor channel, not only the tau-capped transfer
    channel, and exceeds the pre-stated low-single-digit expectation."""
    params, weights, _ess = sn._cycle_weights(NS, SEED, sn.central_label())
    st = sn.evaluate(dict(_BYID["streetcar"], scenario="fold"), [], params, SEED,
                     weights, _GTFS, _TRACTS, NS, sn.bc.RUN_DIR)
    base = pct(st["scenarios"]["fold"]["wm"], 50)
    hb = sn.evaluate(dict(_BYID["harbor"], scenario="fold"), [], params, SEED,
                     weights, _GTFS, _TRACTS, NS, sn.bc.RUN_DIR)
    Hc = sn._as_committed(dict(_BYID["harbor"], scenario="fold"), hb, params,
                          "fold", [])
    st2 = sn.evaluate(dict(_BYID["streetcar"], scenario="fold"), [Hc], params,
                      SEED, weights, _GTFS, _TRACTS, NS, sn.bc.RUN_DIR)
    g3 = pct(st2["scenarios"]["fold"]["wm"], 50)
    pctd = 100.0 * (g3 - base) / base
    dep = st2["deps"][0]
    assert g3 > base, (f"G3 NEGATIVE (bug): streetcar|harbor {g3:,.0f} <= "
                       f"standalone {base:,.0f}")
    assert "harbor" in st2["injected"][0], "harbor not injected as a feeder"
    assert st2["depth"] == 2, ("streetcar depends on harbor -> depth 2", st2["depth"])
    print(f"  G3 OK  streetcar|EMPTY {base:,.0f} -> |HARBOR {g3:,.0f}  "
          f"({pctd:+.2f}%, ABOVE; omega {dep['omega']:.3f}, fold_sub "
          f"{dep['fold_sub']:.0f}; anchor + transfer channel, depth 2)")


def test_g4_crn_rank_stability():
    """G4: seed-drift on the committed-order objective <= 2% (mirrors the ABC
    gate) and the committed ORDER exactly stable on a seed+1 rerun (spec 07 §10
    G4). Knife-edge pairs are reported as P ~ 0.5, not defects."""
    a = _seq(seed=SEED, n=4000)
    b = _seq(seed=SEED + 1, n=4000)
    oa = [p["line"] for p in a["frontier"]["points"]]
    ob = [p["line"] for p in b["frontier"]["points"]]
    va = a["frontier"]["points"][-1]["cum_wm_uncapped"][1]
    vb = b["frontier"]["points"][-1]["cum_wm_uncapped"][1]
    drift = 100.0 * (vb - va) / va
    assert oa == ob, (f"committed order not stable: {oa} vs {ob}")
    assert abs(drift) <= 2.0, (f"objective drift {drift:+.2f}% exceeds 2%")
    print(f"  G4 OK  order {oa} stable seed {SEED}/{SEED+1}; objective P50 "
          f"{va:,.0f} -> {vb:,.0f}  drift {drift:+.2f}%")


def test_g6_artifact_reproducible():
    """G6: the primary artifact is byte-identical on rerun from the same seed +
    configs (spec 07 §10 G6): canonical floats, sorted keys, no timestamps, run
    id = sha256 of the config-set (no wall clock)."""
    a = _seq(n=1500)
    b = _seq(n=1500)
    sa = sn.json.dumps(sn._canon(a), sort_keys=True, indent=2)
    sb = sn.json.dumps(sn._canon(b), sort_keys=True, indent=2)
    assert sa == sb, "artifact not byte-identical on rerun"
    assert a["run_id"] == b["run_id"] and len(a["run_id"]) == 64
    # run id carries no timestamp: identical across the two runs by construction
    print(f"  G6 OK  artifact byte-identical on rerun (run_id "
          f"{a['run_id'][:16]}, {len(sa):,} bytes)")


def test_g7_sensitivity_knob_rows():
    """G7: the sensitivity block carries every N1b-scope knob row IN THIS COMMIT
    (cycle_gap lo/hi, budget lo/hi, omega x {0.5,1.5}, uniform, depth-cap 1/3)
    and NAMES the spec-pending N4/N5 rows (spec 07 §10 G7)."""
    a = _seq(n=1500)
    sens = sn.run_sensitivity(a, _CANDS, _HS, _SUBST, SEED, 1500, "fold",
                              _GTFS, _TRACTS)
    ids = {r["id"] for r in sens["computed_n1b"]}
    need = {"cycle_gap_lo", "cycle_gap_hi", "budget_lo", "budget_hi",
            "omega_0.5", "omega_1.5", "omega_uniform", "depth_cap_1", "depth_cap_3"}
    assert need <= ids, ("missing N1b knob rows", need - ids)
    pending = {r["id"] for r in sens["named_spec_pending"]}
    need_p = {"sigma_struct", "fixed_cost_share", "k3_order_diff",
              "offpeak_to_midday", "ratio_greedy_order"}
    assert need_p <= pending, ("missing named spec-pending rows", need_p - pending)
    # the budget_lo row actually re-selects the portfolio (a real delta)
    blo = next(r for r in sens["computed_n1b"] if r["id"] == "budget_lo")
    assert blo["pct"] is not None and blo["pct"] < 0, "budget_lo must bind"
    # omega rows move the objective (anchor apportionment is live)
    om = {r["id"]: r["pct"] for r in sens["computed_n1b"]
          if r["id"].startswith("omega_")}
    assert om["omega_1.5"] != om["omega_0.5"], "omega sweep inert"
    print(f"  G7 OK  {len(need)} N1b knob rows computed, "
          f"{len(pending)} spec-pending named; budget_lo {blo['pct']:+.1f}%, "
          f"omega x0.5/x1.5 {om['omega_0.5']:+.2f}/{om['omega_1.5']:+.2f}%")


def test_w1_omega_uses_real_worker_mass():
    """Wiring note 1: omega() must receive REAL worker masses (from the corridor
    tracts), not the silent uniform fallback. Assert the worker mass is
    non-uniform AND that worker-mass allocation gives a DIFFERENT omega than the
    uniform variant (so the declared default is real)."""
    H = _BYID["harbor"]
    assert len(H["worker_mass"]) > 0, "no corridor-tract worker mass built"
    assert H["worker_mass"].std() > 0, "worker mass is uniform (fallback leaked)"
    B = _BYID["streetcar"]
    om_worker = nm.omega(H["x"], H["y"], B["x"], B["y"], H["spacing"],
                         worker_pts=H["worker_pts"], worker_mass=H["worker_mass"],
                         B_window=B["window"], allocation="worker_mass")
    om_uniform = nm.omega(H["x"], H["y"], B["x"], B["y"], H["spacing"],
                          worker_pts=H["worker_pts"], worker_mass=H["worker_mass"],
                          B_window=B["window"], allocation="uniform")
    assert om_worker != om_uniform, ("worker-mass omega equals uniform -- masses "
                                     "are not actually differentiating")
    print(f"  W1 OK  worker mass non-uniform (std {H['worker_mass'].std():,.0f} "
          f"over {len(H['worker_mass'])} tracts); omega worker {om_worker:.3f} "
          f"!= uniform {om_uniform:.3f}")


def test_w2_omega_uses_windowed_shape():
    """Wiring note 2: omega() / the injection see the WINDOWED (window-truncated)
    H shape. The loaded candidate's x/y are the truncated polyline; assert its
    length equals the windowed extent, not the full alignment when a window is
    set. (Both candidates have null windows here, so assert the truncation path
    is exercised: route_mi == polyline_length(windowed shape).)"""
    for c in _CANDS:
        assert abs(nm.polyline_length(c["x"], c["y"]) - c["route_mi"]) < 1e-6
        w0, w1 = c["window"]
        assert w1 - w0 <= nm.polyline_length(c["x"], c["y"]) + 1e-6
    # exercise a genuine window truncation on harbor's alignment
    H = _BYID["harbor"]
    full = nm.polyline_length(H["x"], H["y"])
    tx, ty = nm.truncate_polyline(H["x"], H["y"], 1.0, full - 1.0)
    assert nm.polyline_length(tx, ty) < full, "window truncation did not shorten"
    print(f"  W2 OK  candidate shapes are windowed (harbor {H['route_mi']:.2f} mi "
          f"= windowed length); truncation path exercised")


def test_w3_feeder_injection_screened_by_predicate():
    """Wiring note 3: feeder injection is SCREENED by the dependency predicate.
    A committed line with omega <= threshold and no co-location is NOT injected;
    one with omega > threshold IS. Streetcar-into-harbor and harbor-into-streetcar
    both cross, so both inject; a synthetic far-away line does NOT."""
    params, weights, _ess = sn._cycle_weights(NS, SEED, sn.central_label())
    hb = sn.evaluate(dict(_BYID["harbor"], scenario="fold"), [], params, SEED,
                     weights, _GTFS, _TRACTS, NS, sn.bc.RUN_DIR)
    Hc = sn._as_committed(dict(_BYID["harbor"], scenario="fold"), hb, params,
                          "fold", [])
    add, injected, excluded, deps = sn.build_anchor_add(
        dict(_BYID["streetcar"], scenario="fold"), [Hc], _GTFS, params, SEED, NS)
    assert deps[0]["depends"] and injected, "crossing line not injected"
    # a synthetic non-dependent line (omega forced 0 via a disjoint far shape)
    far = dict(_BYID["streetcar"], scenario="fold")
    far["x"] = _BYID["streetcar"]["x"] + 1000.0     # 1000 mi away -> no overlap
    far["y"] = _BYID["streetcar"]["y"] + 1000.0
    far["worker_pts"] = _BYID["streetcar"]["worker_pts"] + 1000.0
    Fc = sn._as_committed(far, hb, params, "fold", [])
    Fc["x"], Fc["y"] = far["x"], far["y"]
    Fc["worker_pts"] = far["worker_pts"]
    add2, inj2, exc2, deps2 = sn.build_anchor_add(
        dict(_BYID["harbor"], scenario="fold"), [Fc], _GTFS, params, SEED, NS)
    assert not deps2[0]["depends"] and not inj2, "far line wrongly injected"
    print(f"  W3 OK  crossing line injected (omega {deps[0]['omega']:.3f} > "
          f"{sn.DEP_OMEGA}); disjoint line screened out (omega "
          f"{deps2[0]['omega']:.3f})")


def test_interaction_and_provenance():
    """The audit-side interaction matrix is symmetrized with the timing
    decomposition + tau caveat (§5.1/§5.4), and the provenance depth chains
    (cycle-2 depth 2, cap 2 -> decision-grade)."""
    a = _seq(n=2000)
    I = a["cycles"][0]["interaction_matrix"][0]
    assert I["pair"] == ["harbor", "streetcar"]
    assert "tau" in I["tau_caveat"].lower()
    assert I["sequencing_component_p50"] == 0.0    # delta=1 in interim
    assert abs(I["approximation_component_p50"] - I["I_p50"]) < 1e-6
    # provenance: the second commitment depends on the first -> depth 2
    depths = [H["depth"] for H in a["provenance_report"]["lines"]]
    assert max(depths) == 2 and a["provenance_report"]["lines"][1]["depth"] == 2
    assert a["frontier"]["points"][1]["depth_label"] == "decision-grade"
    # stopping record carries the economic margin, not "ran out"
    st = a["stopping_record"]
    assert st["reason"] == "candidate_exhaustion"
    assert "bcr_rule_note" in st and "N5" in st["bcr_rule_note"]
    print(f"  INTERACTION/PROVENANCE OK  I{I['pair']} P50 {I['I_p50']:+,.0f} "
          f"(seq comp 0, tau-caveated); depths {depths}; stop {st['reason']}")


def test_budget_binding_stop():
    """Under a binding budget the stop is exhaustion with the SHADOW-PRICE /
    economic margin reported (spec 07 §7), never 'candidates ran out'."""
    a = _seq(n=1500, budget=2000.0)   # < harbor US-TYPICAL (2967) -> harbor excluded
    ids = [p["line"] for p in a["frontier"]["points"]]
    assert "harbor" not in ids, ("harbor should be infeasible under 2000 $M", ids)
    st = a["stopping_record"]
    assert st["reason"] == "budget_exhaustion", st
    assert "economic_margin_note" in st, "no economic margin on budget stop"
    print(f"  BUDGET OK  under 2000 $M -> {ids}; stop {st['reason']} with "
          f"economic margin {st['economic_margin_note']['best_uncommitted']}")


if __name__ == "__main__":
    test_g1_single_line_degeneracy()
    test_g2b_substitution_with_anchor_add()
    test_g3_complementarity_sanity()
    test_g4_crn_rank_stability()
    test_g6_artifact_reproducible()
    test_g7_sensitivity_knob_rows()
    test_w1_omega_uses_real_worker_mass()
    test_w2_omega_uses_windowed_shape()
    test_w3_feeder_injection_screened_by_predicate()
    test_interaction_and_provenance()
    test_budget_binding_stop()
    print("ALL SEQUENCE-HARNESS GATES PASS")
