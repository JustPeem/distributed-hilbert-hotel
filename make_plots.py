"""สร้างกราฟจากไฟล์ CSV ใน results/ (รัน experiments.py ก่อน)

เส้น/จุดคือค่ามัธยฐานของ 3 รอบ (salt 0, 1, 2) แถบคือช่วงต่ำสุด–สูงสุด
"""

import csv
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

RESULTS = "results"
FIGS = os.path.join(RESULTS, "figures")
# ลำดับสีหมวดหมู่คงที่ (slot 1..5) ไม่วนซ้ำ
C1, C2, C3, C4, C5 = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"
INK, MUTED, GRID = "#1f1f1e", "#6b6a65", "#e4e3dd"

plt.rcParams.update({
    "font.size": 10, "axes.edgecolor": MUTED, "axes.labelcolor": INK,
    "xtick.color": MUTED, "ytick.color": MUTED, "axes.grid": True,
    "grid.color": GRID, "grid.linewidth": 0.8, "axes.spines.top": False,
    "axes.spines.right": False, "legend.frameon": False, "lines.linewidth": 2,
    "lines.markersize": 7, "figure.dpi": 150, "savefig.bbox": "tight",
})


def load(name):
    with open(os.path.join(RESULTS, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))


def series(rows, x, metric, **where):
    pick = [r for r in rows if all(r[k] == str(v) for k, v in where.items())]
    pick.sort(key=lambda r: float(r[x]))
    xs = [float(r[x]) for r in pick]
    med = [float(r[f"{metric}_median"]) for r in pick]
    lo = [float(r[f"{metric}_min"]) for r in pick]
    hi = [float(r[f"{metric}_max"]) for r in pick]
    return xs, med, lo, hi


def plot_range(ax, xs, med, lo, hi, color, label, marker="o", ls="-"):
    ax.fill_between(xs, lo, hi, color=color, alpha=0.15, linewidth=0)
    ax.errorbar(xs, med, yerr=[[m - l for m, l in zip(med, lo)], [h - m for m, h in zip(med, hi)]],
                color=color, marker=marker, linestyle=ls, capsize=3, label=label)


def footnote(fig, text):
    fig.text(0.01, -0.02, text, fontsize=8, color=MUTED, ha="left", va="top")


def fig_a():
    rows = load("exp_a_timing_summary.csv")
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.2))
    for metric, color, label, marker in (
            ("assign_guests_ms", C1, "Assign initial guests (all K)", "o"),
            ("sort_rooms_ms", C2, "Sort room list (all K)", "s"),
            ("build_ring_ms", C3, "Build ring (M = 320 points)", "^")):
        plot_range(ax1, *series(rows, "K", metric), color, label, marker)
    ax1.set(xscale="log", yscale="log", xlabel="Number of guests K (log scale)",
            ylabel="Time (ms, log scale)", title="(a1) Whole-set operations vs K")
    ax1.legend(fontsize=8)
    for metric, color, label, marker in (
            ("lookup_guest_us", C1, "Find by guest ID", "o"),
            ("lookup_room_us", C2, "Find by (node_id, room_no)", "s"),
            ("compute_node_us", C3, "Compute node from ring (no cache)", "^"),
            ("add_guest_single_us", C4, "Add one guest", "D"),
            ("remove_guest_single_us", C5, "Remove one guest", "v")):
        plot_range(ax2, *series(rows, "K", metric), color, label, marker)
    ax2.set(xscale="log", yscale="log", xlabel="Number of guests K (log scale)",
            ylabel="Time per operation (µs, log scale)",
            title="(a2) Per-operation time vs K (batches of 1,000)")
    ax2.legend(fontsize=8)
    footnote(fig, "Experiment A: N = 10, V = 32, 10 channels. Line = median of 3 rounds "
                  "(salt 0, 1, 2); bars = min–max. time.perf_counter().")
    fig.savefig(os.path.join(FIGS, "fig_a_time_vs_K.png"))
    plt.close(fig)

    mem = load("exp_a_memory_summary.csv")
    fig, ax = plt.subplots(figsize=(6.5, 4))
    plot_range(ax, *series(mem, "K", "system_current_mib"), C1, "System after setup (current)")
    plot_range(ax, *series(mem, "K", "system_peak_mib"), C2, "System during setup (peak)", "s")
    ax.set(xscale="log", yscale="log", xlabel="Number of guests K (log scale)",
           ylabel="Memory (MiB, log scale)", title="(a3) Memory traced by tracemalloc vs K")
    ax.legend(fontsize=8)
    footnote(fig, "N = 10, V = 32. Python-tracked memory only (not whole process); "
                  "separate run from timing.")
    fig.savefig(os.path.join(FIGS, "fig_a_memory_vs_K.png"))
    plt.close(fig)


