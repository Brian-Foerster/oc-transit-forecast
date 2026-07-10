# Spec 05 — Stage 2 Extension: New Modes & Reference Classes

(streetcar cold-start · elevated ALM · optimism-bias prior)

Status: ADOPTED 2026-07-09 (user instruction: implement) · Builds on spec 02
(pivot logit). Method detail: README.md; internals: scripts/model.py.
Known-issue refs: README issues 14 (ASC transportability) and 15
(matured-vs-launch calibration target).

## 1. Role and non-role

Extends the Stage-2 pivot to (a) corridors with zero ridership history of
their own and (b) non-BRT modes (at-grade streetcar, elevated automated
light metro / ALM), and replaces the display-only BRT `REFERENCE` string
with a mode-appropriate, basis-tagged reference set plus an outside-view
accuracy prior.

Non-role, unchanged from spec 02 and inherited verbatim: the pivot
forecasts the response of the existing travel market only. Market creation
(induced demand, land-use change, network redesign beyond the corridor
local) stays out of scope by construction and must not be silently imputed
to it. Both parts of this spec make that boundary more load-bearing, not
less — see §3.3 and §4.4.

Nothing here gates or filters the mechanism. Per standing preference,
reference classes remain DISPLAY-ONLY: printed beside the forecast, never
used to cap, reweight, or filter draws.

## 2. Motivation

Two triggers:

- **Cold-start question (OC Streetcar).** Can Stage 2 forecast a line with
  no boardings to extrapolate? Yes — by design; the pivot never uses the
  forecast line's own history (§3.1). The work is a config +
  anchor-derivation exercise, not a model change.
- **Mode pivot (2026-07-08).** The Harbor finalist was re-specced from
  arterial rapid transit to elevated ALM. The current `REFERENCE`
  (Twin Cities / UW / Cleveland, all arterial BRT) is now a floor, not a
  matched class, and mixes three measurement bases (§4.1). The streetcar is
  the opposite mode error: at-grade rail sits below the BRT numbers. Both
  need a reference set keyed to mode.

## 3. Part A — Cold-start corridors (OC Streetcar)

### 3.1 Why "no ridership" is not the binding constraint

The pivot is `forecast = anchor x base-share-weighted ratio`, where the
ratio depends only on the change in level of service versus a base service.
Absolute market size and unobserved local constants cancel. The forecast
line's own boardings never enter. What the method needs is not streetcar
data but an existing parallel service to anchor to. So the cold-start
problem reduces to: identify the anchor, and defend it (§3.3).

### 3.2 The line (facts, for the config)

