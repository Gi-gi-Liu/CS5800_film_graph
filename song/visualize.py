"""
visualize.py — Matplotlib plots for the scheduling layer.

Generates:
  1. Exact-solver cost: time and states settled against location count.
  2. Cost above the proven optimum, partitioned vs greedy.
  3. Cost against the region size cap, one panel per production.
  4. Both schedules for one production, drawn on its real coordinates.

All plots are saved to song/plots/ as PNG files.

Run directly to generate all plots from the same data and solvers used
everywhere else in this project:
    python visualize.py
"""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "liu"))

import time
from math import cos, radians
from typing import Dict, List, Tuple

# --- matplotlib configuration (non-interactive backend for script use) -----
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from dijkstra import all_pairs_shortest_paths            # geographic layer
from greedy import greedy_nearest_neighbor               # geographic layer

from clustered_dp import PartitionError, clustered_schedule
from film_data import PRODUCTIONS, build_production
from road_network import GeoNode, assemble_road_network
from schedule_dp import EXACT_LIMIT, optimal_schedule

# Colours are checked for colour-blind separation and for contrast against a
# white page, so the plots stay readable printed in grey as well as on screen.
GREEDY = "#2a78d6"
SCHEDULED = "#eb6834"
EXACT = "#1baf7a"
INK = "#0b0b0b"
MUTED = "#898781"
GRID = "#e1e0d9"

_PLOTS_DIR = os.path.join(_HERE, "plots")


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


def _style(ax: plt.Axes, xlabel: str = "", ylabel: str = "") -> None:
    """Recessive axes and gridlines, so the data is the loudest thing."""
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=9)
    ax.set_axisbelow(True)
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=10, color=INK)
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=10, color=INK)


# ---------------------------------------------------------------------------
# 1. Exact-solver cost against location count
# ---------------------------------------------------------------------------

def plot_exact_scaling(key: str = "la_la_land",
                       filename: str = "exact_scaling.png") -> str:
    """
    Time and states settled for the exact solver, on growing real subsets.

    Both axes are logarithmic, so the doubling per added location shows up as a
    straight line.

    Args:
        key     : Which production's locations to take the subsets from.
        filename: Output file name inside song/plots/.

    Returns:
        The path the figure was written to.
    """
    _, nodes, _ = build_production(key)
    ns, secs, states = [], [], []
    for n in range(4, EXACT_LIMIT + 1):
        sub = [GeoNode(id=i, name=d.name, terrain_type=d.terrain_type,
                       elevation_m=d.elevation_m, is_basecamp=(i == 0),
                       lat=d.lat, lon=d.lon, city=d.city)
               for i, d in enumerate(nodes[:n])]
        cost = all_pairs_shortest_paths(assemble_road_network(sub))
        t0 = time.perf_counter()
        res = optimal_schedule(cost, start=0)
        secs.append(time.perf_counter() - t0)
        states.append(res.states_settled)
        ns.append(n)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.4))

    ax1.plot(ns, secs, color=EXACT, linewidth=2, marker="o", markersize=5,
             markeredgecolor="white", markeredgewidth=1.2)
    ax1.set_yscale("log")
    ax1.grid(True, axis="y", color=GRID, linewidth=0.8)
    _style(ax1, "locations", "seconds to prove the optimum")
    ax1.set_title(f"Time  ({secs[-1]:.1f} s at n = {ns[-1]})",
                  fontsize=11, color=INK, loc="left")

    ax2.plot(ns, states, color=EXACT, linewidth=2, marker="o", markersize=5,
             markeredgecolor="white", markeredgewidth=1.2)
    ax2.set_yscale("log")
    ax2.grid(True, axis="y", color=GRID, linewidth=0.8)
    _style(ax2, "locations", "DP states settled")
    ax2.set_title(f"States  ({states[-1]:,} at n = {ns[-1]})",
                  fontsize=11, color=INK, loc="left")

    fig.suptitle("Exact solver cost by location count (log scale)",
                 fontsize=13, color=INK, x=0.5, y=1.02)
    return _save(fig, filename)


# ---------------------------------------------------------------------------
# 2. Cost above the proven optimum
# ---------------------------------------------------------------------------

def _subset_upto(nodes: List[GeoNode], limit: int) -> List[GeoNode]:
    """Take whole places until adding another would pass `limit` locations."""
    groups: Dict[str, List[GeoNode]] = {}
    for nd in nodes:
        groups.setdefault(nd.city, []).append(nd)
    picked: List[GeoNode] = []
    for members in groups.values():
        if len(picked) + len(members) <= limit:
            picked.extend(members)
    return [GeoNode(id=i, name=nd.name, terrain_type=nd.terrain_type,
                    elevation_m=nd.elevation_m, is_basecamp=(i == 0),
                    lat=nd.lat, lon=nd.lon, city=nd.city)
            for i, nd in enumerate(picked)]


