"""Charts from outputs/results_*.json: forecast intervals + sensitivity tornado.
The `bca` mode (spec 06 W2) instead reads the cross-repo welfare-BCA artifact
(transit-benefit-cost outputs/bca_<corridor>.json) and draws the NPV/BCR
interval chart + the BCA tornado.
usage: python make_charts.py harbor beach       # ridership charts
       python make_charts.py bca harbor          # welfare-BCA charts"""
import json, os, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "outputs")

# spec 06 W2: the welfare-BCA wrapper artifact lives in the transit-benefit-cost
# sibling checkout; same existence-gated, configurable path convention as
# check_assumptions.py (BCA_WRAPPER_ARTIFACT). Only harbor has one (the
# streetcar has no pre-launch ABC target, spec 05).
def _wrapper_path(name):
    if name == "harbor":
        env = os.environ.get("BCA_WRAPPER_ARTIFACT")
        if env:
            return env
    return os.path.join(HERE, "..", "..", "transit-benefit-cost", "outputs",
                        f"bca_{name}.json")

SURFACE = "#fcfcfb"; INK = "#0b0b0b"; INK2 = "#52514e"; MUTED = "#898781"
GRID = "#e1e0d9"; BASE = "#c3c2b7"
BLUE = "#2a78d6"; RED = "#e34948"; GRAY = "#898781"; TEAL = "#1b8a6b"

plt.rcParams["font.family"] = ["Segoe UI", "DejaVu Sans", "sans-serif"]


def intervals(name):
    j = json.load(open(os.path.join(OUT, f"results_{name}.json"), encoding="utf-8"))
    cfg, s = j["config"], j["summary"]
    up = s["ratio_retain"]
    rows = [("Observed today", "corridor anchor (corridor-consistent)",
             cfg["anchor_low"], None, cfg["anchor_high"], GRAY)]
    b = s["uncapped"]["blend"]
    rows.append(("Blended headline - uncapped",
                 "model as-is - implied uplift "
                 f"+{up[0]:.0f}/+{up[1]:.0f}/+{up[2]:.0f}%",
                 b[0], b[1], b[2], BLUE))
    abc_path = os.path.join(OUT, f"abc_{name}.json")
    if os.path.exists(abc_path):
        abc = json.load(open(abc_path, encoding="utf-8"))
        key = [k for k, v in abc["kernels"].items() if v["tag"] == "central"][0]
        d = abc["kernels"][key]
        c = d["forecast"]["blend"]
        rows.append(("Backtest-calibrated (ABC, launch-eq.)",
                     "draws reweighted by the 2013 Bravo! 543 launch-equivalent "
                     f"(mu={d['mu']:,.0f}, sigma={d['sigma']:.0f}, "
                     f"ESS={d['ess']:,.0f})",
                     c[0], c[1], c[2], TEAL))

    fig, ax = plt.subplots(figsize=(10.6, 4.9), dpi=200)
    fig.patch.set_facecolor(SURFACE); ax.set_facecolor(SURFACE)
    fig.subplots_adjust(left=0.36, right=0.975, top=0.82, bottom=0.11)
    tr = ax.get_yaxis_transform()
    ys = list(range(len(rows)))[::-1]
    lo = min(r[2] for r in rows); hi = max(r[4] for r in rows)
    pad = 0.06 * (hi - lo)
    for (label, sub, p10, p50, p90, c), y in zip(rows, ys):
        ax.plot([p10, p90], [y, y], color=c, lw=9, solid_capstyle="round",
                alpha=0.45 if p50 is None else 0.9, zorder=3)
        if p50 is not None:
            ax.plot([p50], [y], "o", ms=9, mfc=c, mec=SURFACE, mew=2, zorder=4)
            ax.annotate(f"{p50:,.0f}", (p50, y), xytext=(0, 10),
                        textcoords="offset points", ha="center",
                        fontsize=9.5, fontweight="bold", color=INK, zorder=5)
        for v, side, dx in ((p10, "right", -8), (p90, "left", 8)):
            ax.annotate(f"{v/1000:.1f}k", (v, y), xytext=(dx, -4),
                        textcoords="offset points", ha=side, va="center",
                        fontsize=8, color=MUTED)
        ax.text(-0.545, y + 0.08, label, transform=tr, ha="left", va="bottom",
                fontsize=10, fontweight="bold", color=INK, clip_on=False)
        ax.text(-0.545, y - 0.10, sub, transform=tr, ha="left", va="top",
                fontsize=8.3, color=INK2, clip_on=False)
    ax.set_xlim(lo - 6 * pad, hi + pad)
    ax.set_ylim(-0.65, len(rows) - 0.35)
    ax.set_yticks([])
    ax.grid(axis="x", color=GRID, lw=0.8, zorder=0)
    ax.tick_params(axis="x", length=0, labelsize=9, labelcolor=MUTED)
    ax.xaxis.set_major_formatter(lambda v, _: f"{v/1000:.0f}k")
    for sp in ("top", "right", "left"):
        ax.spines[sp].set_visible(False)
    ax.spines["bottom"].set_color(BASE)
    fig.text(0.02, 0.94, f"{cfg['title']} — forecast weekday boardings",
             fontsize=13.5, fontweight="bold", color=INK)
    fig.text(0.02, 0.875, "P10–P90, P50 dots · blended fold/retain headline · "
             "uncalibrated and backtest-calibrated side by side — analogs "
             "(display-only): Cleveland +40 launch/+78 matured (fold) · "
             "Twin Cities +30 launch (retain) · study avg +35",
             fontsize=8.8, color=INK2)
    fig.savefig(os.path.join(OUT, f"forecast_{name}.png"), facecolor=SURFACE)
    plt.close(fig)


