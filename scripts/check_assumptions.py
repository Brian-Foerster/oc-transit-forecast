"""
Enforcement + appendix for the assumptions registry (spec 08 §5/§6).

This is what makes `scripts/assumptions.py` LOAD-BEARING rather than decorative:
seven mechanical checks that fail the build (exit nonzero) when the registry
and the artifacts it claims to describe drift apart. `--appendix` regenerates
the committed audit inventory (`outputs/assumptions.md` + `.json`).

    python scripts/check_assumptions.py              # run the 7 checks
    python scripts/check_assumptions.py --appendix    # + regenerate the appendix

Checks (spec 08 §5):
  1. schema      -- required fields per tier; rows-or-disposition; bands scoped
                    to band-edge-row owners (the A2b-landed clause, ratified in
                    §9); history dated.
  2. coverage    -- every claimed (artifact, row-id) exists in its artifact.
  3. no orphans  -- every present (artifact, row-id) is claimed by exactly one
                    entry.
  4. prior integ -- model.PRIORS is the build_priors() sentinel; count ==
                    N_PRIORS and the ordered-name hash == PRIOR_ORDER_FINGERPRINT
                    (both READ FROM test_bca_export.py -- one source).
  5. materiality -- tier-scoped (constant/config/data); a material (>=2%)
                    literature/judgment band-owner must show BOTH edges as rows;
                    structural entries satisfy it by enumerating every alt row;
                    priors are exempt (reported separately in the appendix).
  6. pointers    -- config keys resolve (brace-shorthand expansion), README
                    `logged` items resolve, covered-elsewhere targets are owned,
                    and the anchor_derivation product reproduces the config
                    anchor (round-to-nearest-50, abs tolerance 25).
  7. citation    -- grep specs/ + README for `value [id]`; the adjacent numeric
                    must match the registry. Point-in-time sections carry no ids
                    (invisible by design); unconverted live text is invisible too
                    (stated, not claimed).

spec-pending dispositions are counted WARNINGS, not failures.

House rules: encoding="utf-8" on every open(); ROOT is the parent of this
file's dir, so a scratch COPY of the repo checks itself (negative tests).
"""
import hashlib, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "outputs")
CONFIG = os.path.join(ROOT, "config")
SPECS = os.path.join(ROOT, "specs")
README = os.path.join(ROOT, "README.md")

# import THIS root's registry (scratch copies check themselves)
sys.path.insert(0, HERE)
import assumptions as A                                    # noqa: E402
from assumptions import ASSUMPTIONS                        # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# closed enums (spec 08 §2)
# ---------------------------------------------------------------------------
NO_ROW_EXACT = {"definitional", "quality-knob"}
NO_ROW_PREFIX = ("covered-elsewhere:", "width-block:", "spec-pending:",
                 "non-binding:")
OWNED_TIERS = ("prior", "constant")
BASES = {"measured", "locally-calibrated", "literature", "judgment",
         "definitional"}

MATERIAL_PCT = 2.0            # §5 materiality threshold
ANCHOR_TOL = 25.0            # §6 round-to-nearest-50 tolerance (half of 50)

# ---------------------------------------------------------------------------
# wrapper artifact (the cross-repo welfare-BCA result, spec 06 W1 / spec 08 §5
# check 2). Existence-gated on a configurable sibling path (default: the
# transit-benefit-cost sibling checkout); override with BCA_WRAPPER_ARTIFACT
# so a negative test can point the scan at a scratch copy. When the file is
# absent the wrapper claims degrade to check-2 'pending' warnings, exactly like
# any other absent artifact.
WRAPPER_ARTIFACT = os.environ.get(
    "BCA_WRAPPER_ARTIFACT",
    os.path.join(ROOT, "..", "transit-benefit-cost", "outputs", "bca_harbor.json"))

# check-3 (no-orphans) SCOPING for the wrapper artifact (spec 08 §5/§9 Q7, the
# W1 amendment): the wrapper is scanned for oc-CLAIMED ids only; the engine-
# owned tornado ids -- the ~40 rows that live in the transit-benefit-cost
# RANGES, not this registry (VOT, gamma, lambda, discount, externality/O&M/SCC/
# carbon/rebound/ramp/build/growth/mohring/labor/crowding/avg-fare/traction/
# nonwork/no-ASC/transfer-fullOD/peak-share) -- are EXEMPT from the orphan
# check and covered by G-E7 on the TBCR side. Listed here by reference to the
# tbc `tornado_row_ids` (bca-pipeline.mjs, spec 2026-07-14 §10) as of aa16e0d.
# A wrapper id that is NEITHER engine-owned NOR registry-claimed is a real
# orphan (a new oc-owned row nobody harvested -- fail loudly); a renamed
# oc-claimed id fails check-2 (coverage) as well.
ENGINE_OWNED_WRAPPER = frozenset({
    "vot_lo", "vot_hi", "nonwork_07", "gamma_015", "gamma_025", "gamma_asc",
    "lambda_13", "scc_0", "scc_190", "carbon_growth_2", "gco2_lo", "gco2_hi",
    "no_asc_cs", "labor_05", "disc_2", "disc_3", "disc_7", "disc_declining",
    "ramp_start_1", "ramp_start_lo", "ramp_years_lo", "ramp_years_hi",
    "build_years_4", "build_years_7", "om_lo", "om_hi", "traction_0",
    "rebound_05", "rebound_08", "ext_cong_lo", "ext_cong_hi", "ext_acc_lo",
    "ext_acc_hi", "ext_local_lo", "ext_local_hi", "transfer_fullod",
    "mohring_009", "growth_1", "avg_fare_lo", "avg_fare_hi", "crowding_haircut",
    "peak_hour_share_lo", "peak_hour_share_hi",
    # pre-registered: un-blocked by the W1R um_roh_*/fare_receipts_* streams;
    # engine-side re-pricings of oc streams (no_asc_cs precedent)
    "roh", "fare_sweep",
})

