"""
schedule_dp.py — Held-Karp exact DP for optimal film shooting-order scheduling.

This is the *scheduling layer* of the two-stage pipeline:

    Liu's geographic layer                 Song's scheduling layer
    ----------------------                 -----------------------
    locations -> terrain-weighted graph    cost matrix -> optimal shooting order
    Dijkstra  -> all-pairs cost matrix  ->  Held-Karp subset DP
    Greedy NN -> fast approximate order     (exact, globally optimal)

Key design decisions:
  - The DP consumes an all-pairs *cost matrix* (the output of
    liu.dijkstra.all_pairs_shortest_paths), NOT a raw adjacency matrix.
    In an adjacency matrix 0 means "no direct road"; in a cost matrix 0 means
    "already here".  Passing the wrong one produces silently wrong answers.
  - Locations are assumed pre-deduplicated: every scene at the same location is
    shot in one visit.  Per-location shooting cost is a constant independent of
    ordering, so it does not affect the optimal order and is excluded from the
    objective (see REPORT for the proof).
  - dp[] and parent[] are flat `array` buffers rather than nested lists.  At
    n=18 this is ~43 MB instead of ~300 MB, which is the difference between the
    exact solver being usable and not.

Complexity:
    Time  O(2^n * n^2)
    Space O(2^n * n)
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from array import array
from dataclasses import dataclass, field
from itertools import permutations
from typing import List, Optional, Tuple

INF = float("inf")

# Above this many locations the 2^n table stops fitting in memory / patience.
# Kept as a module constant so benchmarks and callers agree on the ceiling.
EXACT_LIMIT = 20


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

@dataclass
class ScheduleResult:
    """
    Output of one exact scheduling run.

    Attributes:
        order          : Location indices in shooting order, starting at `start`.
                         If the schedule returns to base, `start` also appears
                         as the final element.
        total_cost     : Total transition cost of the schedule.
        leg_costs      : leg_costs[k] is the cost of moving order[k] -> order[k+1].
        states_settled : Number of (subset, last-location) DP states actually
                         relaxed, used for the empirical growth analysis.  It
                         counts the subset DP only: on a partitioned run it
                         reports the region-level states and not the work inside
                         path_cost_table, so it is a growth measure for the
                         unpartitioned solver, not a total work count.
        n_locations    : Number of locations scheduled.
        closed         : True if the schedule returns to the starting base.
    """
    order: List[int]
    total_cost: float
    leg_costs: List[float] = field(default_factory=list)
    states_settled: int = 0
    n_locations: int = 0
    closed: bool = False

    def __str__(self) -> str:
        path = " -> ".join(str(v) for v in self.order)
        kind = "closed" if self.closed else "open"
        return (f"ScheduleResult({kind}, order=[{path}], "
                f"total_cost={self.total_cost:.4f}, "
                f"states={self.states_settled})")


# ---------------------------------------------------------------------------
# Held-Karp exact DP
# ---------------------------------------------------------------------------

def optimal_schedule(cost: List[List[float]],
                     start: int = 0,
                     end: Optional[int] = None,
                     return_to_base: bool = False) -> ScheduleResult:
    """
    Compute the globally optimal shooting order via Held-Karp subset DP.

    State:
        dp[S][v] = minimum cost to have shot exactly the locations in set S,
                   currently standing at location v (v must be in S).

    Recurrence:
        dp[S | {u}][u] = min over v in S of  dp[S][v] + cost[v][u]

    Because S only ever grows, the state space is a DAG and the DP is a
    shortest-path computation over it, evaluated in order of increasing mask.

    Args:
        cost          : n x n all-pairs shortest-path cost matrix.  cost[i][j]
                        may be INF if j is unreachable from i.
        start         : Index of the base / first location to shoot.
        end           : If given, the schedule must finish at this location.
                        Ignored when `return_to_base` is True.
        return_to_base: If True, the crew returns to `start` after the last
                        location (a Hamiltonian cycle rather than a path).

    Returns:
        ScheduleResult with the optimal order, cost, per-leg costs and the
        number of DP states settled.

    Raises:
        ValueError: If the matrix is empty or not square, `start`/`end` are out
                    of range, `end` equals `start`, or n exceeds EXACT_LIMIT.
    """
    n = len(cost)
    if n == 0:
        raise ValueError("Cost matrix is empty.")
    for i, row in enumerate(cost):
        if len(row) != n:
            raise ValueError(
                f"Row {i} has length {len(row)}, expected {n} (square matrix).")
    if not (0 <= start < n):
        raise ValueError(f"start={start} out of range for {n} locations.")
    if end is not None and not (0 <= end < n):
        raise ValueError(f"end={end} out of range for {n} locations.")
    if end is not None and end == start and n > 1:
        # Checked here rather than after the DP: an invalid argument should not
        # cost an exponential run first.
        raise ValueError("end must differ from start for an open schedule.")
    if n > EXACT_LIMIT:
        raise ValueError(
            f"n={n} exceeds the exact-DP ceiling of {EXACT_LIMIT}. "
            f"Use the clustered or heuristic solver at this scale.")

    # Trivial single-location schedule
    if n == 1:
        return ScheduleResult(order=[start], total_cost=0.0, leg_costs=[],
                              states_settled=1, n_locations=1,
                              closed=return_to_base)

    size = 1 << n
    full = size - 1

    # Flat buffers: index (mask, v) as mask * n + v.
    dp = array("d", [INF]) * (size * n)
    parent = array("b", [-1]) * (size * n)

    dp[(1 << start) * n + start] = 0.0
    states_settled = 0

    for mask in range(size):
        # Every reachable state contains the start location.
        if not (mask >> start) & 1:
            continue
        base = mask * n
        for v in range(n):
            if not (mask >> v) & 1:
                continue
            d = dp[base + v]
            if d == INF:
                continue
            states_settled += 1

            row = cost[v]
            for u in range(n):
                if (mask >> u) & 1:
                    continue
                w = row[u]
                if w == INF:
                    continue  # u not reachable from v
                nd = d + w
                idx = ((mask | (1 << u)) * n) + u
                if nd < dp[idx]:
                    dp[idx] = nd
                    parent[idx] = v

    # ---- Choose the terminal state ----
    best_cost = INF
    best_last = -1
    tail_cost = 0.0

    if return_to_base:
        for v in range(n):
            if v == start:
                continue
            d = dp[full * n + v]
            back = cost[v][start]
            if d == INF or back == INF:
                continue
            if d + back < best_cost:
                best_cost = d + back
                best_last = v
                tail_cost = back
    elif end is not None:
        d = dp[full * n + end]
        if d < INF:
            best_cost, best_last = d, end
    else:
        for v in range(n):
            d = dp[full * n + v]
            if d < best_cost:
                best_cost, best_last = d, v

    if best_last < 0 or best_cost == INF:
        # Some location is unreachable — no complete schedule exists.
        return ScheduleResult(order=[], total_cost=INF, leg_costs=[],
                              states_settled=states_settled, n_locations=n,
                              closed=return_to_base)

    # ---- Reconstruct the order by walking parent[] backwards ----
    order: List[int] = []
    mask, v = full, best_last
    while v != -1:
        order.append(v)
        p = parent[mask * n + v]
        mask ^= (1 << v)
        v = p
    order.reverse()

    leg_costs = [cost[order[k]][order[k + 1]] for k in range(len(order) - 1)]
    if return_to_base:
        order.append(start)
        leg_costs.append(tail_cost)

    return ScheduleResult(
        order=order,
        total_cost=best_cost,
        leg_costs=leg_costs,
        states_settled=states_settled,
        n_locations=n,
        closed=return_to_base,
    )


# ---------------------------------------------------------------------------
# Sub-problem primitive used by the clustered (tier-2) solver
# ---------------------------------------------------------------------------

def path_cost_table(cost: List[List[float]],
                    members: List[int]) -> Tuple[List[List[float]],
                                                 List[List[List[int]]]]:
    """
    For one group of locations, solve every (entry, exit) routing question at once.

    Returns the cost of the cheapest route that starts at members[a], visits
    every location in `members` exactly once, and finishes at members[b] — for
    all pairs (a, b).  This is what lets the clustered solver stitch groups
    together without guessing where to enter and leave each group.

    Implemented as one Held-Karp run per entry point: m runs of O(2^m * m^2),
    so O(2^m * m^3) overall.  Kept small by capping group size.

    Args:
        cost   : Full n x n all-pairs cost matrix (global indices).
        members: Global indices belonging to this group.

    Returns:
        (pc, paths) where pc[a][b] is the cost described above (INF if no such
        route exists) and paths[a][b] is the corresponding sequence of *global*
        location indices.
    """
    m = len(members)
    if m > EXACT_LIMIT:
        # This does m Held-Karp runs, so it is m times more expensive than
        # optimal_schedule at the same size — it needs the ceiling at least as
        # much, and without one an oversized region_cap turns a 20 ms call into
        # a multi-minute one.
        raise ValueError(
            f"group of {m} locations exceeds the exact-DP ceiling of "
            f"{EXACT_LIMIT}; lower region_cap.")
    if m == 1:
        return [[0.0]], [[[members[0]]]]

    sub = [[cost[p][q] for q in members] for p in members]
    size = 1 << m
    full = size - 1

    pc = [[INF] * m for _ in range(m)]
    paths: List[List[List[int]]] = [[[] for _ in range(m)] for _ in range(m)]

    for a in range(m):
        dp = array("d", [INF]) * (size * m)
        parent = array("b", [-1]) * (size * m)
        dp[(1 << a) * m + a] = 0.0

        for mask in range(size):
            if not (mask >> a) & 1:
                continue
            base = mask * m
            for v in range(m):
                if not (mask >> v) & 1:
                    continue
                d = dp[base + v]
                if d == INF:
                    continue
                row = sub[v]
                for u in range(m):
                    if (mask >> u) & 1:
                        continue
                    w = row[u]
                    if w == INF:
                        continue
                    nd = d + w
                    idx = ((mask | (1 << u)) * m) + u
                    if nd < dp[idx]:
                        dp[idx] = nd
                        parent[idx] = v

        for b in range(m):
            d = dp[full * m + b]
            if d == INF:
                continue
            pc[a][b] = d
            seq: List[int] = []
            mask, v = full, b
            while v != -1:
                seq.append(members[v])
                p = parent[mask * m + v]
                mask ^= (1 << v)
                v = p
            seq.reverse()
            paths[a][b] = seq

    return pc, paths


# ---------------------------------------------------------------------------
# Brute-force reference implementation (correctness oracle)
# ---------------------------------------------------------------------------

def brute_force_schedule(cost: List[List[float]],
                         start: int = 0,
                         end: Optional[int] = None,
                         return_to_base: bool = False) -> ScheduleResult:
    """
    Enumerate every permutation and return the cheapest schedule.

    This exists purely as a correctness oracle for `optimal_schedule`: it is
    obviously correct (it literally checks every order) and obviously too slow
    to use (O(n!)), so agreement between the two on small inputs is what
    justifies the claim that the DP result is optimal.

    Args:
        cost, start, end, return_to_base: Same meaning as `optimal_schedule`.

    Returns:
        ScheduleResult with the optimal order found by exhaustive search.
    """
    n = len(cost)
    others = [v for v in range(n) if v != start]

    best_cost = INF
    best_perm: Tuple[int, ...] = ()

    for perm in permutations(others):
        if end is not None and not return_to_base and perm and perm[-1] != end:
            continue
        total = 0.0
        cur = start
        ok = True
        for nxt in perm:
            w = cost[cur][nxt]
            if w == INF:
                ok = False
                break
            total += w
            cur = nxt
        if not ok:
            continue
        if return_to_base:
            w = cost[cur][start]
            if w == INF:
                continue
            total += w
        if total < best_cost:
            best_cost = total
            best_perm = perm

    if best_cost == INF:
        return ScheduleResult(order=[], total_cost=INF, n_locations=n,
                              closed=return_to_base)

    order = [start] + list(best_perm)
    leg_costs = [cost[order[k]][order[k + 1]] for k in range(len(order) - 1)]
    if return_to_base:
        leg_costs.append(cost[order[-1]][start])
        order.append(start)

    return ScheduleResult(order=order, total_cost=best_cost,
                          leg_costs=leg_costs, n_locations=n,
                          closed=return_to_base)


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import random

    print("=" * 70)
    print("  schedule_dp.py — Held-Karp exact scheduling self-test")
    print("=" * 70)

    # ---- Test 1: hand-verifiable 4-location mock ----
    # A four-location cost matrix small enough to check by hand: 0<->2 costs 8
    # via node 1, since there is no cheaper direct route.
    print("\n[1] Hand-checked 4-location mock")
    mock = [
        [0.0,  5.0,  8.0,  8.0],
        [5.0,  0.0,  3.0, 10.0],
        [8.0,  3.0,  0.0,  7.0],
        [8.0, 10.0,  7.0,  0.0],
    ]
    res = optimal_schedule(mock, start=0)
    print(f"  open  : order={res.order} cost={res.total_cost:.2f} "
          f"legs={[f'{c:.1f}' for c in res.leg_costs]}")
    res_c = optimal_schedule(mock, start=0, return_to_base=True)
    print(f"  closed: order={res_c.order} cost={res_c.total_cost:.2f}")

    # ---- Test 2: brute-force cross-validation ----
    print("\n[2] Brute-force cross-validation (this is the proof of optimality)")
    rng = random.Random(5800)
    failures = 0
    checks = 0
    for n in range(2, 9):
        for trial in range(40):
            m = [[0.0] * n for _ in range(n)]
            for i in range(n):
                for j in range(i + 1, n):
                    w = round(rng.uniform(1, 50), 2)
                    m[i][j] = m[j][i] = w
            for closed in (False, True):
                a = optimal_schedule(m, start=0, return_to_base=closed)
                b = brute_force_schedule(m, start=0, return_to_base=closed)
                checks += 1
                if abs(a.total_cost - b.total_cost) > 1e-9:
                    failures += 1
                    print(f"  MISMATCH n={n} closed={closed}: "
                          f"dp={a.total_cost} brute={b.total_cost}")
                # The reconstructed order must actually cost what we claim.
                walk = sum(m[a.order[k]][a.order[k + 1]]
                           for k in range(len(a.order) - 1))
                if abs(walk - a.total_cost) > 1e-9:
                    failures += 1
                    print(f"  BAD RECONSTRUCTION n={n} closed={closed}")
        print(f"  n={n}: checked, running total {checks} cases")

    print(f"\n  {checks} cases checked, {failures} failures")
    print("  RESULT:", "PASS — DP matches exhaustive search" if failures == 0
          else "FAIL")
