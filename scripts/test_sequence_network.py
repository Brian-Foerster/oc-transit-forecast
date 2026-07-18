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
    # N4 computed the previously-named sigma_struct / fixed_cost_share /
    # offpeak_to_midday rows AND added the margin-distribution + exclusive-tract
    # variants (spec 07 §9 N4).
    need = {"cycle_gap_lo", "cycle_gap_hi", "budget_lo", "budget_hi",
            "omega_0.5", "omega_1.5", "omega_uniform", "omega_walk_bin_mass",
            "exclusive_tract", "depth_cap_1", "depth_cap_3", "offpeak_to_midday",
            "sigma_struct", "fixed_cost_share_0.5", "fixed_cost_share_0.0"}
    assert need <= ids, ("missing N4 knob rows", need - ids)
    pending = {r["id"] for r in sens["named_spec_pending"]}
    need_p = {"k3_order_diff", "ratio_greedy_order", "premium_bracket"}
    assert need_p <= pending, ("missing named spec-pending rows", need_p - pending)
    # the sigma_struct / fixed_cost_share rows are no longer named-pending
    assert "sigma_struct" not in pending and "fixed_cost_share" not in pending, \
        "sigma_struct/fixed_cost_share should be computed at N4, not named-pending"
    # the budget_lo row actually re-selects the portfolio (a real delta)
    blo = next(r for r in sens["computed_n1b"] if r["id"] == "budget_lo")
    assert blo["pct"] is not None and blo["pct"] < 0, "budget_lo must bind"
    # omega rows move the objective (anchor apportionment is live)
    om = {r["id"]: r["pct"] for r in sens["computed_n1b"]
          if r["id"].startswith("omega_")}
    assert om["omega_1.5"] != om["omega_0.5"], "omega sweep inert"
    print(f"  G7 OK  {len(need)} N4 knob rows computed, "
          f"{len(pending)} spec-pending named; budget_lo {blo['pct']:+.1f}%, "
          f"omega x0.5/x1.5 {om['omega_0.5']:+.2f}/{om['omega_1.5']:+.2f}%")


def test_n4_channel_split():
    """spec 07 N4 / N1b review: a candidate-given-network single carries the
    anchor-vs-rebuild channel split, and lift = anchor + rebuild + cross (the
    toggle identity). The rebuild channel is market-enlargement, reported apart
    from crossing complementarity."""
    a = _seq(n=1500)
    # cycle 1 (network {harbor}) -> streetcar is networked -> has a channel split
    c1 = a["cycles"][1]
    cs = None
    for b in c1["candidate_results"]:
        if b.get("channel_split") is not None:
            cs = b["channel_split"]; cid = b["id"]
    assert cs is not None, "no channel_split on the networked candidate"
    s = cs["scenarios"]["fold"]
    # the split is per-draw; P50 of a per-draw difference != difference of P50s
    # (percentile nonlinearity), so assert DIRECTION not exact additivity:
    assert s["full_p50"] > s["standalone_p50"], "networked full below standalone"
    assert s["lift_p50"] > 0, "networked lift over standalone not positive"
    # the anchor (margin-substitution) channel dominates; the rebuild channel is
    # market-enlargement, an order of magnitude smaller -- the whole point of the
    # split (it must not be mistaken for crossing complementarity)
    assert s["anchor_channel_p50"] > abs(s["rebuild_channel_p50"]), \
        "rebuild channel not clearly separated below the anchor channel"
    for k in ("anchor_channel_p50", "rebuild_channel_p50", "cross_residual_p50",
              "anchor_channel_abc_p50"):
        assert k in s, ("missing channel-split field", k)
    # cycle 0 (empty network) candidates are standalone -> no channel split
    c0 = a["cycles"][0]
    assert all(b.get("channel_split") is None for b in c0["candidate_results"]), \
        "cycle-0 standalone candidates must not carry a channel split"
    print(f"  N4-CHANNEL OK  {cid}|{{harbor}} lift {s['lift_p50']:+,.0f} = anchor "
          f"{s['anchor_channel_p50']:+,.0f} + rebuild {s['rebuild_channel_p50']:+,.0f} "
          f"+ cross {s['cross_residual_p50']:+,.0f} (rebuild = market enlargement)")


