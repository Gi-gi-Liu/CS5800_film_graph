"""
visualize.py — Matplotlib plots for film scheduling algorithm analysis.

Generates:
  1. Runtime curve (log-log): Dijkstra all-pairs vs Greedy vs n.
  2. Adjacency matrix heatmaps for the film benchmarks.

All plots are saved to liu/plots/ as PNG files.

Run directly to generate all plots from the same seeded generators used
everywhere else in this project:
    python visualize.py
"""

from __future__ import annotations
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))
from typing import List

# --- matplotlib configuration (non-interactive backend for script use) -----
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np

from benchmark import TimingResult, run_dijkstra_benchmark, run_greedy_benchmark
from data_gen import create_film_benchmark

# ---------------------------------------------------------------------------
# Output directory
# ---------------------------------------------------------------------------

_PLOTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plots")


def _ensure_plots_dir() -> str:
    """Create and return the plots output directory."""
    os.makedirs(_PLOTS_DIR, exist_ok=True)
    return _PLOTS_DIR


def _save(fig: plt.Figure, filename: str) -> str:
    """Save *fig* as a PNG file in the plots directory and close it."""
    path = os.path.join(_ensure_plots_dir(), filename)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


# ---------------------------------------------------------------------------
# 1. Runtime curve
# ---------------------------------------------------------------------------

def plot_runtime_curves(dijkstra_results: List[TimingResult],
                        greedy_results: List[TimingResult],
                        filename: str = "runtime_curves.png") -> str:
    """
    Plot log-log runtime curves for Dijkstra all-pairs and Greedy.

    Args:
        dijkstra_results: TimingResult list from run_dijkstra_benchmark.
        greedy_results  : TimingResult list from run_greedy_benchmark.
        filename        : Output PNG file name (saved to plots/).

    Returns:
        Absolute path to the saved PNG.
    """
    fig, ax = plt.subplots(figsize=(8, 5))

    d_x = [r.n_nodes for r in dijkstra_results]
    d_y = [r.time_ms for r in dijkstra_results]
    ax.plot(d_x, d_y, "o-", color="steelblue", linewidth=2,
            markersize=6, label="Dijkstra (all-pairs)")

    g_x = [r.n_nodes for r in greedy_results]
    g_y = [r.time_ms for r in greedy_results]
    ax.plot(g_x, g_y, "s--", color="darkorange", linewidth=2,
            markersize=6, label="Greedy Nearest-Neighbor")

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
# 2. Adjacency matrix heatmap
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
    masked = np.where(data == 0, np.nan, data)

    fig, ax = plt.subplots(figsize=(max(5, n * 0.6), max(4, n * 0.6)))

    cmap = plt.cm.YlOrRd.copy()
    cmap.set_bad("white")

    im = ax.imshow(masked, cmap=cmap, aspect="auto",
                   norm=mcolors.LogNorm(
                       vmin=np.nanmin(masked[masked > 0]) if np.any(masked > 0) else 1,
                       vmax=np.nanmax(masked) if np.any(~np.isnan(masked)) else 1))

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
    print("\n" + "=" * 60)
    print("  CS5800 Film Scheduling — Generating Visualizations")
    print("=" * 60 + "\n")

    _ensure_plots_dir()

    sizes = [10, 50, 100, 500]
    print("Collecting Dijkstra benchmark data...")
    dijk_results = run_dijkstra_benchmark(sizes)
    print("Collecting Greedy benchmark data...")
    greedy_results = run_greedy_benchmark(sizes)

    print("\n[1] Runtime curve")
    plot_runtime_curves(dijk_results, greedy_results)

    print("\n[2] Adjacency matrix heatmaps")
    for n_sc in [6, 8, 12]:
        fb = create_film_benchmark(n_sc)
        plot_graph_heatmap(fb.to_matrix(),
                           title=f"{n_sc}-Scene Film Benchmark Adjacency Matrix",
                           filename=f"film_benchmark_{n_sc}_heatmap.png")

    print("\nAll plots saved to:", _PLOTS_DIR)