def tornado(name, top=14):
    j = json.load(open(os.path.join(OUT, f"results_{name}.json"), encoding="utf-8"))
    cfg = j["config"]
    rows = sorted(j["sensitivity"], key=lambda r: -abs(r["pct"]))[:top][::-1]
    fig, ax = plt.subplots(figsize=(9.8, 0.42 * top + 1.6), dpi=200)
    fig.patch.set_facecolor(SURFACE); ax.set_facecolor(SURFACE)
    fig.subplots_adjust(left=0.34, right=0.93, top=0.86, bottom=0.10)
    for i, r in enumerate(rows):
        c = BLUE if r["pct"] >= 0 else RED
        ax.plot([0, r["pct"]], [i, i], color=c, lw=8,
                solid_capstyle="round", zorder=3)
        ax.annotate(f"{r['pct']:+.1f}%", (r["pct"], i),
                    xytext=(8 if r["pct"] >= 0 else -8, 0),
                    textcoords="offset points",
                    ha="left" if r["pct"] >= 0 else "right", va="center",
                    fontsize=8.5, color=INK)
        ax.text(-0.02, i, r["label"], transform=ax.get_yaxis_transform(),
                ha="right", va="center", fontsize=8.8, color=INK2)
    ax.axvline(0, color=BASE, lw=1, zorder=2)
    m = max(abs(r["pct"]) for r in rows)
    ax.set_xlim(-1.25 * m, 1.25 * m)
    ax.set_ylim(-0.7, len(rows) - 0.3)
    ax.set_yticks([])
    ax.grid(axis="x", color=GRID, lw=0.8, zorder=0)
    ax.tick_params(axis="x", length=0, labelsize=9, labelcolor=MUTED)
    ax.xaxis.set_major_formatter(lambda v, _: f"{v:+.0f}%")
    for sp in ("top", "right", "left"):
        ax.spines[sp].set_visible(False)
    ax.spines["bottom"].set_color(BASE)
    fig.text(0.02, 0.945, f"{cfg['title']} — sensitivity of headline "
             f"(central {j['central_blend']:,.0f})",
             fontsize=12.5, fontweight="bold", color=INK)
    fig.text(0.02, 0.895, "one-at-a-time change in uncapped expected-blend P50 · "
             "blue = raises forecast, red = lowers",
             fontsize=8.8, color=INK2)
    fig.savefig(os.path.join(OUT, f"sensitivity_{name}.png"), facecolor=SURFACE)
    plt.close(fig)


