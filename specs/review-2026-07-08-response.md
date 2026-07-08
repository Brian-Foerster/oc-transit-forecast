# Response to External Review (2026-07-08)

The review reproduced the results exactly, then raised 19 comments plus
recommendations on all 13 open spec questions. Disposition summary:
**accepted 16, accepted-with-nuance 3, rejected 0.** Verified
inconsistencies and spec resolutions are FIXED in this commit; comments
requiring model reruns are QUEUED as tracked work items (listed at the
end) so each lands with its own verification pass.

## Verified inconsistencies (1-3) — FIXED

1. **Stale mu=3,700 / ESS ~6,500** (README, HANDOFF files table):
   corrected to mu=4,200 / ESS ~8,600. Cause: first-pass ABC docs not
   updated when the measured-anchor revision retargeted the kernel.
2. **Known-issues numbering (…11, 13, 12)**: reordered/renumbered; the
   trend-factor item is now 12, kernel width 13.
3. **Tornado central (12,051) vs headline (11,969)**: both retained by
   design (expected-blend at fixed bins vs full-MC blend P50); a new
   README section "Reading the outputs" states the difference — and also
   resolves comment 19 (sweep h=peak/2x-off-peak vs the flat-5 row).

## Methodology (4-8)

4. **ASC transportability — ACCEPTED, the review's most important point.**
   The calibrated headline does rest on transporting the 543's
   modest-overlay premium to a categorically larger service, and the
   README's "what the corridor's own experiment implies" framing
   over-claimed. Now: README known issue 14 names the assumption and its
   direction (conservative); spec 02 §4.5c adds an ASC-transportability
   sensitivity (premium factor {1.0, 1.25, 1.5} on the calibrated ASC).
   One nuance kept from the original design: part of the frequency/
   reliability premium is carried mechanically by the schedule-delay
   term, so the ASC does not have to do all the scaling — but the point
   stands and is now priced, not asserted.

5. **"Launch" target is matured ridership — ACCEPTED, with a sharpening.**
   All "launch-era" labels corrected to "matured six-year average"
   (reweight_abc.py, anchor_from_apc.py, README). Beyond the review's
   two options we adopt a third: retarget to a *launch-equivalent* value
   = FY2017 measured (4,615) x the 2013->2017 system back-trend, with
   OCTA FY2013 bus UPT from NTD (public) supplying the ratio — this
   respects the backtest's launch-vintage anchor rather than mixing
   vintages. mu=4,200 becomes a sensitivity. Queued (work item 1);
   expected direction: ASC posterior up, calibrated headline up,
   one-sided residual shrinks. README known issue 15 records all of it.

6. **One-sided residual — ACCEPTED.** It is now explicitly reported as a
   model-saturation signal per our own governance (README issue 15,
   spec 02 §4.4), with the note that the item-5 retarget is the
   first-order response and any residual one-sidedness after it stands
   as a finding.

7. **Hard max vs logsum brackets the truth — ACCEPTED.** Spec 02 §4.5d
   adds small-theta softmax rows (theta {0.1, 0.2}) as the principled
   middle. Registered expectation: with typical inter-service utility
   gaps >= 0.3, small-theta lands within a few percent of the max — if
   it does not, that is real uncertainty we were hiding, exactly as the
   review says. Agreed that walk_spread is not a substitute.

8. **50/50 fold/retain blend — ACCEPTED.** It mixes an operator decision
   into the forecast band. Spec 02 §4.7: lead with the two scenarios
   separately, demote the blend to a labeled summary, and unify on one
   blend convention (expected blend) everywhere. Queued (reporting-only
   change).

## Data and vintage (9-10)

9. **LODES 2022 post-COVID shape — ACCEPTED, upgraded from wording to a
   testable row.** The sharper framing (commute *shape*, not data age) is
   now in the ABC sigma rationale, and spec 02 §4.8 adds a data-based
   sensitivity: rebuild distance bins from pre-COVID LODES 2019 and
   report the delta. Queued (work item 4).

