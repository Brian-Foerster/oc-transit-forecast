# Spec 07 — Network sequencing: a greedy portfolio harness with anti-myopia guards

Status: **BUILT 2026-07-17** (N1–N6 all landed). PROPOSED 2026-07-11, revised
same day after a three-lens adversarial review (optimization economics,
governance consistency, code feasibility); all blocking and major findings
incorporated. N1–N4 landed the interim (welfare-minutes) harness; N5 landed the
full NPV objective (the DEFAULT) after R1 → R6 → W1, pricing every candidate-
given-network through the tbc v3 wrapper (`bca-pipeline.mjs`) and ranking by
within-draw CV in common-base-year PV dollars; N6 landed the spec 00 §3 /
spec 06 §1/§7 amendments. **Headline (NPV objective, 2026-07-17):** at the
welfare-BCA central profile NO Orange County ALM corridor *in the hand-supplied
candidate set* clears BCR=1 — the §7 marginal stop fires at cycle 1 and the
decision-grade recommended build order is EMPTY (best marginal BCR ≈ 0.09
US-TYPICAL / 0.14 LOW, harbor; streetcar lower). This is a statement about the
`hand_supplied: true` candidate universe, NOT about Orange County: the stage-1
screen has failed to warrant a candidate set TWICE (§4.3; README known issue
28).
The county-wide always-ALM scope and the owner decisions that shaped this spec
are recorded in §11.

> One sentence of role: each cycle, candidate ALM lines are evaluated against
> the network built so far, one is committed, and the loop repeats — producing
> a build order and a portfolio frontier as the model's PRIMARY OUTPUT, while
> claiming nothing it cannot deliver (§2).

## 1. Role / non-role

A sequencing and portfolio harness that sits ABOVE the pipeline, replacing
nothing in it. Scope: all Orange County corridors, every candidate evaluated
as an elevated automated light metro (uniform mode — spec 04 capital and spec
02 §4.9 grade-separated speed physics apply to every candidate, so
differences between candidates are pure geography and demand, never mode
artifacts).

Outputs are a build order and a portfolio frontier, NOT a globally optimal
network. Stated plainly: global transit network design is combinatorial and
this tool does not claim to solve it. It formalizes the real decision process
— one funded project per cycle, decided against the network that exists —
and defends that process against its known failure modes (§2, §5).

**Commitments are recommendations.** In-run cycle commitments are made by the
§3 selection rule inside a one-shot model run; spec 00 §3 gate discipline
(gate memo, owner authority, stage-3 STOPS) applies at each REAL programmatic
commitment, per the §6.2 operating mode. The sequence is the primary output
of the *planning layer*; each line's forecast of record remains its own
stage-3 STOPS run (spec 00 §1), which this spec does not displace.

Non-role inheritance verbatim from spec 02: frozen market, no induced demand
in any headline, no land-use feedback (rule-5 firewall; restated at §8c
because network assembly is where the temptation to close that loop is
strongest).

**Gate status and required amendments.** Network output is informational
until spec 00 §3 is amended (653bc68 precedent). Because the sequence is
intended as the primary output, the amendment rides the first gate-relevant
landing (N6, §9). N6 also carries a second, explicit amendment this spec
requires: spec 06 §1's degrade-to-uncapped convention and §7 W1's
omit-ABC-columns behavior are AMENDED to read "ABC weights are properties of
the shared parameter posterior, applicable to any corridor evaluated under
the same draws; degrade-to-uncapped applies only when no county kernel
exists at all" (§6.1). This spec does not pretend that is a no-op: it is a
deliberate, logged change to a written convention, made for the reasons in
§6.1 and §11 Q4.

## 2. Motivation and honest limitations (read this first)

**Greedy's blind spots — there are three, not one.** Greedy selection has
near-optimality guarantees only in a narrow setting (monotone submodular set
function, cardinality constraint) that this problem does not occupy. It
fails here on three independent grounds: (1) **complementarities** — two
crossing lines create transfer value neither has alone; with superadditive
value greedy can be arbitrarily bad (the canonical failure: a grid where no
single line clears the bar but the completed grid dominates); (2) **the
budget** — under a cumulative capital budget (a knapsack), even pure
substitutes defeat naive greedy (a tiny high-ratio line can crowd out a huge
line that nearly exhausts the budget); (3) **discounted sequencing** — the
objective is not a set function at all: order matters, and deferring a
large-NPV line behind a small capital-efficient one has a real welfare cost.
§3's selection rule and §5's guards are designed against all three, and §7
carries the standard cheap safeguard (report the best single feasible
candidate and best feasible archetype beside the greedy portfolio — the
modified-greedy comparison that costs zero extra evaluations).

Substitution, by contrast, is the case the pivot machinery handles natively
— overlapping candidates are discounted because the base already serves the
market — conditional on the S0 approximation logged at §8d. This is
motivation, not a guarantee. The empirical justification for taking
complementarities seriously is the repo's own reference classes (spec 05
§4.3–§4.4): standalone stubs underperform their forecasts (REM South Shore;
Honolulu pending verification per spec 05), networked lines (Canada Line)
overperform.

