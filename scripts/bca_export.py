"""
BCA export: freeze the stage-2 per-draw quantity streams the downstream node
BCA wrapper prices (spec 06 §2/§3 -- "quantities from the ridership model;
prices, time-profile, and public finance from the BCA"). This script runs
run() once per design point with shared params (common random numbers) and
writes outputs/bca_export_<corridor>.json.gz -- the file interface the
wrapper consumes. It computes NO prices and NO welfare valuation; it only
packages what B1-B3 already accumulated per draw.

For a corridor with a backtest calibration target (harbor's 2013 Bravo! 543)
it also exports the ABC draw weights, keyed by kernel label so the spec 02
§4.4 joint kernel can join later. A corridor with no target until post-launch
(the OC Streetcar, spec 05) degrades gracefully: the abc_weights block is
omitted and an abc_weights_absent_reason is recorded instead.

Every big float array is stored at float32 precision (spec 06 §3, ~7 sig
digits); files are gzipped, regenerable, and gitignored. A round-trip
self-check (printed, not written) reads the gz back and matches a P50 against
the committed reference; it exits nonzero on disagreement.

usage: python bca_export.py harbor [--seed-check]
       python bca_export.py streetcar
"""
import gzip, json, os, sys
import numpy as np
from model import Corridor, run, draw_params, pct, wpct, N
from reweight_abc import abc_weights, get_kernels, central_label
from backtest_543 import backtest_corridor
from assumptions import val

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
DER = os.path.join(HERE, "..", "data", "derived")
OUT = os.path.join(HERE, "..", "outputs")
SEED = val("seed")
EQ_DAYS = val("eq_days")              # weekday->annual band (anchor_from_apc convention)

# ABC kernels for a corridor that has a backtest target: (label, mu, sigma),
# central first. Imported from reweight_abc (single source of truth) so the
# export carries exactly the same five launch/matured kernels the calibration
# writes -- no hardcoded labels here.
HARBOR_KERNELS = get_kernels()


def f32(a):
    """float32-round an array to a plain-float JSON list (spec 06 §3 --
    applied uniformly to every big array so the wrapper sees ~7 sig digits)."""
    return np.asarray(a, dtype=np.float32).tolist()


def scenario_block(d, p):
    """One scenario's per-draw streams, PRE-BLEND and WORK-SHAPED (the wrapper
    applies the D8 ws/kappa blend). cm_seg / cm_seg_fullod are (n,3) split into
    three lists in car_frac order 0/1/2+-veh (spec 06 §3). `p` is the shared
    params dict (draw_params) -- source of the vot_behav stream below."""
    def seg(k):
        arr = np.asarray(d[k])                       # (n, 3)
        return [f32(arr[:, j]) for j in range(3)]
    return {
        "newline": f32(d["newline"]),
        "total": f32(d["total"]),
        "um_infra": f32(d["um_infra"]),              # equivalent-IVT min/wd
        "um_margin": f32(d["um_margin"]),
        "um0_infra": f32(d["um0_infra"]),            # no-ASC counterfactual (D1)
        "um0_margin": f32(d["um0_margin"]),
        # spec 06 W1: rule-of-half welfare alternative (D10 roh row). um_roh_infra
        # == um_infra by definition (shared S0·dv term); um_roh_margin is the
        # trapezoid margin, in equivalent-IVT min/wd.
        "um_roh_infra": f32(d["um_roh_infra"]),
        "um_roh_margin": f32(d["um_roh_margin"]),
        "fare_burden": f32(d["fare_burden"]),        # $/wd, 0 at flat fares (D3)
        # spec 06 W1: fiscal fare_receipts (fare_sweep row); $/wd, 0 at flat
        # fares. fare_burden == fare_receipts_infra + 0.5*fare_receipts_margin.
        "fare_receipts_infra": f32(d["fare_receipts_infra"]),
        "fare_receipts_margin": f32(d["fare_receipts_margin"]),
        "cm_seg": seg("cm_seg"),                     # diverted trip-mi, pre-pcar
        "cm_visitor": f32(d["cm_visitor"]),
        "cm_seg_fullod": seg("cm_seg_fullod"),       # transfer legs at full O-D
        # FB batch (external review 2026-07-17): per-draw behavioral-VOT prior
        # draws ($/hr, the vot_behav prior). Scenario-INVARIANT by construction
        # (a prior draw, not an accumulated quantity), duplicated verbatim into
        # both scenario blocks the way um_roh_infra aliases um_infra -- so the
        # wrapper reads every priced stream from one place. Un-blocks the tbc
        # vot_wedge tornado row: re-price the exported minute streams by the
        # draw-level behavioral VOT instead of the engine's welfare VOT (the
        # roh / fare_sweep W1R precedent).
        "vot_behav": f32(p["vot_behav"]),
    }


