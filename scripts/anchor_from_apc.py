"""
Anchor derivation from MEASURED route-level boardings (replaces the old
inference from the Harbor TSP study's ">10,000 daily boardings" quote).

Source: OCTA "Bus Operations Performance Measurements Report" quarterly
detailed reports -- still live on octa.net (found 2026-07 by URL-pattern
probing after the boarding-reports page 404'd; the OC_Bus_Ridership monthly
report needs a %20-encoded space in its filename):

  FY2017  https://www.octa.net/pdf/FY%202017%20Q4%20Detailed%20Report%20PM.pdf
  FY2019  https://www.octa.net/pdf/FY-2019-Q4-Detailed-Report-PM.pdf
  FY2020Q3 https://www.octa.net/pdf/FY2020-Q3-Detailed-Report.pdf
  monthly https://octa.net/pdf/OC_Bus_Ridership_July_2022_to_%20March_2024.pdf

Measured annual boardings (fixed-route sum = sum of route rows):

  period                    Route 43   Route 543   system
  FY2017 (Jul16-Jun17)     2,190,951  1,176,910  38,677,431
  FY2019 (Jul18-Jun19)     2,095,510    953,471  36,651,846
  FY2020 YTD Q3 (Jul-Mar)  1,515,585    641,470  26,093,345
  FY2023 YTD (Jul-Mar)             -          -  23,120,783
  FY2024 YTD (Jul-Mar)             -          -  25,825,884

43+543 = 8.7% / 8.3% / 8.3% of system in FY2017/19/20 -- matches the TSP
study's "8% of all OCTA bus ridership", confirming that quote is this data.

Derivation of the 2024 corridor anchor:
  543 runs weekdays only            -> wd = annual / 255
  43 runs 7 days                    -> wd = annual / weekday-equivalents
                                       (Sa 0.55-0.75, Su+hol 0.4-0.6 of wd
                                        -> 300-330 equivalent days)
  trend FY2019 -> FY2024: system per-month ratio 0.94 (range 0.90-0.99 to
    cover route-share drift and the COVID-window bias in the FY2020 figure;
    the 43+543 system share was stable 2017-2020 and TSP quotes 8% in 2024)
  corridor = 543_wd * 1.0 + 43_wd * corridor_share(0.75 LODES - 0.86 ACS,
    scripts/route43_share.py)

usage: python anchor_from_apc.py
"""
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

FY2019 = {"43": 2_095_510, "543": 953_471, "system": 36_651_846}
WEEKDAYS = 255
EQ_DAYS = (300, 330)          # weekday-equivalent days/yr for 7-day Route 43
TREND = (0.90, 0.99)          # FY2019 -> FY2024 per-month system ratio 0.94
CORR_SHARE = (0.75, 0.86)     # Route 43's share inside the 12.1-mi corridor

wd543 = FY2019["543"] / WEEKDAYS
wd43 = tuple(FY2019["43"] / d for d in EQ_DAYS[::-1])     # (lo, hi)
print(f"FY2019 measured weekday boardings: 543 = {wd543:,.0f}, "
      f"43 = {wd43[0]:,.0f}-{wd43[1]:,.0f}")

lo = (wd543 * TREND[0]) + (wd43[0] * TREND[0] * CORR_SHARE[0])
hi = (wd543 * TREND[1]) + (wd43[1] * TREND[1] * CORR_SHARE[1])
print(f"2024 corridor anchor: {lo:,.0f} - {hi:,.0f}")
print(f"-> config/harbor.json anchor_low/high (rounded to 50): "
      f"{round(lo / 50) * 50:,} - {round(hi / 50) * 50:,}")

# 543 observed series for the backtest/ABC target (launch-era response):
print(f"\n543 measured weekday series: FY2017 = {1_176_910 / WEEKDAYS:,.0f}, "
      f"FY2019 = {wd543:,.0f}, FY2020(YTD) = {641_470 / 190:,.0f}")
print("six-year press cumulative 6.4M (OCTA 2019) ~ 4,250/wd average")
print("-> ABC kernel mu = 4,200 (launch-era average), obs range 3,700-4,600")