**Anchor chaining (repo-specific, and the more important one).** Cycle 1
evaluates against measured anchors. Cycle 2's world contains a line that
does not exist, so its base is partly a cycle-1 forecast; errors compound
and are CORRELATED across cycles — same model, same coefficients, so the
Flyvbjerg prior applies jointly, not independently. §6 is the control:
per-draw anchor propagation makes the compounding visible in the bands, the
provenance ledger makes it legible, and the depth cap makes it binding.

## 3. Objective and selection rule

**Units first (binding).** All decision arithmetic is in common-base-year
present-value dollars. A candidate committed at cycle k starts construction
at year (k−1)·cycle_gap, opens at (k−1)·cycle_gap + build_years (spec 06 E3;
D6 margin-only ramp inherited unchanged), and BOTH its benefit stream and
its capital outlay are discounted to the common base year. Capital is never
compared undiscounted against discounted benefits: ΔNPV and ΔK_PV move down
together for identical projects committed later, and that decline is the
deferral cost this tool exists to surface — not an artifact.

**Selection rule (the k=2 lookahead, stated exactly).** For each feasible
candidate A at cycle k against network N_k, with remaining budget R_k:

    CV(A) = ΔNPV(A | N_k)
          + max( 0 ,  max_{B ≠ A, K_A + K_B ≤ R_k}  δ · ΔNPV(B | N_k + A) )

where δ is the one-cycle_gap discount shift and the max(0, ·) is the null
continuation. Commit argmax CV(A) subject to K_A ≤ R_k. Properties this
buys, stated so the rule is not re-litigated at implementation: the best
single automatically competes through its own best continuation (no
best-single vs best-pair-first-element ambiguity); decisions use DIRECTIONAL
chain values with the second element timed at +cycle_gap; and under a slack
budget the rule orders by NPV *level* with lookahead (the interchange
argument — capital intensity is irrelevant to order when everything gets
built), while the budget constraint enters only through feasibility.
Capital-efficiency *ratios* are reported, and become decision-relevant only
when the budget binds (§7).

**Pair-justified commitments.** If the winner's own ΔNPV(A|N_k) < 0 (A is
committed only because its continuation B* justifies it): record B* and the
pair's joint feasibility in the cycle record; the §7 marginal stop does NOT
fire on A — the pair's joint BCR is carried in the stopping record instead;
and the next cycle's swap pass MUST reconsider A if no continuation worth at
least δ·ΔNPV(B*|N_k+A) is committed. This closes the stranded-first-element
failure of naive lookahead.

**Primary objective (gated on R1 → R6 → W1):** ΔNPV per the spec 06 central
profile, per draw under common random numbers, reported uncapped |
ABC-calibrated side by side (calibration per §6.1), fold and retain
separately (spec 06 §1; each committed line carries its scenario as an
attribute, §4.1).

**Interim objective (available now):** Δ(welfare-minutes) — the B1
exact-logsum accumulators (um_infra + um_margin, person-scaled), with the
spec 06 D8 non-work blend applied at the exported per-draw ws/κ values.
While D8's b_nw = b_work deferral stands, the blend is a common per-draw
scalar and cancels EXACTLY in within-draw ranking (nearly, once tilted
non-work streams exist). Interim ranking is by Δminutes LEVEL, with ΔK
shown as the spec 04 LOW | US-TYPICAL band pair beside it (spec 04 §3.2:
never present the low number alone) and the ratio as a display column only
— the interim layer cannot do timing economics and must not pretend to.
Interim results are labeled INTERIM and never quoted as BCA output. The
capital function is work item N2 (spec 04's markup-inclusive coefficients +
§3.1 fleet formula; spec 04 currently exists as spreadsheet + spec only).

**Aggregation rule (binding).** All portfolio quantities are aggregated
WITHIN-DRAW: sum lines inside each draw, then take percentiles — never sums
of per-line percentiles. Shared parameter draws correlate every line's
forecast; within-draw aggregation carries that correlation into the bands.
Two honest caveats carried as §8 entries and a row: within-draw sums carry
the correlated parameter component but NOT the per-line idiosyncratic
structural error the ABC kernel's σ-floor asserts — so a σ_struct
per-line-independent error row (new priors appended LAST, per the rng
discipline) is mandatory on portfolio bands, which are otherwise too narrow
(§8g); and CRN makes anchor draws comonotone across corridors, overstating
anchor-error correlation (§8h).

## 4. Network state and mechanics

### 4.1 Reality in config; the chain in the output

- `config/network_asbuilt.json` (NEW) is the only persistent network state:
  a human-maintained list of lines that PHYSICALLY EXIST — id, config path,
  scenario as operated, in-service date, anchor source (measured APC), and
  calibration-kernel label if the line has produced one (§6.1). Initially
  empty beyond the implicit OCTA base. It changes only when reality changes.
- The hypothetical chain is NOT persisted as config. Each cycle's record in
  the primary artifact (§7) is self-describing: network-before, candidate
  scores, interaction matrix, archetype gap, swap results, the commitment
  and its scenario, provenance depth. The full run is reproducible end to
  end from committed configs + seed (gate G6).
- A committed line enters the chain with its operator scenario (fold or
  retain) FIXED at commitment, per spec 06's un-blending; the cycle record
  documents the choice — and §4.2's mechanics CONSUME it (fold propagation).

### 4.2 Per-cycle candidate input generation (rebuild, don't patch)