# spec 07 §9 N4: the network-sequence primary artifact (the greedy portfolio
# harness output). Existence-gated on the committed outputs path; absent ->
# check-2 'pending' warnings, exactly like the wrapper. Its assumptions_manifest
# declares the registry leaves capcost + the harness CONSUME (claimed by the
# 07§9-N4 registry entries); its sensitivity-block ids are HARNESS-INTERNAL G7
# rows -- engine-owned in the spec 08 §9 Q7 sense, so they are EXEMPT from the
# orphan check (a network id that is neither harness-internal nor registry-claimed
# is still a real orphan). This mirrors the wrapper scan precedent + the Q7
# tie-break exactly (claimed ids only; engine-owned exemption list).
NETWORK_ARTIFACT = os.environ.get(
    "NETWORK_SEQUENCE_ARTIFACT",
    os.path.join(OUT, "network_sequence.json"))

ENGINE_OWNED_NETWORK = frozenset({
    # computed_n1b G7 knob-sensitivity rows (the harness's own §10 G7 block)
    "cycle_gap_lo", "cycle_gap_hi", "budget_lo", "budget_hi",
    "omega_0.5", "omega_1.5", "omega_uniform", "omega_walk_bin_mass",
    "exclusive_tract", "depth_cap_1", "depth_cap_3", "offpeak_to_midday",
    "sigma_struct", "fixed_cost_share_0.5", "fixed_cost_share_0.0",
    # named spec-pending (N5 / optional) rows
    "k3_order_diff", "ratio_greedy_order", "premium_bracket",
    # spec 07 N5 NPV-objective sensitivity block (landed_n5 + named_spec_pending):
    # the same harness-internal G7 rows under the NPV objective (spec 08 §9 Q7).
    "cost_band_LOW_US_TYPICAL", "cycle_gap_lo_hi", "sigma_struct_std",
})

# spec 01 §5b (S2): the stage-1 DRM screen artifact. The scan reads the
# `sensitivity` block ONLY -- never the ~612 per-window result rows -- and
# extends checks 2/3/5 to screen-claiming registry entries. STAGE-1
# MATERIALITY CONVENTION (spec 01 §4): each sensitivity row's pct =
# 100 * (1 - Spearman rho of the full window ranking vs headline), i.e. rank
# churn, because an ordinal screen has no ridership headline to move; check 5
# consumes that pct unchanged against the same MATERIAL_PCT threshold. There
# is NO engine-owned exemption set for the screen: it has no engine, every
# screen sensitivity id is oc-registry-owned (spec 01 §5b -- the spec 08 §9
# Q7 tie-break does not apply, unlike wrapper/network), so any unclaimed
# present id is a real check-3 orphan. Absent file -> the screen claims
# degrade to check-2 'pending' warnings (spec-pending semantics), exactly
# like any other not-yet-generated artifact (S34 generates it).
SCREEN_ARTIFACT = os.environ.get(
    "SCREEN_RESULTS_ARTIFACT",
    os.path.join(OUT, "screen_results.json"))


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# artifacts (present rows + a (artifact,row-id)->pct map)
# ---------------------------------------------------------------------------
def load_artifacts():
    """Present rows per artifact + a pct map. Missing files -> artifact absent
    (its claims become check-2 'pending' warnings, per §5 wrapper-pending)."""
    present, pct, arts = {}, {}, {}
    rh = os.path.join(OUT, "results_harbor.json")
    rs = os.path.join(OUT, "results_streetcar.json")
    ab = os.path.join(OUT, "abc_harbor.json")
    bt = os.path.join(OUT, "backtest_543.json")
    RH = _load(rh) if os.path.exists(rh) else None
    RS = _load(rs) if os.path.exists(rs) else None
    AB = _load(ab) if os.path.exists(ab) else None
    BT = _load(bt) if os.path.exists(bt) else None
    arts["harbor"], arts["streetcar"], arts["abc"], arts["backtest"] = \
        RH, RS, AB, BT

    if RH is not None:
        present["harbor"] = {r["id"] for r in RH["sensitivity"]}
        for r in RH["sensitivity"]:
            pct[("harbor", r["id"])] = r["pct"]
    if RS is not None:
        present["streetcar"] = {r["id"] for r in RS["sensitivity"]}
        for r in RS["sensitivity"]:
            pct[("streetcar", r["id"])] = r["pct"]
    if AB is not None:
        present["abc"] = {k for k, v in AB["kernels"].items()
                          if v.get("tag") != "central"}
    if BT is not None:
        present["backtest"] = {r["id"] for r in BT["sensitivity"]}
        for r in BT["sensitivity"]:
            pct[("backtest", r["id"])] = r["pct"]
    # spec 08 §4 width blocks -- keyed PER-CORRIDOR (spec 06 W1 fix): the earlier
    # single "width" artifact UNIONED harbor+streetcar, so a width row present in
    # one corridor but missing in the other was masked. Separate width_harbor /
    # width_streetcar artifacts scan each corridor's block independently.
    for corr, R in (("harbor", RH), ("streetcar", RS)):
        if R is not None:
            present[f"width_{corr}"] = {r["id"]
                                        for r in R.get("width_sensitivities", [])}
    # spec 06 W1 / spec 08 §5 check 2: the wrapper artifact (welfare-BCA result).
    # Its full flat `tornado_row_ids` list is the present set for coverage;
    # check-3 orphan-scopes it to oc-claimed ids (ENGINE_OWNED_WRAPPER exempt).
    if os.path.exists(WRAPPER_ARTIFACT):
        WR = _load(WRAPPER_ARTIFACT)
        arts["wrapper"] = WR
        present["wrapper"] = set(WR.get("tornado_row_ids", []))
    # spec 07 §9 N4 network-sequence artifact: present rows = the manifest ids
    # the registry claims UNION the sensitivity-block ids (orphan-scoped to
    # ENGINE_OWNED_NETWORK below). Absent -> its claims become check-2 pending.
    if os.path.exists(NETWORK_ARTIFACT):
        NW = _load(NETWORK_ARTIFACT)
        arts["network"] = NW
        ids = {c["id"] for c in NW.get("assumptions_manifest", {}).get("consumed", [])}
        sens = NW.get("sensitivity") or {}
        # interim objective: computed_n1b + named_spec_pending; NPV objective
        # (spec 07 N5): landed_n5 + named_spec_pending. Scan all three groups.
        for grp in ("computed_n1b", "named_spec_pending", "landed_n5"):
            ids |= {r["id"] for r in sens.get(grp, [])}
        present["network"] = ids
    # spec 01 §5b (S2): the stage-1 screen artifact -- `sensitivity` block
    # ONLY (never the per-window rows); pct is the stage-1 rank-churn
    # convention, 100 * (1 - Spearman rho) -- see the SCREEN_ARTIFACT note.
    # No engine-owned exemption set: every screen id is oc-registry-owned.
    if os.path.exists(SCREEN_ARTIFACT):
        SC = _load(SCREEN_ARTIFACT)
        arts["screen"] = SC
        present["screen"] = {r["id"] for r in SC.get("sensitivity", [])}
        for r in SC.get("sensitivity", []):
            pct[("screen", r["id"])] = r["pct"]
    return present, pct, arts