def bca_intervals(name, bca):
    """Welfare-BCA NPV interval chart (spec 06 W2): one row per scenario ×
    treatment × cost band, NPV P10-P90 in $B with the PV-BCR P50 and P(NPV>0)
    annotated. Flyvbjerg optimism-bias line in the subtitle (spec 05 §4.3)."""
    hl = bca["headline"]
    # order rows so scenarios group, then band, then treatment (ABC above
    # uncapped within a cell). Plotted bottom-up, so build top-down and reverse.
    rows = []
    for scen in ("fold", "retain"):
        for bandk in ("US_TYPICAL", "LOW"):
            for treat in ("abc", "uncapped"):
                cell = hl[scen][bandk][treat]
                npv = cell["npv"]; bcr = cell["bcr"]
                c = TEAL if treat == "abc" else BLUE
                rows.append((
                    f"{scen} · {bandk.replace('_', '-')} · {treat.upper()}",
                    f"PV-BCR {bcr['p50']:.3f} · P(NPV>0)={cell['p_npv_pos']:.0%}"
                    + (f" · ESS {cell['ess']:,.0f}" if cell.get("ess") else ""),
                    npv["p10"] / 1000.0, npv["p50"] / 1000.0,
                    npv["p90"] / 1000.0, c))

    fig, ax = plt.subplots(figsize=(10.6, 5.6), dpi=200)
    fig.patch.set_facecolor(SURFACE); ax.set_facecolor(SURFACE)
    fig.subplots_adjust(left=0.30, right=0.965, top=0.80, bottom=0.11)
    tr = ax.get_yaxis_transform()
    ys = list(range(len(rows)))[::-1]
    lo = min(r[2] for r in rows); hi = max(r[4] for r in rows)
    pad = 0.06 * (hi - lo)
    for (label, sub, p10, p50, p90, c), y in zip(rows, ys):
        ax.plot([p10, p90], [y, y], color=c, lw=9, solid_capstyle="round",
                alpha=0.9, zorder=3)
        ax.plot([p50], [y], "o", ms=9, mfc=c, mec=SURFACE, mew=2, zorder=4)
        ax.annotate(f"${p50:,.2f}B", (p50, y), xytext=(0, 10),
                    textcoords="offset points", ha="center",
                    fontsize=9.5, fontweight="bold", color=INK, zorder=5)
        ax.text(-0.44, y + 0.08, label, transform=tr, ha="left", va="bottom",
                fontsize=9.5, fontweight="bold", color=INK, clip_on=False)
        ax.text(-0.44, y - 0.10, sub, transform=tr, ha="left", va="top",
                fontsize=8.2, color=INK2, clip_on=False)
    ax.axvline(0, color=BASE, lw=1, zorder=2)
    ax.set_xlim(lo - pad, max(hi, 0) + pad)
    ax.set_ylim(-0.65, len(rows) - 0.35)
    ax.set_yticks([])
    ax.grid(axis="x", color=GRID, lw=0.8, zorder=0)
    ax.tick_params(axis="x", length=0, labelsize=9, labelcolor=MUTED)
    ax.xaxis.set_major_formatter(lambda v, _: f"${v:.0f}B")
    for sp in ("top", "right", "left"):
        ax.spines[sp].set_visible(False)
    ax.spines["bottom"].set_color(BASE)
    corr = bca.get("corridor", name).title()
    fig.text(0.02, 0.94, f"{corr} corridor — welfare BCA (NPV P10–P90, PV-BCR "
             f"P50)", fontsize=13.5, fontweight="bold", color=INK)
    fig.text(0.02, 0.885, "fold vs retain reported separately (no blend) · "
             "ABC-calibrated (teal) and uncapped (blue) · US-TYPICAL / LOW "
             f"capital bands · pipeline mode, tbc {bca.get('engine_fn','')}",
             fontsize=8.6, color=INK2)
    fig.text(0.02, 0.845, "Flyvbjerg optimism-bias prior (spec 05 §4.3): rail "
             "capital outturns run materially over ex-ante estimates; the "
             "US-TYPICAL band internalizes part of this — reported beside, not "
             "applied to, the point estimate.", fontsize=7.8, color=MUTED)
    p = os.path.join(OUT, f"bca_{name}.png")
    fig.savefig(p, facecolor=SURFACE)
    plt.close(fig)
    return p


