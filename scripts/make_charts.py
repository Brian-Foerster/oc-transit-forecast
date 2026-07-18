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


# ===========================================================================
# spec 07 N4 network-sequence charts (make_charts.py network mode)
# ===========================================================================
# read outputs/network_sequence.json (the greedy portfolio harness primary
# artifact). Three panels: (1) depth-shaded frontier (cumulative Delta-K_PV vs
# cumulative objective, within-draw bands, base + sigma_struct); (2) build-
# sequence chart; (3) interaction / anchor-vs-rebuild channel-split panel. The
# archetype-gap section renders the N3-pending placeholder. Flyvbjerg annotation
# per spec 05 §4.3 convention.
GOLD = "#c8922b"; VIOLET = "#7b58c4"
DEPTH_COLORS = {1: TEAL, 2: BLUE}     # decision-grade tiers; exploratory -> RED


def _depth_color(depth, label):
    if label == "exploratory":
        return RED
    return DEPTH_COLORS.get(depth, MUTED)


def network_frontier(seq, name="network"):
    """Depth-shaded frontier: cumulative Delta-K_PV (US-TYPICAL) x cumulative
    welfare-minutes P50 with within-draw P10-P90 bars; the sigma_struct-inflated
    band drawn behind the base band; LOW-capital x-position marked; points
    shaded by provenance depth. Flyvbjerg annotation in the subtitle."""
    pts = seq["frontier"]["points"]
    xs_ut = [p["cum_capital_pv_US_TYPICAL"] for p in pts]
    xs_low = [p["cum_capital_pv_LOW"] for p in pts]
    y50 = [p["cum_wm_uncapped"][1] for p in pts]

    fig, ax = plt.subplots(figsize=(10.6, 5.6), dpi=200)
    fig.patch.set_facecolor(SURFACE); ax.set_facecolor(SURFACE)
    fig.subplots_adjust(left=0.11, right=0.965, top=0.80, bottom=0.13)

    # connecting greedy build path (UT capital)
    ax.plot(xs_ut, y50, "-", color=BASE, lw=1.6, zorder=2, alpha=0.9)
    for p in pts:
        x = p["cum_capital_pv_US_TYPICAL"]
        c = _depth_color(p["depth"], p["depth_label"])
        b = p["cum_wm_uncapped"]; ss = p.get("cum_wm_sigma_struct_uncapped", b)
        # sigma_struct band behind (wider, light), base band in front
        ax.plot([x, x], [ss[0], ss[2]], color=c, lw=11, solid_capstyle="round",
                alpha=0.18, zorder=2)
        ax.plot([x, x], [b[0], b[2]], color=c, lw=7, solid_capstyle="round",
                alpha=0.7, zorder=3)
        ax.plot([x], [b[1]], "o", ms=11, mfc=c, mec=SURFACE, mew=2, zorder=5)
        # LOW-capital x-position (lighter marker + connector)
        xl = p["cum_capital_pv_LOW"]
        ax.plot([xl], [b[1]], "o", ms=6, mfc=SURFACE, mec=c, mew=1.6, zorder=4)
        ax.plot([xl, x], [b[1], b[1]], color=c, lw=0.8, ls=":", alpha=0.6, zorder=2)
        ax.annotate(f"+{p['line']}\n{p['depth_label']}", (x, b[2]),
                    xytext=(6, 12), textcoords="offset points", ha="left",
                    va="bottom", fontsize=8.6, fontweight="bold", color=INK)
        ax.annotate(f"{b[1]/1000:.0f}k", (x, b[1]), xytext=(9, -2),
                    textcoords="offset points", ha="left", va="center",
                    fontsize=8.2, color=INK2)

    ax.set_xlim(0, max(xs_ut) * 1.18)
    ax.set_ylim(0, max(p["cum_wm_uncapped"][2] for p in pts) * 1.12)
    ax.grid(color=GRID, lw=0.8, zorder=0)
    ax.tick_params(length=0, labelsize=9, labelcolor=MUTED)
    ax.xaxis.set_major_formatter(lambda v, _: f"${v/1000:.1f}B")
    ax.yaxis.set_major_formatter(lambda v, _: f"{v/1000:.0f}k")
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    for sp in ("bottom", "left"):
        ax.spines[sp].set_color(BASE)
    ax.set_xlabel("cumulative Delta-K_PV (US-TYPICAL; hollow = LOW band)",
                  fontsize=9, color=INK2)
    ax.set_ylabel("cumulative welfare-minutes (within-draw)",
                  fontsize=9, color=INK2)
    fig.text(0.02, 0.94, "Network portfolio frontier - greedy build order",
             fontsize=13.5, fontweight="bold", color=INK)
    fig.text(0.02, 0.885, "cumulative Delta-K_PV x cumulative welfare-minutes P50 "
             "(P10-P90 bars) - depth-shaded (teal=1, blue=2, red=exploratory); "
             "faint band = +sigma_struct (per-line independent structural error)",
             fontsize=8.5, color=INK2)
    fig.text(0.02, 0.845, seq["frontier"]["flyvbjerg_annotation"],
             fontsize=7.6, color=MUTED, wrap=True)
    p = os.path.join(OUT, f"{name}_frontier.png")
    fig.savefig(p, facecolor=SURFACE); plt.close(fig)
    return p