def headline_band(results):
    """P90 - P10 of the headline uncapped blend (denominator for width %)."""
    b = results["summary"]["uncapped"]["blend"]
    return b[2] - b[0]


def claimed_rows(aid, e):
    """Expand an entry's row claims to a list of (artifact, row-id).
    Priors' 'auto' -> {id}_lo/{id}_hi in BOTH corridor results; `extras`
    (per-artifact) merge in on top."""
    out = []
    rows = e.get("rows")
    if rows == "auto":
        for art in ("harbor", "streetcar"):
            out.append((art, f"{aid}_lo"))
            out.append((art, f"{aid}_hi"))
    elif isinstance(rows, dict):
        for art, ids in rows.items():
            for rid in ids:
                out.append((art, rid))
    extras = e.get("extras")
    if isinstance(extras, dict):
        for art, ids in extras.items():
            for rid in ids:
                out.append((art, rid))
    return out


def owns_rows(e):
    rows = e.get("rows")
    if rows == "auto":
        return True
    if isinstance(rows, dict) and any(rows.values()):
        return True
    return bool(e.get("extras"))


def all_owned_rowids():
    """Every row-id claimed by any entry, in any artifact (for covered-elsewhere
    target resolution -- 'exists and is owned')."""
    s = set()
    for aid, e in ASSUMPTIONS.items():
        for _, rid in claimed_rows(aid, e):
            s.add(rid)
    return s


# ---------------------------------------------------------------------------
# effect (shared by materiality + appendix)
# ---------------------------------------------------------------------------
def entry_effect(aid, e, pct, arts):
    """max |effect| for a non-prior entry, or None if it owns no measurable
    rows (ABC-kernel rows carry no corridor %). Width owners: max |band_delta|
    as a share of the headline band."""
    claims = claimed_rows(aid, e)
    # width owners now claim per-corridor (width_harbor / width_streetcar,
    # spec 06 W1): the band-delta effect is that corridor's width row over that
    # corridor's headline band.
    width_claims = {corr: [rid for art, rid in claims if art == f"width_{corr}"]
                    for corr in ("harbor", "streetcar")}
    if any(width_claims.values()):
        best = None
        for corr in ("harbor", "streetcar"):
            ids = width_claims[corr]
            R = arts.get(corr)
            if R is None or not ids:
                continue
            hb = headline_band(R)
            for w in R.get("width_sensitivities", []):
                if w["id"] in ids:
                    v = abs(w["band_delta"]) / hb * 100.0
                    best = v if best is None else max(best, v)
        return best
    effs = [abs(pct[(art, rid)]) for art, rid in claims if (art, rid) in pct]
    return max(effs) if effs else None


def n_point_rows(aid, e, pct):
    return sum(1 for art, rid in claimed_rows(aid, e) if (art, rid) in pct)


# ===========================================================================
# CHECK 1 -- schema
# ===========================================================================
def check_schema():
    fails, warns = [], []
    for aid, e in ASSUMPTIONS.items():
        tier = e.get("tier")
        # required-everywhere fields
        for f in ("title", "tier", "status", "basis", "history"):
            if not e.get(f):
                fails.append(f"{aid}: missing/empty required field '{f}'")
        if e.get("basis") not in BASES:
            fails.append(f"{aid}: basis {e.get('basis')!r} not in the closed set")
        # history dated + non-empty
        hist = e.get("history")
        if not isinstance(hist, list) or not hist:
            fails.append(f"{aid}: history must be a non-empty list")
        else:
            d0 = hist[-1][0] if isinstance(hist[-1], (list, tuple)) else None
            if not (isinstance(d0, str) and re.match(r"^\d{4}-\d{2}-\d{2}$", d0)):
                fails.append(f"{aid}: history entries need an ISO date first")
        # owned tiers carry a value
        if tier in OWNED_TIERS and "value" not in e:
            fails.append(f"{aid}: {tier}-tier entry missing 'value'")
        # config tier points somewhere
        if tier == "config" and not e.get("config_key"):
            fails.append(f"{aid}: config-tier entry missing 'config_key'")
        # rows non-empty OR closed-enum disposition + non-null accepted
        if not owns_rows(e):
            nr = e.get("no_row_reason")
            ok = nr in NO_ROW_EXACT or (isinstance(nr, str)
                                        and nr.startswith(NO_ROW_PREFIX))
            if not ok:
                fails.append(f"{aid}: rowless but no_row_reason {nr!r} "
                             "not in the closed enum")
            elif e.get("accepted") in (None, False):
                fails.append(f"{aid}: rowless/dispositioned but 'accepted' "
                             "stamp is null")
            if isinstance(nr, str) and nr.startswith("spec-pending:"):
                warns.append(f"[check1] {aid}: {nr} (row pending a spec landing)")
        # band scoping (the ratified A2b clause -- see §9):
        # band REQUIRED for prior/constant EXCEPT basis in {definitional,
        # measured} (a chosen point with no propagated band) OR rowless-
        # dispositioned. Priors always carry a derived band.
        if tier in OWNED_TIERS and tier != "prior":
            # spec 07 §9 N4: a network-artifact MANIFEST claim is a consumed-value
            # DECLARATION (the harness records that it consumed this leaf), not a
            # swept lo/hi band-edge tornado row -- so it does not require a band to
            # source edges (a categorical knob like omega_allocation, or a fixed
            # markup like cap_markup_ut, has no numeric band). Entries whose owned
            # rows are all in the network artifact are exempt on that basis.
            claims = claimed_rows(aid, e)
            network_only = bool(claims) and all(a == "network" for a, _ in claims)
            exempt = (e.get("basis") in ("definitional", "measured")
                      or not owns_rows(e) or network_only)
            if not exempt and A.band(aid) is None:
                fails.append(f"{aid}: {e['basis']}-basis constant owns rows "
                             "but has band=None (needs a band to source edges)")
    return fails, warns


