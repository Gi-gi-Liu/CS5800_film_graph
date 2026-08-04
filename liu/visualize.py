"""
visualize.py — Matplotlib plots for film scheduling algorithm analysis.

Generates:
  1. Runtime curves (log-log): Dijkstra all-pairs vs Greedy vs n.
  2. Memory usage bar chart.
  3. Optimality gap bar chart (% above Dijkstra lower bound).
  4. Adjacency matrix heatmap.

All plots are saved to liu/plots/ as PNG files.

Run directly to generate all plots from precomputed test data:
    python visualize.py
"""

from __future__ import annotations
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))
from typing import List, Optional, Dict

# --- matplotlib configuration (non-interactive backend for script use) -----
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np

from benchmark import BenchmarkResult, run_dijkstra_benchmark, run_greedy_benchmark
from benchmark import compare_optimality
from data_gen import load_matrix, create_film_benchmark
from dijkstra import INF

# ---------------------------------------------------------------------------
# Output directory
# ---------------------------------------------------------------------------

_PLOTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plots")


def _ensure_plots_dir() -> str:
    """Create and return the plots output directory."""
    os.makedirs(_PLOTS_DIR, exist_ok=True)
    return _PLOTS_DIR


# ---------------------------------------------------------------------------
# Plot helpers
# ---------------------------------------------------------------------------

def _save(fig: plt.Figure, filename: str) -> str:
    """Save *fig* as a PNG file in the plots directory and close it."""
    path = os.path.join(_ensure_plots_dir(), filename)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


# ---------------------------------------------------------------------------
# 1. Runtime curves
# ---------------------------------------------------------------------------

def plot_runtime_curves(dijkstra_results: List[BenchmarkResult],
                        greedy_results: List[BenchmarkResult],
                        filename: str = "runtime_curves.png") -> str:
    """
    Plot log-log runtime curves for Dijkstra all-pairs and Greedy.

    Both curves are plotted on the same axes to allow direct comparison of
    growth rates.  Reference O(n²) and O(n log n) guide lines are included.

    Args:
        dijkstra_results: BenchmarkResult list from run_dijkstra_benchmark.
        greedy_results  : BenchmarkResult list from run_greedy_benchmark.
        filename        : Output PNG file name (saved to plots/).

    Returns:
        Absolute path to the saved PNG.
    """
    fig, ax = plt.subplots(figsize=(8, 5))

    # Dijkstra
    d_x = [r.n_nodes for r in dijkstra_results]
    d_y = [r.time_ms for r in dijkstra_results]
    ax.plot(d_x, d_y, "o-", color="steelblue", linewidth=2,
            markersize=6, label="Dijkstra (all-pairs)")

    # Greedy
    g_x = [r.n_nodes for r in greedy_results]
    g_y = [r.time_ms for r in greedy_results]
    ax.plot(g_x, g_y, "s--", color="darkorange", linewidth=2,
            markersize=6, label="Greedy Nearest-Neighbor")

    # Reference lines anchored to the largest Dijkstra point
    if d_x and d_y:
        x_ref = np.array(sorted(set(d_x + g_x)))
        x0, y0 = d_x[-1], d_y[-1]

        # O(n^2) guide
        ref_n2 = y0 * (x_ref / x0) ** 2
        ax.plot(x_ref, ref_n2, ":", color="gray", linewidth=1.2,
                label=r"$O(n^2)$ reference")

        # O(n log n) guide
        ref_nlogn = y0 * (x_ref * np.log(np.maximum(x_ref, 2))) / (
            x0 * np.log(max(x0, 2)))
        ax.plot(x_ref, ref_nlogn, "-.", color="lightgray", linewidth=1.2,
                label=r"$O(n \log n)$ reference")

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Number of Nodes (n)", fontsize=12)
    ax.set_ylabel("Runtime (ms)", fontsize=12)
    ax.set_title("Algorithm Runtime: Dijkstra vs Greedy (log-log)", fontsize=13)
    ax.legend(fontsize=10)
    ax.grid(True, which="both", linestyle="--", alpha=0.4)
    fig.tight_layout()
    path = _save(fig, filename)
    print(f"  Saved: {path}")
    return path


# ---------------------------------------------------------------------------
# 2. Memory usage
# ---------------------------------------------------------------------------