OC Streetcar: 4.15 mi, Santa Ana Regional Transportation Center (SARTC) to
the Harbor/Westminster transit hub in Garden Grove, ~10 stops, running the
Pacific Electric ROW plus 4th St / Santa Ana Blvd; ~10-15 min headway,
~22 min end-to-end (avg ~11 mph). Revenue service pushed to ~2027 (was
targeted spring 2026). OCTA official projection ~6,000-7,300 daily; CEO has
more recently floated ~5,000. West terminus feeds the Harbor Blvd bus
corridor (OCTA's busiest) — i.e. it physically touches the spec-02 Harbor
study corridor at one point (§3.5).

### 3.3 Anchor derivation (the hard part)

Pattern follows `anchor_from_apc.py` x `route43_share.py`: measured
route-level boardings x corridor share. But the streetcar anchor is WEAKER
than Harbor's and the config note must say so:

- Harbor had a clean co-located pair (Rt 43 local + 543 rapid on the same
  street), so the new service diverts a measurable existing market.
- The streetcar largely follows a diagonal greenfield ROW no current bus
  tracks closely. More of its ridership is genuinely new access (out of
  scope by construction — upside risk, per §1), not diverted boardings.
  Anchor candidates: OCTA locals serving downtown Santa Ana / 4th St /
  Santa Ana Blvd, plus the SARTC (Metrolink/Amtrak) and Harbor transfer
  markets. Lean harder on the transfer market (`tau`) than Harbor did;
  widen the anchor interval.

Implementation: `scripts/anchor_streetcar.py` computes, for every OCTA
route, the share of its GTFS shape inside the streetcar corridor buffer,
multiplies measured FY2019 weekday boardings by that share for the
PARALLEL routes (the crossing routes enter via the transfer market
mechanically), and prints the derivation. `config/streetcar.json` carries
the result with the weakness note. Field names follow the ACTUAL config
schema consumed by build_corridor.py/model.py (anchor_low/high,
services_base, service_new), not the sketch in the proposal.

### 3.4 Rail-ASC transportability (Issue 14, sharpened)

The ASC posterior (0.06/0.11/0.16) is calibrated to a bus overlay (543). A
streetcar is a rail-class product; the bus-calibrated constant is a
conservative floor. Use the widened ASC premium bracket already introduced
for the metro scenario ({1.0, 1.5, 2.0}) and report it as a band, not a
point. Honest tension to print, not bury: a street-running streetcar is
SLOWER than the rapid bus, so the in-vehicle-time term may be ~flat or
negative; most of any uplift then rides on the ASC — exactly the parameter
with the least local support. The utility structure already prices
speed/headway/walk explicitly, so this shows up mechanically rather than
being asserted.

### 3.5 Calibration and the feedback loop

No prior streetcar natural experiment exists in OC, so there is no local
ABC target for a rail-class ASC. Interim: borrow the 543-calibrated
behavioral params (bivt/ovt), treat the ASC as bracketed (§3.4), and print
reference-class analogs (Part B) beside the result. Once the streetcar
opens (~2027) and stop-level APC flows, it becomes the rail-class ABC
target the model currently lacks (addresses the gap behind Issue 14).
Because it meets the Harbor corridor at Harbor/Westminster, that data also
sharpens the spec-02 Harbor forecast — the `records_request_draft.md` CPRA
request is extended to cover it post-launch.

### 3.6 Cross-check

Sanity-check the pivot output against OCTA's official ~5,000-7,300 daily
band, the way spec 02 cross-checks Harbor against the TSP study. A pivot
result far outside that band is a finding to report (anchor or ASC
mis-set), not to force.

## 4. Part B — Reference-class overhaul

### 4.1 Current state and defect

`REFERENCE` (scripts/model.py) is a hardcoded string printed beside the
implied uplift: `Twin Cities +33% | UW +35% | Cleveland HealthLine +78%`.
It affects nothing (display-only) — the question is whether it is a fair
yardstick. It is not, for three reasons: the three numbers sit on different
bases (Cleveland = fold/replacement, 5-yr matured, confounded by a $200M
rebuild + Univ Circle TOD; Twin Cities A Line = retain/overlay, first-year;
UW = a 2017 study average across BRT corridors, not one corridor); the +78%
is the matured high end while Cleveland's launch year was ~+40% (Issue-15
matured-vs-launch problem, recurring here); and the whole class is arterial
BRT while the finalist is now elevated ALM.

### 4.2 Relabel (adopted)

Replace the string with structured entries tagged `regime`
{fold, retain, study} x `horizon` {launch, matured}, print each beside the
matching uplift (`ratio_fold` vs `ratio_retain`), flag whether each analog
falls inside the model's P10-P90, and print the study-average once as an
overall gut-check. Cleveland split into launch (+40%) and matured (+78%)
rows; Twin Cities set to the canonical first-year ~+30%. Stays
display-only.

### 4.3 Better classes for elevated ALM (three tiers)

"Better" depends on the quantity benchmarked. Three tiers, each labelled
with what it can and cannot inform:

1. **Mode-matched grade-separated driverless metros** — informs absolute
   ridership and forecast accuracy, NOT a clean corridor uplift (these open
   on new alignments, not as a bus replacement on the same street).
   Anchors: Vancouver Canada Line (2009; beat its ~100k/day target by
   2010; 2019 ~150k vs a 120k forecast — optimism-confirming pole);
   Montreal REM South Shore (2023; ~30k/day projected, early counts ~24k —
   cautionary launch pole). Candidate to add once verified: Honolulu
   Skyline (2023), a standalone-stub underperformer.
2. **Rail-over-bus "mode bonus"** — the empirical anchor for the
   {1.0, 1.5, 2.0} ASC bracket (Issue 14), better matched to the constant
   than any BRT-over-bus delta. Cleanest local-flavored instance: the
   Canada Line displacing the 98 B-Line. Pairs with §3.4 for the streetcar
   and with the metro scenario for Harbor.