# ===========================================================================
# CHECK 2 -- coverage (every claimed row exists in its artifact)
# ===========================================================================
def check_coverage(present, arts):
    fails, warns = [], []
    n = 0
    for aid, e in ASSUMPTIONS.items():
        for art, rid in claimed_rows(aid, e):
            n += 1
            if art not in present:
                # artifact file absent -> pending, not a failure (§5)
                warns.append(f"[check2] {aid}: artifact '{art}' absent -- "
                             f"row '{rid}' pending")
                continue
            if rid not in present[art]:
                fails.append(f"{aid}: claims {art}:{rid} but it is not present "
                             f"in the {art} artifact")
    return fails, warns, n


# ===========================================================================
# CHECK 3 -- no orphans (every present row claimed by exactly one entry)
# ===========================================================================
def check_orphans(present):
    fails, warns = [], []
    owner = {}          # (artifact, row-id) -> [entry-ids]
    for aid, e in ASSUMPTIONS.items():
        for art, rid in claimed_rows(aid, e):
            owner.setdefault((art, rid), []).append(aid)
    # double-claims
    for key, owners in owner.items():
        if len(owners) > 1:
            fails.append(f"row {key[0]}:{key[1]} double-claimed by "
                         f"{', '.join(owners)}")
    # orphans
    n = 0
    for art, ids in present.items():
        for rid in ids:
            # spec 08 §9 Q7 (W1): the wrapper artifact is scanned for oc-claimed
            # ids ONLY -- engine-owned tornado rows live in the TBCR RANGES, not
            # this registry, so they are exempt from the orphan check (covered by
            # G-E7 there). A wrapper id that is neither engine-owned nor claimed
            # is still a real orphan (an oc row nobody harvested).
            if art == "wrapper" and rid in ENGINE_OWNED_WRAPPER:
                continue
            # spec 07 §9 N4: network sensitivity-block ids are harness-internal
            # (engine-owned in the Q7 sense) -> exempt; the manifest ids the
            # registry claims are NOT exempt (they must be owned).
            if art == "network" and rid in ENGINE_OWNED_NETWORK:
                continue
            n += 1
            if (art, rid) not in owner:
                if art == "wrapper":
                    fails.append(f"orphan row wrapper:{rid} -- unclassified "
                                 "wrapper tornado row (neither ENGINE_OWNED_WRAPPER "
                                 "nor claimed by a registry entry); classify it "
                                 "engine-owned or add an oc claim (spec 08 §9 Q7)")
                elif art == "network":
                    fails.append(f"orphan row network:{rid} -- unclassified "
                                 "network-artifact row (neither ENGINE_OWNED_NETWORK "
                                 "nor claimed by a registry entry); classify it "
                                 "harness-internal or add a registry claim "
                                 "(spec 07 §9 N4 / spec 08 §9 Q7)")
                else:
                    fails.append(f"orphan row {art}:{rid} -- present but claimed "
                                 "by no entry (rule-2 evasion by omission)")
    return fails, warns, n


# ===========================================================================
# CHECK 4 -- prior integrity (sentinel + count + fingerprint)
# ===========================================================================
def _read_test_constants():
    """Single source: N_PRIORS + PRIOR_ORDER_FINGERPRINT from test_bca_export.py."""
    p = os.path.join(HERE, "test_bca_export.py")
    with open(p, encoding="utf-8") as f:
        txt = f.read()
    m_n = re.search(r"^N_PRIORS\s*=\s*(\d+)", txt, re.M)
    m_fp = re.search(r'PRIOR_ORDER_FINGERPRINT\s*=\s*\\?\s*"([0-9a-f]{64})"', txt)
    return (int(m_n.group(1)) if m_n else None,
            m_fp.group(1) if m_fp else None)


def check_prior_integrity():
    fails, warns = [], []
    info = ""
    n_priors, fp_pinned = _read_test_constants()
    if n_priors is None or fp_pinned is None:
        fails.append("could not read N_PRIORS / PRIOR_ORDER_FINGERPRINT from "
                     "test_bca_export.py")
        return fails, warns, info
    try:
        import model
    except Exception as exc:                                # pragma: no cover
        fails.append(f"cannot import model to inspect PRIORS: {exc!r}")
        return fails, warns, info
    PR = model.PRIORS
    if getattr(PR, "generated_by", None) != "assumptions.build_priors":
        fails.append("model.PRIORS is not the build_priors() sentinel "
                     "(generated_by missing)")
    if len(PR) != n_priors:
        fails.append(f"len(PRIORS)={len(PR)} != N_PRIORS={n_priors}")
    fp = hashlib.sha256("|".join(PR.keys()).encode("utf-8")).hexdigest()
    if fp != fp_pinned:
        fails.append(f"prior-order fingerprint {fp[:12]}... != pinned "
                     f"{fp_pinned[:12]}... (a reorder shifts the rng stream)")
    info = f"{len(PR)} priors, fp {fp[:12]}..., sentinel OK"
    return fails, warns, info


