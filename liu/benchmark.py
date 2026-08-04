"""
benchmark.py — Timing and memory benchmarks comparing Dijkstra vs Greedy.

Metrics collected:
  - Wall-clock time in milliseconds (time.perf_counter).
  - Approximate memory in KB (sys.getsizeof on key data structures).
  - Number of nodes visited / settled by Dijkstra.
  - Optimality gap: (greedy_cost - dijkstra_lower_bound) / dijkstra_lower_bound.

Run directly to execute all benchmarks and print formatted tables:
    python benchmark.py
"""

from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import time
from dataclasses import dataclass, field
from typing import List, Optional, Dict

from graph import SpatialGraph
from data_gen import generate_sparse_graph, create_film_benchmark
from dijkstra import (dijkstra, all_pairs_shortest_paths,
                      all_pairs_results, DijkstraResult, INF)
from greedy import greedy_nearest_neighbor, GreedyResult


# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------

@dataclass
class BenchmarkResult:
    """
    Statistics for a single algorithm run on a single graph size.

    Attributes:
        algo_name    : Human-readable algorithm identifier.
        n_nodes      : Number of graph nodes.
        time_ms      : Wall-clock time in milliseconds.
        memory_kb    : Approximate peak memory used (KB), estimated via sys.getsizeof.
        visited_nodes: Nodes settled (Dijkstra) or scenes visited (Greedy).
        optimality_gap: Relative gap vs Dijkstra lower bound (0.0 for Dijkstra itself).
    """
    algo_name: str
    n_nodes: int
    time_ms: float
    memory_kb: float
    visited_nodes: int
    optimality_gap: float = 0.0

    def row(self) -> str:
        """Format as a fixed-width table row."""
        gap_str = f"{self.optimality_gap * 100:.2f}%" if self.optimality_gap else "  N/A"
        return (f"  {self.algo_name:<22s}  {self.n_nodes:>7d}  "
                f"{self.time_ms:>10.2f}  {self.memory_kb:>10.1f}  "
                f"{self.visited_nodes:>14d}  {gap_str:>12s}")


def _header() -> str:
    return (f"  {'Algorithm':<22s}  {'N Nodes':>7s}  "
            f"{'Time (ms)':>10s}  {'Memory KB':>10s}  "
            f"{'Visited Nodes':>14s}  {'Optimality Gap':>12s}")


def _separator() -> str:
    return "  " + "-" * 88


# ---------------------------------------------------------------------------
# Memory estimation helpers
# ---------------------------------------------------------------------------

def _sizeof_list2d(lst: List[List[float]]) -> int:
    """Approximate bytes used by a 2-D list of floats."""
    total = sys.getsizeof(lst)
    for row in lst:
        total += sys.getsizeof(row)
        total += len(row) * 8  # 8 bytes per float
    return total


def _sizeof_dijkstra_result(result: DijkstraResult) -> int:
    """Approximate bytes used by a single DijkstraResult."""
    return (sys.getsizeof(result)
            + sys.getsizeof(result.dist) + len(result.dist) * 8
            + sys.getsizeof(result.prev) + len(result.prev) * 8)


# ---------------------------------------------------------------------------
# Dijkstra benchmark
# ---------------------------------------------------------------------------

