"""
clustered_dp.py — The scheduler: partition into regions, then solve exactly.

Motivation
----------
Solving a shooting order exactly costs 2^n, so it runs out of room around 20
locations.  A real feature film has more.  Real productions do not solve this by
being cleverer about the whole map — they shoot *block by block*: finish
everything in one region, then strike camp and move to the next.  Nobody drives
Beijing -> Hengdian -> Beijing -> Qingdao.

This module turns that industry practice into an algorithm:

    1. Group locations into regions by building a minimum spanning tree and
       deleting its heaviest edges — the long hauls between cities.
    2. Solve every region internally with exact DP — for all possible entry
       and exit points, not just one (see schedule_dp.path_cost_table).
    3. Solve the region-level tour with a second exact DP whose state carries
       the exit location, so the joins between regions are optimised too.

Every step is built from material the course covers: Kruskal's MST with
union-find for the grouping, subset DP for both routing levels.

What is exact and what is not
-----------------------------
Steps 2 and 3 are both exact: within a region the route is provably optimal,
and where to leave one region and enter the next is optimised jointly with the
region ordering.  **The partition is the only approximation in the method.**

There is no separate small-input algorithm.  A production that already fits the
exact solver has nothing to partition, so the method runs with a single region
and returns a proven global optimum — plain Held-Karp is this method's
degenerate case, not a different one.  The self-test at the bottom of this file
checks that the two paths agree.

So the quality of an answer rests entirely on whether the regions are sensible
— which is exactly the assumption a producer already makes when they decide to
block-shoot.

Cost
----
    grouping        O(n^2 log n)          Kruskal over the dense cost matrix
    within regions  O(k * 2^m * m^3)      m = region size cap
    across regions  O(2^k * k^2 * m^2)
Both exponents are now on small numbers instead of on n.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from schedule_dp import (EXACT_LIMIT, INF, ScheduleResult, optimal_schedule,
                         path_cost_table)

# Max locations per region.  This is a real trade-off, not just a speed knob:
# bigger regions are solved more exactly, but "finish this region before moving
# on" is a *constraint*, so making regions bigger makes that constraint bite
# harder.  Measured across the three productions, cost is flat from cap 7 to 11
# and degrades at 12 (La La Land 435 -> 443), while caps below 7 push Tenet past
# the region limit.  10 sits in the middle of the flat band and is the fastest
# setting for the largest production.
DEFAULT_REGION_CAP = 10
MAX_REGIONS = 13          # keeps the region-level 2^k DP cheap


# ---------------------------------------------------------------------------
# Region discovery (minimum spanning tree, cut at the widest gap)
# ---------------------------------------------------------------------------

def _mst_edges(cost: List[List[float]]) -> List[Tuple[float, int, int]]:
    """
    Build a minimum spanning tree over the locations with Kruskal's algorithm.

    Sort every pair by cost, keep an edge whenever it joins two locations that
    are not already linked, and stop at n-1 edges.  Union-find with path
    compression does the "are these already linked" test.

    Args:
        cost: n x n all-pairs cost matrix.

    Returns:
        The n-1 tree edges as (weight, i, j), in the order Kruskal accepted them.
    """
    n = len(cost)
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    candidates = sorted((cost[i][j], i, j)
                        for i in range(n) for j in range(i + 1, n)
                        if cost[i][j] != INF)
    tree: List[Tuple[float, int, int]] = []
    for w, i, j in candidates:
        a, b = find(i), find(j)
        if a != b:
            parent[a] = b
            tree.append((w, i, j))
            if len(tree) == n - 1:
                break
    return tree


def _components(n: int, edges: List[Tuple[float, int, int]]) -> List[List[int]]:
    """Group locations by which ones remain connected through `edges`."""
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for _, i, j in edges:
        a, b = find(i), find(j)
        if a != b:
            parent[a] = b

    groups: Dict[int, List[int]] = {}
    for v in range(n):
        groups.setdefault(find(v), []).append(v)
    return list(groups.values())


def find_regions(cost: List[List[float]], start: int = 0,
                 region_cap: int = DEFAULT_REGION_CAP,
                 n_regions: Optional[int] = None) -> List[List[int]]:
    """
    Split the locations into regions by cutting a minimum spanning tree.

    Build the MST, then delete its k-1 heaviest edges: what remains is k groups
    of locations that are cheap to reach from one another.  A long haul between
    two cities is exactly the sort of expensive edge this removes, so the groups
    come out as the cities.

    How many regions?  The tree's own edge weights say so.  On a real map the
    weights fall off a cliff between the last inter-city hop and the first local
    road, so the count is taken at the widest ratio gap in the sorted weights —
    no threshold to tune.  Ties to the size cap: keep cutting past that point if
    any region is still too large for the exact solver.

    Args:
        cost      : n x n all-pairs cost matrix.
        start     : Unused; kept so callers need not care which grouping method
                    is in play.
        region_cap: Maximum locations per region.
        n_regions : Fix the region count instead of inferring it — use this when
                    the production already knows its shooting blocks.

    Returns:
        List of regions, each a list of global location indices.

    Raises:
        ValueError: If no admissible region count exists within MAX_REGIONS.
    """
    n = len(cost)
    if n <= region_cap and n_regions is None:
        return [list(range(n))]

    tree = _mst_edges(cost)
    if len(tree) < n - 1:
        raise ValueError("Cost matrix is disconnected; cannot form regions.")
    heavy_first = sorted(tree, reverse=True)

    # --- Step 1: cut at the natural break in the tree's edge weights ---------
    if n_regions is not None:
        cuts = max(0, min(n_regions, n) - 1)
    else:
        cuts, best_ratio = 0, 0.0
        for k in range(2, min(MAX_REGIONS, n) + 1):
            if k - 1 >= len(heavy_first):
                break
            last_cut, first_kept = heavy_first[k - 2][0], heavy_first[k - 1][0]
            ratio = last_cut / first_kept if first_kept > 0 else INF
            if ratio > best_ratio:
                best_ratio, cuts = ratio, k - 1

    removed = set(range(cuts))          # indices into heavy_first

    # --- Step 2: split anything still too big for the exact solver ----------
    # A region is a connected piece of the tree, so the tree edges inside it
    # already form its own spanning tree — splitting it is just cutting its
    # heaviest internal edge.  Doing it region by region, rather than by
    # continuing down the global weight order, keeps every other region intact:
    # eleven locations in one city get halved without shattering the cities
    # around it.
    while True:
        kept = [e for i, e in enumerate(heavy_first) if i not in removed]
        regions = _components(n, kept)
        oversized = [g for g in regions if len(g) > region_cap]
        if not oversized:
            break
        if len(regions) >= MAX_REGIONS:
            raise ValueError(
                f"n={n} cannot be split into regions of at most {region_cap} "
                f"locations within the {MAX_REGIONS}-region limit.")
        target = set(max(oversized, key=len))
        inside = [i for i, (_, a, b) in enumerate(heavy_first)
                  if i not in removed and a in target and b in target]
        if not inside:
            raise ValueError("Cannot split an oversized region any further.")
        removed.add(min(inside))        # heavy_first is sorted, so this is the
                                        # heaviest edge still inside the region
    return regions


# ---------------------------------------------------------------------------
# The solver
# ---------------------------------------------------------------------------

@dataclass
class ClusteredResult(ScheduleResult):
    """A ScheduleResult that also records the regions and the region order."""
    regions: List[List[int]] = field(default_factory=list)
    region_order: List[int] = field(default_factory=list)


def clustered_schedule(cost: List[List[float]],
                       start: int = 0,
                       region_cap: int = DEFAULT_REGION_CAP,
                       return_to_base: bool = False,
                       always_partition: bool = False) -> ClusteredResult:
    """
    Partition the locations into regions, then solve exactly — inside each
    region, and across them.

    When the whole production already fits the exact solver there is nothing to
    partition: the method collapses to plain Held-Karp over every location and
    returns a proven optimum.  That is not a separate algorithm bolted on for
    small inputs — it is this one with a single region, and it returns the same
    order the partitioned path would (verified in the self-test below).  The
    single-region case is routed straight to `optimal_schedule` only for speed:
    `path_cost_table` solves every entry point because a region can be entered
    from anywhere, but with one region the entry is fixed, and doing the extra
    work costs an order of magnitude for an identical answer.

    So the only approximation anywhere in the method is the partition itself.

    Args:
        cost          : n x n all-pairs cost matrix.
        start         : Base / first location.
        region_cap    : Maximum locations per region.
        return_to_base: If True the crew returns to `start` at wrap.
        always_partition: Run the partitioned machinery even when the input
                        would not normally need partitioning.  Off in ordinary
                        use — it only makes the answer worse or slower.  The
                        experiments need it: measuring what the partition costs
                        requires actually partitioning something the exact
                        solver could have handled, and the correctness test
                        needs the partition code to run at sizes exhaustive
                        search can check.

    Returns:
        ClusteredResult with the full location order, total cost, the regions
        that were used and the order they were shot in.
    """
    n = len(cost)
    if always_partition or n > EXACT_LIMIT:
        regions = find_regions(cost, start=start, region_cap=region_cap)
    else:
        regions = [list(range(n))]

    if len(regions) == 1 and not always_partition:
        exact = optimal_schedule(cost, start=start,
                                 return_to_base=return_to_base)
        return ClusteredResult(
            order=exact.order, total_cost=exact.total_cost,
            leg_costs=exact.leg_costs, states_settled=exact.states_settled,
            n_locations=n, closed=return_to_base,
            regions=regions, region_order=[0])

    # The base must anchor whichever region contains it.
    home = next(i for i, g in enumerate(regions) if start in g)
    k = len(regions)

    # ---- Step 2: every entry/exit route inside each region, exactly ----
    tables = [path_cost_table(cost, g) for g in regions]

    # best_join[x][d][b]: cheapest way to stand at global location x, travel
    # into region d, cover it entirely, and come out at local index b.
    # Also remember which entry point achieved it, for reconstruction.
    best_join: Dict[Tuple[int, int, int], Tuple[float, int]] = {}
    for d in range(k):
        members = regions[d]
        pc, _ = tables[d]
        md = len(members)
        for x in range(n):
            row = cost[x]
            for b in range(md):
                bc, ba = INF, -1
                for a in range(md):
                    step = row[members[a]]
                    inner = pc[a][b]
                    if step == INF or inner == INF:
                        continue
                    tot = step + inner
                    if tot < bc:
                        bc, ba = tot, a
                if ba >= 0:
                    best_join[(x, d, b)] = (bc, ba)

    # ---- Step 3: region-level DP, state = (regions done, region, exit) ----
    # g[mask][(c, b)] = (cost, back-pointer)
    g: List[Dict[Tuple[int, int], Tuple[float, Optional[Tuple]]]] = [
        {} for _ in range(1 << k)]

    home_members = regions[home]
    pc_home, _ = tables[home]
    a_home = home_members.index(start)
    for b in range(len(home_members)):
        c = pc_home[a_home][b]
        if c < INF:
            g[1 << home][(home, b)] = (c, None)

    states = 0
    for mask in range(1 << k):
        if not (mask >> home) & 1 or not g[mask]:
            continue
        for (c, b), (dcost, _) in g[mask].items():
            states += 1
            x = regions[c][b]
            for d in range(k):
                if (mask >> d) & 1:
                    continue
                nm = mask | (1 << d)
                for b2 in range(len(regions[d])):
                    join = best_join.get((x, d, b2))
                    if join is None:
                        continue
                    nd = dcost + join[0]
                    cur = g[nm].get((d, b2))
                    if cur is None or nd < cur[0]:
                        g[nm][(d, b2)] = (nd, (mask, c, b))

    full = (1 << k) - 1
    if not g[full]:
        return ClusteredResult(order=[], total_cost=INF, n_locations=n,
                               closed=return_to_base, regions=regions)

    best_key, best_cost = None, INF
    for key, (c, _) in g[full].items():
        tail = cost[regions[key[0]][key[1]]][start] if return_to_base else 0.0
        if tail == INF:
            continue
        if c + tail < best_cost:
            best_cost, best_key = c + tail, key

    if best_key is None:
        return ClusteredResult(order=[], total_cost=INF, n_locations=n,
                               closed=return_to_base, regions=regions)

    # ---- Reconstruct: walk the region chain back, splicing in each route ----
    chain: List[Tuple[int, int, int]] = []   # (mask, region, exit local idx)
    mask, (c, b) = full, best_key
    while True:
        chain.append((mask, c, b))
        prev = g[mask][(c, b)][1]
        if prev is None:
            break
        mask, c, b = prev
    chain.reverse()

    order: List[int] = []
    region_order: List[int] = []
    for i, (mask_i, c, b) in enumerate(chain):
        _, paths = tables[c]
        if i == 0:
            a = regions[c].index(start)
        else:
            prev_exit = regions[chain[i - 1][1]][chain[i - 1][2]]
            a = best_join[(prev_exit, c, b)][1]
        order.extend(paths[a][b])
        region_order.append(c)

    leg_costs = [cost[order[j]][order[j + 1]] for j in range(len(order) - 1)]
    if return_to_base:
        leg_costs.append(cost[order[-1]][start])
        order.append(start)

    return ClusteredResult(
        order=order,
        total_cost=best_cost,
        leg_costs=leg_costs,
        states_settled=states,
        n_locations=n,
        closed=return_to_base,
        regions=regions,
        region_order=region_order,
    )


# ---------------------------------------------------------------------------
# Self-test — the partitioned path and plain Held-Karp must agree
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import random
    from schedule_dp import brute_force_schedule

    print("=" * 72)
    print("  clustered_dp — one region must reproduce the exact optimum")
    print("=" * 72)

    rng = random.Random(5800)
    checks = mismatches = 0
    for n in range(2, 10):
        for _ in range(25):
            m = [[0.0] * n for _ in range(n)]
            for i in range(n):
                for j in range(i + 1, n):
                    m[i][j] = m[j][i] = round(rng.uniform(1, 60), 2)
            for closed in (False, True):
                # region_cap >= n forces a single region, so the partitioned
                # machinery runs in full rather than short-circuiting.
                # always_partition forces the region machinery to run rather
                # than short-circuiting to the exact solver, so this really is
                # testing the partitioned path.
                partitioned = clustered_schedule(m, start=0, region_cap=n,
                                                 return_to_base=closed,
                                                 always_partition=True)
                truth = brute_force_schedule(m, start=0, return_to_base=closed)
                checks += 1
                walked = sum(m[partitioned.order[k]][partitioned.order[k + 1]]
                             for k in range(len(partitioned.order) - 1))
                if (abs(partitioned.total_cost - truth.total_cost) > 1e-9
                        or abs(walked - partitioned.total_cost) > 1e-9):
                    mismatches += 1
                    print(f"  MISMATCH n={n} closed={closed}: "
                          f"{partitioned.total_cost} vs {truth.total_cost}")
    print(f"\n  {checks} single-region cases vs exhaustive search, "
          f"{mismatches} mismatches")

    # And the partition itself, on a map with obvious regions.
    print("\n  Partitioning a map with three well-separated clusters:")
    pts = [(0, 0), (1, 1), (2, 0), (0.5, 2),          # cluster A
           (100, 0), (101, 1), (100.5, 2),            # cluster B
           (50, 200), (51, 201)]                      # cluster C
    n = len(pts)
    dist = [[((pts[i][0] - pts[j][0]) ** 2
              + (pts[i][1] - pts[j][1]) ** 2) ** 0.5
             for j in range(n)] for i in range(n)]
    for r in sorted(find_regions(dist, region_cap=5), key=len, reverse=True):
        print(f"    {r}")
    sched = clustered_schedule(dist, start=0, region_cap=5)
    print(f"  order {sched.order}  cost {sched.total_cost:.2f}")
    print("\n  RESULT:", "PASS" if mismatches == 0 else "FAIL")