# ===========================================================================
# CHECK 5 -- materiality (tier-scoped)
# ===========================================================================
def check_materiality(pct, arts):
    fails, warns = [], []
    n_material = 0
    for aid, e in ASSUMPTIONS.items():
        tier = e.get("tier")
        if tier == "prior":
            continue                          # exempt (already propagated)
        if tier == "structural":
            # satisfied when every enumerated alternative has a row
            if not owns_rows(e):
                fails.append(f"{aid}: structural toggle with no alternative row")
            continue
        if tier not in ("constant", "config", "data"):
            continue
        eff = entry_effect(aid, e, pct, arts)
        if eff is None:
            continue
        if eff >= MATERIAL_PCT and e.get("basis") in ("literature", "judgment") \
                and A.band(aid) is not None:
            n_material += 1
            if n_point_rows(aid, e, pct) < 2:
                fails.append(f"{aid}: material ({eff:.1f}%) {e['basis']} band "
                             "but only one edge is a row (need both edges)")
    return fails, warns, n_material


# ===========================================================================
# CHECK 6 -- pointers (config keys, logged items, covered-elsewhere, anchor)
# ===========================================================================
def _expand_braces(path):
    """config/{harbor,streetcar}.json -> [config/harbor.json, config/streetcar.json]."""
    m = re.search(r"\{([^}]*)\}", path)
    if not m:
        return [path]
    return [path[:m.start()] + opt + path[m.end():]
            for opt in m.group(1).split(",")]


def _resolve_dotted(obj, dotted):
    cur = obj
    for part in dotted.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return False
    return True


def _check_config_key(aid, config_key, fails):
    # "config/harbor.json: anchor_low / anchor_high" -> path + keys
    parts = config_key.split(":", 1)
    path_part = parts[0].strip()
    key_part = parts[1].strip() if len(parts) > 1 else ""
    for path in _expand_braces(path_part):
        full = os.path.join(ROOT, path.replace("/", os.sep))
        if not os.path.exists(full):
            fails.append(f"{aid}: config_key path '{path}' does not exist")
            continue
        obj = _load(full)
        if not key_part:
            continue
        # strip parenthetical annotations, split on '/', resolve each plain token
        cleaned = re.sub(r"\([^)]*\)", " ", key_part)
        for tok in cleaned.split("/"):
            tok = tok.strip()
            if not tok or not re.match(r"^[A-Za-z0-9_]+(\.[A-Za-z0-9_]+)*$", tok):
                continue
            if not _resolve_dotted(obj, tok):
                fails.append(f"{aid}: config_key '{tok}' unresolved in {path}")


# measured weekday route boardings feeding the anchor derivation. These are
# DATA inputs (scripts/anchor_from_apc.py FY2019 totals / weekday-equivalents;
# scripts/anchor_streetcar.py FY2019 shape-share composite). This cross-check
# validates the DERIVATION bands (trend / corr_share / uniformity, now the
# config anchor_derivation structured keys the registry owns) against the
# committed anchor_low/high -- not the raw boardings.
_FY2019_43 = 2_095_510                       # anchor_from_apc.py FY2019 Route 43
_WD543 = 953_471 / 255                       # 543 wkdy-only annual / 255
_STREETCAR_BASE = 5034.0                     # anchor_streetcar.py FY2019 composite


def _anchor_crosscheck(fails, info):
    eq = A.val("eq_days")                     # (300, 330) -- weekday-equiv days
    wd43_lo, wd43_hi = _FY2019_43 / eq[1], _FY2019_43 / eq[0]
    checks = []
    hp = os.path.join(CONFIG, "harbor.json")
    if os.path.exists(hp):
        h = _load(hp)
        d = h.get("anchor_derivation", {})
        tr, sh = d.get("trend"), d.get("corr_share")
        if tr and sh:
            lo = _WD543 * tr[0] + wd43_lo * tr[0] * sh[0]
            hi = _WD543 * tr[1] + wd43_hi * tr[1] * sh[1]
            checks += [("harbor-lo", lo, h["anchor_low"]),
                       ("harbor-hi", hi, h["anchor_high"])]
    sp = os.path.join(CONFIG, "streetcar.json")
    if os.path.exists(sp):
        s = _load(sp)
        d = s.get("anchor_derivation", {})
        un, tr = d.get("uniformity"), d.get("trend")
        if un and tr:
            lo = _STREETCAR_BASE * un[0] * tr[0]
            hi = _STREETCAR_BASE * un[1] * tr[1]
            checks += [("streetcar-lo", lo, s["anchor_low"]),
                       ("streetcar-hi", hi, s["anchor_high"])]
    worst = 0.0
    for name, comp, cfg in checks:
        delta = abs(comp - cfg)
        worst = max(worst, delta)
        if delta > ANCHOR_TOL:
            fails.append(f"anchor {name}: derivation {comp:,.1f} vs config "
                         f"{cfg} differ by {delta:.1f} > {ANCHOR_TOL} "
                         "(not within rounding-to-50)")
    info.append(f"anchor xcheck {len(checks)} edges, worst dev {worst:.1f}")


def _readme_issue_numbers():
    nums = set()
    if os.path.exists(README):
        with open(README, encoding="utf-8") as f:
            for line in f:
                m = re.match(r"^(\d+)\.\s", line)
                if m:
                    nums.add(int(m.group(1)))
    return nums


