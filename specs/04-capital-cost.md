# Spec 04 — Capital Cost Module (elevated automated light metro)

Status: DRAFT · 2026-07-08 · Mode decision (user, 2026-07-08): **elevated
automated light metro, REM-class (GoA4 driverless, 4-car Metropolis
basis, 1-mi stations)**. Core rate card: `costs/metro_cost_model.xlsx`
(user-supplied, REM-calibrated, constant 2026 US$, intentionally
aggressive — used as the LOW scenario, see §3).

## 1. Role and non-role

Produces per-finalist capital cost bands for gate 2 (comparison) and the
finalist evaluation (cost-effectiveness reporting). It prices ONE mode;
if BRT alternatives re-enter the study, they need a separate rate card —
this module supersedes the old "route-miles x lane-treatment" cost proxy
(spec 00 §3) for the metro mode. Costs never combine with ridership into
a composite score (governance); cost-per-rider is reported as a ratio
with both numerator and denominator bands shown.

## 2. Core model (adopted as-is from costs/metro_cost_model.xlsx)

Linear MECE structure, §4 of the sheet:

    Total = markup x [ Fixed + a*route-km(+ elevated add-on) 
                       + b*stations + c*cars ]

with current rates (2026 US$M): elevated viaduct 23/km; track 4/km;
traction 8.5/km; CBTC wayside 4/km; utilities 3/km; LEAN elevated
station 22 + PSD 2.3 + telecom 2.3 + AFC 1.7 per station; OCC 28;
depot 125 fixed; car 3.4 + stabling 2.3 + spares 0.5 per car; markups
10% design + 10% contingency. Sheet's own sanity band: 100-125 $M/km.

## 3. Additions (the assumption sets the sheet does not carry)

**3.1 Fleet size becomes DERIVED, not input.**

    trainsets_peak = ceil( cycle_time / headway_peak )
    cycle_time     = 2 * route_length / v_avg * (1 + layover_frac)
    cars           = trainsets_peak * cars_per_train * (1 + spare_frac)

- v_avg from the derived-speed model (spec 02 §4.9, grade-separated
  variant): cruise 70-90 km/h prior, dwell 20-30 s, no signal delay.
  At 80 km/h cruise / 25 s dwell / 1.6-km spacing: ~47 km/h ≈ 29.5 mph —
  independently validates the 30-mph config value.
- layover_frac 0.12-0.18; spare_frac 0.10-0.15.
- **Consist policy (parameterized, adopted 2026-07-08):** capital cost
  keys on the PEAK consist only — GoA4 coupling makes time-of-day train
  shortening an operating decision, not a purchase decision, and the
  required demand precision is low (a +/-50% error on the ~1,000-pphpd
  peak-flow estimate does not flip the conclusion against 3,600 pphpd of
  2-car capacity). Model as:
  - `peak_consist` parameter c in {2, 4}; capacity check = c x 150 pax x
    (60/headway_min) per direction-hour vs stage-2 peak load (daily
    boardings x peak-hour share 0.08-0.10 x max-load-point factor
    ~0.5-0.6, directional). **Default: c = 2** (resolves Q1).
  - **Priced expansion option:** 2 -> 4 later = additional cars at the
    sheet's per-car rate (3.4 + 2.3 + 0.5 = $6.2M; ~$7.4M with markups;
    ~ +$180M for the Harbor fleet), reported as a separate line so the
    option's cost is visible, CONDITIONAL on the next bullet.
  - **Option-preserving envelope:** platforms stay 76 m (already the
    sheet's LEAN basis) AND the depot land envelope + stabling-road
    layout are dimensioned for the 4-car fleet on day one — the modest
    premium now vs an expensive retrofit is the one place a 2-car
    decision could otherwise paint the line into a corner.
  - The hard-to-forecast quantity (30-yr demand growth) is handled by
    BUYING THE OPTION, not by sharpening the forecast.
  Illustrative Harbor fleet: 12 trainsets x 2 cars x 1.12 ≈ 27 cars
  (vs 32 in the sheet as shipped; 4-car policy would be ~54).

**3.2 Two-scenario rate band.** The sheet is the **efficient/low**
scenario (its markups are efficient-agency 10%+10% vs Metrolinx-class
17%+19%, which the sheet itself cites). Add a **US-typical** scenario:
soft costs 17%, contingency 19% (early-stage FTA practice is higher
still), and a delivery-environment factor on civil items — 1.5-2.0x on
viaduct/stations (Transit Costs Project: US elevated comps), 3-5x on any
bored tunnel (not currently in scope). Report LOW and US-TYPICAL side by
side, assumptions written down; never present the low number alone.
Ranking caveat: aggressive-but-uniform rates cancel in ranking EXCEPT
between corridors with different tunnel/elevated shares, where the
non-uniform aggressiveness biases the comparison — flag any finalist
pair whose alignment mixes differ materially.

**3.3 Per-corridor quantity sheet.** For each finalist: elevated vs
at-grade km split; station count (from stage-2 spacing); depot count and
CANDIDATE SITE (a 15-20-acre parcel in built-out OC — siting is a real
constraint, feeds 3.4); and a **special-structures line** (below).

*Special structures — rationale.* The $23M/km viaduct rate is calibrated
on REPETITIVE guideway (~30-40 m spans, ordinary piers, workable ROW).
At freeway, river, and railroad crossings repetition breaks: long spans
(100-200+ m; balanced-cantilever / steel truss / cable-stayed), taller
piers, heavier foundations, staged construction over live traffic, and
third-party agency processes (Caltrans for I-5 and SR-22, flood-control
authorities for the Santa Ana River channel, BNSF for the Fullerton
terminal approach — railroads are the slowest and costliest to build
over). Each crossing costs a large multiple of the per-km rate; a purely
linear model silently flatters barrier-laced corridors over clean ones,
so this line exists for gate-2 COMPARABILITY. Count x unit cost, band
30-80 $M per major crossing (low = simple channel span, high = wide
freeway interchange under traffic), FLAGGED for replacement by an
engineering reference. It prices the structure only — alignment
compromises a crossing forces (tight radii, displaced stations, e.g.
threading the I-5/Harbor interchange near the resort) are noted per
corridor as unpriced risk.

**3.3b Street expenses (elevated-in-arterial segments; adopted
2026-07-08).** Two items, per km of elevated guideway in a live
arterial (zero for genuinely clean ROW):
- **Utilities diversion — segment-dependent, LOW rate is a floor.** The
  sheet's $3M/km carries its own caveat ("~0 in clean ROW; high in old
  CBD"). Harbor is the second case: a century of water/sewer/storm/gas/
  fiber under a mature arterial, with drilled-shaft pier foundations
  every ~35 m in the median. REM's calibration (rail ROW, highway
  medians) underweights exactly this. Keep $3M/km in LOW; use
  $8-15M/km for dense segments (Anaheim resort district, downtown
  Fullerton) in US-TYPICAL, with the dense-km share coming from the
  quantity sheet.
