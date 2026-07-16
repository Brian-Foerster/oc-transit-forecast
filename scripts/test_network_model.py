"""
Gates for the model-side N1a wiring (spec 07 §4.2 / §10): the `persistent`
service flag, the `anchor_add` run() extension, and build_corridor's networked
rebuild (synthetic-feeder injection, fold propagation, output routing, the
never-overwrite guard). Runs at reduced n for speed; the FULL-pipeline
byte-identity gate is separate (rerun model/backtest/abc/results/exports).

    python test_network_model.py

  - G2c persistent flag: a co-located persistent committed line's utility is
    present in BOTH ls0 (its presence suppresses the new line's total via the
    raised base) AND ls1 (it out-competes the new line, so newshare -> 0 in
    fold AND retain); WITHOUT the flag it is deleted from the fold system
    (newshare_fold -> 1). This is the §4.2.2 systems-construction fix.
  - G2a substitution direction: a candidate PARALLEL to an injected persistent
    line scores below standalone (base-service injection alone).
  - anchor_add: default None is inert (byte-identical); rng-NEUTRAL (ratio_fold
    unchanged); LINEAR (total shifts by add*ratio per draw); anchor += add.
  - build_corridor networked rebuild: the never-overwrite guard fires; an
    injected committed line appears in the feeder set with its offpeak->midday
    headway; a fold-propagated route is dropped from the live feeders.
"""
import os
import sys

import numpy as np

from model import Corridor, run

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
CORR = os.path.join(HERE, "..", "data", "derived", "corridor_harbor.json")
N = 3000


def _cor():
    return Corridor(CORR)


def _newshare(res, scen):
    d = res["uncapped"][scen]
    return float(np.median(d["newline"] / d["total"]))


def test_persistent_g2c():
    """§4.2.2 / G2c: a dominant co-located persistent metro's utility is present
    in BOTH scenario systems (ls1) and in the base (ls0)."""
    cor = _cor()
    metro = {"speed": 90.0, "headway": 3.0, "spacing": 0.5, "persistent": True}
    # asc pinned 0 so the new line has no ASC edge -> the fast/frequent metro
    # cleanly dominates every cell, making the ls1-membership signal crisp.
    standalone = run(cor, n=N, asc=0.0)
    persist = run(cor, n=N, asc=0.0,
                  cfg_patch={"services_base": {"metro": dict(metro)}})
    metro_off = dict(metro); metro_off["persistent"] = False
    notpersist = run(cor, n=N, asc=0.0,
                     cfg_patch={"services_base": {"metro": metro_off}})
    ns_fold_p = _newshare(persist, "fold")
    ns_ret_p = _newshare(persist, "retain")
    ns_fold_np = _newshare(notpersist, "fold")
    # ls1: the persistent metro out-competes the new line in BOTH systems
    assert ns_fold_p < 0.05, f"persistent metro not in ls1_fold (newshare {ns_fold_p})"
    assert ns_ret_p < 0.05, f"persistent metro not in ls1_retain (newshare {ns_ret_p})"
    # WITHOUT the flag the metro is DELETED from the fold system -> new wins all
    assert ns_fold_np > 0.95, f"non-persistent metro still in ls1_fold ({ns_fold_np})"
    # ls0: the metro is in the base regardless of the flag -> it raises ls0 and
    # suppresses the new line's total vs the metro-free standalone
    t_standalone = float(np.median(standalone["uncapped"]["fold"]["total"]))
    t_persist = float(np.median(persist["uncapped"]["fold"]["total"]))
    assert t_persist < t_standalone, (t_persist, t_standalone)
    print(f"  test_persistent_g2c OK  (ls1: newshare fold {ns_fold_p:.2f}/retain "
          f"{ns_ret_p:.2f} -> 0 WITH flag, {ns_fold_np:.2f} -> 1 WITHOUT; "
          f"ls0: total {t_persist:.0f} < {t_standalone:.0f})")


def test_g2a_substitution_direction():
    """G2a: a candidate PARALLEL to an injected persistent line scores below
    standalone (base-service injection alone)."""
    cor = _cor()
    sn = cor.cfg["service_new"]
    twin = dict(sn)
    twin.pop("derived_speed", None)          # a committed at-grade twin (parallel)
    twin["speed"] = 30.0
    twin["persistent"] = True
    standalone = float(np.median(run(cor, n=N)["uncapped"]["fold"]["newline"]))
    parallel = float(np.median(
        run(cor, n=N, cfg_patch={"services_base": {"twin": twin}})
        ["uncapped"]["fold"]["newline"]))
    assert parallel < standalone, (parallel, standalone)
    print(f"  test_g2a_substitution_direction OK  (parallel {parallel:.0f} < "
          f"standalone {standalone:.0f})")