3. **Optimism-bias / accuracy prior** — the most mode-matched to what this
   repo exists to do (honest uncertainty). Flyvbjerg, Holm & Buhl (2005,
   JAPA 71(2), 131-146; 210 projects): 9 of 10 rail passenger forecasts are
   overestimated; average overestimation ~106% (actual ~51% below
   forecast); 84% of rail forecasts wrong by more than +/-20%; 72%
   overestimated by more than two-thirds. An outside-view prior on the
   whole forecast, printed beside the headline. It pulls OPPOSITE to
   tier-1 BRT-uplift intuition — the honest resolution is wide intervals,
   which the model already reports. Flyvbjerg's prescribed cure is
   reference-class forecasting, which the tagged structure operationalizes.

### 4.4 Two ALM selection cautions (both have model hooks)

- **Network/feeder dependence.** The metros that overshoot (SkyTrain,
  Canada Line) sit in a feeder network; those that undershoot at launch
  (REM South Shore, Honolulu) open as standalone stubs. Implication: `tau`
  (transfer market) should carry more weight for a grade-separated line
  than it did for the 543 overlay; the existing tau-low / no-transfer
  sensitivity rows double as the standalone-launch discount.
- **Stop-spacing walk tradeoff.** Grade separation buys speed/reliability
  (larger ASC) but forces ~1-mi stops, shedding the local's 0.25-mi walk
  market. The rider-position walk quadrature already prices this, so ALM
  references pair with the FOLD scenario (a metro rarely runs under a
  retained parallel local), not retain.

### 4.5 Preference guard

Tiers in §4.3 are printed, never applied. The optimism-bias prior in
particular is an accuracy annotation, not an envelope filter on draws —
this respects the standing decision against reference-class filtering
while still surfacing the outside view. If anyone later wants the in-band
flag (§4.2) to mean more, compare against the backtest-calibrated band
from `reweight_abc.py`, not the uncapped `res`.

## 5. Inputs / outputs

New / changed:
- `config/streetcar.json` (new; §3.3) + `scripts/anchor_streetcar.py`;
  `build_corridor.py` gains `corridor_waypoints` (explicit polyline)
  support, since no GTFS route traces the PE ROW.
- `scripts/model.py`: `REFERENCE` becomes the tagged object (§4.2) with
  the three tiers (§4.3); print block updated; optional `cross_check`
  config block printed beside the headline (§3.6).
- `outputs/results_streetcar.json` (+ `abc_streetcar.json` post-launch
  only), charts.
- `outputs/records_request_draft.md`: extended to cover streetcar APC
  post-launch (§3.5).

## 6. Open questions / risks

- Streetcar anchor identity is unresolved until derived (§3.3) — the
  greenfield ROW means no single parallel local carries the corridor; the
  derived anchor may be dominated by transfer + downtown-local markets,
  with a large out-of-scope new-access residual. Main threat to a
  defensible number; report the anchor note prominently.
- Rail ASC for an at-grade slow streetcar is genuinely uncertain and may
  differ from the grade-separated ALM premium — the metro bracket is
  BORROWED for the streetcar and flagged as such.
- Tier-1 metros lack a clean uplift basis; resist backing out a
  pseudo-uplift — keep them in the absolute / accuracy columns only.

## 7. Done-when

- [ ] `config/streetcar.json` committed with a derived anchor + note.
- [ ] Streetcar pivot runs, output cross-checked vs the ~5,000-7,300 OCTA
      band (§3.6); anchor/ASC assumptions printed, not buried.
- [ ] `REFERENCE` relabeled (§4.2) and extended to the three tiers (§4.3);
      print block matches; nothing filters draws (§4.5).
- [ ] Optimism-bias prior printed beside every headline.
- [ ] Post-launch hook noted: streetcar APC -> rail-class ABC target,
      feeding both this line and the Harbor forecast (§3.5).

## Sources (paraphrased; for the estimator, not the model)

- OC Streetcar scope / schedule / projection: OCTA project pages and
  contemporaneous reporting (opening slip to ~2027; ~6,000-7,300 daily,
  CEO ~5,000).
- Vancouver Canada Line / SkyTrain ridership vs forecast: Canada Line and
  SkyTrain (Vancouver) encyclopedia entries.
- Montreal REM ridership vs projection: REM entry + McGill TRAM
  before-and-after progress report; CDPQ Infra ridership studies.
- Rail forecast optimism bias: Flyvbjerg, Holm & Buhl (2005), "How
  (In)accurate Are Demand Forecasts in Public Works Projects? The Case of
  Transportation," JAPA 71(2), 131-146.
