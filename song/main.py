"""
main.py — End-to-end pipeline: a film's locations in, its shooting schedule out.

    real filming locations
          |
          v
    [ geographic layer ]         terrain-weighted graph
          |                      Dijkstra all-pairs
          v
      cost matrix                "what does each move really cost?"
          |
          v
    [ scheduling layer ]         MST regions, then exact DP within and across
          |
          v
    shooting order               "so shoot them in this order"

Locations are taken as already deduplicated: all scenes sharing a location are
shot in one visit.  Per-location shooting cost is then a constant that every
ordering pays equally, so it cannot change which ordering is cheapest and is
left out of the objective.

Usage:
    python main.py                    # list the available productions
    python main.py la_la_land         # schedule one
    python main.py tenet --closed     # ... and return to base at wrap
"""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "liu"))


from dijkstra import all_pairs_shortest_paths           # geographic layer
from greedy import greedy_nearest_neighbor              # geographic layer

from film_data import PRODUCTIONS, build_production, true_groups
from solver import solve                                # scheduling layer


def run_pipeline(key: str, return_to_base: bool = False) -> None:
    """
    Run both layers on one production and print the resulting schedule.

    Args:
        key           : A key from film_data.PRODUCTIONS.
        return_to_base: If True the crew returns to base after the last location.
    """
    graph, nodes, prod = build_production(key)
    groups = true_groups(nodes)

    print("=" * 78)
    print(f"  SHOOTING SCHEDULE — {prod.title}")
    print(f"  {prod.scale}"
          f"{', returning to base' if return_to_base else ''}")
    print("=" * 78)

    # ---- Layer 1: locations -> terrain-weighted graph -> cost matrix --------
    roads = sum(1 for i in range(graph.n) for j in range(i + 1, graph.n)
                if graph.weight(i, j) > 0)
    cost = all_pairs_shortest_paths(graph)

    print(f"\n  [1] Geographic layer")
    print(f"      {graph.n} locations in {len(groups)} places, {roads} roads")
    print(f"      Dijkstra -> {graph.n}x{graph.n} cost matrix")
    print(f"      source: {prod.source}")

    # ---- Layer 2: cost matrix -> shooting order ----------------------------
    report = solve(cost, start=0, return_to_base=return_to_base)
    res = report.result

    print(f"\n  [2] Scheduling layer")
    print(f"      regions   : {report.regions}"
          f"{'  (nothing to partition — solved exactly)' if report.regions == 1 else ''}")
    print(f"      guarantee : {report.guarantee}")
    print(f"      solved in : {report.elapsed_ms:.1f} ms")

    # ---- Output ------------------------------------------------------------
    print(f"\n  SHOOTING ORDER")
    print(f"  {'#':>3s}  {'location':<30s} {'place':<20s} {'move':>9s}")
    print("  " + "-" * 68)
    prev_place = None
    for step, v in enumerate(res.order):
        place = nodes[v].city
        shown = place if place != prev_place else ""
        prev_place = place
        move = "— base —" if step == 0 else f"{res.leg_costs[step - 1]:,.0f}"
        print(f"  {step + 1:>3d}  {nodes[v].name:<30s} {shown:<20s} {move:>9s}")
    print("  " + "-" * 68)
    print(f"  {'':>3s}  {'TOTAL TRANSITION COST':<30s} {'':<20s} "
          f"{res.total_cost:>9,.0f}")

    moves = sum(1 for a, b in zip(res.order, res.order[1:])
                if nodes[a].city != nodes[b].city)
    print(f"\n  Moved between places {moves} times "
          f"(fewest possible: {len(groups) - 1}).")

    draft = greedy_nearest_neighbor(cost, start=0)
    if not return_to_base and draft.total_cost > res.total_cost:
        saved = draft.total_cost - res.total_cost
        print(f"  The greedy draft costs {draft.total_cost:,.0f} — "
              f"this schedule saves {saved:,.0f} "
              f"({saved / draft.total_cost * 100:.1f}%).")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print("Available productions:\n")
        for key, prod in PRODUCTIONS.items():
            print(f"  {key:<16s} {prod.title:<24s} "
                  f"{len(prod.locations):>3d} locations — {prod.scale}")
        print("\nUsage: python main.py <key> [--closed]")
        sys.exit(0)
    if args[0] not in PRODUCTIONS:
        print(f"Unknown production {args[0]!r}. "
              f"Choose from: {', '.join(PRODUCTIONS)}")
        sys.exit(1)
    run_pipeline(args[0], return_to_base="--closed" in sys.argv)