def fig_b():
    rows = load("exp_b_summary.csv")
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), sharey=True)
    for ax, op, title in ((axes[0], "add", "(b1) Add 1 building (id N+1)"),
                          (axes[1], "remove", "(b2) Remove 1 building (id 1)")):
        xs, med, lo, hi = series(rows, "N", "move_rate", operation=op, method="ch-range")
        plot_range(ax, xs, med, lo, hi, C1, "Consistent hashing (measured)")
        xs2, med2, lo2, hi2 = series(rows, "N", "move_rate", operation=op, method="mod-n")
        plot_range(ax, xs2, med2, lo2, hi2, C2, "hash mod N (measured)", "s")
        dense = [n / 10 for n in range(45, 205)]
        if op == "add":
            ch_exp = [1 / (n + 1) for n in dense]
            mod_exp = [n / (n + 1) for n in dense]
        else:
            ch_exp = [1 / n for n in dense]
            mod_exp = [(n - 1) / n for n in dense]
        ax.plot(dense, ch_exp, color=C1, ls="--", lw=1.2, label="CH expected")
        ax.plot(dense, mod_exp, color=C2, ls=":", lw=1.2, label="mod N expected")
        ax.set(xlabel="Buildings before the change N", title=title, xticks=[5, 10, 20],
               ylim=(0, 1.02))
        ax.legend(fontsize=8, loc="center right")
    axes[0].set_ylabel("Move rate = guests moved / K")
    footnote(fig, "Experiment B: K = 10,000, V = 32. Median of 3 rounds (salt 0, 1, 2), "
                  "bars = min–max. Same guests, building ids and hashes for both methods.")
    fig.savefig(os.path.join(FIGS, "fig_b_move_rate_vs_N.png"))
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), sharey=True)
    for ax, op, title in ((axes[0], "add", "(b3) Time to add 1 building"),
                          (axes[1], "remove", "(b4) Time to remove 1 building")):
        for method, color, label, marker in (
                ("ch-range", C1, "CH, affected range only (method B)", "o"),
                ("ch-scan", C3, "CH, rescan all guests (method A)", "^"),
                ("mod-n", C2, "hash mod N (rescan all)", "s")):
            plot_range(ax, *series(rows, "N", "total_ms", operation=op, method=method),
                       color, label, marker)
        ax.set(xlabel="Buildings before the change N", title=title, xticks=[5, 10, 20])
        ax.legend(fontsize=8)
    axes[0].set_ylabel("Total time (ms) = ring update + find + apply")
    footnote(fig, "K = 10,000, V = 32. Each round = median of 5 repeats on a fresh system; "
                  "line = median of 3 rounds, bars = min–max.")
    fig.savefig(os.path.join(FIGS, "fig_b_time_vs_N.png"))
    plt.close(fig)