def test_anchor_add_inert_neutral_linear():
    """anchor_add: None inert; rng-neutral (ratio unchanged); linear in add."""
    cor = _cor()
    r_none = run(cor, n=N)
    r_none2 = run(cor, n=N, anchor_add=None)
    tf = r_none["uncapped"]["fold"]["total"]
    # inert: default None is byte-identical to absent
    assert np.array_equal(tf, r_none2["uncapped"]["fold"]["total"]), "None not inert"
    add = np.linspace(-200.0, 500.0, N)
    r_add = run(cor, n=N, anchor_add=add)
    # rng-neutral: the ratio (jitter-stream-driven) is byte-identical -> the
    # anchor draw's downstream stream did not shift
    assert np.array_equal(r_none["ratio_fold"], r_add["ratio_fold"]), "not rng-neutral"
    # linear: total = anchor*ratio, so total shifts by exactly add*ratio
    assert np.allclose(r_add["uncapped"]["fold"]["total"],
                       tf + add * r_none["ratio_fold"], rtol=0, atol=1e-6)
    # the anchor itself is shifted by add (post-pin retention path)
    assert np.allclose(r_add["anchor"], r_none["anchor"] + add)
    print("  test_anchor_add_inert_neutral_linear OK  (None inert; ratio "
          "identical; total += add*ratio; anchor += add)")


def test_anchor_add_retained_under_pin():
    """anchor_add applies AFTER the over['anchor'] pin branch, so a pinned anchor
    RETAINS the network adjustment (spec 07 §4.2)."""
    cor = _cor()
    pin = 8000.0
    add = np.full(N, 250.0)
    r = run(cor, n=N, anchor=pin, anchor_add=add)
    assert np.allclose(r["anchor"], pin + 250.0), r["anchor"][:3]
    print(f"  test_anchor_add_retained_under_pin OK  (pin {pin:.0f} + 250 kept)")


def test_build_corridor_networked():
    """build_corridor: never-overwrite guard; injection appends the committed
    line with its offpeak->midday headway; fold propagation drops a live feeder."""
    import build_corridor as bc
    cfg_path = os.path.join(HERE, "..", "config", "harbor.json")
    # guard: a networked rebuild without an explicit dest is refused
    try:
        bc.main(cfg_path, injected_lines=[{"route": "x", "corridor_route": "43"}])
        raise AssertionError("guard did not fire")
    except ValueError as exc:
        assert "overwrite" in str(exc)
    # baseline live feeders (committed build), then a networked rebuild that
    # (a) injects Route 43 as a committed line and (b) fold-propagates Route 30.
    import json
    base_dest = bc.networked_path("harbor", "n1a_base")
    bc.main(cfg_path, dest=base_dest)
    base = json.load(open(base_dest, encoding="utf-8"))
    base_feeders = {f["route"] for f in base["feeders"]}
    assert "30" in base_feeders, "expected Route 30 as a baseline feeder"

    net_dest = bc.networked_path("harbor", "n1a_net")
    bc.main(cfg_path, dest=net_dest,
            injected_lines=[{"route": "harbor_metro", "corridor_route": "43",
                             "window_mi": [1.0, 6.0],
                             "headway": {"peak": 5.0, "offpeak": 12.0}}],
            excluded_fold_routes=["30"])
    net = json.load(open(net_dest, encoding="utf-8"))
    net_by_route = {f["route"]: f for f in net["feeders"]}
    assert "harbor_metro" in net_by_route, "injected committed line missing"
    assert net_by_route["harbor_metro"]["headway"] == 12.0, "offpeak->midday map"
    assert "30" in base_feeders and "30" not in net_by_route, "fold route not dropped"
    for d in (base_dest, net_dest):
        os.remove(d)
    print("  test_build_corridor_networked OK  (guard fires; 43 injected @ hw 12 "
          "offpeak->midday; fold route 30 dropped)")


if __name__ == "__main__":
    test_persistent_g2c()
    test_g2a_substitution_direction()
    test_anchor_add_inert_neutral_linear()
    test_anchor_add_retained_under_pin()
    test_build_corridor_networked()
    print("ALL NETWORK-MODEL GATES PASS")