def plot_optimality_gap(filename: str = "optimality_gap.png") -> str:
    """
    Percentage above the proven optimum, partitioned and greedy.

    Measured on the largest subset of each production the exact solver can still
    prove, so there is a true optimum to compare against.

    Args:
        filename: Output file name inside song/plots/.

    Returns:
        The path the figure was written to.
    """
    titles, part_gaps, greedy_gaps = [], [], []
    for key in PRODUCTIONS:
        _, nodes, prod = build_production(key)
        sub = _subset_upto(nodes, EXACT_LIMIT)
        cost = all_pairs_shortest_paths(assemble_road_network(sub))
        opt = optimal_schedule(cost, start=0).total_cost
        # always_partition, or a subset this size would skip the partition and
        # simply be the exact solver again.
        part = clustered_schedule(cost, start=0, always_partition=True)
        draft = greedy_nearest_neighbor(cost, start=0)
        gap = lambda v: 0.0 if abs(v - opt) < 1e-9 else (v - opt) / opt * 100
        titles.append(prod.title)
        part_gaps.append(gap(part.total_cost))
        greedy_gaps.append(gap(draft.total_cost))

    y = list(range(len(titles)))
    fig, ax = plt.subplots(figsize=(8.5, 3.4))
    # Dots rather than bars: the partitioned gap is 0.00% on every production,
    # and a zero-width bar renders as nothing at all.
    for i, (pg, gg) in enumerate(zip(part_gaps, greedy_gaps)):
        ax.plot([pg, gg], [i, i], color=GRID, linewidth=2, zorder=1)
        ax.scatter([gg], [i], s=110, color=GREEDY, zorder=3,
                   edgecolors="white", linewidths=1.5)
        ax.scatter([pg], [i], s=110, color=SCHEDULED, zorder=4,
                   edgecolors="white", linewidths=1.5)
        ax.annotate(f"+{gg:.2f}%", (gg, i), xytext=(9, 0),
                    textcoords="offset points", va="center", fontsize=9,
                    color=INK)
    ax.axvline(0, color=EXACT, linewidth=2, zorder=2)
    ax.annotate("proven optimum", (0, len(titles) - 0.42), xytext=(6, 0),
                textcoords="offset points", fontsize=9, color=EXACT)
    ax.set_yticks(y)
    ax.set_yticklabels(titles, fontsize=10, color=INK)
    ax.invert_yaxis()
    ax.set_xlim(-0.15, max(greedy_gaps) * 1.3)
    ax.set_ylim(len(titles) - 0.3, -0.7)
    ax.grid(True, axis="x", color=GRID, linewidth=0.8)
    _style(ax, "cost above the proven optimum (%)")
    ax.scatter([], [], s=110, color=SCHEDULED, label="Partitioned")
    ax.scatter([], [], s=110, color=GREEDY, label="Greedy draft")
    ax.legend(frameon=False, fontsize=9, loc="lower right")
    ax.set_title("Cost above the proven optimum",
                 fontsize=12, color=INK, loc="left", pad=12)
    return _save(fig, filename)


# ---------------------------------------------------------------------------
# 3. Cost against the region size cap
# ---------------------------------------------------------------------------

def plot_region_cap(filename: str = "region_cap.png") -> str:
    """
    Cost against the region size cap, as a percentage above each production's
    own best, with the caps that cannot be partitioned marked.

    Args:
        filename: Output file name inside song/plots/.

    Returns:
        The path the figure was written to.
    """
    caps = list(range(2, 13))
    fig, axes = plt.subplots(1, len(PRODUCTIONS), figsize=(12, 3.6),
                             sharey=True)
    for ax, key in zip(axes, PRODUCTIONS):
        graph, _, prod = build_production(key)
        cost = all_pairs_shortest_paths(graph)
        xs, ys, failed = [], [], []
        for cap in caps:
            try:
                ys.append(clustered_schedule(cost, start=0,
                                             region_cap=cap).total_cost)
                xs.append(cap)
            except PartitionError:
                failed.append(cap)
        best = min(ys)
        pct = [(v - best) / best * 100 for v in ys]
        ax.plot(xs, pct, color=SCHEDULED, linewidth=2, marker="o",
                markersize=5, markeredgecolor="white", markeredgewidth=1.2)
        for cap in failed:
            ax.axvspan(cap - 0.5, cap + 0.5, color=GRID, alpha=0.7, lw=0)
        ax.grid(True, axis="y", color=GRID, linewidth=0.8)
        _style(ax, "region size cap")
        ax.set_title(prod.title, fontsize=10.5, color=INK, loc="left")
        if failed:
            ax.text(failed[0] - 0.3, ax.get_ylim()[1] * 0.9,
                    "cannot partition", fontsize=8, color=MUTED, rotation=90,
                    va="top")
    axes[0].set_ylabel("% above this production's best", fontsize=10, color=INK)
    fig.suptitle("Cost by region size cap", fontsize=13, color=INK,
                 x=0.5, y=1.04)
    return _save(fig, filename)