def network_build_sequence(seq, name="network"):
    """Build-sequence chart: one row per committed line in build order, showing
    the line's OWN Delta-K band (LOW|US-TYPICAL, PV-discounted) and its marginal
    welfare-minute contribution, with the depth label."""
    pts = seq["frontier"]["points"]
    rows = list(enumerate(pts))
    fig, (axk, axw) = plt.subplots(1, 2, figsize=(11.0, 0.72 * len(pts) + 2.1),
                                   dpi=200, gridspec_kw={"width_ratios": [1, 1]})
    fig.patch.set_facecolor(SURFACE)
    fig.subplots_adjust(left=0.13, right=0.965, top=0.80, bottom=0.13, wspace=0.28)
    prev = 0.0
    for ax in (axk, axw):
        ax.set_facecolor(SURFACE)
    ys = list(range(len(pts)))[::-1]
    for (k, p), y in zip(rows, ys):
        c = _depth_color(p["depth"], p["depth_label"])
        kl = p["capital_LOW"] * p["pv_factor"]
        ku = p["capital_US_TYPICAL"] * p["pv_factor"]
        axk.plot([kl, ku], [y, y], color=c, lw=9, solid_capstyle="round", zorder=3)
        axk.annotate(f"{kl:.0f}|{ku:.0f}", (ku, y), xytext=(8, 0),
                     textcoords="offset points", ha="left", va="center",
                     fontsize=8.3, color=INK)
        # marginal welfare = this step's cum P50 minus the previous step's
        cumw = p["cum_wm_uncapped"][1]
        marg = cumw - prev
        prev = cumw
        axw.plot([0, marg], [y, y], color=c, lw=9, solid_capstyle="round", zorder=3)
        axw.annotate(f"+{marg/1000:.0f}k", (marg, y), xytext=(8, 0),
                     textcoords="offset points", ha="left", va="center",
                     fontsize=8.3, color=INK)
        axk.text(-0.02, y, f"{k}. {p['line']}\n{p['depth_label']}",
                 transform=axk.get_yaxis_transform(), ha="right", va="center",
                 fontsize=8.6, color=INK2)
    for ax, lbl, fmt in ((axk, "Delta-K_PV ($M): LOW | US-TYPICAL", "${x:.0f}M"),
                         (axw, "marginal welfare-minutes", "{x}")):
        ax.set_ylim(-0.7, len(pts) - 0.3)
        ax.set_yticks([])
        ax.grid(axis="x", color=GRID, lw=0.8, zorder=0)
        ax.tick_params(length=0, labelsize=8.5, labelcolor=MUTED)
        for sp in ("top", "right", "left"):
            ax.spines[sp].set_visible(False)
        ax.spines["bottom"].set_color(BASE)
        ax.set_xlabel(lbl, fontsize=8.8, color=INK2)
    axk.xaxis.set_major_formatter(lambda v, _: f"${v:.0f}M")
    axw.xaxis.set_major_formatter(lambda v, _: f"{v/1000:.0f}k")
    fig.text(0.02, 0.945, "Network build sequence (greedy order)",
             fontsize=13.0, fontweight="bold", color=INK)
    fig.text(0.02, 0.895, "per-line PV-discounted capital band and marginal "
             "welfare-minutes; depth-shaded (teal=1, blue=2, red=exploratory)",
             fontsize=8.4, color=INK2)
    p = os.path.join(OUT, f"{name}_build_sequence.png")
    fig.savefig(p, facecolor=SURFACE); plt.close(fig)
    return p


