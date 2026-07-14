# Spec 08 — Assumptions registry: single-source values, enforced legibility

Status: **BUILT 2026-07-14** (A1 + A2a + A2b + A3 landed on branch
`spec08-assumptions`). Originally DRAFT 2026-07-11, revised same day after a
three-lens adversarial review (architecture, governance, code feasibility);
all blocking and major findings incorporated. Extends the spec 05 typing move
from DISPLAY-ONLY data to RULE-BEARING, code-feeding data — a deliberate
escalation, named as such: this is the repo's first data structure that code
imports values from.

> **Landed (A3, 2026-07-14; response to whole-branch review same day).**
> `scripts/assumptions.py` (90 entries: 19 prior + 45 constant + 12 config +
> 10 structural + 4 data — the data tier landed in the review response;
> see §2/§7) is the single source; `scripts/check_assumptions.py` runs the
> seven §5 checks and is a standing validation gate (green on the repo as
> landed: 0 failures, 6 spec-pending warnings counted — `lodes_2022` joins
> the original five once the data tier exists to carry it; 135 claimed rows
> == 135 present rows across harbor/streetcar/abc/backtest/width).
> `--appendix` regenerates the committed inventory
> `outputs/assumptions.{md,json}` (schema-versioned, byte-deterministic).
> The top unpropagated exposure is `streetcar_service_new` (±53.8%, the
> 1.5-mi stop-spacing design row); `asc` leads the priors' tornado at 25.7%
> (`asc_lo`, streetcar corridor-only, auto edge — already propagated into
> the band) — NOT the 54.0% originally reported here, which was `bt_asc0`'s
> own pct (an unrelated backtest no-Bravo-branding probe) leaking through
> the priors-section max; its untrimmed extra `asc_untrimmed` reaches
> further still (38.1%, harbor) but sits outside the trimmed 0–0.40 prior
> support, so it is reported separately and is NOT part of the propagated
> band (review finding; see §5 check 5 and the appendix §2 `extras` column).
> Negative tests (scratch, uncommitted) confirm checks 2, 3, 4 and 7 each
> fail on a deliberately broken copy.

> Problem statement, from observed failure modes: (1) INVENTORY OPACITY —
> no artifact enumerates the model's assumptions; auditing means reading
> PRIORS + constants across five scripts + configs + the README log + six
> specs. (2) CITATION DRIFT — values cited in N places drift at rate N (the
> post-R1 sweep touched four specs and still missed an instance).
> (3) GRANDFATHERED CONSTANTS — rule 2 is review-enforced for NEW knobs,
> but nothing enumerates old ones: WALK_MPH=3.0 has no row while jerk
> (0.17%) has three; the four Dirichlet jitter strengths are silently
> load-bearing. Each failure mode gets a MECHANICAL treatment below —
> where a claim cannot be mechanized, the spec says so instead of
> overclaiming (review finding: the draft promised more than its checks
> delivered).

## 1. Role / non-role

A first-class registry of every asserted quantity and structural choice in
the stage-2 pipeline: single-source values (code imports them), a dated
basis lifecycle, enforced row coverage keyed on stable ids, and a generated
appendix as the auditable inventory. Non-role: no model-behavior change
(A1 lands byte-identical); the README known-issues log remains the
NARRATIVE record of dilemmas (the registry is the INVENTORY; entries
cross-reference and the check script resolves the pointers both ways);
config-owned values stay in configs (the registry documents and points).

## 2. The registry (`scripts/assumptions.py`)

A dependency-free module (imports nothing from the pipeline; verified
acyclic — current graph is model ← backtest_543 ← reweight_abc ←
bca_export, and build_corridor imports no pipeline module). Authoring
format is Python (comments, tuples, exact literals); the CONSUMPTION
format is `outputs/assumptions.json` — committed, deterministic,
schema-versioned, emitted by the check script — which is the cross-repo
interface (the node wrapper reads JSON, not Python). Entry schema:

```python
"j_comfort": {
    "title": "service jerk limit (grade-separated kinematics)",
    "tier": "constant",   # prior | constant | config | structural | data
    "status": "active",   # active | superseded-kept-as-row | retired
    "value": 0.75, "units": "m/s^3",       # OWNED tiers (prior/constant) only
    "band": (0.5, 1.0),
    "basis": "literature",  # measured | locally-calibrated | literature | judgment | definitional
    "history": [("2026-07-11", 0.75, "literature", "spec02 s4.9b, 5e63eb2")],
                          # append-only dated (date, value, basis, ref) transitions;
                          # current state = last element; the basis census and
                          # "what changed" appendix section generate from this
    "provenance": "EN 13452-family passenger comfort band 0.5-1.0; REM-class service",
    "rows": {"harbor": ["jk_lo", "jk_hi", "jk_trapezoid"]},   # per-ARTIFACT row IDS
    "no_row_reason": None,   # closed enum + detail, required iff rows empty:
                             # definitional | covered-elsewhere:<row-id> |
                             # quality-knob | width-block:<block-id> |
                             # spec-pending:<spec §> | non-binding:<evidence-ref>
                             # (A2b: non-binding is a REAL judgment/behavioral
                             # assumption that provably never binds at central --
                             # the evidence-ref cites the empirical check; it is
                             # NOT "definitional" and must not be laundered as such)
    "accepted": None,        # (owner-ref, date) — REQUIRED non-null for every
                             # rowless or definitional entry (see §9 Q1)
    "logged": "README known-issue 25 addendum",
    "upgrade": "vehicle procurement spec / observed REM telemetry",
},
```

Tier semantics and ownership:

- **prior** — OWNED. `(lo, hi, shape)` + an `order` int. `model.PRIORS` is
  GENERATED (`build_priors()`), emitted sorted by order — verified able to
  reproduce the exact current 19-key sequence (bivt … pkshare, vot_behav,
  pcar0-2, pcarv, v_cruise, dwell). **The append-only guard is a committed
  FINGERPRINT, not a self-consistency assertion** (review: a consistent
  renumber passes any static check): the contract test pins the exact
  ordered (name, order) tuple hash — N_PRIORS-style — so ANY reorder fails
  against a reference that does not derive from the registry itself.
  Updating the fingerprint is the explicit, greppable act of appending.
  Stated honestly: the byte-identical regression gates remain the ultimate
  rng backstop; the fingerprint makes reorders fail FAST and NAMED.
  Prior rows are `"auto"` (the generated lo/hi rows) plus an explicit
  `extras` list for additional probe points (e.g. asc's untrimmed 0.55).
  Literal typing is load-bearing: values are copied as exact Python
  literals (floats stay floats — `70.0` not `70`), because auto row labels
  derive from float repr; the check script asserts regenerated labels
  match the results file.
- **constant** — OWNED. Module constants become imports
  (`WALK_MPH = val("walk_mph")`), local names kept so call sites don't
  churn. Constant band-edge rows are GENERATED from the registry the same
  way prior rows are (review: the draft hand-listed labels, recreating the
  three-place synchronization it claimed to kill); the prose gloss
  ("comfort floor") is display-only and ignored by the join.
- **config** — NOT owned; entry points at a structured config key. Two
  quantities the draft mishandled are PROMOTED to structured keys in A2:
  the FY2019→FY2024 trend band and the Route-43 corridor share currently
  live only inside `anchor_note` prose — they become
  `"anchor_derivation": {"trend": [0.90, 0.99], "corr_share": [0.75, 0.86]}`
  with `anchor_low/high` cross-checked against them (within rounding) by
  the check script. The corridor share becomes ONE entry cited by BOTH the
  forward anchor and the 2013 backtest derivations (it was silently the
  same assumption in two places). Config-echo cascade handled by the B4
  §4 verified-echo protocol.
- **structural** — NOT owned; names the toggle and its row-ids
  (variety_logsum, linear_wait, smooth_k, no_transfer, no_visitor,
  no_bin0, nonwork_short, exogenous_speed, blend convention, tie-break).
- **data** — NOT owned; vintages (LODES 2022, ACS 2023, GTFS 2026-07, NTD
  snapshot 2026-07) with row linkage or a disposition. The LODES-vintage
  entry carries `spec-pending:02§4.8` — reported as a WARNING in the
  appendix (visible, counted), not a green-gate failure, until §4.8 lands.

Derived values stay derived (registry holds leaves; MU_LAUNCH is computed
from UPT leaves in code). The 2013 backtest world — which straddled every
tier in the draft — is resolved by PROMOTION: A2 moves the hardcoded 2013
scenario out of `backtest_543.py` into `config/backtest_543.json`
(config-tier, pointer-resolvable, diffable), with the anchor band stored
as leaves (Route 43 total ≈13,000 × the shared corr_share entry) and
computed in code. The hardcoded prior-central dict in `backtest_543.py`
(a live citation-drift instance — it duplicates all 12 pre-D3 midpoints)
is REPLACED by `{k: (lo+hi)/2}` computed from PRIORS — same values, so it
lands inside A1's byte-identical gate.

Superseded values get their own entries with `status:
"superseded-kept-as-row"` (mu_matured 4,200 cross-linked to the mu-target
entry) — the inventory shows them without competing with active values.

## 3. Row identity (the join key)

Sensitivity rows gain a stable machine `id` alongside the display `label`
in `results_*.json` (A2 — which already changes those files; A1 touches
nothing). The registry claims row IDS per ARTIFACT:
`rows: {"harbor": [...], "streetcar": [...], "abc": [...], "backtest":
[...], "width": [...]}`. This resolves the draft's two join defects:
labels embedding float reprs were a fragile key, and cross-corridor label
collisions ("anchor -> low" means DIFFERENT assumptions in harbor vs
streetcar) made bare-label ownership unsatisfiable — harbor and streetcar
anchors are now separate entries claiming per-artifact ids; shared
behavioral priors claim their auto ids in all artifacts via one entry.
Design-exploration rows (headway/spacing/offset variants) are claimed by
the corridor's `service_new` config-tier entry — every row has exactly one
owner within its artifact.

## 4. Width sensitivities (a new block, for width assumptions)

Review finding (blocking): the Dirichlet strengths and the S0-jitter scale
govern band WIDTH, not the central — a `point()` row is vacuously 0.0%
because the sensitivity table pins `fix_bins` and those code paths sit
inside `if not fixed`. Mandating such rows would have shipped fake
coverage. New mechanism: a `width_sensitivities` block in
`results_<corridor>.json` — full-headline reruns (N draws, jitters ON)
under the variant, reporting P10/P50/P90 against the headline run:

    dirichlet_strength ×0.5 / ×2   (all FOUR sites jointly: ww 300, xw 300,
                                    vw 100, cf 400 — a deliberate, stated
                                    exception to one-at-a-time, because the
                                    four strengths encode one "how much do
                                    we trust the bin shapes" assumption)
    s0_se_scale ×0.5 / ×2          (the S0 lognormal jitter width)

Width variants consume the SAME draws (params=shared) so only the jitter
streams differ; expected: P50 ≈ unchanged, bands move. Build-time
assumptions get the REBUILT-VARIANT mechanism (the spec 02 §4.8 pattern):
`build_corridor.py` gains a parameter-override flag writing scratch
variant derived files (never committed) that width/point rows run against
— used now for the intra-tract distance rule variant, and later for the
§4.8 LODES-2019 row. `moe_z` is RECLASSIFIED definitional (Census
publishes 90% MOEs; /1.645 is the documented conversion — the draft's
{1.96} row tested a counterfactual misreading; review accepted).

## 5. The enforcement script (`scripts/check_assumptions.py`)

Exit nonzero on violation; checks:

1. **Schema**: required fields per tier; `rows` non-empty per artifact OR
   closed-enum `no_row_reason` + non-null `accepted`; bands required for
   prior/constant EXCEPT basis=definitional. Bands exist to SOURCE band-edge
   rows, so the requirement is scoped to entries that own such rows: a
   rowless-dispositioned entry, or a definitional-VALUE constant (a chosen
   point with no propagated band — unit conversions, clips, thresholds, grids,
   seeds, per the §2 schema), may carry `band=None` regardless of `basis`
   (A2a already ships judgment-basis grid/clip entries this way; A2b's
   asc_calibrated/intra_divisor_alt follow). A width-block owner instead
   carries the joint ×-scale band whose edges ARE its two width rows (§5
   check 5). `history` non-empty and dated.
2. **Coverage**: every claimed row-id exists in its artifact — results
   files (both corridors), `abc_harbor.json` (kernel keys, sensitivity =
   tag != "central"), `backtest_543.json` (which A2 extends to carry its
   sensitivity rows — today they are stdout-only, unverifiable),
   width blocks. `wrapper`/`network` are NOT YET scanned artifacts — as
   ratified at review, the draft overclaimed this as already mechanical.
   `check_assumptions.py` today has no `wrapper`/`network` entry in its
   artifact list (`load_artifacts()`/`present`), so the `eq_days` /
   `bca_config` `spec-pending:06§E4` dispositions surface only as check-1
   WARNINGS, not a check-2 fail-flip. The wrapper-artifact scan — closing
   that gap so `wrapper-pending` actually FAILS once `outputs/bca_*.json`
   exists — SHIPS WITH W1's landing commit, not before: a stated future
   commitment, not present-tense behavior.
3. **No orphans**, keyed (artifact, row-id): every row-id in every scanned
   artifact is claimed by exactly one entry. This forces harvest
   completeness (63 harbor rows, 58 streetcar (as landed) — counted, not
   "~50") and makes rule-2 evasion by omission fail loudly.
4. **Prior integrity**: `build_priors()` provenance sentinel on
   `model.PRIORS`; count matches the contract test; ordered-tuple hash
   matches the committed fingerprint (the reorder guard).
5. **Materiality** — SCOPED BY TIER (review: the draft's uniform 2% rule
   was ill-typed and unsatisfiable): applies to constant/config/data
   entries only. Priors are exempt (their uncertainty is already
   propagated into the headline bands; their tornado contributions are
   reported in a separate appendix section, not the exposure sort).
   Structural entries satisfy materiality when every enumerated
   alternative code path has a row (all six existing material toggles
   already do). For scoped entries: effect = max |pct| over claimed
   point rows (band-width entries: band delta over the width block);
   effect ≥ 2% with basis ∈ {literature, judgment} requires both band
   edges present as rows. The appendix header states the local-derivative
   caveat (one-at-a-time at central; interactions invisible).
6. **Pointers**: config-tier keys resolve (structured keys, incl. the
   promoted anchor_derivation block; prose-pointer entries are not
   permitted — promotion, not blob-matching); `logged` README item
   numbers resolve against the README's numbered list; `covered-
   elsewhere:<row-id>` targets exist and are owned.
7. **Citation sync (the drift check the draft lacked)**: live-section
   citations use `value [id]`; the script greps specs/ and README for the
   `[id]` pattern, parses the adjacent numeric, and compares to the
   registry. Point-in-time records (landed-actuals blocks, R-deltas,
   resolved-questions) use bare numbers with as-of dates and NEVER carry
   ids — so the sweep cannot corrupt history. Pre-08 live sections are
   converted opportunistically; unconverted live values are simply
   invisible to the check (stated limitation, not a claim).

## 6. The generated appendix (`outputs/assumptions.md` + `assumptions.json`)

`check_assumptions.py --appendix` writes both (committed; determinism
pins: `open(..., "w", encoding="utf-8", newline="")` with explicit `\n`,
effect column formatted `%.1f%%`, primary sort |effect| desc, secondary
sort id, `|` escaped in any embedded label). Sections: (1) unpropagated
exposures (constant/config/data/structural), sorted by measured effect —
the audit's headline; (2) priors with tornado contributions (separate,
labeled as already-propagated); (3) width sensitivities; (4) rowless
dispositions with their `accepted` stamps — every escape hatch in one
place for the owner to veto; (5) basis census + a generated
what-changed section from entry `history`. README gets a two-line
pointer; the appendix is the inventory.

## 7. The harvest (initial population)

Everything in the draft's list PLUS the review's completeness findings:
`TSP_SPEEDUP` 0.075 (a textbook entry: literature basis, upgrade = the
held-out TSP experiment), the S0 pivot clips 1e-6/0.95 (0.95 is a real
max-share assumption), the visitor-Dirichlet alpha floor 1e-3, the
walk_spread grid (0.85/1.0/1.15 @ 0.25/0.5/0.25), the sens-run n=4,000,
the `asc_calibrated` display fallback 0.109 (drift bait — registry-owned
or computed), the sub-cell merge epsilon round(W,9), the ESS<1,000
warning threshold, `UPT_FY2014_MB`, the projection constants
MI_LAT/MI_LON, and ONE data-tier entry for the 543 measurements that
OBS_543 and the FY2017 4,615 target are both views of. Mandated new
point rows: `walk_mph` {2.5, 3.5} (auto-generated edges; verified
implementable — single consumer, no PRIORS collision through `point()`'s
kwargs forwarding, stated here as the standing constraint: over-key names
must never shadow a PRIORS key). Width block per §4. Everything else
rowless gets a closed-enum disposition + accepted stamp, visible in
appendix section 4.

**Logged deviation (A3, 2026-07-14, response to whole-branch review):** the
"ONE data-tier entry for the 543 measurements" above did NOT land as
planned. `OBS_543` and `OBS_543_FY2017` are CONSTANT-tier entries
(`obs_543`, `obs_543_fy2017`), not a single data-tier entry, because
`backtest_543.py` / `reweight_abc.py` import their literal values via
`val()` — and data-tier entries are NOT owned (§2: no `value` field, so
there is nothing for code to import). This is a stated, reviewed deviation
from this section's original plan, not a silent drop: the two constant
entries cross-reference each other's provenance, and the new
`ntd_snapshot_2026_07` data-tier entry (added in the review response, §2)
now separately carries the dataset-VINTAGE side of the assumption — which
NTD monthly-release snapshot the UPT leaves were pulled from — disposed
`covered-elsewhere:543_launch14_s500`, the same vintage-choice-sensitivity
row those constant entries already point at.

## 8. Work items (SDD, one branch)

- **A1 — registry + single-source refactor.** Owned tiers populated;
  constants imported; `PRIORS = build_priors()` + committed order
  fingerprint; backtest central dict → computed midpoints; literal-typing
  discipline. GATE: full pipeline byte-identical (pure refactor).
- **A2 — row identity + harvest completion + new coverage.** Row `id`
  fields in results/backtest sensitivity entries (backtest_543.py starts
  writing its rows into its json); all non-owned tiers populated
  per-artifact; 2013 world promoted to `config/backtest_543.json`;
  `anchor_derivation` structured keys (echo-cascade protocol); walk_mph
  rows; the width-sensitivity block + shared-draw machinery; the
  rebuilt-variant flag on build_corridor + intra-tract variant row.
  GATE: headline/summary blocks unchanged; only additive fields/rows/
  blocks; config cascades echo-only; every new row/block's effect
  reported in the commit message.
- **A3 — enforcement + appendix + docs.** The seven checks;
  `--appendix` (md + json); README pointer + HANDOFF rows + run-order
  note; amendments in the SAME commit: spec 00 governance line AND spec
  02 §5 (add "check_assumptions.py green" to the standing gates; rewrite
  its rule-2 bullet to designate registry semantics as the authoritative
  mechanization — review: leaving four differently-strong statements of
  rule 2 would recreate the multi-source disease for RULES). GATE: green
  on the repo as landed; negative tests demonstrating checks 2, 3, 4 and
  7 each fail on a deliberately broken scratch copy.

## 9. Questions resolved at review (2026-07-11)

- **Q1 — escape-hatch authority:** `no_row_reason` is a closed enum and
  every rowless/definitional entry carries an `accepted` stamp. Initial
  harvest dispositions are adopted under the owner directive of
  2026-07-11 ("add the full version") and stamped accordingly; the
  appendix's disposition section exists precisely so the owner can veto
  any of them at any review — folded into §2/§5/§6.
- **Q2 — moe_z:** definitional (Census-documented conversion), no row;
  the draft's {1.96} row tested a misreading — folded into §4.
- **Q3 — priors vs materiality:** priors exempt from check 5; their
  spread is already in the bands; appendix reports them separately —
  folded into §5/§6.
- **Q4 — what stays honest about enforcement limits:** re-accumulation of
  unregistered literals is NOT machine-caught (a new bare number in code
  trips no check until review); the citation check covers only
  id-converted live text; the fingerprint, not the order field, is the
  reorder guard. Stated here so nobody mistakes the registry for more
  than it is — the review gates remain the last line.
- **Q5 — check-1 band scoping RATIFIED (A3, 2026-07-14):** the A2b-landed
  clause (bands exist to SOURCE band-edge rows, so the band requirement is
  scoped to entries that own such rows) is adopted, and its mechanization is
  fixed here: `check_assumptions.py` check 1 requires a non-null `band` for a
  prior/constant entry EXCEPT when `basis ∈ {definitional, measured}` (a
  chosen point with no propagated band — unit conversions, clips, thresholds,
  grids, seeds, and single-point measurements whose alternative readings are
  categorical rows, not a swept band) OR the entry is rowless-dispositioned.
  Priors always carry a derived band. This passes the landed registry
  faithfully (e.g. `upt_fy2014_mb` / `mu_matured` own ABC-kernel rows, not
  band edges, so they keep `band=None`; `walk_mph` / `abc_sigma` /
  `dirichlet_strength` own band-edge rows and must carry a band).
- **Q6 — model.py full-table now needs `data/raw` (accepted, A3):** the
  A2b `intra_tract_alt` rebuilt-variant row makes `model.py main()` rebuild a
  scratch corridor via `build_corridor.py`, which reads `data/raw`. The
  zero-download property (README) still holds for `run()` and for a fresh
  clone's committed outputs, but NOT for regenerating the full sensitivity
  table from scratch. Accepted disposition: the rebuilt-variant row is worth
  the dependency; the note is recorded in the README known-issues log and
  HANDOFF rather than engineered around with a graceful skip (which would
  silently drop a coverage row and trip check 2).