Candidate inputs are REBUILT each cycle via `build_corridor.py`, so crossing
detection, feeder assignment, and transfer-bin construction reflect the
network the same way they reflect real OCTA routes today. Empty-network
rule (load-bearing for G1): when the network-before is empty, the harness
passes the committed config FILE through verbatim — no regeneration, no
added keys — so cycle-1 byte-identity holds by construction.

The rebuild requires four itemized mechanics, all N1 code (the alignment
*sources* exist — GTFS shapes and `corridor_waypoints` — but no injection
path does; stated plainly so N1 is costed honestly):

1. **Synthetic feeder injection.** Committed lines enter the feeder-
   construction pass as synthetic routes: shape from their config alignment,
   truncated to their committed window (new code — no shape-truncation path
   exists today); the working object `{route, node_pos, headway, x, y}`
   appended before the node-assignment loop; headway mapped from the
   committed {peak, offpeak} plan to the feeder convention's single scalar
   as **offpeak → midday**, a declared convention with a sensitivity row
   (peak-mapped variant).
2. **Co-located base-service injection needs a model change.** model.py
   hardcodes the scenario systems (fold = [new], retain = [new, local]);
   any other services_base entry silently vanishes from the build world —
   a committed metro would be DELETED by the candidate's opening. N1 adds a
   per-service persistence flag (`svc["persistent"]: true`) honored by the
   systems construction in BOTH scenarios; injection is valid only with the
   flag, and gate G2c asserts the committed line's utility appears in both
   ls0 and ls1.
3. **Fold propagation.** A committed line's fold consequences propagate:
   generated candidate configs append every committed-fold route to
   `excluded_feeders` (build_corridor iterates live GTFS routes and would
   otherwise double-book a dead route as a live feeder), and the anchor
   adjustment (below) carries the corresponding subtraction.
4. **Output routing.** build_corridor gains an output-path/name parameter;
   per-cycle rebuilds write `corridor_<candidate>_<fingerprint>.json` into
   a run directory and NEVER overwrite the committed derived files (which
   the backtest and export round-trip read).

**Anchor adjustment (per-draw, margin-only — the load-bearing mechanic).**
For candidate B evaluated against a network containing hypothetical line H
(committed scenario s_H):

    anchor_B'(draw) = anchor_B_measured(draw)
                    + ω(H,B) · [ total_H(draw) − anchor_H(draw) ]     (margin)
                    − fold_sub(H, B)                                   (ghosts)

The margin term uses H's committed-scenario per-draw MARGIN — total minus
anchor, both already exported per draw (spec 06 §3) — never gross newline:
H's diverted riders are already inside anchor_B_measured wherever the routes
they came from cross B's buffer, and base-service injection already
discounts them in the ratio; adding gross newline would count them twice,
inflate every overlapping candidate, and flip G2's sign in the parallel
case. fold_sub removes folded routes' measured boardings attributable
inside B's buffer (geometric share along the folded route's shape). The
residual approximation — apportioning H's margin by ω — is logged (§8i)
with rows ω × {0.5, 1.5}.

ω(H,B) is the share of H's forecast attributable to H's stops inside B's
0.9-mi buffer. Two pieces must be *declared*, since no pipeline output
allocates a line's boardings along its length: stops are materialized every
`spacing` mi along H's alignment polyline, and boardings are allocated
along H **proportional to corridor-tract worker mass** (default), with a
uniform-along-line variant as the sensitivity row.

Mechanically the anchor add is one small model.py extension (N1):
`run(..., anchor_add=None)` taking an (n,) array added AFTER the anchor's
uniform draw — rng-neutral at the verified draw site (the anchor is the
first consumption on run()'s second stream, so nothing downstream shifts;
the always-consume guarantee is draw_params-only, so this claim is scoped
to the unpinned path). anchor_add applies AFTER the `over["anchor"]` pin
branch, so the anchor→low/high sensitivity rows pin the MEASURED component
and retain the network adjustment.

**S0 staleness (logged approximation).** Base transit shares are
corridor-level per car segment and stay measured even where a hypothetical
line raised true shares. The anchor carries the level, so this is
second-order (pivot curvature and den weighting), but substitution
correctness in overlaps is conditional on it. Bound: spec 02 §4.3's
exclusive-tract-assignment sensitivity for any pair sharing > 30% of
catchment tracts. §8d.

### 4.3 Evaluation discipline