def network_channel_panel(seq, name="network"):
    """Interaction / channel-split panel: (left) the symmetrized interaction
    matrix I(A,B) per cycle with the approximation/sequencing decomposition;
    (right) the anchor-vs-rebuild channel split for each networked candidate-
    given-network eval, so market-enlargement (rebuild) is visibly separated
    from crossing complementarity. Archetype gap = the N3-pending placeholder."""
    # collect interactions + channel splits across cycles
    inter = []
    splits = []
    for cyc in seq["cycles"]:
        for I in cyc.get("interaction_matrix", []):
            inter.append((cyc["cycle"], I))
        for b in cyc.get("candidate_results", []):
            cs = b.get("channel_split")
            if cs is not None:
                splits.append((cyc["cycle"], b["id"], cs["scenarios"]["fold"]))

    fig, (axi, axc) = plt.subplots(1, 2, figsize=(11.2, 5.2), dpi=200)
    fig.patch.set_facecolor(SURFACE)
    fig.subplots_adjust(left=0.13, right=0.965, top=0.79, bottom=0.12, wspace=0.34)
    for ax in (axi, axc):
        ax.set_facecolor(SURFACE)

    # left: interaction magnitudes
    ys = list(range(len(inter)))[::-1]
    for (cyc, I), y in zip(inter, ys):
        v = I["I_p50"]
        c = TEAL if v >= 0 else RED
        axi.plot([0, v], [y, y], color=c, lw=9, solid_capstyle="round", zorder=3)
        axi.plot([I["I_p10"], I["I_p90"]], [y, y], color=c, lw=2, alpha=0.5, zorder=2)
        axi.annotate(f"{v:+,.0f}", (v, y), xytext=(8 if v >= 0 else -8, 0),
                     textcoords="offset points",
                     ha="left" if v >= 0 else "right", va="center",
                     fontsize=8.4, color=INK)
        axi.text(-0.02, y, f"c{cyc} I{I['pair']}",
                 transform=axi.get_yaxis_transform(), ha="right", va="center",
                 fontsize=8.4, color=INK2)
    if inter:
        axi.axvline(0, color=BASE, lw=1, zorder=2)
        axi.set_ylim(-0.7, len(inter) - 0.3)
        _lo = min(0.0, min(I["I_p10"] for _, I in inter))
        _hi = max(I["I_p90"] for _, I in inter)
        axi.set_xlim(_lo - 0.05 * (_hi - _lo), _hi + 0.20 * (_hi - _lo))
    axi.set_yticks([])
    axi.grid(axis="x", color=GRID, lw=0.8, zorder=0)
    axi.tick_params(length=0, labelsize=8.5, labelcolor=MUTED)
    for sp in ("top", "right", "left"):
        axi.spines[sp].set_visible(False)
    axi.spines["bottom"].set_color(BASE)
    axi.set_xlabel("I(A,B) welfare-min (P10-P90 whisker); tau-muted (spec 07 §8a)",
                   fontsize=8.3, color=INK2)

    # right: stacked anchor + rebuild + cross for each split
    ys = list(range(len(splits)))[::-1]
    for (cyc, cid, s), y in zip(splits, ys):
        segs = [("anchor", s["anchor_channel_p50"], TEAL),
                ("rebuild", s["rebuild_channel_p50"], GOLD),
                ("cross", s["cross_residual_p50"], VIOLET)]
        left_pos = left_neg = 0.0
        for lbl, val, c in segs:
            base_x = left_pos if val >= 0 else left_neg
            axc.barh(y, val, left=base_x, color=c, height=0.5, zorder=3,
                     edgecolor=SURFACE, lw=0.5)
            if val >= 0:
                left_pos += val
            else:
                left_neg += val
        axc.annotate(f"lift {s['lift_p50']:+,.0f}", (left_pos, y),
                     xytext=(8, 0), textcoords="offset points", ha="left",
                     va="center", fontsize=8.2, color=INK)
        axc.text(-0.02, y, f"c{cyc} {cid}", transform=axc.get_yaxis_transform(),
                 ha="right", va="center", fontsize=8.4, color=INK2)
    if splits:
        axc.axvline(0, color=BASE, lw=1, zorder=2)
        axc.set_ylim(-0.7, len(splits) - 0.3)
        _hi = max(s["lift_p50"] for _, _, s in splits)
        _lo = min(0.0, min(min(s["anchor_channel_p50"], s["rebuild_channel_p50"],
                               s["cross_residual_p50"]) for _, _, s in splits))
        axc.set_xlim(_lo - 0.03 * (_hi - _lo), _hi + 0.28 * (_hi - _lo))
    else:
        axc.text(0.5, 0.5, "no networked candidate\n(cycle 0 is standalone)",
                 transform=axc.transAxes, ha="center", va="center",
                 fontsize=9, color=MUTED)
    axc.set_yticks([])
    axc.grid(axis="x", color=GRID, lw=0.8, zorder=0)
    axc.tick_params(length=0, labelsize=8.5, labelcolor=MUTED)
    for sp in ("top", "right", "left"):
        axc.spines[sp].set_visible(False)
    axc.spines["bottom"].set_color(BASE)
    axc.set_xlabel("channel split: anchor (teal) + rebuild=market-enlargement "
                   "(gold) + cross (violet)", fontsize=8.0, color=INK2)

    fig.text(0.02, 0.94, "Complementarity audit - interactions & channel split",
             fontsize=13.0, fontweight="bold", color=INK)
    ag = seq["cycles"][0].get("archetype_gap", {}) if seq.get("cycles") else {}
    fig.text(0.02, 0.885, "left: symmetrized I(A,B) at common timing (approximation "
             "isolated from sequencing); right: the anchor-vs-rebuild toggle - "
             "rebuild is synthetic-feeder MARKET ENLARGEMENT, never crossing "
             "complementarity", fontsize=8.0, color=INK2)
    fig.text(0.02, 0.845, f"archetype gap: {ag.get('status', 'n/a').upper()} "
             f"({ag.get('work_item', 'N3')}-pending - owner-designed networks, "
             "spec 07 §5.3); safeguard line carries greedy vs best-single only",
             fontsize=7.6, color=MUTED)
    p = os.path.join(OUT, f"{name}_channels.png")
    fig.savefig(p, facecolor=SURFACE); plt.close(fig)
    return p


