# Draft: Public Records Request to OCTA

*(Prepared 2026-07-07; NARROWED the same day after route-level boardings
through FY2020-Q3 and monthly system ridership through Mar 2024 were
recovered directly from octa.net — see `scripts/anchor_from_apc.py`. The
items below are only what remains unmeasured. Submit via OCTA's public
records portal or clerk of the board.)*

---

**To:** Orange County Transportation Authority — Clerk of the Board / Public
Records

**Re:** California Public Records Act request — bus ridership data for
Routes 43 and 543

Under the California Public Records Act (Gov. Code § 7920.000 et seq.), I
request the following records, in electronic form (CSV or Excel preferred
where available):

1. **Route-level average weekday boardings** for OC Bus Route 43 and
   Bravo! Route 543 for (a) fiscal years 2014–2016 (the 543's launch ramp;
   the quarterly "Bus Operations Performance Measurements" detailed reports
   for FY2017–FY2021 are already public on octa.net) and (b) FY2021-Q3
   onward (the series stops at FY2021 online).

2. **Stop-level average weekday boardings and alightings** (APC data) for
   Routes 43 and 543, most recent available service period, ideally split by
   time-of-day period (peak / midday / evening).
   If a **systemwide** extract (all fixed routes, same fields) is no harder
   to produce, that broader version is preferred — it would additionally
   ground catchment-level validation for a county-wide corridor screen
   (stage 1 of the same analysis), not only the two corridor routes.

3. From the **most recent systemwide on-board / customer survey**: the share
   of riders whose one-way trip involves a transfer between routes, and, if
   tabulated, transfer rates for riders boarding Routes 43 or 543.

4. *(post-launch, ~2027)* **OC Streetcar stop-level average weekday
   boardings and alightings** (APC), monthly from revenue-service start,
   plus transfer counts at the Harbor/Westminster and SARTC termini. This
   becomes the first rail-class calibration target for the corridor models
   (spec 05 §3.5) and directly sharpens the Harbor Blvd forecast via the
   shared transfer node.

Purpose (offered for context, not as a condition): an open-methodology
corridor ridership analysis of Harbor Boulevard transit. Item 1(a) grounds
the 2013 Bravo! 543 launch response used as a calibration target, item 1(b)
updates a trend factor currently carried from FY2019, item 2 grounds the
boarding distribution along the corridor, and item 3 replaces an assumed
25–40% transfer share.

Please let me know if any portion can be provided sooner than the rest, or
if a fee applies above a nominal amount.

---

*Model integration notes (for whoever receives the data):*
- Item 1(a) → sharpens the ABC kernel target (`scripts/reweight_abc.py`,
  currently mu=4,200 from FY2017/six-year figures); 1(b) → the 0.90–0.99
  trend factor in `scripts/anchor_from_apc.py`.
- Item 2 → replaces the LODES-proxied boarding distribution and directly
  tests the walk/transfer market split.
- Item 3 → narrows the `tau` prior (0.25–0.40) in `scripts/model.py`.
