# Draft: Public Records Request to OCTA

*(Prepared 2026-07-07. Web research found that the relevant reports exist but
are not retrievable online: the "OC Bus Ridership July 2022 to March 2024"
boarding report link on octa.net/news/publications/bus-boarding-reports/
returns 404, and the January 2026 Bimonthly Transit Performance Report on
octa.legistar.com has been deleted. Submit via OCTA's public records portal
or clerk of the board.)*

---

**To:** Orange County Transportation Authority — Clerk of the Board / Public
Records

**Re:** California Public Records Act request — bus ridership data for
Routes 43 and 543

Under the California Public Records Act (Gov. Code § 7920.000 et seq.), I
request the following records, in electronic form (CSV or Excel preferred
where available):

1. **Route-level average weekday boardings** for OC Bus Route 43 and
   Bravo! Route 543, monthly or quarterly, for fiscal years 2019 through the
   most recent period available. (The report series titled "OC Bus Ridership"
   — e.g. "OC Bus Ridership July 2022 to March 2024," formerly posted at
   octa.net/news/publications/bus-boarding-reports/ — appears responsive.)

2. **Stop-level average weekday boardings and alightings** (APC data) for
   Routes 43 and 543, most recent available service period, ideally split by
   time-of-day period (peak / midday / evening).

3. **The most recent Bimonthly Transit Performance Report** presented to the
   Transit Committee (e.g. the January 2026 report, agenda item on
   octa.legistar.com), including any route-level performance appendix.

4. From the **most recent systemwide on-board / customer survey**: the share
   of riders whose one-way trip involves a transfer between routes, and, if
   tabulated, transfer rates for riders boarding Routes 43 or 543.

Purpose (offered for context, not as a condition): an open-methodology
corridor ridership analysis of Harbor Boulevard transit. These figures
replace inferred values — item 1 sets the forecast anchor (currently derived
indirectly from the Harbor TSP study's ">10,000 daily boardings" statement),
item 2 grounds the boarding distribution along the corridor, and item 4
replaces an assumed 25–40% transfer share.

Please let me know if any portion can be provided sooner than the rest, or
if a fee applies above a nominal amount.

---

*Model integration notes (for whoever receives the data):*
- Item 1 → `anchor_low/high` in `config/harbor.json` (route totals × corridor
  share via `scripts/route43_share.py`); the anchor is the forecast's #2
  sensitivity (±13%).
- Item 2 → replaces the LODES-proxied boarding distribution and directly
  tests the walk/transfer market split.
- Item 4 → narrows the `tau` prior (0.25–0.40) in `scripts/model.py`.