def run_dijkstra_benchmark(
        sizes: Optional[List[int]] = None,
        all_pairs_threshold: int = 1000) -> List[BenchmarkResult]:
    """
    Benchmark Dijkstra on sparse graphs of increasing size.

    For sizes up to *all_pairs_threshold*:
        Runs all_pairs_shortest_paths (one Dijkstra per source).
    For sizes above the threshold:
        Runs a single-source Dijkstra and extrapolates time to approximate
        all-pairs cost, keeping the benchmark practical for n=5000/10000.

    Args:
        sizes               : List of node counts to test.
                              Default: [10, 50, 100, 500, 1000, 5000, 10000].
        all_pairs_threshold : Maximum n for which all-pairs is run in full.

    Returns:
        List of BenchmarkResult, one per size.
    """
    if sizes is None:
        sizes = [10, 50, 100, 500, 1000, 5000, 10000]

    results: List[BenchmarkResult] = []
    for n in sizes:
        graph = generate_sparse_graph(n, edge_prob=0.05, seed=n)

        if n <= all_pairs_threshold:
            # Full all-pairs run
            t0 = time.perf_counter()
            cost_matrix = all_pairs_shortest_paths(graph)
            t1 = time.perf_counter()
            time_ms = (t1 - t0) * 1000.0
            mem_kb = _sizeof_list2d(cost_matrix) / 1024.0
            single = dijkstra(graph, 0)
            total_visited = single.visited_count * n  # approximate
            algo_name = "Dijkstra (all-pairs)"
        else:
            # Single-source run; extrapolate for all-pairs estimate
            t0 = time.perf_counter()
            single = dijkstra(graph, 0)
            t1 = time.perf_counter()
            single_ms = (t1 - t0) * 1000.0
            time_ms = single_ms * n  # extrapolated all-pairs time
            # Memory: n×n cost matrix (estimated)
            mem_kb = (n * n * 8) / 1024.0
            total_visited = single.visited_count * n
            algo_name = "Dijkstra (all-pairs,est)"

        results.append(BenchmarkResult(
            algo_name=algo_name,
            n_nodes=n,
            time_ms=time_ms,
            memory_kb=mem_kb,
            visited_nodes=total_visited,
            optimality_gap=0.0,
        ))

    return results


# ---------------------------------------------------------------------------
# Greedy benchmark
# ---------------------------------------------------------------------------

def run_greedy_benchmark(
        sizes: Optional[List[int]] = None) -> List[BenchmarkResult]:
    """
    Benchmark the greedy nearest-neighbor heuristic on sparse graphs.

    For each size:
        1. Generate sparse graph.
        2. Compute all-pairs Dijkstra cost matrix (preprocessing, not counted).
        3. Time the greedy nearest-neighbor run over all nodes.
        4. Record time, memory (cost matrix + GreedyResult), visited count.

    Args:
        sizes: List of node counts.  Default: [10, 50, 100, 500, 1000].

    Returns:
        List of BenchmarkResult, one per size.
    """
    if sizes is None:
        sizes = [10, 50, 100, 500, 1000]

    results: List[BenchmarkResult] = []
    for n in sizes:
        graph = generate_sparse_graph(n, edge_prob=0.05, seed=n)
        # Precompute cost matrix (not timed — this is Dijkstra's responsibility)
        cost_matrix = all_pairs_shortest_paths(graph)

        t0 = time.perf_counter()
        greedy_res = greedy_nearest_neighbor(cost_matrix, start=0)
        t1 = time.perf_counter()

        time_ms = (t1 - t0) * 1000.0
        mem_kb = (_sizeof_list2d(cost_matrix)
                  + sys.getsizeof(greedy_res.order) * len(greedy_res.order) * 8
                  ) / 1024.0

        results.append(BenchmarkResult(
            algo_name="Greedy NearestNeighbor",
            n_nodes=n,
            time_ms=time_ms,
            memory_kb=mem_kb,
            visited_nodes=len(greedy_res.order),
            optimality_gap=0.0,  # filled in by compare_optimality
        ))

    return results


# ---------------------------------------------------------------------------
# Optimality gap comparison
# ---------------------------------------------------------------------------