# ===========================================================================
# spec 07 N5 NPV-objective network charts. The NPV artifact's frontier is a
# CANDIDATE SCATTER in ΔNPV vs ΔK_PV (the recommended portfolio is EMPTY -- the
# §7 marginal stop fires at cycle 1), so the frontier panel plots each candidate
# far below the ΔNPV=0 (BCR=1) hurdle, and the build-sequence panel becomes a
# marginal-BCR bar chart against BCR=1 with the premium-bracket rows.
# ===========================================================================
def npv_frontier(seq, name="network"):
    """ΔNPV vs ΔK_PV candidate scatter (US-TYPICAL, ABC), σ_struct std whiskers,
    the ΔNPV=0 (BCR=1) hurdle line. Every candidate sits far below it: the
    recommended portfolio is EMPTY (build nothing at the welfare-BCA profile)."""
    pts = seq["frontier"]["points"]
    scen = seq.get("scenario", "fold")
    fig, ax = plt.subplots(figsize=(10.6, 5.8), dpi=200)
    fig.patch.set_facecolor(SURFACE); ax.set_facecolor(SURFACE)
    fig.subplots_adjust(left=0.12, right=0.965, top=0.79, bottom=0.13)
    xs = [p["dK_pv_US_TYPICAL"] for p in pts]
    ys = [(p["npv_abc_US_TYPICAL"] or p["npv_uncapped_US_TYPICAL"])[1] for p in pts]
    ax.axhline(0, color=BASE, lw=1.4, zorder=2)
    ax.annotate("BCR = 1 (ΔNPV = 0) hurdle", (max(xs) * 0.5, 0), xytext=(0, 6),
                textcoords="offset points", ha="center", va="bottom",
                fontsize=8.4, color=MUTED)
    for p in pts:
        x = p["dK_pv_US_TYPICAL"]
        cell = p["npv_abc_US_TYPICAL"] or p["npv_uncapped_US_TYPICAL"]
        c = RED       # every candidate is below the hurdle
        # within-draw P10-P90 band + σ_struct std whisker behind
        ss = p.get("sigma_struct", {})
        halfstd = ss.get("std_sigma_struct", 0.0)
        ax.plot([x, x], [cell[1] - halfstd, cell[1] + halfstd], color=c, lw=10,
                solid_capstyle="round", alpha=0.16, zorder=2)
        ax.plot([x, x], [cell[0], cell[2]], color=c, lw=7, solid_capstyle="round",
                alpha=0.7, zorder=3)
        ax.plot([x], [cell[1]], "o", ms=12, mfc=c, mec=SURFACE, mew=2, zorder=5)
        # LOW-capital x-position (hollow)
        xl = p["dK_pv_LOW"]
        yl = (p["npv_abc_LOW"] or p["npv_uncapped_LOW"])[1]
        ax.plot([xl], [yl], "o", ms=7, mfc=SURFACE, mec=c, mew=1.7, zorder=4)
        ax.plot([xl, x], [yl, cell[1]], color=c, lw=0.9, ls=":", alpha=0.6, zorder=2)
        ax.annotate(f"{p['line']}\nBCR {p['marginal_bcr_US_TYPICAL']:.3f}",
                    (x, cell[0]), xytext=(7, -6), textcoords="offset points",
                    ha="left", va="top", fontsize=8.8, fontweight="bold", color=INK)
    ax.set_xlim(0, max(xs) * 1.22)
    ymin = min((p["npv_uncapped_US_TYPICAL"][0]) for p in pts)
    ax.set_ylim(ymin * 1.14, abs(ymin) * 0.10)
    ax.grid(color=GRID, lw=0.8, zorder=0)
    ax.tick_params(length=0, labelsize=9, labelcolor=MUTED)
    ax.xaxis.set_major_formatter(lambda v, _: f"${v/1000:.1f}B")
    ax.yaxis.set_major_formatter(lambda v, _: f"-${abs(v)/1000:.1f}B" if v < 0 else f"${v/1000:.1f}B")
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    for sp in ("bottom", "left"):
        ax.spines[sp].set_color(BASE)
    ax.set_xlabel("ΔK_PV (US-TYPICAL; hollow = LOW band), $M capcost",
                  fontsize=9, color=INK2)
    ax.set_ylabel(f"ΔNPV ({scen}, ABC, within-draw P10-P90)", fontsize=9, color=INK2)
    fig.text(0.02, 0.94, "Network NPV frontier - recommended build order: EMPTY",
             fontsize=13.5, fontweight="bold", color=INK)
    fig.text(0.02, 0.885, "ΔNPV x ΔK_PV per candidate (US-TYPICAL solid, LOW hollow); "
             "faint whisker = +/-1 σ_struct std. Every OC ALM corridor sits FAR "
             "below the BCR=1 hurdle -> the §7 marginal stop fires at cycle 1.",
             fontsize=8.3, color=INK2)
    fig.text(0.02, 0.845, seq["frontier"]["flyvbjerg_annotation"],
             fontsize=7.6, color=MUTED, wrap=True)
    p = os.path.join(OUT, f"{name}_frontier.png")
    fig.savefig(p, facecolor=SURFACE); plt.close(fig)
    return p