# ---------------------------------------------------------------------------
# 4. Both schedules on the map
# ---------------------------------------------------------------------------

def _blocks(nodes: List[GeoNode],
            order: List[int]) -> List[Tuple[str, float, float]]:
    """
    Collapse a location-level order to the places it moves between.

    At map scale the locations inside one place sit within a pixel or two of
    each other, so the readable unit is the place.
    """
    out: List[Tuple[str, float, float]] = []
    for v in order:
        place = nodes[v].city
        if out and out[-1][0] == place:
            continue
        members = [nd for nd in nodes if nd.city == place]
        out.append((place,
                    sum(nd.lat for nd in members) / len(members),
                    sum(nd.lon for nd in members) / len(members)))
    return out


def plot_routes(key: str = "la_la_land",
                filename: str = "routes_la_la_land.png") -> str:
    """
    Draw the greedy draft and the scheduled route on their real coordinates.

    Args:
        key     : Which production to draw.
        filename: Output file name inside song/plots/.

    Returns:
        The path the figure was written to.
    """
    graph, nodes, prod = build_production(key)
    cost = all_pairs_shortest_paths(graph)
    routes = [("Greedy draft", greedy_nearest_neighbor(cost, start=0), GREEDY),
              ("Scheduled", clustered_schedule(cost, start=0), SCHEDULED)]

    scale = cos(radians(sum(nd.lat for nd in nodes) / len(nodes)))
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.4))
    for ax, (label, res, colour) in zip(axes, routes):
        blocks = _blocks(nodes, list(res.order))
        xs = [lon * scale for _, _, lon in blocks]
        ys = [lat for _, lat, _ in blocks]
        ax.plot(xs, ys, color=colour, linewidth=1.8, zorder=2, alpha=0.9)
        ax.scatter(xs, ys, s=45, color=colour, edgecolors="white",
                   linewidths=1.5, zorder=3)
        ax.scatter([xs[0]], [ys[0]], s=190, facecolors="none",
                   edgecolors=INK, linewidths=1.4, zorder=4)
        # Place labels collide badly where a production clusters — Hollywood
        # and West Hollywood land almost on top of each other. Offsets are
        # chosen greedily: try the four corners, keep the first that does not
        # overlap a label already placed.
        placed: List[Tuple[float, float, float, float]] = []
        w_per_char, h_lab = 0.0062 * (max(xs) - min(xs)), 0.030 * (max(ys) - min(ys))
        for i, (place, _, _) in enumerate(blocks):
            text = f"{i + 1}. {place}"
            w_lab = len(text) * w_per_char
            for dx, dy, ha in ((0.008, 0.012, "left"), (-0.008, 0.012, "right"),
                               (0.008, -0.022, "left"), (-0.008, -0.022, "right"),
                               (0.008, 0.036, "left"), (-0.008, -0.046, "right")):
                ox = xs[i] + dx * (max(xs) - min(xs)) * 3
                oy = ys[i] + dy * (max(ys) - min(ys)) * 3
                x0 = ox if ha == "left" else ox - w_lab
                box = (x0, oy - h_lab / 2, x0 + w_lab, oy + h_lab / 2)
                if not any(box[0] < q[2] and q[0] < box[2]
                           and box[1] < q[3] and q[1] < box[3] for q in placed):
                    break
            placed.append(box)
            ax.annotate(text, (ox, oy), fontsize=7.5, color=MUTED, ha=ha,
                        va="center")
        ax.set_aspect("equal")
        ax.set_xticks([])
        ax.set_yticks([])
        for side in ("top", "right", "left", "bottom"):
            ax.spines[side].set_visible(False)
        ax.set_title(f"{label} — cost {res.total_cost:,.0f}",
                     fontsize=11, color=INK, loc="left")
        ax.margins(0.12)

    fig.suptitle(f"{prod.title} — {graph.n} locations, "
                 f"numbered in shooting order (circle = base)",
                 fontsize=13, color=INK, x=0.5, y=1.02)
    return _save(fig, filename)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Generating plots into song/plots/ ...")
    for fn in (plot_exact_scaling, plot_optimality_gap,
               plot_region_cap, plot_routes):
        print(f"  {fn.__name__:<22s} -> {fn()}")
    print("Done.")