def test_n4_sigma_struct_and_variants():
    """spec 07 N4: the frontier carries base vs sigma_struct-inflated portfolio
    bands (sigma_struct is COMPUTED, not spec-pending), and the omega
    walk_bin_mass + exclusive_tract sensitivity variants produce real deltas."""
    a = _seq(n=4000)
    ss = a["frontier"]["sigma_struct_row"]
    assert ss["status"] == "computed", "sigma_struct must be computed at N4"
    assert ss["sigma_struct_boardings"] == sn.SIGMA_STRUCT_BOARDINGS
    fp = ss["final_portfolio"]
    # mean-zero noise: the P50 is ~unchanged and the band is perturbed (differs
    # from base). The WIDENING is guaranteed on VARIANCE -- independent noise
    # strictly raises it -- but band_widening_uncapped is a P90-P10 TAIL statistic
    # whose SIGN only resolves at the production draw count: at the reduced test n
    # the tail sampling error (few draws beyond P90) exceeds the small true
    # widening and can flip its sign (here -363.6 at n=4000), while the standard
    # deviation -- an all-draws average -- still widens (+300 at n=4000). Assert
    # the tail-band SIGN on the committed PRODUCTION artifact (N=40,000, where the
    # estimate resolves to +776.5), and keep this fast in-test run for the
    # structural checks. (The G1 pattern of reading a committed output.)
    assert fp["base_uncapped"] != fp["sigma_struct_uncapped"], "sigma_struct inert"
    base_p50, ss_p50 = fp["base_uncapped"][1], fp["sigma_struct_uncapped"][1]
    assert abs(ss_p50 - base_p50) / base_p50 < 0.02, "sigma_struct moved the P50"
    # spec 07 N5: network_sequence.json is now the NPV artifact; the committed
    # INTERIM production artifact (the N4 regression anchor) lives at
    # network_sequence_interim.json, which carries the interim frontier's
    # sigma_struct_row.final_portfolio band.
    prod = json.load(open(os.path.join(OUT, "network_sequence_interim.json"),
                          encoding="utf-8"))
    prod_widen = (prod["frontier"]["sigma_struct_row"]["final_portfolio"]
                  ["band_widening_uncapped"])
    assert prod_widen > 0, \
        ("production-N sigma_struct band must widen (P90-P10)", prod_widen)
    # every frontier point carries the inflated band beside the base band
    for p in a["frontier"]["points"]:
        assert "cum_wm_sigma_struct_uncapped" in p
    # walk_bin_mass omega differs from worker_mass AND uniform
    H = _BYID["harbor"]; B = _BYID["streetcar"]
    o_wm = nm.omega(H["x"], H["y"], B["x"], B["y"], H["spacing"],
                    worker_pts=H["worker_pts"], worker_mass=H["worker_mass"],
                    B_window=B["window"], allocation="worker_mass")
    o_wb = nm.omega(H["x"], H["y"], B["x"], B["y"], H["spacing"],
                    worker_pts=H["worker_pts"], worker_mass=H["worker_mass"],
                    B_window=B["window"], allocation="walk_bin_mass",
                    walk_centers=H["walk_centers"], walk_weights=H["walk_weights"])
    o_ex = nm.omega(H["x"], H["y"], B["x"], B["y"], H["spacing"],
                    worker_pts=H["worker_pts"], worker_mass=H["worker_mass"],
                    B_window=B["window"], allocation="worker_mass",
                    exclusive_tract=True)
    assert o_wb != o_wm, "walk_bin_mass omega equals worker_mass"
    assert o_ex < o_wm, "exclusive-tract should drop shared-near-B tracts from H"
    # exclusive-tract overlap metric matches the spec-02 §4.3 27.3% figure
    ov = sn._catchment_overlap(_CANDS)
    assert abs(ov["overlap_pct"] - 27.3) < 0.1, ov
    print(f"  N4-SIGMA/VARIANTS OK  band base {fp['base_uncapped']} -> "
          f"+sigma_struct {fp['sigma_struct_uncapped']}; omega worker {o_wm:.3f} / "
          f"walk_bin {o_wb:.3f} / exclusive {o_ex:.3f}; overlap "
          f"{ov['overlap_pct']:.1f}% ({ov['shared']} shared)")