def fig_c():
    rows = load("exp_c_summary.csv")
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.2))
    plot_range(ax1, *series(rows, "V", "cv"), C1, "CV of guests per building")
    ax1.set(xscale="log", xlabel="Virtual nodes per building V (log scale)",
            ylabel="CV = std / mean (lower = more balanced)", title="(c1) Load balance vs V")
    xs = sorted(float(r["V"]) for r in rows)
    ax1.set_xticks(xs, [str(int(x)) for x in xs])
    ax1.legend(fontsize=8)
    xs2, med, lo, hi = series(rows, "V", "ring_current_mib")
    k = 1024
    plot_range(ax2, xs2, [m * k for m in med], [m * k for m in lo], [m * k for m in hi], C2,
               "Ring memory (current)", "s")
    ax2.set(xscale="log", yscale="log", xlabel="Virtual nodes per building V (log scale)",
            ylabel="Memory of ring (KiB, log scale)", title="(c2) Ring memory vs V")
    ax2.set_xticks(xs, [str(int(x)) for x in xs])
    ax2.legend(fontsize=8)
    footnote(fig, "Experiment C: N = 10, K = 10,000 (M = N·V points). Median of 3 rounds "
                  "(salt 0, 1, 2), bars = min–max. V = 128, 512 are extra points beyond the brief.")
    fig.savefig(os.path.join(FIGS, "fig_c_V_effect.png"))
    plt.close(fig)

    loads = load("exp_c_loads.csv")
    fig, ax = plt.subplots(figsize=(10, 4))
    width = 0.26
    for i, (v, color) in enumerate((("1", C1), ("8", C2), ("32", C3))):
        pick = sorted((r for r in loads if r["V"] == v and r["salt"] == "0"),
                      key=lambda r: int(r["node_id"]))
        xs = [int(r["node_id"]) + (i - 1) * width for r in pick]
        ax.bar(xs, [int(r["guests"]) for r in pick], width=width - 0.03, color=color,
               label=f"V = {v}")
    ax.axhline(1000, color=INK, lw=1, ls="--")
    ax.text(10.55, 1000, "ideal mean 1,000", va="bottom", ha="right", fontsize=8, color=INK)
    ax.set(xlabel="Building node_id", ylabel="Guests in building", xticks=range(1, 11),
           title="(c3) Guests per building, salt 0")
    ax.legend(fontsize=8)
    footnote(fig, "N = 10, K = 10,000. One round (salt 0) shown; other rounds in exp_c_loads.csv.")
    fig.savefig(os.path.join(FIGS, "fig_c_loads_per_node.png"))
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.5, 4))
    plot_range(ax, *series(rows, "V", "add_rate"), C1, "Add building 11")
    plot_range(ax, *series(rows, "V", "remove_rate"), C2, "Remove building 1", "s")
    ax.axhline(1 / 11, color=C1, ls="--", lw=1.2)
    ax.axhline(1 / 10, color=C2, ls=":", lw=1.2)
    ax.set(xscale="log", xlabel="Virtual nodes per building V (log scale)",
           ylabel="Move rate", title="(c4) Move rate vs V (dashed = expected 1/11, 1/10)")
    ax.set_xticks(xs2, [str(int(x)) for x in xs2])
    ax.legend(fontsize=8)
    footnote(fig, "N = 10, K = 10,000. Median of 3 rounds, bars = min–max.")
    fig.savefig(os.path.join(FIGS, "fig_c_move_rate_vs_V.png"))
    plt.close(fig)


def fig_d():
    rows = load("exp_d_summary.csv")
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), sharey=True)
    for ax, op, title in ((axes[0], "add", "(d1) Find affected guests: add building"),
                          (axes[1], "remove", "(d2) Find affected guests: remove building")):
        plot_range(ax, *series(rows, "K", "find_ms", operation=op, method="ch-range"), C1,
                   "Method B: affected range only")
        plot_range(ax, *series(rows, "K", "find_ms", operation=op, method="ch-scan"), C3,
                   "Method A: rescan all K", "^")
        ax.set(xscale="log", yscale="log", xlabel="Number of guests K (log scale)", title=title)
        ax.legend(fontsize=8)
    axes[0].set_ylabel("Find step time (ms, log scale)")
    footnote(fig, "Extra experiment D: N = 10, V = 32. Only step (b) 'find affected guests' "
                  "is shown. Median of 3 rounds, bars = min–max.")
    fig.savefig(os.path.join(FIGS, "fig_d_find_scan_vs_range.png"))
    plt.close(fig)


if __name__ == "__main__":
    os.makedirs(FIGS, exist_ok=True)
    fig_a()
    fig_b()
    fig_c()
    fig_d()
    print("สร้างกราฟใน", FIGS, ":", ", ".join(sorted(os.listdir(FIGS))))