Every evaluation in a cycle runs under shared `draw_params` (CRN, same
seed); rankings are noise-free; pairwise P(A beats B) reported from the
per-draw arrays alongside bands. Full N = 40,000 for every evaluation
including pairs and archetypes — the run is one-shot and primary; nothing
is screened at reduced n. An "evaluation" = one corridor rebuild (~4 s
measured) + one `run()` (~7 s measured at n = 40,000; the ~56 s figure
elsewhere is model.py's full main() with its sensitivity table) ≈ ~12 s.

**Candidate pool.** The stage-1 DRM screen refreshes the candidate POOL
between real programmatic commitments (windows may enter or exit per the
gate-1 rules, promotion owner-mediated per spec 01 §4b); it does NOT
re-score counterfactual networks — the screen is a static cross-sectional
fit, and network interaction is this harness's job via `anchor_add`.
**Standing condition (STRENGTHENED 2026-07-21, rule-3 log — README known
issue 28).** The candidate universe is `hand_supplied: true`
(`config/candidates.json`; the 13-arterial shortlist in HANDOFF is the
natural seed), and this is now the STANDING condition, not a temporary
bridge "until spec 01's first artifact lands": spec 01's artifacts HAVE
landed and the screen has FAILED to supply a decision-grade window-level
corridor-selection product **TWICE** — the v2.0 screen and the v2.1
rebuild both returned `ordinal_ok = FALSE` (spec 01 §5/§9, README issues
35–42), and the v2.2 productivity estimand (spec 01 §10) is only
pre-registered and unrun (README issue 43). CONSEQUENCE, binding on every
downstream headline: the §7 "no OC ALM corridor clears BCR=1" verdict is a
statement about the HAND-SUPPLIED candidate set, **not** a screen-warranted
statement about Orange County — no empirical screen has selected or ranked
this candidate universe, so the harness ranks the analyst's corridors and
claims nothing about the alignments the analyst did not supply. The
hand-supplied substitution stays stated in the artifact.

**Stage-2 scoping under the v2.4 stopping rule (owner-ratified 2026-07-22,
option (ii); rule-3 log — README known issue 47; spec 01 §12.2).** The v2.4
BCA-queue build (spec 01 §12, §9.5 stopping rule) is stage 1's LAST method
attempt. If its branch (a) ever lands a decision-grade benefit-per-cost queue,
that queue is a PROMOTED candidate set — which would STRAND this spec's verdict
and stage 2's welfare BCA, both computed on the HAND-SUPPLIED harbor/streetcar
set. The adopted resolution, the one consistent with the item-8 stopping rule
(v2.4 = last STAGE-1 attempt, NOT a stage-2/3 re-trigger):

- the §7 "no OC ALM corridor clears BCR=1" verdict is **PERMANENTLY SCOPED to
  the corridors ACTUALLY EVALUATED** (hand-supplied harbor/streetcar) — it never
  silently extends to a promoted set;
- the v2.4 queue is **FORWARD-LOOKING input for FUTURE stage-2 work — NOT a
  trigger to re-run stage 2/3, and NOT auto-promoted into
  `config/candidates.json` for the CURRENT verdict**;
- **DISALLOWED STATE, stated explicitly:** shipping a NEW candidate set
  (`hand_supplied: false`) ALONGSIDE verdicts computed from the OLD
  hand-supplied one is an incoherent artifact and must never be committed. A
  promotion lands ONLY in a batch that also RE-RUNS the stage-2/3 verdicts that
  consume it; otherwise the promotion does not land and the verdict keeps its
  hand-supplied scope.

## 5. Anti-myopia guards (the load-bearing section)

1. **k=2 lookahead** — the §3 CV rule (conditional chaining; the machinery
   never runs two new lines jointly). Per cycle: singles + directional
   continuations (with ~8 candidates, 8 + 56 evaluations). The audit-side
   interaction matrix is the symmetrized

       I(A,B) = ½ · [ (V(B|A) − V(B)) + (V(A|B) − V(A)) ]

   computed with BOTH legs at COMMON timing (δ undone), so it isolates
   approximation error (S0 staleness, anchor chaining) from genuine
   sequencing value; the δ-timed sequencing component is reported
   separately in the cycle record. Decisions use directional values only.
   Blind k=3 as a default is rejected — not on cost (the run is one-shot)
   but because the archetype guard covers higher-order structure more
   directly; an OPTIONAL k=3 deep pass over the top 3 candidates is an
   exposed knob, with an order-difference diagnostic row (does it change
   the committed order?).
2. **Swap/removal moves, bounded.** After each commitment, test replacing
   each HYPOTHETICAL committed line with the cycle's runner-up only (one
   alternative per position), re-evaluating the chain suffix under the
   swap. Cost is suffix-length-dependent — swapping position j at cycle k
   costs (k−j+1) evaluations, ≈ Σ(k−j) per full pass — stated so the
   budget (§9) is honest. Greedy + bounded local search escapes early
   mistakes without combinatorial search. Built lines (`network_asbuilt`)
   are never swapped — sunk; reality, not a model choice.
3. **Archetype competition.** 2–4 owner-designed complete networks
   (trunk+feeders, crossing pair, mini-grid), committed to the repo
   (`config/archetypes/*.json`), each with a DECLARED internal build order,
   on the SAME cycle_gap clock and price-base year as the greedy sequence.
   Evaluated ONCE per run (they do not depend on the greedy chain); the
   greedy-vs-archetype gap is re-plotted each cycle against the growing
   frontier, compared at MATCHED cumulative capital (interpolated), so the
   gap never conflates "better network" with "more capital spent." A
   persistent large gap converts the output to "build toward the archetype
   in greedy order." (§11 Q3: owner-designed, not generated.)