def compute_weights(name, params, seed):
    """ABC draw weights for a corridor with a backtest target. Harbor only
    today (its 543 natural experiment); a corridor with no calibration target
    until post-launch returns None. The streetcar path is safe not because of
    where backtest_corridor is imported -- reweight_abc already imports it at
    module load, so the harbor-specific backtest is present regardless -- but
    because of the harbor-only call gate below: backtest_corridor() is never
    CALLED off the harbor branch."""
    if name != "harbor":
        return None
    pred = run(backtest_corridor(), params=params,
               seed=seed)["uncapped"]["retain"]["newline"]
    return abc_weights(pred, HARBOR_KERNELS)


def build_export(name, res, seed, weights, design, routes_removed, base_service,
                 n=None, network_fp=None, cost_design=None):
    """Assemble the spec 06 §3 export dict FROM IN-MEMORY run() RESULTS -- no
    re-run (spec 07 N5). The standalone CLI path (build_design_point) and the
    sequencing harness both funnel through here, so the schema is single-source.

    The two spec 07 N5 EXPORTER additions ride OPTIONAL kwargs, so the standalone
    path (which passes neither) writes the byte-identical B4 schema:
      * network_fingerprint (spec 06 §3, N5): sha256 of the networked rebuild
        descriptor -- present only on the harness-built candidate-given-network
        exports, so the fingerprint-bearing filename and the wrapper's networked
        output can never collide across candidates/cycles.
      * cost_design (N5): the harness-owned capital bands (capcost.py / spec 04)
        + the corridor service design the wrapper prices under. The harness OWNS
        capital (spec 06 §2 division of labor), so it ships it here rather than
        letting the wrapper re-read a static cost profile K; the wrapper's
        networked mode overrides profile.capital with this block.
    """
    export = {
        "corridor": name,
        "design": design,
        "n": n if n is not None else len(res["anchor"]),
        "seed": seed,
        "eq_days": EQ_DAYS,
        "scenarios": {scen: scenario_block(res["uncapped"][scen], res["params"])
                      for scen in ("fold", "retain")},
        "params": {k: f32(v) for k, v in res["params"].items()},
    }
    export["params"]["anchor"] = f32(res["anchor"])
    if weights is not None:
        export["abc_weights"] = {label: f32(w) for label, w in weights.items()}
    else:
        export["abc_weights_absent_reason"] = (
            "no calibration target until post-launch (spec 05): the corridor "
            "has no pre-launch natural experiment to reweight draws against, "
            "so the export degrades to uncapped-only")
    # spec 06 §3: routes_removed is a TOP-LEVEL key (per-scenario route lists
    # from the config bca block; {"fold": [], "retain": []} when the corridor
    # folds nothing). base_service carries ONLY rev_hours_weekday -- empty {}
    # (rev_hours_weekday absent) when the corridor defines none, e.g. the
    # streetcar's synthetic composite local has no single route to remove.
    export["routes_removed"] = routes_removed
    export["base_service"] = base_service
    # spec 07 N5 exporter additions (optional; absent on the standalone path so
    # the B4 schema/bytes are unchanged).
    if network_fp is not None:
        export["network_fingerprint"] = network_fp
    if cost_design is not None:
        export["cost_design"] = cost_design
    return export


def _bca_block(cor):
    """(design, routes_removed, base_service) for the standalone CLI path, read
    from the committed corridor config's bca block (spec 06 §3)."""
    bca = cor.cfg.get("bca", {})
    routes_removed = bca.get("routes_removed", {"fold": [], "retain": []})
    rev_hours = bca.get("rev_hours_weekday", {})
    base_service = {"rev_hours_weekday": rev_hours} if rev_hours else {}
    return cor.cfg["service_new"], routes_removed, base_service


def build_design_point(name, seed):
    """Run one design point (one seed) and assemble the §3 export dict (standalone
    CLI path). Shared params flow through both the forward run and (for harbor)
    the backtest run -- the same common random numbers reweight_abc.py uses.
    Passes NO network_fp / cost_design, so the schema/bytes are the B4 schema."""
    cor = Corridor(os.path.join(DER, f"corridor_{name}.json"))
    params = draw_params(N, seed)
    res = run(cor, params=params, seed=seed)
    weights = compute_weights(name, params, seed)
    design, routes_removed, base_service = _bca_block(cor)
    return build_export(name, res, seed, weights, design, routes_removed,
                        base_service, n=N)