- **Street restoration & maintenance-of-traffic (NEW line — absent from
  the sheet).** Years of pier construction down a live arterial obligate
  full restoration (repave/restripe disturbed width, curb/gutter/
  sidewalk/ADA around stations, signal modifications, lighting
  relocation, median reconstruction) — typically a municipal permit
  condition — plus multi-year MOT on a ~50k-vehicle street. Rate:
  $2-4M/km LOW, $5-8M/km US-TYPICAL. The MOT *political* cost is
  unpriceable here and is mentioned in the gate memo instead.
Net effect: widens the band rather than moving the floor (~+$75-200M on
US-TYPICAL for Harbor, little change to LOW) — which is the correct
behavior as scope realism accumulates.

**3.4 Land/ROW flag (not dollars).** §6 exclusions (land, escalation,
financing, taxes) stay excluded UNIFORMLY for constant-$ comparison —
except land is not corridor-neutral: median width, station footprints,
TPSS sites and the depot parcel differ by corridor. The economic-potential
layer's parcel data (spec 00 §3, R7) double-duties as a qualitative
land/ROW flag per finalist. Any budget-facing number adds all four §6
items explicitly.

## 4. Outputs

`outputs/capcost_<corridor>.json` + gate-memo table row: route-km by
type, stations, derived fleet (policy stated), LOW and US-TYPICAL totals,
$/km both scenarios, special-structures count, land/ROW flag,
cost-per-forecast-rider shown as band/band (never a single number).

## 5. Validation gates

- Reproduce the sheet's shipped configuration exactly (20 km/16 stn/32
  cars -> its own E55) before any corridor run.
- REM outturn sanity: the LOW scenario applied to REM's quantities must
  land inside the sheet's 100-125 $M/km band (it is calibrated to REM;
  this guards regressions when rates are edited).
- Cross-check the US-TYPICAL scenario against 2+ named US elevated
  comparators (Transit Costs Project database) and record them in the
  sheet's source column, per its own convention.
- Fleet formula vs REM service plan (67 km, ~4-min peak, 2/4-car mix)
  within ~15% of REM's 212-car order scaled to line length.

## 6. Ridership-side back-propagation of the mode decision

Recorded here, implemented in the owning specs:
- **ASC transportability (spec 02 §4.5c) sharpens:** the calibration
  experiments are BUS overlays; the forward line is a rail-class
  product. Premium bracket widened to {1.0, 1.5, 2.0} on the calibrated
  ASC (a 2.0 premium returns roughly the prior midpoint).
- **Derived speed (spec 02 §4.9):** grade-separated variant — no signal
  delay, cruise prior 70-90 km/h, dwell 20-30 s; the 43/543 street
  calibration remains for the (bus) backtest experiments only.
- **Economic layer (spec 00 §3):** premium band moves from bus-class
  ~0-10% to rail-class ~5-25%, permanence-keyed (elevated guideway =
  high permanence); comparators switch to SkyTrain/Canada Line-class
  hedonics.
- **Stage 3 (spec 03):** fixed guideway is STOPS's home turf — the mode
  decision strengthens the stage-3 fit; build GTFS coded as rail mode.
- Out of scope at stage 2, unchanged: elevator/vertical-circulation
  access time at elevated stations is folded into the walk term's
  station approach; note as a refinement if station designs firm up.

## 7. Questions resolved / open

- Q1 (RESOLVED 2026-07-08): 2-car peak consist is the default, with the
  priced 2->4 expansion option and the option-preserving depot/platform
  envelope (§3.1) — flexibility is an operating decision; the option is
  bought structurally.
- Q2 (RESOLVED 2026-07-08): the 30-80 $M crossing placeholder is
  accepted as a comparability correction until an engineering reference
  replaces it (§3.3 rationale).
- Q3 (OPEN): does the depot site search belong to R7's parcel work
  (shared data) or to this module?