10. **Trend factor conservative for a transit-dependent corridor —
    ACCEPTED.** README known issue 12 now distinguishes "share stable
    pre-COVID (measured)" from "share held through recovery (assumed,
    plausibly conservative here)". Partially testable now: the FY2021
    quarterly reports (live on octa.net) measure the corridor's COVID-era
    share — if 43+543's share rose during COVID, the trend range's upper
    bound should rise. Queued (work item 5).

## Pipeline/specs (11-16)

11. **Stage 2 is calibrated, not validated — ACCEPTED and stated
    plainly** in spec 00 §5. Substantive mitigation adopted: the 529 is
    sequenced validate-then-calibrate (spec 02 §4.4) — the 543-calibrated
    prediction of the 529 outcome is committed *before* the comparison,
    giving stage 2 a genuine near-term out-of-sample test without
    spending the experiment twice silently.
12. **543 cross-stage double-use — ACCEPTED as a tension, tolerated with
    stated rationale** (spec 00 §5, spec 03 §6): STOPS's parameters are
    nationally estimated, so the replication tests engine
    transferability, not shared fitted parameters; it is a diagnostic,
    never claimed as independent validation; TSP becomes the preferred
    stage-3 check when its data lands.
13. **Agreement can be falsely reassuring — ACCEPTED.** Spec 00 §6 now
    requires the reconciliation memo to separate shared-input agreement
    from informative agreement, with pre-registered divergence sources
    (e.g., FTC park-and-ride) itemized.
14. **ABC's two roles — ACCEPTED.** Spec 00 §3 now states the division of
    labor: ABC-calibrated = decision metric at gates; uncapped =
    transparency companion, always shown together; owner retains final
    gate authority. This is calibration against local data, not a
    literature filter — the governance distinction is now explicit.
15. **Circular stage-1 sanity check — ACCEPTED.** Spec 01 §5 reordered:
    rank stability + observed-productivity ranking are primary; the
    13-arterial reproduction is demoted to a smoke test.
16. **LOO gate looseness — ACCEPTED.** Spearman rho >= 0.9 is now the
    primary gate; the +/-40% LOO error is a secondary diagnostic.

## Open-question recommendations

All 13 adopted as recommended, folded into the specs as "Questions
resolved (review 2026-07-08)" sections. Two with substance beyond
yes/no: the panel kernel sigma is now *estimated* from the ridership
drift of unchanged-service routes rather than the round-number 3x
(spec 02 §4.4), and the registered TSP prediction will publish both the
corridor total and the 43-vs-543 split (spec 02 §4.4).

## Nits (17-19)

17. ENVELOPES single-element list: intent comment added in model.py
    (retained deliberately for one-line reintroduction of treatments).
18. requirements.txt: exact pins (numpy 2.3.4 / pandas 2.3.3 /
    matplotlib 3.10.8) with a rationale comment; statsmodels will be
    pinned when stage 1 lands.
19. Sweep-vs-flat-5 confusion: covered by the README "Reading the
    outputs" section (see item 3).

## Queued work items (each = one commit + verification pass)

1. Launch-equivalent kernel retarget (comment 5; NTD FY2013 UPT; mu=4,200
   kept as sensitivity) — do FIRST, it moves the calibrated headline.
2. ASC-transportability sensitivity rows (comment 4 / spec 02 §4.5c).
3. Small-theta choice rows (comment 7 / §4.5d) + nonlinear-time rows
   gamma {0.7, 0.8, 0.9} (§4.5a) + induced-demand column (§4.5b).
4. LODES 2019 vintage sensitivity (comment 9 / §4.8).
5. FY2021 corridor-share check -> trend-range revisit (comment 10).
6. Fold/retain presentation + blend-convention unification (comment 8 /
   §4.7).
7. 529 validate-then-calibrate sequence (comment 11 / §4.4), then joint
   ABC with estimated panel sigma.
8. Registered TSP prediction, total + route split (§4.4).

Items 1-3 interact (all touch the ABC/ASC); they will be landed in that
order with the headline re-stated once at the end rather than thrice.
