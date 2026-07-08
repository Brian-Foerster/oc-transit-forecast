"""Charts from outputs/results_*.json: forecast intervals + sensitivity tornado.
usage: python make_charts.py harbor beach"""
import json, os, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "outputs")

SURFACE = "#fcfcfb"; INK = "#0b0b0b"; INK2 = "#52514e"; MUTED = "#898781"
GRID = "#e1e0d9"; BASE = "#c3c2b7"
BLUE = "#2a78d6"; RED = "#e34948"; GRAY = "#898781"

plt.rcParams["font.family"] = ["Segoe UI", "DejaVu Sans", "sans-serif"]


def intervals(name):
    j = json.load(open(os.path.join(OUT, f"results_{name}.json"), encoding="utf-8"))
    cfg, s = j["config"], j["summary"]
    up = s["ratio_retain"]
    rows = [("Observed today", "corridor anchor (corridor-consistent)",
             cfg["anchor_low"], None, cfg["anchor_high"], GRAY)]
    for label, sub in [("uncapped", "model as-is - implied uplift "
                        f"+{up[0]:.0f}/+{up[1]:.0f}/+{up[2]:.0f}%"),
                       ("cap +80%", "uplift clipped at Cleveland-class ceiling"),
                       ("cap +55%", "uplift clipped at incremental-BRT ceiling")]:
        b = s[label]["blend"]
        rows.append((f"Blended headline - {label}", sub,
                     b[0], b[1], b[2], BLUE))

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
             "envelope treatments shown separately — reference class: "
             "Twin Cities +33%, UW +35%, Cleveland +78%",
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


if __name__ == "__main__":
    for name in sys.argv[1:]:
        intervals(name)
        tornado(name)
        print(f"charts written for {name}")

