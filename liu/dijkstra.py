"""
dijkstra.py — Dijkstra's shortest-path algorithm with a custom min-heap.

Key design decisions:
  - MinHeap is implemented from scratch as a list-based binary heap.
    Decrease-key is handled via *lazy deletion*: stale (dist, node) pairs are
    pushed and silently skipped when popped if a shorter path was already found.
  - DijkstraResult records visited_count and heap_ops for benchmarking.
  - all_pairs_shortest_paths returns a cost matrix (2-D list) for use by the
    greedy solver and Song's DP solver.
"""

from __future__ import annotations
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple

from graph import SpatialGraph

INF = float("inf")


# ---------------------------------------------------------------------------
# Custom min-heap (no heapq)
# ---------------------------------------------------------------------------

class MinHeap:
    """
    Binary min-heap operating on (priority, value) tuples.

    Implemented as a list-based binary tree where:
        parent(i)      = (i - 1) // 2
        left_child(i)  = 2*i + 1
        right_child(i) = 2*i + 2

    Supports:
        push(priority, value)  — O(log n)
        pop()                  — O(log n) → (priority, value) or raises IndexError
        peek()                 — O(1) → (priority, value) without removing
        __len__                — number of items currently stored
    """

    def __init__(self) -> None:
        """Initialise an empty heap."""
        self._data: List[Tuple[float, int]] = []
        self.ops: int = 0  # total sift operations performed (for benchmarking)

    # ------------------------------------------------------------------
    # Core heap operations
    # ------------------------------------------------------------------

    def push(self, priority: float, value: int) -> None:
        """
        Insert (priority, value) into the heap.

        Time complexity: O(log n).
        """
        self._data.append((priority, value))
        self._sift_up(len(self._data) - 1)
        self.ops += 1

    def pop(self) -> Tuple[float, int]:
        """
        Remove and return the (priority, value) pair with the smallest priority.

        Raises:
            IndexError: If the heap is empty.

        Time complexity: O(log n).
        """
        if not self._data:
            raise IndexError("pop from an empty MinHeap")
        # Swap root with last element, then shrink and sift down
        self._data[0], self._data[-1] = self._data[-1], self._data[0]
        item = self._data.pop()
        if self._data:
            self._sift_down(0)
        self.ops += 1
        return item

    def peek(self) -> Tuple[float, int]:
        """
        Return the minimum (priority, value) without removing it.

        Raises:
            IndexError: If the heap is empty.

        Time complexity: O(1).
        """
        if not self._data:
            raise IndexError("peek on an empty MinHeap")
        return self._data[0]

    def __len__(self) -> int:
        """Return the number of items in the heap."""
        return len(self._data)

    def is_empty(self) -> bool:
        """Return True if the heap contains no items."""
        return len(self._data) == 0

    # ------------------------------------------------------------------
    # Internal sift helpers
    # ------------------------------------------------------------------

    def _sift_up(self, idx: int) -> None:
        """
        Restore the heap property by moving element at idx upward.

        Called after insertion (element placed at the end).
        """
        data = self._data
        while idx > 0:
            parent = (idx - 1) // 2
            if data[parent][0] > data[idx][0]:
                data[parent], data[idx] = data[idx], data[parent]
                idx = parent
            else:
                break

    def _sift_down(self, idx: int) -> None:
        """
        Restore the heap property by moving element at idx downward.

        Called after extraction (root replaced by last element).
        """
        data = self._data
        n = len(data)
        while True:
            smallest = idx
            left = 2 * idx + 1
            right = 2 * idx + 2

            if left < n and data[left][0] < data[smallest][0]:
                smallest = left
            if right < n and data[right][0] < data[smallest][0]:
                smallest = right

            if smallest == idx:
                break
            data[idx], data[smallest] = data[smallest], data[idx]
            idx = smallest


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

@dataclass
class DijkstraResult:
    """
    Output of a single Dijkstra run from one source node.

    Attributes:
        dist         : dist[v] = shortest distance from source to v (INF if unreachable).
        prev         : prev[v] = predecessor of v on the shortest path (−1 if none).
        visited_count: Number of nodes extracted from the heap (i.e., settled).
        heap_ops     : Total heap push + pop operations performed.
        source       : The source node index used for this run.
    """
    dist: List[float]
    prev: List[int]
    visited_count: int
    heap_ops: int
    source: int


# ---------------------------------------------------------------------------
# Dijkstra implementation
# ---------------------------------------------------------------------------