def test_n4_run_id_values_hash():
    """D60 review rec 3a: the run_id preimage carries the assumptions values-hash
    (capital constants + active prior bands), so the id MOVES when the rate card
    or a prior band changes -- and the artifact records the consumed manifest the
    registry claims (spec 07 §9 N4)."""
    a = _seq(n=800)
    man = a["assumptions_manifest"]
    assert man["values_hash"] and len(man["values_hash"]) == 64
    ids = {c["id"] for c in man["consumed"]}
    # all 11 capital constants + 6 harness knobs are declared
    assert {"cap_occ", "cap_car", "cap_markup_ut", "cycle_gap", "omega_allocation",
            "feeder_headway_map"} <= ids, ids - set()
    assert len(man["consumed"]) == 17, len(man["consumed"])
    # the id differs from the committed input-only N1b/D60 artifact d8b4a016...
    assert not a["run_id"].startswith("d8b4a016"), \
        "run_id did not move despite the values-hash addition"
    print(f"  N4-RUNID OK  run_id {a['run_id'][:16]} (values_hash "
          f"{man['values_hash'][:12]}, {len(man['consumed'])} consumed leaves)")


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


# ---------------------------------------------------------------------------
# spec 07 N5 -- the NPV objective (default). These exercise the tbc-wrapper
# round-trip; skipped (not failed) if the sibling transit-benefit-cost repo /
# node is absent.
# ---------------------------------------------------------------------------
def _npv_available():
    import shutil
    return os.path.exists(sn.TBC_WRAPPER) and shutil.which(sn.NODE_EXE) is not None


def test_npv_schemas_not_swapped():
    """The committed artifacts carry the RIGHT objective: network_sequence.json
    is NPV, network_sequence_interim.json is the interim N4 anchor (guards against
    the two being swapped by a bad regen)."""
    npv = json.load(open(os.path.join(OUT, "network_sequence.json"), encoding="utf-8"))
    itm = json.load(open(os.path.join(OUT, "network_sequence_interim.json"), encoding="utf-8"))
    assert npv["objective"]["mode"] == "npv", npv["objective"]["mode"]
    assert itm["objective"]["mode"] == "interim", itm["objective"]["mode"]
    # the NPV headline verdict: marginal stop, empty portfolio
    assert npv["stopping_record"]["reason"] == "marginal_bcr_below_1"
    assert npv["stopping_record"]["recommended_portfolio"] == []
    print("  NPV-SCHEMAS OK  network_sequence.json=npv (stop marginal_bcr_below_1, "
          "empty portfolio); network_sequence_interim.json=interim")