def check_pointers():
    fails, warns, info = [], [], []
    owned = all_owned_rowids()
    issue_nums = _readme_issue_numbers()
    n_cfg = n_logged = n_covered = 0
    for aid, e in ASSUMPTIONS.items():
        if e.get("tier") == "config":
            n_cfg += 1
            _check_config_key(aid, e["config_key"], fails)
        logged = e.get("logged")
        if isinstance(logged, str):
            m = re.search(r"known-issue\s+(\d+)", logged)
            if m:
                n_logged += 1
                if int(m.group(1)) not in issue_nums:
                    fails.append(f"{aid}: logged '{logged}' -- README has no "
                                 f"issue {m.group(1)}")
        nr = e.get("no_row_reason")
        if isinstance(nr, str) and nr.startswith("covered-elsewhere:"):
            n_covered += 1
            tgt = nr.split(":", 1)[1]
            if tgt not in owned:
                fails.append(f"{aid}: covered-elsewhere:{tgt} -- target row is "
                             "not owned by any entry")
    _anchor_crosscheck(fails, info)
    info.insert(0, f"{n_cfg} config keys, {n_logged} logged items, "
                   f"{n_covered} covered-elsewhere")
    return fails, warns, "; ".join(info)


# ===========================================================================
# CHECK 7 -- citation sync
# ===========================================================================
_CITE = re.compile(r"(?<![\w.])(-?\d[\d,]*\.?\d*)\s*\[([a-z0-9_]+)\]")


def _citable_numbers(e):
    nums = set()

    def add(x):
        if isinstance(x, bool):
            return
        if isinstance(x, (int, float)):
            nums.add(float(x))
        elif isinstance(x, (tuple, list)):
            for y in x:
                add(y)
    add(e.get("value"))
    add(e.get("band"))
    return nums


def check_citations():
    fails, warns = [], []
    n_cited, n_files = 0, 0
    files = [README] if os.path.exists(README) else []
    if os.path.isdir(SPECS):
        files += [os.path.join(SPECS, f) for f in sorted(os.listdir(SPECS))
                  if f.endswith(".md")]
    for path in files:
        with open(path, encoding="utf-8") as f:
            txt = f.read()
        hit = False
        for m in _CITE.finditer(txt):
            num_s, cid = m.group(1), m.group(2)
            if cid not in ASSUMPTIONS:
                continue                       # not a registry citation
            hit = True
            n_cited += 1
            cited = float(num_s.replace(",", ""))
            cands = _citable_numbers(ASSUMPTIONS[cid])
            if not any(abs(cited - c) <= abs(c) * 1e-9 + 1e-9 for c in cands):
                fails.append(f"{os.path.basename(path)}: '{num_s} [{cid}]' does "
                             f"not match registry {sorted(cands)}")
        if hit:
            n_files += 1
    info = (f"{n_cited} citations across {n_files} files; unconverted live "
            "text and point-in-time (dated, id-less) sections are invisible")
    return fails, warns, info


# ===========================================================================
# driver
# ===========================================================================
def run_checks():
    present, pct, arts = load_artifacts()
    results = []
    f, w = check_schema()
    results.append(("1", "schema", f, w, f"{len(ASSUMPTIONS)} entries"))
    f, w, n = check_coverage(present, arts)
    results.append(("2", "coverage", f, w, f"{n} claimed rows"))
    f, w, n = check_orphans(present)
    results.append(("3", "no orphans", f, w, f"{n} present rows"))
    f, w, info = check_prior_integrity()
    results.append(("4", "prior integrity", f, w, info))
    f, w, n = check_materiality(pct, arts)
    results.append(("5", "materiality", f, w,
                    f"{n} material lit/judgment band-owner(s)"))
    f, w, info = check_pointers()
    results.append(("6", "pointers", f, w, info))
    f, w, info = check_citations()
    results.append(("7", "citation sync", f, w, info))
    return results


def print_report(results):
    print(f"check_assumptions.py -- spec 08 registry enforcement "
          f"({len(ASSUMPTIONS)} entries)\n")
    all_fails, all_warns = [], []
    for num, name, fails, warns, info in results:
        label = f"[{num}] {name}".ljust(26, ".")
        status = "FAIL" if fails else "PASS"
        print(f"{label} {status}  ({info})")
        for msg in fails:
            print(f"       FAIL: {msg}")
        all_fails += [(num, m) for m in fails]
        all_warns += warns
    if all_warns:
        print(f"\nWARNINGS ({len(all_warns)}, counted -- not failures):")
        for m in all_warns:
            print(f"  {m}")
    n = len(all_fails)
    print(f"\nRESULT: {'RED' if n else 'GREEN'} "
          f"({n} failure{'s' if n != 1 else ''}, {len(all_warns)} warnings)")
    return n


# ===========================================================================
# APPENDIX (spec 08 §6)
# ===========================================================================
SCHEMA_VERSION = "08-A3.3"   # W1 rider 2: + machine `values` section


def values_section():
    """Machine-readable value block (schema 08-A3.3, spec 06 W1 rider 2): the
    scalars the transit-benefit-cost wrapper resolves from this artifact instead
    of hardcoding (G-E5) -- eq_days, default_fare, the ABC kernel labels with an
    explicit `central` flag (from reweight_abc, the single source), and
    (lo, hi, shape) for the five wrapper-re-priced priors (behavioral VOT + the
    pcar diversion set, spec 06 D3/D7). Imported lazily so plain `check` runs
    (and scratch-copy negative tests) never pull in numpy/model."""
    from reweight_abc import get_kernels, central_label
    repriced = ("vot_behav", "pcar0", "pcar1", "pcar2", "pcarv")
    return {
        "eq_days": A.val("eq_days"),
        "default_fare": A.val("default_fare"),
        "kernels": {"labels": [lbl for lbl, _, _ in get_kernels()],
                    "central": central_label()},
        "wrapper_repriced_priors": {k: list(A.val(k)) for k in repriced},
    }


def _esc(s):
    return str(s).replace("|", "\\|")


def _fmt_pct(x):
    if x is None:
        return "--"
    v = round(x, 1)
    if v == 0:
        v = 0.0                                # normalize -0.0
    return f"{v:.1f}%"