4. **Complementarity audit.** Publish I(A,B) each cycle in common-base-year
   dollars (interim: welfare-minutes). PRIMARY caveat, corrected at review:
   **tau pinning** (§8a) is what suppresses cross-line synergy in the
   objective itself — transfer volume pins to a share of base boardings, so
   G3's expected magnitude is muted and every interaction estimate says so.
   Spec 06 D7's corridor-leg undercount additionally biases the CAR-MILE
   externality slice of NPV interactions, bounded by the cm_seg_fullod row
   (that row exists only for car-miles; a full-O-D welfare bound would be a
   new export design point per spec 06 §3's mechanism, queued only if the
   audit shows it matters). Eventual fix for tau: the records-request
   transfer-rate item, cited rather than re-litigated.

## 6. Calibration and anchor-provenance discipline

### 6.1 One county posterior (Q4 resolution — an explicit amendment)

All candidates are ranked under the SHARED OC parameter posterior: the ABC
weights of spec 02 §4.4's joint kernel — currently the single 543 kernel
(launch-equivalent after R1) — applied uniformly to every candidate's CRN
draws, uncapped always alongside. This AMENDS spec 06 §1/W1's
degrade-to-uncapped convention (amendment rides N6; §1). Rationale: the
parameters are county-common (every corridor runs the same PRIORS), so
conditioning them on OC's own experiments is the model's own logic taken
seriously — local-data calibration, not a literature filter. Under
county-wide always-ALM the bus→rail transportability assumption is
COMMON-MODE: it moves program levels, not build order (to first order;
ASC-sensitivity varies mildly with market composition — §8f). Where it
bites is the STOPPING RULE, which therefore carries the R2 premium-bracket
{1.0, 1.5, 2.0} rows on every stop decision.

Mechanics (corrected at review): the weights are a function of (params,
seed) via the harbor backtest and are IDENTICAL across corridors under CRN
— so they are computed once per cycle and shipped as one weights file
referenced by kernel label, not recomputed per candidate export;
bca_export.py's harbor-only gate is lifted accordingly (N5). Weighted ESS
is reported in the artifact for EVERY ABC-weighted portfolio statistic,
inheriting spec 02 §4.4's ESS < 1,000 saturation rule.

**The loop is self-calibrating — under the standing registry discipline.**
Each line that opens becomes a new experiment, but joins the kernel only
through spec 00 §5 / spec 02 §4.4's validate-then-calibrate sequence:
(i) the line's cycle record in the primary artifact is NAMED as its frozen
registered prediction at real-world commitment; (ii) on opening, that
prediction is scored out-of-sample FIRST and reported; (iii) the opening
gets a validation-registry row with an explicit calibrate-vs-validate
assignment, respecting the registry's 3–4-target cap and its no-dual-use
rule — rail-class openings may argue for kernel slots on the grounds that
the cap currently counts bus experiments, but that argument is made in the
registry, not assumed here. The post-launch OC Streetcar (~2027) is the
first RAIL-class kernel OC will ever have — the only local data that can
discipline the ALM premium itself — and is named as the priority
calibration event. Spatial caveat, scoped honestly: the 529 (a bus overlay)
tests spatial homogeneity of the bus-calibrated parameters — the nearest
available test of the county-posterior assumption — while the MODE
dimension of the premium remains bracketed by the R2 rows until the
streetcar kernel exists (§8e).

### 6.2 Provenance ledger