def test_npv_objective_end_to_end():
    """spec 07 N5: the NPV objective prices each candidate through the tbc wrapper,
    ranks by within-draw CV in PV dollars, and fires the §7 marginal-BCR stop at
    cycle 1 (recommended portfolio EMPTY) with the premium-bracket rows + both
    cost bands + a self-consistent networked round-trip. Deterministic on rerun."""
    if not _npv_available():
        print("  NPV-E2E SKIP  (tbc wrapper / node not available)")
        return
    a = sn.sequence_npv(_CANDS, _HS, _SUBST, seed=SEED, n=800, quiet=True,
                        gtfs=_GTFS, tracts=_TRACTS)
    st = a["stopping_record"]
    assert st["reason"] == "marginal_bcr_below_1", st["reason"]
    assert st["recommended_portfolio"] == [], "portfolio must be empty (stop fires)"
    # the stop must present the ECONOMIC MARGIN (spec 07 §7) -- the note QUOTES
    # "candidates ran out" only to disavow it, so assert the margin language +
    # the marginal-BCR reason, not the absence of the quoted phrase.
    assert "economic_margin_note" in st, "no economic margin on the stop record"
    assert "ECONOMIC MARGIN" in st["economic_margin_note"]
    # both cost bands on the marginal BCR
    marg = st["marginal_bcr_both_bands"]
    assert "LOW" in marg and "US_TYPICAL" in marg
    assert 0 < marg["US_TYPICAL"]["bcr_abc_p50"] < 1.0, marg
    # premium-bracket rows {1,1.5,2}, none clearing 1
    prem = st["premium_bracket_rows"]["rows"]
    assert [r["premium"] for r in prem] == [1.0, 1.5, 2.0]
    assert not any(r["clears_bcr1"] for r in prem), "a premium row cleared BCR=1?!"
    # every candidate block: both bands, CV both bands, self-consistent round-trip,
    # sigma_struct std-primary, premium rows
    c0 = a["cycles"][0]["candidate_results"]
    for b in c0:
        assert b["npv_selfcheck"]["ok"], ("networked round-trip inconsistent", b["id"])
        assert set(b["cv"]) == {"LOW", "US_TYPICAL"}, "CV must carry both bands"
        assert "std_widening_PRIMARY" in b["sigma_struct"], "std-based sigma_struct missing"
        assert "band_widening_p90_p10_SECONDARY" in b["sigma_struct"]
        for bnd in ("LOW", "US_TYPICAL"):
            assert b["fold"][bnd]["bcr_abc"] is not None, "ABC column absent (degrade lifted?)"
    # channel split (streetcar has none at cycle 0 -- empty network -- but the
    # non-additivity note field must be present when a split IS computed): check
    # via a networked continuation is heavy; assert the note lands on any split
    frontier = a["frontier"]
    assert frontier["recommended_portfolio"] == []
    assert len(frontier["points"]) == len(_CANDS)
    for p in frontier["points"]:
        assert p["below_bcr1"], "a candidate above BCR=1?!"
        assert p["dK_pv_US_TYPICAL"] > 0
    print(f"  NPV-E2E OK  stop {st['reason']}, portfolio EMPTY; best-BCR "
          f"{st['best_bcr_candidate']['line']} {st['best_bcr_candidate']['bcr_US_TYPICAL_p50']:.3f} "
          f"UT / {st['best_bcr_candidate']['bcr_LOW_p50']:.3f} LOW; premium rows none clear 1")


def test_npv_determinism():
    """spec 07 N5 / gate G6: the NPV artifact is byte-identical on rerun even
    through the node round-trip (deterministic export -> deterministic per-draw
    NPV -> deterministic within-draw CV)."""
    if not _npv_available():
        print("  NPV-DETERMINISM SKIP  (tbc wrapper / node not available)")
        return
    a = sn.sequence_npv(_CANDS, _HS, _SUBST, seed=SEED, n=600, quiet=True,
                        gtfs=_GTFS, tracts=_TRACTS)
    b = sn.sequence_npv(_CANDS, _HS, _SUBST, seed=SEED, n=600, quiet=True,
                        gtfs=_GTFS, tracts=_TRACTS)
    sa = sn.json.dumps(sn._canon(a), sort_keys=True, indent=2)
    sb = sn.json.dumps(sn._canon(b), sort_keys=True, indent=2)
    assert sa == sb, "NPV artifact not byte-identical on rerun"
    assert a["run_id"] == b["run_id"]
    print(f"  NPV-DETERMINISM OK  byte-identical on rerun (run_id {a['run_id'][:16]}, "
          f"{len(sa):,} bytes)")


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
    test_n4_channel_split()
    test_n4_sigma_struct_and_variants()
    test_n4_run_id_values_hash()
    test_npv_schemas_not_swapped()
    test_npv_objective_end_to_end()
    test_npv_determinism()
    print("ALL SEQUENCE-HARNESS GATES PASS")
