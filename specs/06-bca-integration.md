# Spec 06 — BCA integration: allocation rule and dilemma resolutions

Status: DRAFT 2026-07-10, revised same day after a three-lens adversarial
review (welfare economics, governance consistency, code feasibility); all
blocking and major findings incorporated. Companion engine spec to be added to
`transit-benefit-cost` (`docs/specs/2026-07-XX-v3-pipeline-mode.md`) once this
spec's allocation decisions are accepted.

> Governing principle (user decision 2026-07-10): **everything that can be done
> through the ridership model is done there; the BCA engine covers only what is
> beyond it.** This spec turns that principle into a binding interface contract,
> resolves the open dilemmas under it, and queues the work items.

## 1. Role / non-role

This spec governs the hookup between the stage-2 pivot-logit pipeline (this
repo) and the welfare BCA engine (`github.com/Brian-Foerster/transit-benefit-cost`,
TBCR v2). It produces, per corridor × design × scenario:

- full-uncertainty NPV / PV-BCR distributions (per-draw, N=40,000),
- reported **uncapped | ABC-calibrated side by side** where a calibration
  target exists (governance rule 1; corridors without one — the streetcar
  until post-launch — degrade to uncapped-only with the reason printed),
- **fold and retain reported separately, no blend of any kind** — a stated,
  deliberate deviation from spec 02 §4.7's labeled expected-blend summary
  line: fold and retain carry different cost structures (avoided base O&M,
  fleet), so blending would average over operator decisions inside an NPV,
- with every monetization judgment an exposed knob carrying a sensitivity row
  (governance rule 2).

Non-role: this BCA is NOT the federal template (a separate, simpler mapping —
memory/federal-bca-2026-framework); it does not price land-value uplift
(rule 5 firewall — the economic-potential layer stays descriptive and is
never summed with user benefits).

**Gate-2 status:** making this BCA a gate-2 secondary criterion is a spec 00
§3 amendment, not something this spec can do silently (house precedent:
commit 653bc68 amended spec 00 to admit the economic-potential layer). Until
spec 00 §3 is amended — one line, queued as part of W1's landing commit —
BCA output is informational only. The amendment must carry a rule-5 note:
the agglomeration/user-benefit share of NPV and the economic-potential uplift
column are two lenses on partially the same channel and are never to be read
additively in a gate memo.

## 2. The allocation rule (binding)

**Quantities from the ridership model; prices, time-profile, and public
finance from the BCA.**

| Channel | Owner | Form |
|---|---|---|
| Ridership response to service (speed/headway/spacing/ASC) | stage 2 | dV, S1 — already built |
| Ridership response to fare | stage 2 (NEW — D3) | fare term in utility |
| User benefits — exact CS, in equivalent minutes | stage 2 (NEW — B1, D10) | per-draw logsum accumulators, infra/margin split |
| Fare burden of fare-policy deltas | stage 2 (NEW — D3) | per-draw dollar stream (money never goes through VOT) |
| Car-VMT diverted | stage 2 (NEW — B2, D7) | per-draw per-segment trip-mile masses |
| Crowding | BCA diagnostic only (D4) | load flag; spec 04 consist check is the instrument |
| Externality prices ($/car-mi, carbon, rebound) | BCA | exposed params with rows (D8) |
| VOT (monetization) | BCA | exposed prior, distinct from behavioral VOT (D3) |
| Agglomeration, MCPF, labor channel | BCA | γ, λ knobs (D5, D9) |
| Ramp, growth, discounting, asset lifecycle | BCA | time-profile params (D6) |
| Capital + O&M dollars | spec 04 + new O&M module | scenario bands |