Every line in a cycle's network is tagged **measured** (from
`network_asbuilt`) or **hypothetical** (forecast-anchored). Depth is the
recursive DAG rule (corrected at review — the flat cycle-count reading
mislabels spatially independent programs):

    depth(measured line) = 0
    depth(candidate evaluation) = 1 + max{ depth(H) : H hypothetical in the
        network-before AND the candidate DEPENDS on H }
    (max over the empty set = 0; a committed line inherits its
    evaluation's depth)

where "depends on" is the explicit predicate: ω(H, candidate) > 0.01, OR
co-located persistent-service injection, OR a feeder/transfer-bin edge in
the rebuilt inputs. Without the threshold the rule degenerates to
cycle-count. Depth is capped at 2: beyond, output is labeled EXPLORATORY
and excluded from gate memos. Consequence, stated because the sequence is
the primary output: a spatially spread program can stay decision-grade for
many cycles; a tightly chained one goes exploratory by cycle 4 — the
frontier chart shades by depth either way, so no reader mistakes the tail
for a forecast. The depth-cap value carries a labeling-sensitivity row
(cap 1 / cap 3).

**Operating mode.** A planning tool re-run between real build cycles as
lines open and forecasts become measurements — not a one-shot 30-year
simulator. Each re-run starts from the updated `network_asbuilt`, the
enriched kernel, and re-measured anchors; provenance depth resets
accordingly.

The Flyvbjerg annotation (spec 05 §4.3, display-only) prints beside every
network-level output, noting that portfolio optimism is worse than
single-project optimism because forecast errors are correlated across the
model's lines — which within-draw aggregation plus the σ_struct row (§3)
makes arithmetic, not rhetoric.

## 7. Stopping rule and outputs

**Stop** under the budget-slack regime when the best candidate's CV ≤ 0 at
the spec 06 central profile (λ = 1.0; the λ = 1.3 row supplies the
second-best view), carrying the §6.1 premium-bracket rows and BOTH spec 04
cost bands (LOW | US-TYPICAL — the stop decision is level-sensitive on both
sides). Pair-justified commitments are exempt per §3. Under a binding
budget, the stop is exhaustion, and the record reports the SHADOW-PRICE
cutoff — the marginal committed line's BCR, which exceeds 1 — rather than
pretending the hurdle was 1. Never "candidates ran out": if the screen
empties, the artifact reports the economic margin at which it emptied.

**Safeguard comparison line (from §2):** the artifact reports
max{greedy portfolio, best single feasible candidate, best feasible
archetype} beside the greedy result — the standard knapsack fix, zero extra
evaluations.

**Primary artifact:** `outputs/network_sequence.json` — run id (a function
of seed + config-set hash, NO timestamps), kernel set + per-statistic ESS,
candidate universe (and whether hand-supplied), then per cycle:
network-before (ids + provenance tags), per-candidate results (fold and
retain, uncapped | ABC bands, pairwise P(beats)), CV components (own ΔNPV,
continuation, timing split), the interaction matrix with the
approximation/sequencing decomposition, archetype-gap entry, swap results,
the commitment (line, scenario, pair-justification if any, one-line
rationale), and provenance depth; then the frontier (cumulative capital-PV
vs cumulative objective, within-draw bands, σ_struct row, depth-shaded,
both cost bands), the stopping record, and the provenance report.
Committed, regenerable by one script (G6).

**Charts** (make_charts.py style): depth-shaded frontier, build-sequence
chart, archetype-gap series, network map; Flyvbjerg annotation per §6.2.

## 8. Known limitations to log (README entries; expected to land as 25+ as of 2026-07-11)

a. **tau pinning is the model's weakest network-effect channel** — transfer
   volume pins to 25–40% of base boardings even between two new lines;
   sensitivity row on every interaction estimate; records-request item 3 is
   the eventual fix; G3's pre-stated muted magnitude is this, quantified.
b. **Frozen-market compounding across cycles** — each hypothetical line's
   induced demand is absent from the next cycle's base; downward bias
   growing with depth; the depth cap is the control.
c. **Rule-5 firewall restated** — the economic-potential layer stays
   descriptive; uplift and user benefits never summed; spec 06 §1's
   gate-memo caution applies to every network memo.
d. **S0 staleness in overlaps** (§4.2) — second-order; bounded by the
   exclusive-tract sensitivity.
e. **Spatial transportability of the county posterior** (§6.1) — 543
   premium applied county-wide; the 529 tests the spatial dimension for
   bus-calibrated parameters; the mode dimension stays R2-bracketed until
   the streetcar kernel.
f. **Composition-dependent ABC re-ranking** — ASC-sensitivity varies with
   market composition, so reweighting can reorder candidates second-order.
g. **Portfolio bands omit per-line idiosyncratic structural error** —
   within-draw sums carry the correlated parameter component only; the
   σ_struct independent-error row is the visible correction.
h. **Anchor comonotonicity under CRN** — every corridor's anchor sits at
   the same uniform position per draw, overstating anchor-measurement-error
   correlation across lines (sign: portfolio bands too wide from this
   channel, too narrow from g — both logged rather than netted).
i. **ω margin apportionment** (§4.2) — allocating H's margin along its
   length by worker mass is a declared judgment; rows ω × {0.5, 1.5} and
   the uniform-allocation variant.
j. **Shared fixed assets unmodeled** — spec 04's fixed term (OCC + depot)
   is a standalone-line assumption; later lines plausibly share it, so
   Δcapital for lines 2..k is overstated; knob `fixed_cost_share` for
   lines after the first, rows {1.0, 0.5, 0.0}.

## 9. Sequencing and work items

Runtime budget (measured, house convention): an evaluation ≈ 12 s
(rebuild ~4 s + run() ~7 s at n = 40,000). Cycle k: 8 singles + 56
directional continuations + swap pass (suffix-dependent, ≈ Σ(k−j) ≈ up to
~15 evaluations by cycle 6, runner-up-only per §5.2) ≈ 65–80 evaluations ≈
15–20 min; archetypes once per run (~12 evaluations); a 6-cycle full run
≈ 2–3 h, k=3 optional pass ≈ +1 h. Cheap enough that nothing is ever
economized to reduced n. N5 export disk: ~12 MB per candidate-export,
~1 GB per cycle if all are exported (gitignored, regenerable) — export
only committed lines + finalists by default, knob to export all.

- **N1 — skeleton** (interim objective), itemized honestly after the
  feasibility audit: `network_asbuilt` reader; per-cycle rebuild with the
  FOUR §4.2 mechanics (synthetic-feeder injection incl. shape truncation
  and the offpeak→midday mapping row; the `persistent` service flag in
  model.py's systems construction; fold propagation into excluded_feeders
  and fold_sub; build_corridor output routing + empty-network
  verbatim-config rule); the `anchor_add` model.py extension (post-pin-
  branch, rng-neutral); CRN evaluation loop with the §3 CV rule; the
  interaction matrix with timing decomposition; bounded swap moves;
  provenance DAG; canonical-serialization utilities (see G6).
- **N2 — capital function**: spec 04 coefficients + §3.1 fleet formula as
  code, BOTH bands, `fixed_cost_share` knob; coordinates with spec 04's
  own gates (reproduce E55 exactly).
- **N3 — archetype harness** + matched-capital gap series; owner supplies
  2–4 archetypes with declared build orders.
- **N4 — provenance/labels, σ_struct row, charts, primary-artifact writer.**
  **LANDED 2026-07-17** (branch spec07-n4). The primary-artifact writer and
  provenance/labels shipped at N1b; N4 completed the remaining §3/§6.2/§7 items
  and the two reviewed carry-ins:
  (a) **Anchor-vs-rebuild channel split** (N1b-review binding): each
  candidate-given-network single decomposes its lift into the anchor_add channel
  (margin substitution/complementarity) and the rebuild channel (synthetic-feeder
  MARKET ENLARGEMENT) by the reviewer's toggle method — two extra evaluations
  (anchor-only, rebuild-only) under CRN, in the artifact + printout, so market-
  enlargement can never be read as crossing complementarity. Cycle-2
  streetcar|{harbor}: the lift is ~entirely the anchor channel, rebuild ≈ 0.
  (b) **Margin-boarding-distribution sensitivity** (§8i): ω recomputed with H's
  margin allocated by the walk-bin-mass-weighted variant (beside the existing
  uniform-along-line), as an artifact row.
  (c) **Exclusive-tract row** (spec 02 §4.3): the harbor/streetcar pair (27.3%
  catchment overlap — near the 30% threshold, computed anyway per the review),
  shared tracts assigned to the nearer corridor, as an artifact row.
  (d) **σ_struct row** (§3/§8g): per-line INDEPENDENT structural error, N(0,
  σ_struct = 400 boardings) scaled to welfare-minutes and summed within-draw,
  seeded deterministically from the run fingerprint — implemented HARNESS-SIDE,
  NO new PRIORS key (the append-last discipline is not triggered because the
  error is post-processing, not a swept model input); base vs σ_struct-inflated
  portfolio bands carried on the frontier.
  (e) **run_id values-hash** (D60 review rec 3a): the preimage gains the sha256
  of the consumed capital constants + active prior bands, so a rate-card or
  prior-band edit MOVES the id (the old input-only key did not); regenerated,
  the id changed, recorded in the artifact's provenance block.
  (f) **Registry conversion** (§9/§10 G7): the 17 capital + network-mechanics
  spec-pending:07§9-N4 leaves now claim rows in the artifact's
  `assumptions_manifest`; check_assumptions scans `network_sequence.json`
  (claimed ids; harness-internal sensitivity ids engine-owned/exempt, the
  spec 08 §9 Q7 precedent) — warnings 21 → 4. Charts: depth-shaded frontier,
  build-sequence, interaction/channel-split panel (make_charts.py `network`);
  the archetype-gap section renders the N3-pending placeholder.
- **N5 — full NPV objective. LANDED 2026-07-17** (branch spec07-n5, after
  R1 → R6 → W1). `sequence_network.py --objective npv` is the DEFAULT; the
  interim welfare-minutes objective is retained as `--objective interim` (the
  byte-identical N4 regression anchor). Mechanics as built:
  (a) **Exporter (`bca_export.py`).** An importable `build_export(name, res,
  …)` assembles the §3 export FROM the in-memory `run()` result (no re-run); the
  standalone CLI path funnels through it unchanged (byte-identical B4 schema).
  The two N5 additions ride OPTIONAL kwargs: `network_fingerprint` (sha256 of
  the networked-rebuild descriptor) AND fingerprint-bearing filenames
  (`bca_export_<corridor>_<fp12>.json.gz`, already inside B4's gitignore glob);
  and a `cost_design` block (the harness-owned capcost capital bands + corridor
  service design). A networked ROUND-TRIP mode is a SELF-CONSISTENCY check
  (recompute one weighted P50 from the arrays) — a candidate-given-network point
  has no committed reference, so the committed-reference comparison stays scoped
  to the standalone empty-network case.
  (b) **Wrapper (`bca-pipeline.mjs`, tbc `feat(v3)`).** A networked mode accepts
  an explicit `--export` path, reads `cost_design` to OVERRIDE the static
  cost-profile capital + service design (the harness owns capital; the wrapper
  prices every candidate under the SHARED central profile, §6.1 — the harbor-
  only weight gate is lifted because the ABC weights ship in the export), and
  emits a fingerprint-named `bca_<corridor>_<fp12>.json` PLUS a compact per-draw
  ΔNPV companion (`.npv.json`) — the documented mechanism for reading 40k
  per-draw NPVs back from node (the exact linear decomposition produces them for
  free). The committed-artifact identity test stays scoped to the standalone
  harbor artifact.
  (c) **Harness (`sequence_network.py`).** Per candidate-given-network the
  harness builds the export in-process, invokes the wrapper (node, synchronous,
  ~2 s at N=40,000), and reads back per-draw ΔNPV for the WITHIN-DRAW CV (§3),
  with δ = one-cycle_gap deferral on the profile 4% clock. Both cost bands are
  carried (LOW | US-TYPICAL); the §7 stopping rule fires on the marginal-BCR
  test with the R2 premium-bracket rows and the max{greedy, best-single, best-
  archetype-placeholder} safeguard line; the frontier is ΔNPV vs ΔK_PV. The N4
  carry-ins land here too: std-based σ_struct widening is the PRIMARY reported
  measure (P90−P10 secondary), and the channel split gains a P50-non-additivity
  note field.
  **Result:** the §7 marginal stop fires at CYCLE 1 — every OC ALM candidate's
  ΔNPV is deeply negative (best marginal BCR ≈ 0.09 US-TYPICAL / 0.14 LOW,
  harbor) and no continuation is positive, so the decision-grade recommended
  portfolio is EMPTY, reported per §7 with the economic margin printed, never
  "candidates ran out."
- **N6 — amendments. LANDED 2026-07-17** (same commit as N5): spec 00 §3 gains
  the network-sequence row (PRIMARY planning output, one line + rule-5 note,
  653bc68 precedent) AND the spec 06 §1/§7 W1 degrade-to-uncapped amendment
  (§6.1 — ABC weights are properties of the shared posterior, applicable to any
  corridor under the same draws; degrade fires only when no county kernel exists
  at all). Spec 06 §3 gains the `network_fingerprint` + `cost_design` export
  fields. Spec 07 status → BUILT.

Nothing here reorders R1/R2/R6 or the W-items; the interim objective
exists precisely so N1–N4 need not wait on them.

## 10. Validation gates

- **G1 — single-line degeneracy:** one cycle, empty `network_asbuilt`, no
  prior commitments → byte-identical standalone corridor results, by
  construction via the verbatim-config rule (§4.2) and the inert
  `anchor_add=None`/absent-`persistent` paths.
- **G2 — substitution family:** (a) a parallel candidate scores below
  standalone under base-service injection alone; (b) still below standalone
  WITH the anchor adjustment active, across the ω × {0.5, 1.5} sweep — the
  double-count failure this gate exists to catch is first-order, so G2b is
  not optional; (c) a co-located persistent committed line's utility
  appears in BOTH ls0 and ls1 (the systems-construction fix, §4.2.2).
- **G3 — complementarity sanity:** a candidate crossing a committed line at
  a high-transfer node scores above standalone. Expected magnitude stated
  IN ADVANCE: low single-digit percent of standalone value, because tau
  pinning caps the transfer response — a weak positive reads as §8a; a
  null or negative reads as a bug.
- **G4 — CRN rank stability:** ranking invariant to seed within tolerance
  (≤ 2% seed-drift on the objective P50, mirroring the ABC gate); ranking
  itself exactly stable except knife-edge pairs, which are reported as
  P(A beats B) ≈ 0.5, not as defects.
- **G5 — archetype accounting:** archetypes evaluated with identical
  machinery, same CRN draws, same cycle_gap clock and price base, matched-
  capital comparison; no privileged treatment in either direction.
- **G6 — primary-artifact reproducibility:** re-running from committed
  configs + seed reproduces `network_sequence.json` byte-identically.
  Determinism rules, stated because they WILL otherwise break silently:
  any gzip artifact written with mtime=0 (gzip stamps wall-clock by
  default — verified on the existing exports); run id contains no
  timestamp; `network_fingerprint` = sha256 of the canonical serialization
  (sort_keys, fixed separators); every set-derived list sorted before
  writing.
- **G7 — rule-2 knob gate** (mirrors spec 06 G5): every knob this spec
  introduces ships with its row in the primary artifact's sensitivity
  block in the same commit — cycle_gap lo/hi; budget lo/hi; k=3
  order-difference; ω × {0.5, 1.5} + uniform-allocation; offpeak→midday
  mapping variant; depth-cap 1/3; σ_struct on/off; fixed_cost_share rows;
  ratio-greedy-ordering comparison row (the §3 regime choice made
  visible).

## 11. Questions resolved at proposal review (2026-07-10/11)

- **Q1 — cycle_gap:** exposed knob, prior U(4, 8) yr, lo/hi rows (G7); NOT
  an optimization variable (timing optimization adds a dimension the
  provenance cap cannot discipline) — folded into §3.
- **Q2 — budget form:** cumulative program budget with lo/hi rows;
  per-cycle caps bias toward small lines — folded into §7.
- **Q3 — archetypes:** owner-designed, 2–4, committed to the repo; a
  generator reintroduces the combinatorial problem this spec declines to
  solve — folded into §5.3.
- **Q4 — calibration under county-wide always-ALM:** shared OC parameter
  posterior for all rankings, uncapped alongside; transportability is
  common-mode for ranking and bites at the stopping rule (premium-bracket
  rows mandatory); openings join the kernel only through the
  validate-then-calibrate registry discipline; streetcar post-launch is the
  priority (first rail-class) kernel; spatial caveat scoped to what the
  529 can actually test — folded into §6.1, with the spec 06 amendment it
  requires carried at §1/N6.
- **Q5 — state architecture under a one-shot primary run:** reality in
  `config/network_asbuilt.json`; the hypothetical chain only in the
  self-describing primary artifact; reproducibility gate G6; full-n
  everywhere; provenance shading of the primary output accepted (head
  decision-grade, tail exploratory) — folded into §4.1/§6.2/§7.

Standing-governance check, restated after review: display-only reference
classes, no baked-in filters or caps (the stopping rule applies the
declared decision metric with uncapped alongside — a decision rule, not a
draw filter), two-way firewall, fold/retain un-blending — none weakened.
ONE standing convention is deliberately amended, not silently: spec 06
§1/W1's degrade-to-uncapped, per §6.1, via N6, with this spec as the
written record of why.