def _sort_key(item):
    # primary: |effect| desc (None last); secondary: id asc. item[0] is the
    # effect and item[1] the id for both 2-tuples (exposures) and 3-tuples
    # (priors, which carry a trailing extras-effect) -- extra elements are
    # ignored by the key.
    eff, aid = item[0], item[1]
    return (-(eff if eff is not None else -1.0), aid)


# priors' "tornado" column claims to be "already propagated into the
# headline band" (spec 08 §5/§9 Q3) -- true only of the AUTO lo/hi edge rows
# (the literal swept prior support). A prior's `extras` (e.g. asc's untrimmed
# 0.55 probe, OUTSIDE the trimmed 0-0.40 support) are NOT part of that
# propagated band, so they are reported SEPARATELY, never folded into the
# max. BOTH are restricted to the corridor artifacts -- `extras` may also
# claim a `backtest` row (asc's bt_asc0, an unrelated no-Bravo-branding
# probe), which is not a corridor edge and must not dominate either figure
# (spec 08 A3 fix: this bug is what let asc's tornado read a bogus 54.0%,
# bt_asc0's own pct, instead of a real corridor number).
CORRIDOR_ARTIFACTS = ("harbor", "streetcar")


def _prior_effects(aid, e, pct):
    auto_ids = {f"{aid}_lo", f"{aid}_hi"}
    auto_effs, extra_effs = [], []
    for art, rid in claimed_rows(aid, e):
        if art not in CORRIDOR_ARTIFACTS or (art, rid) not in pct:
            continue
        (auto_effs if rid in auto_ids else extra_effs).append(abs(pct[(art, rid)]))
    tornado = max(auto_effs) if auto_effs else None
    extras_pct = max(extra_effs) if extra_effs else None
    return tornado, extras_pct


def build_appendix():
    present, pct, arts = load_artifacts()
    entries = ASSUMPTIONS

    # ---- section data ----
    exposures = []          # (effect, aid) for constant/config/data/structural
    priors = []             # (tornado, aid, extras_pct)
    for aid, e in entries.items():
        tier = e["tier"]
        if tier == "prior":
            tornado, extras_pct = _prior_effects(aid, e, pct)
            priors.append((tornado, aid, extras_pct))
        elif tier in ("constant", "config", "data", "structural"):
            if owns_rows(e):
                exposures.append((entry_effect(aid, e, pct, arts), aid))
    exposures.sort(key=_sort_key)
    priors.sort(key=_sort_key)

    width_rows = []
    for corr in ("harbor", "streetcar"):
        R = arts.get(corr)
        if R is None:
            continue
        hb = headline_band(R)
        for wsrow in R.get("width_sensitivities", []):
            width_rows.append({
                "corridor": corr, "id": wsrow["id"], "label": wsrow["label"],
                "band": wsrow["band"], "band_delta": wsrow["band_delta"],
                "pct_of_headline_band": round(wsrow["band_delta"] / hb * 100, 2),
            })

    dispositions = []
    for aid, e in entries.items():
        if not owns_rows(e):
            dispositions.append({
                "id": aid, "tier": e["tier"], "basis": e["basis"],
                "no_row_reason": e.get("no_row_reason"),
                "accepted": list(e["accepted"]) if e.get("accepted") else None,
            })
    dispositions.sort(key=lambda d: d["id"])

    basis_census, tier_census = {}, {}
    for e in entries.values():
        basis_census[e["basis"]] = basis_census.get(e["basis"], 0) + 1
        tier_census[e["tier"]] = tier_census.get(e["tier"], 0) + 1

    changed = []            # entries whose history records a transition
    for aid, e in entries.items():
        if isinstance(e.get("history"), list) and len(e["history"]) > 1:
            changed.append({"id": aid, "history": [list(h) for h in e["history"]]})
    changed.sort(key=lambda c: c["id"])

    warnings = []
    for aid, e in entries.items():
        nr = e.get("no_row_reason")
        if isinstance(nr, str) and nr.startswith("spec-pending:"):
            warnings.append({"id": aid, "no_row_reason": nr})
    warnings.sort(key=lambda x: x["id"])

    return dict(present=present, pct=pct, arts=arts, exposures=exposures,
                priors=priors, width_rows=width_rows, dispositions=dispositions,
                basis_census=basis_census, tier_census=tier_census,
                changed=changed, warnings=warnings)