def plot_memory_usage(results: List[BenchmarkResult],
                      filename: str = "memory_usage.png") -> str:
    """
    Plot a grouped bar chart of memory footprint for different algorithms.

    Args:
        results : Combined list of BenchmarkResult (any algorithms).
        filename: Output PNG file name.

    Returns:
        Absolute path to the saved PNG.
    """
    # Group by algorithm
    algo_data: Dict[str, Dict[int, float]] = {}
    for r in results:
        algo_data.setdefault(r.algo_name, {})[r.n_nodes] = r.memory_kb

    algos = sorted(algo_data.keys())
    all_sizes = sorted({r.n_nodes for r in results})

    x = np.arange(len(all_sizes))
    width = 0.35
    colors = ["steelblue", "darkorange", "seagreen", "tomato"]

    fig, ax = plt.subplots(figsize=(10, 5))

    for k, algo in enumerate(algos):
        mem_vals = [algo_data[algo].get(n, 0.0) for n in all_sizes]
        offset = (k - (len(algos) - 1) / 2.0) * width
        bars = ax.bar(x + offset, mem_vals, width * 0.9,
                      label=algo, color=colors[k % len(colors)], alpha=0.85)
        # Value labels on bars
        for bar, val in zip(bars, mem_vals):
            if val > 0:
                ax.text(bar.get_x() + bar.get_width() / 2,
                        bar.get_height() + max(mem_vals) * 0.01,
                        f"{val:.0f}", ha="center", va="bottom",
                        fontsize=7, rotation=45)

    ax.set_yscale("log")
    ax.set_xticks(x)
    ax.set_xticklabels([str(n) for n in all_sizes], rotation=30, ha="right")
    ax.set_xlabel("Number of Nodes (n)", fontsize=12)
    ax.set_ylabel("Memory (KB, log scale)", fontsize=12)
    ax.set_title("Memory Footprint: Key Data Structures", fontsize=13)
    ax.legend(fontsize=10)
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    fig.tight_layout()
    path = _save(fig, filename)
    print(f"  Saved: {path}")
    return path


# ---------------------------------------------------------------------------
# 3. Optimality gap
# ---------------------------------------------------------------------------

def plot_optimality_gap(comparison_results: List[Dict],
                        filename: str = "optimality_gap.png") -> str:
    """
    Plot a bar chart of the greedy optimality gap (%) vs graph sizes.

    Args:
        comparison_results: List of dicts, each with keys:
                            'n_scenes', 'optimality_gap_pct',
                            'greedy_cost', 'dijkstra_lb'.
        filename: Output PNG file name.

    Returns:
        Absolute path to the saved PNG.
    """
    ns = [d["n_scenes"] for d in comparison_results]
    gaps = [d["optimality_gap_pct"] for d in comparison_results]
    greedy_costs = [d["greedy_cost"] for d in comparison_results]
    lb_costs = [d["dijkstra_lb"] for d in comparison_results]

    x = np.arange(len(ns))
    width = 0.35

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    # Left: gap percentage
    ax = axes[0]
    bars = ax.bar(x, gaps, color="tomato", alpha=0.85, width=0.6, label="Gap %")
    for bar, val in zip(bars, gaps):
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.3,
                f"{val:.1f}%", ha="center", va="bottom", fontsize=9)
    ax.set_xticks(x)
    ax.set_xticklabels([f"n={n}" for n in ns])
    ax.set_ylabel("Optimality Gap (%)", fontsize=12)
    ax.set_title("Greedy vs Dijkstra Lower Bound — Gap %", fontsize=12)
    ax.grid(axis="y", linestyle="--", alpha=0.4)

    # Right: absolute costs
    ax2 = axes[1]
    ax2.bar(x - width / 2, greedy_costs, width, label="Greedy cost",
            color="darkorange", alpha=0.85)
    ax2.bar(x + width / 2, lb_costs, width, label="Dijkstra LB",
            color="steelblue", alpha=0.85)
    ax2.set_xticks(x)
    ax2.set_xticklabels([f"n={n}" for n in ns])
    ax2.set_ylabel("Total Schedule Cost", fontsize=12)
    ax2.set_title("Absolute Costs: Greedy vs Dijkstra LB", fontsize=12)
    ax2.legend(fontsize=10)
    ax2.grid(axis="y", linestyle="--", alpha=0.4)

    fig.suptitle("Greedy Nearest-Neighbor Optimality Analysis", fontsize=13,
                 fontweight="bold")
    fig.tight_layout()
    path = _save(fig, filename)
    print(f"  Saved: {path}")
    return path


# ---------------------------------------------------------------------------
# 4. Adjacency matrix heatmap
# ---------------------------------------------------------------------------