def npv_bcr_bars(seq, name="network"):
    """Marginal-BCR bars per candidate (LOW | US-TYPICAL, ABC) against the BCR=1
    hurdle, with the premium-bracket {1,1.5,2} ticks -- the stopping-rule verdict
    made visual: nothing clears 1, and even a 2x ASC premium does not."""
    pts = seq["frontier"]["points"]
    cyc0 = seq["cycles"][0]["candidate_results"]
    byid = {b["id"]: b for b in cyc0}
    scen = seq.get("scenario", "fold")
    fig, ax = plt.subplots(figsize=(10.6, 0.95 * len(pts) + 2.4), dpi=200)
    fig.patch.set_facecolor(SURFACE); ax.set_facecolor(SURFACE)
    fig.subplots_adjust(left=0.16, right=0.965, top=0.79, bottom=0.16)
    ys = list(range(len(pts)))[::-1]
    for p, y in zip(pts, ys):
        b = byid[p["line"]]
        bcr_ut = (b[scen]["US_TYPICAL"]["bcr_abc"] or b[scen]["US_TYPICAL"]["bcr_uncapped"])[1]
        bcr_lo = (b[scen]["LOW"]["bcr_abc"] or b[scen]["LOW"]["bcr_uncapped"])[1]
        ax.barh(y + 0.16, bcr_lo, height=0.30, color=TEAL, zorder=3, label="LOW" if y == ys[0] else None)
        ax.barh(y - 0.16, bcr_ut, height=0.30, color=BLUE, zorder=3, label="US-TYPICAL" if y == ys[0] else None)
        ax.annotate(f"{bcr_lo:.3f}", (bcr_lo, y + 0.16), xytext=(5, 0),
                    textcoords="offset points", ha="left", va="center", fontsize=8.2, color=INK)
        ax.annotate(f"{bcr_ut:.3f}", (bcr_ut, y - 0.16), xytext=(5, 0),
                    textcoords="offset points", ha="left", va="center", fontsize=8.2, color=INK)
        # premium-bracket ticks (US-TYPICAL first-order scaling)
        for row in b["premium_bracket_rows"]["rows"]:
            if row["premium"] == 1.0:
                continue
            ax.plot([row["marginal_bcr_first_order"]], [y - 0.16], "|", ms=10,
                    mec=GOLD, mew=1.8, zorder=4)
        ax.text(-0.01, y, p["line"], transform=ax.get_yaxis_transform(),
                ha="right", va="center", fontsize=9.2, fontweight="bold", color=INK2)
    ax.axvline(1.0, color=RED, lw=1.6, ls="--", zorder=2)
    ax.annotate("BCR = 1", (1.0, len(pts) - 0.5), xytext=(4, 0),
                textcoords="offset points", ha="left", va="center", fontsize=8.6, color=RED)
    ax.set_xlim(0, 1.1)
    ax.set_ylim(-0.7, len(pts) - 0.3)
    ax.set_yticks([])
    ax.grid(axis="x", color=GRID, lw=0.8, zorder=0)
    ax.tick_params(length=0, labelsize=8.6, labelcolor=MUTED)
    for sp in ("top", "right", "left"):
        ax.spines[sp].set_visible(False)
    ax.spines["bottom"].set_color(BASE)
    ax.set_xlabel(f"marginal welfare BCR ({scen}, ABC) - gold ticks = premium x1.5/x2 (first-order)",
                  fontsize=8.6, color=INK2)
    ax.legend(loc="lower right", fontsize=8.4, frameon=False)
    fig.text(0.02, 0.945, "Marginal BCR vs the BCR=1 hurdle (stopping verdict)",
             fontsize=13.0, fontweight="bold", color=INK)
    fig.text(0.02, 0.895, "no Orange County ALM corridor clears BCR=1 on either cost "
             "band; even a 2x ASC premium (gold tick) leaves it far below -> "
             "recommended portfolio EMPTY (spec 07 §7)", fontsize=8.2, color=INK2)
    p = os.path.join(OUT, f"{name}_build_sequence.png")
    fig.savefig(p, facecolor=SURFACE); plt.close(fig)
    return p


def network_charts(name="network"):
    path = os.path.join(OUT, "network_sequence.json")
    if not os.path.exists(path):
        print(f"network charts SKIPPED: no artifact at {path} "
              "(run scripts/sequence_network.py first)")
        return
    seq = json.load(open(path, encoding="utf-8"))
    mode = seq.get("objective", {}).get("mode", "interim")
    if mode == "npv":
        p1 = npv_frontier(seq, name)
        p2 = npv_bcr_bars(seq, name)
    else:
        p1 = network_frontier(seq, name)
        p2 = network_build_sequence(seq, name)
    p3 = network_channel_panel(seq, name)
    print(f"network charts written [{mode}]: {os.path.basename(p1)}, "
          f"{os.path.basename(p2)}, {os.path.basename(p3)}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "bca":       # spec 06 W2 welfare-BCA charts
        for name in (args[1:] or ["harbor"]):
            bca_charts(name)
    elif args and args[0] == "network":  # spec 07 N4 network-sequence charts
        network_charts(args[1] if len(args) > 1 else "network")
    else:
        for name in args:
            intervals(name)
            tornado(name)
            print(f"charts written for {name}")