def bca_tornado(name, bca, scen="fold", top=16):
    """Welfare-BCA tornado (spec 06 W2): top rows by |ΔNPV_P50| around the
    central-cell NPV, same style as the ridership tornado. Blue = raises NPV
    (less negative), red = lowers."""
    t = bca["tornado"][scen]
    central = t["central_npv_p50"]
    rows = sorted(t["rows"].values(), key=lambda r: -abs(r["delta_npv_p50"]))
    rows = [r for r in rows if abs(r["delta_npv_p50"]) > 0][:top][::-1]
    cell = t["cell"]
    fig, ax = plt.subplots(figsize=(9.8, 0.42 * len(rows) + 1.7), dpi=200)
    fig.patch.set_facecolor(SURFACE); ax.set_facecolor(SURFACE)
    fig.subplots_adjust(left=0.30, right=0.93, top=0.85, bottom=0.09)
    for i, r in enumerate(rows):
        d = r["delta_npv_p50"]
        c = BLUE if d >= 0 else RED
        ax.plot([0, d], [i, i], color=c, lw=8, solid_capstyle="round", zorder=3)
        ax.annotate(f"{d:+,.0f}", (d, i), xytext=(8 if d >= 0 else -8, 0),
                    textcoords="offset points",
                    ha="left" if d >= 0 else "right", va="center",
                    fontsize=8.5, color=INK)
        ax.text(-0.02, i, r.get("label", ""), transform=ax.get_yaxis_transform(),
                ha="right", va="center", fontsize=8.6, color=INK2)
    ax.axvline(0, color=BASE, lw=1, zorder=2)
    m = max(abs(r["delta_npv_p50"]) for r in rows)
    ax.set_xlim(-1.3 * m, 1.3 * m)
    ax.set_ylim(-0.7, len(rows) - 0.3)
    ax.set_yticks([])
    ax.grid(axis="x", color=GRID, lw=0.8, zorder=0)
    ax.tick_params(axis="x", length=0, labelsize=9, labelcolor=MUTED)
    ax.xaxis.set_major_formatter(lambda v, _: f"{v:+.0f}")
    for sp in ("top", "right", "left"):
        ax.spines[sp].set_visible(False)
    ax.spines["bottom"].set_color(BASE)
    corr = bca.get("corridor", name).title()
    fig.text(0.02, 0.955, f"{corr} corridor — welfare-BCA tornado, {scen} "
             f"(central NPV ${central/1000:,.2f}B)", fontsize=12.5,
             fontweight="bold", color=INK)
    fig.text(0.02, 0.905, f"one-at-a-time ΔNPV_P50 ($M) around the "
             f"{cell['weighting'].upper()} / {cell['band'].replace('_','-')} / "
             f"{cell['kernel']} cell · blue = raises NPV, red = lowers · "
             f"blocked rows: {', '.join(sorted(t.get('blocked', {})))}",
             fontsize=8.0, color=INK2)
    p = os.path.join(OUT, f"bca_tornado_{name}.png")
    fig.savefig(p, facecolor=SURFACE)
    plt.close(fig)
    return p


def bca_charts(name):
    path = _wrapper_path(name)
    if not os.path.exists(path):
        print(f"bca charts SKIPPED for {name}: no wrapper artifact at {path} "
              "(existence-gated, spec 06 W2)")
        return
    bca = json.load(open(path, encoding="utf-8"))
    p1 = bca_intervals(name, bca)
    p2 = bca_tornado(name, bca)
    print(f"bca charts written for {name}: {os.path.basename(p1)}, "
          f"{os.path.basename(p2)}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "bca":       # spec 06 W2 welfare-BCA charts
        for name in (args[1:] or ["harbor"]):
            bca_charts(name)
    else:
        for name in args:
            intervals(name)
            tornado(name)
            print(f"charts written for {name}")