def plot_graph_heatmap(matrix: List[List[float]],
                       title: str = "Adjacency Matrix",
                       filename: str = "graph_heatmap.png") -> str:
    """
    Plot a heatmap of an adjacency matrix.

    Zero entries (no edge) are shown in white; positive weights use a sequential
    colour map so heavier edges appear darker.

    Args:
        matrix  : 2-D list of floats (square adjacency matrix).
        title   : Plot title.
        filename: Output PNG file name.

    Returns:
        Absolute path to the saved PNG.
    """
    n = len(matrix)
    data = np.array(matrix, dtype=float)

    # Replace 0 (no edge) with NaN so they render as white
    masked = np.where(data == 0, np.nan, data)

    fig, ax = plt.subplots(figsize=(max(5, n * 0.6), max(4, n * 0.6)))

    cmap = plt.cm.YlOrRd.copy()
    cmap.set_bad("white")          # NaN → white

    im = ax.imshow(masked, cmap=cmap, aspect="auto",
                   norm=mcolors.LogNorm(
                       vmin=np.nanmin(masked[masked > 0]) if np.any(masked > 0) else 1,
                       vmax=np.nanmax(masked) if np.any(~np.isnan(masked)) else 1))

    # Cell annotations for small matrices
    if n <= 20:
        for i in range(n):
            for j in range(n):
                val = matrix[i][j]
                txt = f"{val:.0f}" if val > 0 else ""
                ax.text(j, i, txt, ha="center", va="center",
                        fontsize=max(6, 10 - n // 3),
                        color="black" if val < np.nanmax(masked) * 0.7 else "white")

    plt.colorbar(im, ax=ax, label="Edge Weight")
    ax.set_xticks(range(n))
    ax.set_yticks(range(n))
    ax.set_xticklabels([str(i) for i in range(n)], fontsize=max(6, 10 - n // 5))
    ax.set_yticklabels([str(i) for i in range(n)], fontsize=max(6, 10 - n // 5))
    ax.set_xlabel("Node Index", fontsize=11)
    ax.set_ylabel("Node Index", fontsize=11)
    ax.set_title(title, fontsize=13)
    fig.tight_layout()
    path = _save(fig, filename)
    print(f"  Saved: {path}")
    return path


# ---------------------------------------------------------------------------
# Main: generate all plots
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("  CS5800 Film Scheduling — Generating All Visualizations")
    print("=" * 70 + "\n")

    _ensure_plots_dir()

    # ---- Runtime benchmark data ----
    print("Collecting Dijkstra benchmark data...")
    dijk_results = run_dijkstra_benchmark(
        sizes=[10, 50, 100, 500, 1000, 5000, 10000])
    print("Collecting Greedy benchmark data...")
    greedy_results = run_greedy_benchmark(sizes=[10, 50, 100, 500, 1000])

    # ---- 1. Runtime curves ----
    print("\n[1] Runtime curves")
    plot_runtime_curves(dijk_results, greedy_results)

    # ---- 2. Memory usage ----
    print("\n[2] Memory usage")
    combined = dijk_results + greedy_results
    plot_memory_usage(combined)

    # ---- 3. Optimality gap ----
    print("\n[3] Optimality gap")
    gap_data = []
    for n_sc in [6, 8, 10, 12, 15, 20]:
        graph = create_film_benchmark(n_sc)
        scenes = list(range(n_sc))
        info = compare_optimality(graph, scenes)
        info["n_scenes"] = n_sc
        gap_data.append(info)
    plot_optimality_gap(gap_data)

    # ---- 4. Heatmaps for test matrices ----
    print("\n[4] Adjacency matrix heatmaps")
    test_data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "test_data")
    heatmap_configs = [
        ("toy_4node.txt",  "4-Node Toy Graph"),
        ("toy_6node.txt",  "6-Node Toy Graph"),
        ("scene_8.txt",    "8-Scene Film Benchmark"),
        ("scene_12.txt",   "12-Scene Film Benchmark"),
    ]
    for fname, title in heatmap_configs:
        fpath = os.path.join(test_data_dir, fname)
        if os.path.exists(fpath):
            mat = load_matrix(fpath)
            safe_name = fname.replace(".txt", "_heatmap.png")
            plot_graph_heatmap(mat, title=title, filename=safe_name)
        else:
            print(f"  (skipping {fname} — not found)")

    # ---- 5. Film benchmark heatmap ----
    print("\n[5] Film benchmark heatmap (8-scene)")
    fb8 = create_film_benchmark(8)
    plot_graph_heatmap(fb8.to_matrix(),
                       title="8-Scene Film Benchmark Adjacency Matrix",
                       filename="film_benchmark_8_heatmap.png")

    print("\nAll plots saved to:", _PLOTS_DIR)