In pipeline mode the engine performs **no demand logic**: `computeDemand`,
the elasticity pivot (`eps_f`, `eps_t`), the fare optimizer, and the Mohring
markup are all bypassed (the Mohring *hook* remains as a parameter defaulting
to 0 so D2's row is a parameter change, not a code fork). The engine prices
exogenous per-draw quantity streams and aggregates them over the lifecycle.
The widget's endogenous mode remains for standalone exploration only.

## 3. Interface contract

`scripts/bca_export.py` (NEW) writes `outputs/bca_export_<corridor>.json.gz`
per design point (values at float32 precision, ~7 significant digits; far-tail
ABC weights flush to zero, immaterial at the round-trip gate's tolerance):

```
{
  "corridor": "harbor", "design": {...service_new...}, "n": 40000, "seed": 42,
  "eq_days": [300, 330],                 // weekday->annual (anchor_from_apc convention)
  "scenarios": {
    "fold": {
      "newline": [...], "total": [...],
      // welfare quantities, equivalent-IVT minutes/weekday, WORK-SHAPED
      // and PRE-BLEND (wrapper applies the D8 blend from params.ws/kappa):
      "um_infra":   [...],   // Σ P·S0·dv               (existing riders)
      "um_margin":  [...],   // exact-logsum total − infra (marginal riders)
      "um0_infra":  [...], "um0_margin": [...],   // no-ASC counterfactual (D1)
      "fare_burden": [...],  // $/weekday, 0 at current flat-fare designs (D3)
      // diverted-trip-mile masses, PRE-pcar, per car-ownership segment (D7):
      "cm_seg":       [[...],[...],[...]],   // 0-veh, 1-veh, 2+-veh (walk+transfer)
      "cm_visitor":   [...],
      "cm_seg_fullod": [[...],[...],[...]]   // transfer legs at full O-D distance (row)
    },
    "retain": { same }
  },
  "params": { all 19 PRIORS keys (12 original + vot_behav + pcar0/1/2/v + v_cruise + dwell — B3/R6), "anchor": [...] },
  "abc_weights": { "543_matured_s500": [...], "543_matured_s350": [...],
                   "543_matured_s800": [...] },   // OPTIONAL; keyed by kernel
                                                  // label, not bare sigma, so the
                                                  // spec-02 §4.4 joint kernel can
                                                  // join without churning the schema
  "base_service": { "rev_hours_weekday": { "43": ..., "543": ... } },  // {} when routes_removed is empty
  "routes_removed": { "fold": ["43", "543"], "retain": ["543"] }       // {"fold": [], "retain": []} when nothing folds
}
```

`routes_removed` is a top-level key (per-scenario route lists); `base_service`
carries ONLY `rev_hours_weekday` (config prose notes are not shipped).
`rev_hours_weekday` is absent — `base_service` is `{}` — when `routes_removed`
is empty: a corridor that folds no route sheds no base O&M (the streetcar's
synthetic composite local, spec 05 §3.3, has no single route to remove).

Division of labor for sensitivity rows (governance-audit fix): rows that
re-price exported quantities (VOT, pcar set, kappa→1, transfer-full-OD, λ, γ,
SCC, discount, ramp, externality rates) are **wrapper-computed** from the
decomposed arrays above; rows that change stage-2 structure (nonwork_short
tilt, premium factors, design variants) are **additional export design
points**. `bca_export.py --seed-check` emits a seed+1 companion file
(mirroring reweight_abc.py's pattern) for gate G4.

New config requirements: per-route `rev_hours_weekday` (from GTFS/OCTA
published service data) and optional `fare_base` (default: module-level
OCTA flat fare, documented) in `config/*.json`.

## 4. Dilemma resolutions

### D1 — ASC monetization: single-channel, true counterfactual computed natively

**Decision.** Headline consumer surplus monetizes **dV including the ASC**.
The companion is a **true no-ASC counterfactual computed in stage 2** — one
extra `combine()` pass per scenario with the ASC zeroed, its own
`ls1_noasc`, its own pivot `S1_noasc`, no rng consumed — exported as
`um0_*`. (The naive decomposition `dv − asc·pn` is rejected: it books
negative time benefits to retain-scenario riders whose unchanged local still
exists, and pushes ASC-attracted marginal riders into the margin at negative
surplus — systematically overstating how much of the case rests on the ASC.
The counterfactual CAN be done in the ridership model, so per the allocation
rule it IS.) The no-ASC variant is a *monetization* counterfactual only; the
ridership headline is untouched.

In pipeline mode the BCA carries **no separate reliability / comfort /
amenity benefit line** — the TBCR Part-B "reliability" item is retired for
pipeline use. The ASC subtracted in the counterfactual is the **effective
(premium-scaled) ASC**, so the R2 transportability rows {1.0, 1.5, 2.0}
(spec 02 §4.5c) stay consistent automatically.

**Rationale.** The ASC is ABC-disciplined against the corridor's own 543
experiment (posterior 0.14/0.19/0.24) and bracketed for the rail-class
product by spec 05's tier-2 analogs. The calibrated choice model is the best
available statement of what riders value; excluding the ASC from welfare
while using it for ridership would assert the model is right about behavior
but wrong about value. Monetizing it AND adding an amenity line would double
count — hence single-channel. Monetizing the ASC at social VOT is internally
consistent because the ASC is behaviorally an IVT-equivalent (asc/|bivt| ≈
4.2 min at central values).

**Rows.** "CS = no-ASC counterfactual" (uses `um0_*`); "reliability line
restored at TBCR default + no-ASC CS" (bounds the *under*count direction —
the no-ASC row bounds only the overcount side); premium-factor rows arrive
with R2.

### D2 — Mohring effect: coefficient 0; frequency benefits live in dV

**Decision.** `mohring_coef = 0` in the pipeline profile; the engine keeps a
`(1 + mohring_coef)` hook on the user-benefit term so the row is a parameter.

**Rationale.** The classic Mohring markup proxies (a) riders' wait-time gains
from frequency — stage 2 prices these exactly, per market, per period, so a
markup would double count — and (b) the true scale externality (operator
raises frequency as demand grows), which is a supply policy expressible as
stage-2 design scenarios, not a coefficient. TBCR's own spec says to zero the
coefficient when frequency response is modeled.

**Rows.** `mohring_coef = 0.09` labeled "unmodeled endogenous-frequency
externality" — sensitivity only, never headline.

### D3 — Fare into the ridership model; money stays money-metric; two VOTs

**Decision (behavior).** Add a fare term to the service utility:
`u += bcost · (svc_fare − fare_base)` with `bcost = bivt · 60 / vot_behav`
and a new prior `vot_behav` ~ tri($10, $22)/hr (behavioral VOT of the
corridor's rider base). `fare_base = cfg.get("fare_base", DEFAULT_FARE)`
(module default = OCTA flat fare, documented); services default to
`svc.get("fare", fare_base)`, so **the backtest corridor inherits the default
and the ABC path is untouched**. At today's flat fare, dV is unchanged —
regression gate G1.

**Decision (welfare — blocking-finding fix).** The fare term is **never
monetized through VOT**. The welfare accumulators (B1) use the no-fare
utility variant (fare terms zeroed, same mechanism as the D1 no-ASC pass);
the money side is exported separately as `fare_burden` in dollars —
`P·(S0 + ½·ΔS)·Δfare_chosen` per draw — which the engine prices at exactly
$1 and nets against revenue. Otherwise a $1 transfer from an inframarginal
rider would be booked as a VOT/vot_behav-dollar welfare loss against a $1
revenue credit (1.1× at central values, 4× at tornado corners), minting
phantom welfare in every fare sweep. At Δfare = 0 the streams are
identically zero.

**Decision (revenue — blocking-finding fix).** Revenue is **incremental
system fare revenue against the base**, symmetric with avoided base O&M:
`fareRevDay = avg_fare × (total − base corridor boardings)` per draw, per
scenario — never gross new-line boardings × fare (riders diverted from
Routes 43/543 paid the same flat fare before; gross booking would overstate
the offset ~3.5× and the λ column would inflate the error).

**Two VOTs, deliberately distinct (standard appraisal practice).**
`vot_behav` (stage 2) converts dollars to utils and governs fare response;
social `VOT` (BCA) ~ tri($15, $30)/hr central $22.50 converts minutes to
dollars (the federal 2024$ all-purpose $21.80 sits mid-band as a reference
point, not an authority). Single VOT across trip purposes is a named
judgment; row: "non-work minutes at 0.7 × VOT". Caution printed in the
tornado: the VOT and vot_behav rows must not be read jointly at opposite
extremes (jointly implausible preferences).

**Rows.** vot_behav lo/hi; VOT lo/hi; non-work 0.7×; avg-fare-per-
incremental-boarding (transfer-discount) lo/hi.

### D4 — Crowding: diagnostic flag, not a benefit adjustment

**Decision.** Stage 2 gets no crowding module; pipeline mode computes peak
load(t) as a **diagnostic** and flags any year where load exceeds the comfort
threshold, pointing at spec 04's 2→4-car consist option. No CS haircut in v1.

**Rationale (arithmetic, stated as the conservative bound).** Using a
deliberately high peak decomposition (17% peak-hour share × 0.60 direction —
spec 04 §3.1's own band is 8–10% × 0.5–0.6, i.e. ~half this; the two bases
are hereby cross-referenced, and D4 uses the conservative end): 12,000 ×
0.17 × 0.60 ≈ 1,220 pax/hr-dir against 5-min × 2-car × 150 = 3,600 — load
≈ 0.34, far below the 0.80 comfort threshold even before halving. A crowding
equilibrium in the pivot logit would be dead code priced into every draw.
Considered and rejected; revisit if any corridor's flag fires.

**Rows.** "CS haircut when load > comfort" wrapper variant, so tail exposure
is visible.

### D5 — MCPF: exposed, with λ = 1.0 as the tornado central

**Decision.** The central profile runs λ = 1.0; λ = 1.3 is a labeled
sensitivity row (and a full column in the output JSON for anyone who wants
the second-best view). λ mechanics pinned: λ applies to the **net public
funding requirement** (capex + O&M − incremental revenue), i.e. revenue
offsets at λ; user benefits are never scaled.

**Rationale (governance-audit fix).** The uncapped | ABC column pair earns
side-by-side status from spec 00's decision-metric/companion division; λ has
no gate role and belongs with the other contested price-side judgments
(discount rate, γ, SCC) as rows around one declared central. This also gives
the tornado a well-defined center, which "both are headline" did not.

### D6 — Ramp and growth: BCA-side; margin-only; the R1 tension logged honestly

**Decision.** Ramp and growth are BCA time-profile knobs. **The ramp applies
to margin components only** (`um_margin`, car-miles, incremental fare
revenue — all ∝ ΔS); `um_infra` (existing riders, who switch services at
opening) is NOT ramped. `ramp_start` is defined as a **margin-adoption
ratio**, prior U(0.6, 1.0) — support includes the no-ramp null — with an
explicit ramp_start = 1.0 row; ramp_years U(3, 7); g = 0 default with
0–1%/yr rows (growth scales all streams together — whole-market scaling is
coherent; only the ramp had the composition defect).

**Corrected relationship to R1 (governance-audit fix).** R1 (spec 02 §4.6)
retargets the ABC kernel via FY2017 measured × the 2013→2017 **system
back-trend** — a decline correction implying the 543 launched HIGHER than
FY2017 and eroded; it uses no ramp assumption. The BCA ramp prior assumes
the opposite shape (launch below steady state) and currently has **no local
support**: the observable 543 series (FY2017 4,615 → FY2019 3,739) shows no
visible ramp-up. This tension is logged per rule 3, not hidden: until
records item 1a (FY2014–16 route-level) lands and disciplines both, the R1
back-trend is measurement-anchored and the BCA ramp is a literature/judgment
prior whose no-ramp end is inside the support. When 1a lands, both consumers
update from the same fact.

### D7 — Car diversion: per-segment trip-mile masses computed in stage 2

**Decision.** Stage 2 exports **pre-pcar diverted-trip-mile masses per
car-ownership segment** (`cm_seg`, `cm_visitor`, plus the full-O-D transfer
variant); the wrapper multiplies by the exported per-draw diversion priors —
`pcar0` ~ U(0.05, 0.25), `pcar1` ~ U(0.35, 0.65), `pcar2` ~ U(0.55, 0.85),
`pcarv` ~ U(0.0, 0.30) — so the pcar rows are wrapper re-pricings, not
stage-2 reruns. Transfer-market miles use the corridor-leg distance in the
base arrays (documented undercount; the full-O-D variant bounds it).

**Rationale.** The ridership model knows what a flat alpha cannot: which
segments the new riders come from and how far they ride. A 0-vehicle
household's new transit trip does not remove a car from the road. Quantities
from the model, prices from the BCA.

**Rows.** Each pcar prior lo/hi (wrapper); transfer-full-OD; rebound (D8).

### D8 — Externality prices, carbon, rebound; the blend for delta-quantities

**Decision (prices).** Congestion / accident / local-pollutant rates become
engine parameters with lo/hi rows. **The emissions rate is re-specified as
local-pollutants-only (~0.7–1.0 ¢/mi default)** — the inherited 1.5 ¢/mi is
Parry–Small's combined "CO2 + local" figure, and keeping it beside an
explicit SCC line double-counts embedded carbon. Carbon:
`car_miles × (gCO2_per_mi / 1e6) × SCC × carbonFactor(t)` with
`carbonFactor(t) = (1 + carbon_growth)^t` (TBCR's existing definition,
default carbon_growth = 0, row at 2%/yr); SCC central $50/t, rows 0 / 190.
A **traction-power carbon debit** (grid gCO2/car-km × SCC) enters E5 with a
zero row (clean-grid case) — crediting avoided car CO2 while ignoring the
metro's own traction carbon would be asymmetric. A **rebound knob** (fraction
of diverted car-miles re-filled by induced traffic) applies to the congestion
component only, rows 0 / 0.5 / 0.8, default 0 with the row making the
baked-in-zero visible; accident/local-pollutant relief survives re-fill
differently (new trips emit too) — documented.

**Decision (non-work blend — feasibility fix).** The ridership ratio blend
`ws·r + (1−ws)(1+κ(r−1))` pivots around base 1 and must NOT be reused for
delta quantities. For benefits and car-miles:
`b_blend = ws·b_work + (1−ws)·κ·b_nw`, where `b_nw = b_work` except on the
`nonwork_short` rerun path (which supplies its own tilted `umS/denS`; both
`system_response` call sites — model.py:322 and :332 — are updated for the
extended return signature). The blend is applied **by the wrapper** from the
exported pre-blend arrays and per-draw ws/κ, making the κ→1 row free.

**Logged deferral (B1-scope, per rule 3).** The `nonwork_short` rerun today
DISCARDS its tilted welfare / car-mile / fare streams — model.py drops them
with `_`, keeping only `numS/denS` for the ridership ratio. So `b_nw = b_work`
is the ONLY blend input currently available; the tilted `umS/cmS/fbS` are not
threaded through. This is a deliberate deferral: the `nonwork_short` export is
an "additional export design point" (§3), not a base stream, and no consumer
exists until W1. Revisit if that design point is ever built — thread the
tilted streams through `system_response`'s extended return at that point.

### D9 — Labor-market channel: dropped with reasons, bounded by a row (NEW)

**Decision.** TBCR's Parry–Bento labor line (5% of CS) is set to 0 in
pipeline mode. **Rationale, logged:** (a) when the γ row is active, WEI-style
agglomeration calibrations already contain labor-supply effects — a separate
line double-counts; (b) the channel interacts with λ (both stem from the
labor tax wedge), so carrying both at independent defaults compounds a
second-best correction. **Row:** "labor +5% of time-based CS", with a note
that it must not be read jointly with the γ rows.

### D10 — CS measure: exact logsum, not rule-of-half (NEW)

**Decision.** The headline welfare accumulator uses the **exact per-sub-cell
binary-logit surplus**: per capita `ΔCS = ln(1 + S0·(e^dv − 1))` in utils
(reusing the pivot's already-computed clipped `e` array), summed with the
same P weights as ridership; the infra/margin split for D6 is
`um_infra = Σ P·S0·dv`, `um_margin = um_total − um_infra`. Rule-of-half
becomes a sensitivity row.

**Rationale.** Each sub-cell IS a binary logit with fixed outside utility —
the exact measure is one line and native to the ridership model (allocation
rule), while ROH is a trapezoid that systematically overstates positive CS
at low base shares (+1.3% at dv=0.5, +4.7% at dv=1.0 for S0=0.1 — the
transit shares here are 0.02–0.15) and overstates fold's short-trip losses.
It also stays exact under the variety_logsum / small-theta toggles.

### Presentation principle (governance-audit fix)

One named **central profile** anchors everything: λ=1.0, γ=0, SCC=$50,
mohring=0, labor=0, rebound=0, VOT central, discount 4% flat, ramp central,
LOW and US-TYPICAL capital both shown (spec 04's band convention). The
headline table is fold/retain rows × uncapped|ABC columns × cost-band pair;
the tornado runs one-at-a-time around the central profile; the full
{scenario × treatment × λ × band} cross lives in the output JSON only.
Stated principle for knob placement: **column status is reserved for spec-00
decision-metric pairs; every price-side judgment is a row around the
central.** γ=0 central keeps literature uplift out of the headline (the γ
rows 0.15/0.25 apply to the **no-ASC time-based** user-benefit stream —
marking up a comfort premium with a factor calibrated on time savings would
add phantom benefit; "γ on ASC-inclusive CS" is itself a labeled row).
Per spec 05 §4.3, the Flyvbjerg optimism-bias annotation is printed beside
the BCA headline table, same convention as the ridership charts.

## 5. Stage-2 work items (this repo)

Regression gate for all of B1–B4: `results_harbor.json` and
`results_streetcar.json` headline percentiles **byte-identical** before/after.
Verified safe against the actual code (feasibility audit): `draw_params`
consumes its child stream in dict insertion order (model.py:116–121), so the
5 new PRIORS keys (`vot_behav`, `pcar0/1/2/v`) are appended AFTER all existing
keys; the accumulators consume no rng; `run()`'s anchor/jitter/blend stream is
the independent `spawn(2)[1]` (model.py:156); `point()` auto-pins new keys
with no kwarg collisions.

### B1 — welfare accumulators (`scripts/model.py`)

Inside `market_terms` (model.py:268–292), alongside the existing reductions
(shapes per the feasibility audit: `dv` (n, C) where C = bins·Q after the
`np.unique` merge, `pnew` 2-D before its `[:, :, None]` expansion, `dists_e`
(C,), `P` (n, C, seg), `S0` (n, 1, seg)):

```python
# spec 06 B1/D10: exact logsum CS, infra/margin split, in utils
cs_cell   = np.log1p(S0 * (e - 1.0))            # e = pivot's clipped exp(dv), (n,C,seg) after broadcast
um_total  = (P * cs_cell).sum(axis=(1, 2))
um_infra  = (P * S0 * dv[:, :, None]).sum(axis=(1, 2))
um_margin = um_total - um_infra
```

The no-ASC counterfactual (D1) and no-fare welfare variant (D3) are parallel
`combine()` passes with the relevant additive term zeroed — same quadrature,
same rng-free structure — producing `um0_*` (own pivot `S1_noasc`) and the
`fare_burden` dollar stream `((P·(S0 + 0.5·(S1−S0))·Δfare_chosen)).sum` (zero
at flat fares). Notes: raw-vs-clipped dv consistency follows the pivot (the
±20 clip is numerically irrelevant here and keeps one `e` array); um is NOT
multiplied by `pnew` (benefits accrue to all corridor transit riders; `pnew`
only splits boardings); negative dv (fold short trips) flows through signed.
Thread the accumulators through `system_response` with the same TOD `wgt`
and fx/fv scaling as `num` — **both call sites** (model.py:322 and :332,
the `nonwork_short` rerun) updated for the extended return. Person-scale in
`run`: `minutes = anchor · (um / den) / |bivt|`; export PRE-BLEND (D8).

Verification: (a) G1 byte-identical headline; (b) two-cell synthetic corridor
hand-check (spreadsheet-reproducible) for exact-logsum, infra/margin, and
no-ASC values; (c) sanity: `minutes / total` (corridor-total denominator —
per the audit, dividing by newline-only overstates retain) ≈ per-rider
minutes, expected O(5–15), reported against TBCR's old hand-set 12-min
slider (gate G3: disagreement is a finding, not an error to tune away).

### B2 — diverted-trip-mile masses (`scripts/model.py`)

Same loop; per-segment, PRE-pcar (D7):

```python
dcm = (P * (S1 - S0) * dists_e[None, :, None])       # (n, C, seg) signed trip-miles
cm_seg = dcm.sum(axis=1)                              # (n, seg); order matches car_frac: 0/1/2+ veh
```

Visitor market accumulates its own `cm_visitor`; the transfer market is
scaled by fx like `num` and additionally accumulated at full O-D distance
into `cm_seg_fullod`. Verification as B1 (byte-identical, synthetic
hand-check, magnitude sanity vs newline × plausible mi/trip).

### B3 — fare term (`scripts/model.py`, `config/*.json`)

`PRIORS["vot_behav"] = (10.0, 22.0, "tri")` and the four pcar priors appended
last. `DEFAULT_FARE` module constant (OCTA flat fare, documented);
`fare_base = cfg.get("fare_base", DEFAULT_FARE)`;
`svc_fare = svc.get("fare", fare_base)` read where `util()` already receives
the service dict (model.py:203). Gate: with no config fares set, all outputs
byte-identical — including the backtest/ABC path, which inherits the default.
Rows: vot_behav lo/hi (0.0% until a fare sweep exists — visible per rule 2).

### B4 — ABC weight export + exporter (`scripts/reweight_abc.py`, NEW `scripts/bca_export.py`)

Extract the kernel as `abc_weights(pred, kernels)` where `pred` is the
per-draw backtest prediction (computed ONCE, as today at reweight_abc.py:47–49)
and `kernels` is a list of `(label, mu, sigma)` — single-entry today,
ready for the spec 02 §4.4 joint multi-experiment kernel without interface
churn. `bca_export.py` runs `run()` per design point with shared `params`,
writes the §3 schema (+ `--seed-check` companion at seed+1 for G4). Gates:
`reweight_abc.py` output unchanged; export round-trips (weighted P50 matches
`abc_harbor.json` to 4 significant figures).

## 6. Engine work items (transit-benefit-cost, v3 spec in that repo)

- **E1 — pipeline mode.** `lifecycleCorePipeline(params, quantities)` taking
  per-draw scalars `{umInfraMin, umMarginMin, fareBurdenDay, carMilesComponents,
  fareRevDay, baseOpexAvoidedYr, R0}`. Annual benefits =
  `[(umInfra + ramp_margin(t)·umMargin)·(VOT/60)·(1 + mohring_coef)·(1 + γ_on_time_base)
  − fareBurdenDay + carMiles_eff(t)·(c_cong·(1−rebound) + c_acc + c_emis_local
  + (gCO2_per_mi/1e6)·SCC·carbonFactor(t))] · eq_days / 1e6` $M — note the
  grams→tonnes `/1e6` is explicit and separate from the dollars→$M `/1e6`
  (feasibility blocking fix). Margin-only ramp (D6); labor term absent (D9);
  γ applies to the no-ASC time-based stream (presentation principle).
- **E2 — parameterize + boundary hygiene.** `eq_days`, externality rates,
  gCO2_per_mi, SCC, carbon_growth, rebound, build_years, O&M params all added
  to RANGES with bounds (parseState strips unknown keys — without this the
  pipeline params silently vanish); `mohring_coef` range floor lowered to 0
  (currently clamps to 0.05, which would silently reinstate a 5% markup over
  D2); the wrapper's input path enforces the assets `life ≥ 5` guard whether
  or not it routes through `parseState` (capexSchedule infinite-loops on
  life ≤ 0).
- **E3 — construction period.** `build_years` (default 5, judgment — row at
  4/7): capex classes spread over years 0..B−1, opening (ramp, benefits, O&M)
  at year B; residuals measured from in-service dates.
- **E4 — avoided base O&M + incremental revenue.** Per-scenario avoided cost
  from `routes_removed` × `rev_hours_weekday` × an **avoidable-cost rate**
  knob (prior spanning marginal→fully-allocated $/rev-hr; NTD full allocation
  overstates what folding two routes actually sheds — row at the marginal
  end). Revenue = incremental system fare revenue per D3, offsets subsidy at
  λ per D5.
- **E5 — GoA4 O&M.** `fixed_yr + var_per_car_km · car_km_yr`, with
  `car_km_yr = eq_days · Σ_periods 2 · route_km · (60/headway_p) · hours_p ·
  cars_per_train` — sharing route_length/headway/consist inputs with spec 04
  §3.1 (which sizes the FLEET; it does not itself produce car-km — the
  feasibility audit corrected this citation). Priors anchored wide to
  SkyTrain/Copenhagen/NTD benchmarks; traction-carbon debit per D8.
- **E6 — tests.** The full engine suite as of the landing commit (160 at spec time) stays green (endogenous mode untouched).
  Pipeline-mode anchor **with the comparator explicitly configured**
  (economics-audit fix): `lifecycleCore` run with mohring_coef=0, labor=0,
  reliability off, γ=0, λ=1, quantities constructed from us_lrt's demand-side
  streams — then pipeline mode must match within 0.5%; without that
  configuration the gate is unpassable (~20% apart by construction).
  Structural invariants (BCR↓ in discount rate, residual↑ with life,
  margin-ramp ⇒ early-year benefits ≥ all-ramped variant) re-asserted.

## 7. Wrapper and presentation (W1–W2)

- **W1 — `bca-pipeline.mjs`** (transit-benefit-cost repo, node ≥ 22): reads
  the §3 export + a corridor cost-profile JSON (spec-04 LOW / US-TYPICAL),
  loops draws through `lifecycleCorePipeline` (base loop ~1–4 s at 40k;
  the tornado reuses cached per-draw component PVs where rows are pure
  re-pricings — λ, SCC, VOT, γ, pcar, κ — and re-loops only for structural
  rows, keeping the full deliverable in tens of seconds, not minutes).
  Output `outputs/bca_<corridor>.json`: central-profile headline
  (fold/retain × uncapped|ABC × LOW/US-TYPICAL: NPV & BCR P10/50/90,
  P(NPV>0)), the full cross, and the tornado. Tornado rows (complete list,
  closing the G5 audit): VOT lo/hi, non-work 0.7×VOT, vot_behav lo/hi,
  γ 0.15/0.25 (time-base), γ-on-ASC-inclusive, λ=1.3, SCC 0/190,
  car-fleet gCO₂/mi lo/hi (`gco2_lo`/`gco2_hi` — the E2 emissions-rate row,
  wrapper-artifact rows; this line closes the latent G5 gap where §7 listed
  SCC/carbon but not the gCO₂/mi rate the carbon term multiplies),
  carbon_growth 2%, traction-carbon 0/grid, rebound 0.5/0.8,
  externality-rate lo/hi (each), pcar set lo/hi, transfer-full-OD, κ→1,
  no-ASC CS, ROH-instead-of-logsum, reliability-restored bound,
  mohring 0.09, labor +5%, discount 2/3/7% + declining schedule,
  ramp_start 1.0 (no-ramp) and lo, ramp_years lo/hi, growth 1%,
  build_years 4/7, avoidable-cost marginal end, O&M prior lo/hi,
  avg-fare-per-incremental-boarding lo/hi, ABC σ350/σ800 (weights already
  exported), crowding-haircut variant, eq_days 300/330.
  Where a corridor lacks `abc_weights` (streetcar pre-launch), the ABC
  columns are omitted with the reason printed.
  **LANDED 2026-07-15 (tbc `aa16e0d`, `outputs/bca_harbor.json`):** headline
  **NPV −$4.17B / PV-BCR 0.075** (fold, ABC-weighted, US-TYPICAL band, P50);
  every scenario × treatment × band is deeply negative (P(NPV>0)=0). The
  ROH and fare-sweep tornado rows are un-blocked by the W1 rider batch's
  `um_roh_*` / `fare_receipts_*` export streams (this repo, same landing).
- **W2 — charts.** Extend `make_charts.py`: BCR/NPV interval chart (rows =
  scenario × treatment × band) with the spec 05 Flyvbjerg annotation in the
  subtitle, and the BCA tornado, same style as the ridership charts.

## 8. Sequencing

1. **B1–B4 can land now** — pure additions, gated on byte-identical headlines
   (G1 verified feasible against the code; nothing in the R-queue conflicts).
2. **E1–E6 in parallel** (own repo, own tests).
3. **W1–W2 and any quoted BCA headline wait for R1 and R6.** Precisely:
   R6 moves dV (hence all exported quantities); R1 moves the ABC posterior
   and therefore every ABC-weighted statistic (per-draw dV is untouched
   under CRN). Running W1 first would mean restating the BCA headline within
   days. The existing R-queue order is unchanged.
4. The spec 00 §3 amendment (gate-2 status, §1) rides in W1's landing commit.

## 9. Validation gates

- **G1 (rng discipline):** after B1–B3, `results_harbor.json` and
  `results_streetcar.json` headline percentiles byte-identical; new PRIORS
  keys appended last; accumulators draw nothing. (Mechanism verified:
  dict-order consumption at model.py:116–121; independent second stream
  at :156.)
- **G2 (engine):** the full engine suite as of the landing commit (160 at spec time) green; configured pipeline-mode anchor within
  0.5% (per E6); invariants re-asserted.
- **G3 (cross-model):** derived per-rider minutes (corridor-total
  denominator) reported against TBCR's old 12-min slider; disagreement is a
  finding.
- **G4 (stability):** seed-drift on ABC-weighted BCR P50 ≤ 2%, computed from
  the seed+1 companion export (B4).
- **G5 (rule 2):** every knob introduced by this spec appears in W1's tornado
  list (§7) in the same commit that introduces it.

## 10. Known issues opened by this spec (README log entries)

1. Behavioral VOT ≠ social VOT — deliberate, both exposed; rows not to be
   read jointly at opposite extremes (D3).
2. Transfer-market diverted car-miles undercounted at corridor-leg distance —
   full-O-D variant row bounds it (D7).
3. Growth scales all quantity streams proportionally (coherent); the ramp is
   margin-only by construction (D6) — the earlier all-streams linear ramp had
   opposite-signed biases by stream and was rejected at review.
4. R1's back-trend retarget and the BCA ramp prior currently pull opposite
   directions on the 543's launch shape, and the 543 series shows no visible
   ramp-up; records item 1a disciplines both when it lands (D6).
5. γ, SCC, and the pcar/O&M priors are literature-informed knobs with
   zero/lo rows — allowed as exposed priors; filters remain rejected.
6. Crowding deliberately out of stage 2; diagnostic flag only; D4's load
   arithmetic uses a conservative peak decomposition ~2× spec 04 §3.1's —
   cross-referenced, conclusion robust to either.
7. The single-VOT-across-purposes choice and the κ-blend's quantity-not-
   valuation role are named judgments with rows (D3, D8).
8. Avoided-cost rate: fully-allocated NTD $/rev-hr overstates avoidable
   cost — knob spans marginal→allocated (E4).