def compare_optimality(graph: SpatialGraph,
                       scene_indices: List[int]) -> Dict[str, float]:
    """
    Compare the greedy schedule cost against a Dijkstra-based lower bound.

    Lower bound construction:
        For each consecutive pair in the greedy order, the shortest-path cost
        (from Dijkstra) gives the minimum possible transition cost.  The sum of
        all n−1 minimum-cost transitions is a lower bound on any tour visiting
        all scenes.

        Note: this is a *relaxed* lower bound because it ignores ordering
        constraints.  The true optimum (TSP) is NP-hard; Dijkstra gives us the
        pairwise minimum transition costs.

    Args:
        graph        : The SpatialGraph to analyse.
        scene_indices: Node indices of the scenes to be filmed.

    Returns:
        Dict with keys:
            'greedy_cost'       : Total cost from the greedy heuristic.
            'dijkstra_lb'       : Dijkstra-based lower bound.
            'optimality_gap'    : (greedy - lb) / lb  (relative gap, 0..∞).
            'optimality_gap_pct': Gap as percentage.
    """
    cost_matrix = all_pairs_shortest_paths(graph)
    greedy_res = greedy_nearest_neighbor(cost_matrix, start=scene_indices[0],
                                         scene_indices=scene_indices)
    greedy_cost = greedy_res.total_cost

    # Lower bound: sum of cheapest outgoing edges from each scene (except last)
    lb = 0.0
    for i, u in enumerate(scene_indices[:-1]):
        # Cheapest way to reach *any* other scene in the set
        remaining = [v for v in scene_indices if v != u]
        best = min(cost_matrix[u][v] for v in remaining
                   if cost_matrix[u][v] < INF)
        lb += best

    gap = (greedy_cost - lb) / lb if lb > 0 else 0.0

    return {
        "greedy_cost": greedy_cost,
        "dijkstra_lb": lb,
        "optimality_gap": gap,
        "optimality_gap_pct": gap * 100.0,
    }


# ---------------------------------------------------------------------------
# Formatted table printing
# ---------------------------------------------------------------------------

def print_table(results: List[BenchmarkResult], title: str = "") -> None:
    """Print a formatted benchmark table to stdout."""
    if title:
        print(f"\n{'='*90}")
        print(f"  {title}")
        print(f"{'='*90}")
    print(_header())
    print(_separator())
    for r in results:
        print(r.row())
    print()


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("\n" + "=" * 90)
    print("  CS5800 Film Location Scheduling — Liu's Algorithm Benchmarks")
    print("=" * 90)

    # ---- 1. Dijkstra all-pairs benchmark ----
    print("\nRunning Dijkstra all-pairs benchmark...")
    print("  (n <= 1000: full all-pairs run; n > 1000: single-source * n extrapolation)")
    dijk_results = run_dijkstra_benchmark(
        sizes=[10, 50, 100, 500, 1000, 5000, 10000],
        all_pairs_threshold=1000)
    print_table(dijk_results, "Dijkstra All-Pairs Shortest Paths")

    # ---- 2. Greedy benchmark ----
    print("Running Greedy Nearest-Neighbor benchmark...")
    greedy_results = run_greedy_benchmark(sizes=[10, 50, 100, 500, 1000])
    print_table(greedy_results, "Greedy Nearest-Neighbor Schedule")

    # ---- 3. Optimality gap comparison on film benchmarks ----
    print("=" * 90)
    print("  Optimality Gap: Greedy vs Dijkstra Lower Bound")
    print("=" * 90)
    print(f"  {'Graph':<20s}  {'Greedy Cost':>12s}  "
          f"{'Dijkstra LB':>12s}  {'Gap %':>10s}")
    print("  " + "-" * 62)

    for n_sc in [6, 8, 10, 12]:
        graph = create_film_benchmark(n_sc)
        scenes = list(range(n_sc))
        gap_info = compare_optimality(graph, scenes)
        print(f"  film_benchmark_{n_sc:<5d}  "
              f"{gap_info['greedy_cost']:>12.2f}  "
              f"{gap_info['dijkstra_lb']:>12.2f}  "
              f"{gap_info['optimality_gap_pct']:>9.2f}%")

    print()
    print("  Note: Dijkstra LB is a relaxed lower bound (sum of cheapest")
    print("  per-node outgoing costs); true TSP optimum may be higher.")
    print()

    # ---- 4. Single-source Dijkstra stats on a mid-size graph ----
    print("=" * 90)
    print("  Single-Source Dijkstra Statistics (n=100, source=0)")
    print("=" * 90)
    g100 = generate_sparse_graph(100, edge_prob=0.05, seed=7)
    t0 = time.perf_counter()
    res = dijkstra(g100, 0)
    t1 = time.perf_counter()
    print(f"  Nodes visited  : {res.visited_count}")
    print(f"  Heap ops       : {res.heap_ops}")
    print(f"  Time           : {(t1-t0)*1000:.3f} ms")
    reachable = sum(1 for d in res.dist if d < INF)
    print(f"  Reachable nodes: {reachable} / {g100.n}")
    print()