def dijkstra(graph: SpatialGraph, source: int) -> DijkstraResult:
    """
    Run Dijkstra's algorithm from *source* on *graph*.

    Uses a custom MinHeap with lazy deletion for decrease-key.
    Processes each edge at most once per heap pop (edges are re-relaxed only
    when a shorter distance is found).

    Args:
        graph : A SpatialGraph instance.
        source: Index of the starting node (0-based).

    Returns:
        DijkstraResult with dist[], prev[], visited_count, heap_ops, source.

    Time complexity: O((V + E) log V) with the lazy-deletion heap.
    Space complexity: O(V + E).
    """
    n = graph.n
    dist = [INF] * n
    prev = [-1] * n
    dist[source] = 0.0
    visited_count = 0

    heap = MinHeap()
    heap.push(0.0, source)

    # in_heap[v] tracks the best distance for which v is *currently* in the heap.
    # If we pop a pair whose distance is greater than dist[v], it is stale.
    in_heap_dist = [INF] * n
    in_heap_dist[source] = 0.0

    while not heap.is_empty():
        d, u = heap.pop()

        # Lazy deletion: skip stale entries
        if d > dist[u]:
            continue

        visited_count += 1

        for v, w in graph.neighbors(u):
            new_dist = dist[u] + w
            if new_dist < dist[v]:
                dist[v] = new_dist
                prev[v] = u
                # Push new (distance, node) pair; old entry will be skipped lazily
                heap.push(new_dist, v)
                in_heap_dist[v] = new_dist

    return DijkstraResult(
        dist=dist,
        prev=prev,
        visited_count=visited_count,
        heap_ops=heap.ops,
        source=source,
    )


def shortest_path(graph: SpatialGraph, source: int,
                  target: int) -> Tuple[List[int], float]:
    """
    Compute and reconstruct the shortest path from *source* to *target*.

    Args:
        graph : A SpatialGraph instance.
        source: Starting node index.
        target: Goal node index.

    Returns:
        A tuple (path, cost) where:
            path : List of node indices from source to target (inclusive).
                   Empty list if target is unreachable.
            cost : Total path cost (INF if unreachable).
    """
    result = dijkstra(graph, source)
    cost = result.dist[target]

    if cost == INF:
        return [], INF

    # Reconstruct path by walking prev[] backwards
    path: List[int] = []
    cur = target
    while cur != -1:
        path.append(cur)
        cur = result.prev[cur]
    path.reverse()

    # Sanity check: path should start at source
    if path[0] != source:
        return [], INF

    return path, cost


def all_pairs_shortest_paths(graph: SpatialGraph) -> List[List[float]]:
    """
    Compute all-pairs shortest-path costs using Dijkstra from every source node.

    Returns a 2-D cost matrix where cost_matrix[i][j] is the shortest-path
    distance from node i to node j (INF if j is unreachable from i).

    This matrix is the primary input consumed by the greedy solver and Song's DP
    solver.

    Args:
        graph: A SpatialGraph instance.

    Returns:
        List[List[float]] of shape n × n.

    Time complexity: O(V * (V + E) log V).
    """
    n = graph.n
    cost_matrix = [[INF] * n for _ in range(n)]
    for src in range(n):
        result = dijkstra(graph, src)
        cost_matrix[src] = result.dist[:]
    return cost_matrix


def all_pairs_results(graph: SpatialGraph) -> Dict[int, DijkstraResult]:
    """
    Run Dijkstra from every source and return a dict keyed by source index.

    Useful for benchmarking (provides visited_count and heap_ops per run).

    Args:
        graph: A SpatialGraph instance.

    Returns:
        Dict mapping source → DijkstraResult.
    """
    return {src: dijkstra(graph, src) for src in range(graph.n)}


# ---------------------------------------------------------------------------
# Self-test / demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from data_gen import generate_toy_graph

    print("=== Dijkstra self-test ===")
    g = generate_toy_graph(6, seed=42)
    print(g.summary())
    print()

    src, tgt = 0, 5
    path, cost = shortest_path(g, src, tgt)
    print(f"Shortest path {src} → {tgt}: {path}, cost={cost:.2f}")

    print("\nAll-pairs cost matrix:")
    matrix = all_pairs_shortest_paths(g)
    header = "     " + "  ".join(f"{j:6d}" for j in range(g.n))
    print(header)
    for i, row in enumerate(matrix):
        vals = "  ".join(f"{v:6.2f}" if v < INF else "   inf" for v in row)
        print(f"  {i}: {vals}")