def write_appendix():
    d = build_appendix()
    entries = ASSUMPTIONS
    pct, arts = d["pct"], d["arts"]

    # ---------- markdown ----------
    L = []
    L.append("# Assumptions registry appendix (generated)")
    L.append("")
    L.append("Generated by `scripts/check_assumptions.py --appendix` from "
             "`scripts/assumptions.py` (spec 08 §6). Do not hand-edit -- rerun "
             "the generator. Effects are one-at-a-time deltas at central, fixed "
             "bins (the local-derivative caveat: interactions are invisible; "
             "band-width knobs move the band, not the central).")
    L.append("")
    L.append(f"- schema version: `{SCHEMA_VERSION}`")
    L.append(f"- entries: {len(entries)}  |  by tier: "
             + ", ".join(f"{k} {d['tier_census'][k]}"
                         for k in sorted(d["tier_census"])))
    L.append(f"- by basis: "
             + ", ".join(f"{k} {d['basis_census'][k]}"
                         for k in sorted(d["basis_census"])))
    L.append("")

    L.append("## 1. Unpropagated exposures (constant / config / data / structural)")
    L.append("")
    L.append("Sorted by measured one-at-a-time effect (|effect| desc, id asc). "
             "These are NOT in the headline band -- they are the audit's "
             "headline.")
    L.append("")
    L.append("UNITS CAVEAT: effects sourced from `screen:*` rows are stage-1 "
             "RANK-CHURN percentages (100 * (1 - Spearman rho) of the window "
             "ranking vs headline, spec 01 §4) -- not ridership-headline "
             "deltas; the two magnitudes are not comparable across rows.")
    L.append("")
    L.append("| effect | id | tier | basis | rows / note |")
    L.append("|---:|---|---|---|---|")
    for eff, aid in d["exposures"]:
        e = entries[aid]
        rowdesc = ", ".join(f"{a}:{r}" for a, r in claimed_rows(aid, e)) or "--"
        # eff is None when the entry owns only rows with no corridor pct (ABC
        # kernel rows, or wrapper tornado rows priced in the tbc artifact)
        note = rowdesc if eff is not None else f"off-corridor row ({rowdesc})"
        L.append(f"| {_fmt_pct(eff)} | {_esc(aid)} | {e['tier']} | "
                 f"{e['basis']} | {_esc(note)} |")
    L.append("")

    L.append("## 2. Priors (already propagated into the headline band)")
    L.append("")
    L.append("Reported SEPARATELY from the exposure sort (spec 08 §5): a prior's "
             "spread is already in the P10-P90 band. Below is each prior's "
             "one-at-a-time tornado contribution (max |lo/hi| over the "
             "CORRIDOR rows only -- harbor/streetcar, never `backtest` -- for "
             "reference only). A separate `extras` column reports any probe "
             "rows OUTSIDE the swept prior support (e.g. asc's untrimmed 0.55 "
             "probe): these are NOT part of the propagated band and are never "
             "folded into the tornado max (spec 08 A3 fix: the prior version "
             "of this table let asc's backtest-only `bt_asc0` probe, an "
             "unrelated no-Bravo-branding read, masquerade as its corridor "
             "tornado).")
    L.append("")
    L.append("| tornado | id | title | basis | extras (corridor-only probes) |")
    L.append("|---:|---|---|---|---:|")
    for eff, aid, extras_pct in d["priors"]:
        e = entries[aid]
        L.append(f"| {_fmt_pct(eff)} | {_esc(aid)} | {_esc(e['title'])} | "
                 f"{e['basis']} | {_fmt_pct(extras_pct)} |")
    L.append("")

    L.append("## 3. Width sensitivities (band-width, not central)")
    L.append("")
    L.append("| corridor | id | band | Δband | % of headline band |")
    L.append("|---|---|---:|---:|---:|")
    for w in d["width_rows"]:
        L.append(f"| {w['corridor']} | {_esc(w['id'])} | {w['band']:.1f} | "
                 f"{w['band_delta']:+.1f} | {w['pct_of_headline_band']:+.2f}% |")
    L.append("")

    L.append("## 4. Rowless dispositions (with accepted stamps)")
    L.append("")
    L.append("Every escape hatch in one place, for the owner to veto at review "
             "(spec 08 §9 Q1). `spec-pending` dispositions are counted WARNINGS "
             "in the check, not failures.")
    L.append("")
    L.append("| id | tier | basis | no_row_reason | accepted |")
    L.append("|---|---|---|---|---|")
    for r in d["dispositions"]:
        acc = f"{r['accepted'][0]} / {r['accepted'][1]}" if r["accepted"] else "--"
        L.append(f"| {_esc(r['id'])} | {r['tier']} | {r['basis']} | "
                 f"{_esc(r['no_row_reason'])} | {_esc(acc)} |")
    L.append("")

    L.append("## 5. Basis census + what changed")
    L.append("")
    for k in sorted(d["basis_census"]):
        L.append(f"- **{k}**: {d['basis_census'][k]}")
    L.append("")
    L.append("What changed (entries whose append-only history records a "
             "transition):")
    L.append("")
    if d["changed"]:
        for c in d["changed"]:
            L.append(f"- **{_esc(c['id'])}**")
            for h in c["history"]:
                L.append(f"    - {h[0]}: value `{_esc(h[1])}`, basis "
                         f"{_esc(h[2])} ({_esc(h[3])})")
    else:
        L.append("- (none)")
    L.append("")
    if d["warnings"]:
        L.append("Spec-pending warnings (counted, not failures):")
        L.append("")
        for wn in d["warnings"]:
            L.append(f"- {_esc(wn['id'])}: {_esc(wn['no_row_reason'])}")
        L.append("")

    md = "\n".join(L) + "\n"
    with open(os.path.join(OUT, "assumptions.md"), "w",
              encoding="utf-8", newline="\n") as f:
        f.write(md)

    # ---------- json (schema-versioned cross-repo artifact) ----------
    def eff_num(x):
        if x is None:
            return None
        v = round(x, 1)
        return 0.0 if v == 0 else v

    payload = {
        "schema_version": SCHEMA_VERSION,
        "n_entries": len(entries),
        "tier_census": d["tier_census"],
        "basis_census": d["basis_census"],
        "values": values_section(),
        "exposures": [
            {"id": aid, "tier": entries[aid]["tier"],
             "basis": entries[aid]["basis"], "effect_pct": eff_num(eff),
             "rows": [[a, r] for a, r in claimed_rows(aid, entries[aid])]}
            for eff, aid in d["exposures"]],
        "priors": [
            {"id": aid, "basis": entries[aid]["basis"],
             "tornado_pct": eff_num(eff), "extras_pct": eff_num(extras_pct)}
            for eff, aid, extras_pct in d["priors"]],
        "width_sensitivities": d["width_rows"],
        "dispositions": d["dispositions"],
        "what_changed": d["changed"],
        "spec_pending_warnings": d["warnings"],
    }
    txt = json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True)
    with open(os.path.join(OUT, "assumptions.json"), "w",
              encoding="utf-8", newline="\n") as f:
        f.write(txt + "\n")

    return md


# ===========================================================================
if __name__ == "__main__":
    do_appendix = "--appendix" in sys.argv[1:]
    results = run_checks()
    nfail = print_report(results)
    if do_appendix:
        write_appendix()
        print("\nwrote outputs/assumptions.md + outputs/assumptions.json")
    sys.exit(1 if nfail else 0)