def write_gz(path, obj):
    with gzip.open(path, "wt", encoding="utf-8") as f:
        json.dump(obj, f)
    return os.path.getsize(path)


def _sig4(x):
    return float(f"{x:.4g}")


def roundtrip_check(name, path):
    """Read the gz back and match a P50 against the committed reference to 4
    significant figures (float32 rounding is well inside that). Harbor: the
    ABC central-kernel retain P50 (weighted) vs abc_harbor.json. Streetcar (no
    weights): the unweighted retain newline P50 vs results_streetcar.json.
    Returns True/False; the caller turns False into a nonzero exit."""
    with gzip.open(path, "rt", encoding="utf-8") as f:
        e = json.load(f)
    newline = np.asarray(e["scenarios"]["retain"]["newline"])
    if "abc_weights" in e:
        lbl = central_label()
        w = np.asarray(e["abc_weights"][lbl])
        got = wpct(newline, w, 50)
        with open(os.path.join(OUT, f"abc_{name}.json"), encoding="utf-8") as fh:
            ref = json.load(fh)["kernels"][lbl]["forecast"]["retain"][1]
        what = f"ABC central ({lbl}) retain P50, weighted, vs abc_{name}.json"
    else:
        got = pct(newline, 50)
        with open(os.path.join(OUT, f"results_{name}.json"),
                  encoding="utf-8") as fh:
            ref = json.load(fh)["summary"]["uncapped"]["retain"][1]
        what = f"unweighted retain newline P50 vs results_{name}.json"
    # spec 06 §3 round-trip gate: strict 4-significant-figure match. float32
    # rounding lands ~1e-8 relative, well inside 4 sig figs, so the earlier
    # 5e-4 relative fallback is dropped -- code now matches its stated contract.
    ok = _sig4(got) == _sig4(ref)
    tag = "OK" if ok else "FAIL"
    print(f"round-trip [{tag}] {what}: export {got:,.4f} vs committed "
          f"{ref:,.4f}  (rel {abs(got - ref) / abs(ref):.2e})")
    return ok


def networked_export_path(name, fp, out_dir=OUT):
    """Gitignored, fingerprint-bearing filename for a harness-built candidate-
    given-network export (spec 07 N5). The 12-char fp keeps distinct candidate /
    cycle points from colliding; the bca_export_* glob (B4) already gitignores
    it, so these heavy files are never committed."""
    return os.path.join(out_dir, f"bca_export_{name}_{fp[:12]}.json.gz")


def selfcheck_weighted_p50(path, label=None):
    """Networked round-trip SELF-CONSISTENCY (spec 07 N5): read the gz back and
    recompute ONE weighted (ABC central) -- or unweighted, for a corridor with no
    kernel -- retain newline P50 from its OWN arrays. A candidate-given-network
    point has NO committed reference (it is a hypothetical), so this proves the
    write/read/float32 path is lossless-consistent, NOT a committed match; the
    caller compares it to the same P50 computed from the in-memory export."""
    with gzip.open(path, "rt", encoding="utf-8") as f:
        e = json.load(f)
    newline = np.asarray(e["scenarios"]["retain"]["newline"])
    if "abc_weights" in e:
        lbl = label or central_label()
        return float(wpct(newline, np.asarray(e["abc_weights"][lbl]), 50))
    return float(pct(newline, 50))


def inmemory_weighted_p50(export, label=None):
    """The same P50 selfcheck_weighted_p50 recomputes, but from the IN-MEMORY
    export dict (before the gz write) -- the reference side of the self-
    consistency check."""
    newline = np.asarray(export["scenarios"]["retain"]["newline"])
    if "abc_weights" in export:
        lbl = label or central_label()
        return float(wpct(newline, np.asarray(export["abc_weights"][lbl]), 50))
    return float(pct(newline, 50))


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    name = argv[0]
    seed_check = "--seed-check" in argv[1:]

    path = os.path.join(OUT, f"bca_export_{name}.json.gz")
    size = write_gz(path, build_design_point(name, SEED))
    print(f"-> {path}  ({size / 1e6:.2f} MB, seed {SEED})")

    if seed_check:
        # seed+1 companion (mirrors reweight_abc.py's seed-drift pattern);
        # weights recomputed from the seed+1 backtest run -- feeds gate G4.
        path2 = os.path.join(OUT, f"bca_export_{name}_seed{SEED + 1}.json.gz")
        size2 = write_gz(path2, build_design_point(name, SEED + 1))
        print(f"-> {path2}  ({size2 / 1e6:.2f} MB, seed {SEED + 1})")

    ok = roundtrip_check(name, path)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
