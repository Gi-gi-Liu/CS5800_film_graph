# CS5800 — A Dual-Layer Film Production Optimization Framework
## Song's Section: Exact Shooting-Order Scheduling by Partition and Subset DP

---

## 1. Introduction

### Context

A film shoots at many locations, and the crew has to be moved between them.
Once the geographic layer has answered *what does each move cost*, one question
is left, and it is the one that decides the schedule: **in what order should the
locations be shot?**

The two layers form a pipeline. Liu's layer turns filming locations into a
terrain-weighted graph and runs Dijkstra to produce an all-pairs cost matrix —
the true cheapest cost of moving between any two locations, routed through
intermediate stops where that is cheaper. That matrix is the input to this
layer, which chooses the order. Neither half is usable alone: without the cost
matrix there is nothing to order, and without an order the matrix is a table
nobody has acted on.

The dependency is not nominal. Across the three productions studied here,
**81–86% of location pairs have no direct road between them** (Section 2.5), so
most entries in the matrix exist only because a shortest path was computed.

### Research Question

> **Given the cost of moving between any two filming locations, what shooting
> order minimises total transition cost — and how large a production can be
> scheduled with a provable guarantee rather than a heuristic?**

Concretely:

- Can the optimal order be *proved* optimal, not merely produced?
- How large a production does an exact method reach before it becomes
  impractical, and what exactly runs out — time, or memory?
- When a production is too large to solve exactly, what is the cheapest
  assumption that restores tractability, and what does that assumption cost?

### Scope and the objective function

Locations are taken as already deduplicated: every scene sharing a location is
shot in one visit. This is not a convenience, it is exact. Total cost splits as

```
total = Σ per-location shooting cost  +  Σ transition cost between locations
        └──── constant, order-independent ────┘   └──── the only term order affects ────┘
```

Every ordering pays the same shooting cost, so the optimal order is determined
entirely by transition cost. Dropping the first term changes nothing.

The objective is therefore a minimum-cost Hamiltonian path from a fixed base
through all locations — the path variant of the Travelling Salesman Problem,
which is NP-complete (CLRS §34.5.4). Exact methods are therefore expected to be
exponential, and the interesting question is *how far* they reach.

---

## 2. Analysis

### 2.1 The method

The whole scheduling layer is one method:

> **Partition the locations into regions, then solve exactly — inside each
> region and across them.**

When a production already fits the exact solver there is nothing to partition,
so the method runs with a single region and returns a proven global optimum.
Plain subset DP is this method's degenerate case, not a separate algorithm for
small inputs; Section 2.4 verifies that the two paths agree.

**The partition is the only approximation anywhere in the method.** Everything
downstream of it — the route within each region, the order of the regions, and
the choice of where to leave one region and enter the next — is exact.

The partition is also the step with a real-world justification. Productions do
not schedule by being clever about the whole map: they *block-shoot*, finishing
one region before striking camp. A schedule that respects that is not merely
cheaper to compute, it is the kind of schedule a producer would accept.

### 2.2 Algorithm 1 — Exact ordering by subset DP

The state is a set and a position:

```
dp[S][v] = minimum cost to have shot exactly the locations in S,
           standing at location v, where v ∈ S
```

Because `S` only ever grows, the states form a directed acyclic graph, and the
recurrence is a shortest-path computation over it evaluated in order of
increasing `S`:

```
DP-SCHEDULE(cost, start):
    dp[{start}][start] ← 0,  all other dp ← ∞
    for each S in increasing order of bitmask:
        for each v ∈ S with dp[S][v] < ∞:
            for each u ∉ S:
                if dp[S][v] + cost[v][u] < dp[S ∪ {u}][u]:
                    dp[S ∪ {u}][u]     ← dp[S][v] + cost[v][u]
                    parent[S ∪ {u}][u] ← v
    return  min over v of dp[full][v]            (open schedule)
       or   min over v of dp[full][v] + cost[v][start]   (returning to base)
```

The order itself is recovered by walking `parent` backwards, clearing one bit of
the mask at each step (CLRS §15.3, reconstructing an optimal solution from the
DP table).

This is the algorithm of Bellman (1962) and Held & Karp (1962). CLRS does not
contain it — the closest is Problem 15-3, a bitonic restriction of TSP — but the
paradigm it is built from is Chapter 15: optimal substructure, overlapping
subproblems, and reconstruction from the table.

**Time** `O(2ⁿ · n²)`  **Space** `O(2ⁿ · n)`

*Implementation note.* `dp` and `parent` are flat `array` buffers indexed as
`mask · n + v`, not nested Python lists. Nested lists of floats carry per-object
overhead that dominates at these sizes; the flat buffers hold raw doubles and
signed bytes. This is what puts n = 20 within reach on the test machine rather
than several sizes lower — see Section 2.5.

### 2.3 Algorithm 2 — Partitioning, and scheduling across regions

#### Finding the regions

Regions are found by cutting a minimum spanning tree:

```
FIND-REGIONS(cost, cap):
    T ← MST(cost)                          # Kruskal + union-find
    sort T's edges heaviest first
    cut the k-1 heaviest edges  →  k connected components
    while some region is larger than cap:
        cut the heaviest edge still inside the largest oversized region
    return the components
```

Deleting the `k-1` heaviest MST edges leaves `k` groups whose members are cheap
to reach from one another; a long haul between cities is exactly the kind of
expensive edge that gets removed. Both ingredients are course material —
Kruskal's algorithm (CLRS §23.2) and disjoint sets with path compression
(CLRS Chapter 21). The clustering step itself is not a separate algorithm: it is
Kruskal stopped early. Its optimality (it maximises the minimum spacing between
groups) is the standard result in Kleinberg & Tardos §4.7.

**How many regions?** The tree's own edge weights answer this, so nothing has to
be tuned. On a real map the weights fall off a cliff between the last inter-city
hop and the first local road, so the cut is taken where the ratio between
consecutive sorted weights is largest. On *La La Land* the heaviest MST edge is
205 and the next is 33 — a **6.2× break** — and that heaviest edge is exactly
"Los Angeles ↔ Big Bear Lake".

If a region is still too large for the exact solver, it is split again using its
own heaviest internal edge. Splitting region by region rather than continuing
down the global weight order matters: Tenet's eleven Tallinn locations can be
halved without shattering the cities around them.

**Time** `O(n² log n)` — Kruskal over the dense cost matrix dominates.

#### Solving within a region — every way in and out

A region cannot be routed in isolation, because the cost of covering it depends
on where the crew enters and where it leaves. So for each region the exact
solver is run once per entry point, yielding the cheapest route that starts at
member `a`, covers the region, and finishes at member `b`, **for all pairs
(a, b)**:

```
PATH-COST-TABLE(cost, members):
    for each entry a:
        run DP-SCHEDULE restricted to members, starting at a
        for each exit b:  pc[a][b] ← dp[full][b];  record the path
    return pc, paths
```

**Time** `O(2^m · m³)` for a region of `m` locations.

#### Scheduling across regions

The region-level DP carries the exit location in its state, so the joins between
regions are optimised jointly with the region ordering rather than chosen
afterwards:

```
g[R][c][b] = minimum cost to have shot exactly the regions in R,
             standing at location b, the exit of region c

g[R ∪ {d}][d][y] = min over (c, b) ∈ g[R], over entries e of d:
                      g[R][c][b] + cost[b][e] + pc_d[e][y]
```

The inner minimisation over entry points `e` is precomputed once per
(exit location, target region, exit slot) triple, so the transition itself is
`O(1)`.

**Time** `O(2^k · k² · m²)` for `k` regions of at most `m` locations.

Both exponents are now on small numbers — region count and region size — instead
of on the location count.

### 2.4 Testing

**Correctness of the exact solver.** Cross-checked against exhaustive
enumeration of every permutation, which is obviously correct and obviously too
slow to use. Random symmetric cost matrices, every size from n = 2 to 8, forty
matrices per size, open and returning-to-base:

> **560 cases, 0 disagreements.**

Reconstructed orders are re-walked and re-costed against the matrix, so a
correct total paired with a wrong path cannot pass.

**Correctness of the partitioned path.** The same comparison, but forcing the
region machinery to run rather than short-circuiting to the exact solver
(`always_partition=True`), sizes n = 2 to 9, twenty-five matrices per size:

> **400 cases, 0 disagreements.**

This is what makes the claim in Section 2.1 checkable rather than asserted: with
one region the partitioned method reproduces the exact optimum, so plain subset
DP really is its degenerate case.

**Validity on real data.** Every schedule produced for the three productions was
checked to be a permutation of all locations whose leg costs sum to the reported
total.

**Ground truth for the partition.** Each location carries the district, town or
city it truly belongs to. The scheduler never sees this field; it exists only so
the partition can be scored against it (Section 2.5).

### 2.5 Data

Locations come from three real productions, chosen so that the same method can
be tested at three geographic scales:

| Production | Locations | Real places | Scale |
|---|---|---|---|
| La La Land (2016) | 28 | 12 Los Angeles districts | one city |
| Forrest Gump (1994) | 31 | 13 towns across 8 states | one country |
| Tenet (2020) | 34 | 9 cities across 7 countries | the world |

Coordinates are real latitude and longitude; distances are great-circle
kilometres; edge weights come from the geographic layer's own terrain and
elevation formula, unchanged. Locations within a place are all connected to each
other (local roads); places connect only through their first-listed location and
only to their nearest few, so a cross-country move is a genuine routing problem.
A spanning tree over those hubs is laid down first, because a pure
nearest-neighbour long-haul network strands whole coasts.

**Provenance.** Location lists are transcribed from published location guides
(`movie-locations.com`), which are enthusiast reconstructions, not production
paperwork. Coordinates are landmark-accurate for named landmarks and
street-accurate for entries given only as an address — an error of a few hundred
metres, immaterial next to the tens of kilometres between districts. Real
shooting order is not published for any of the three, so these schedules can be
compared with each other but not against what the crews actually did.

### 2.6 Results

All timings are wall-clock on the development machine (Apple silicon, CPython
3.14) and are machine-dependent; the growth rates are not.

#### What the exact solver reaches

| Locations | Time to prove optimal | DP states settled |
|---|---|---|
| 15 | 0.11 s | 114,689 |
| 16 | 0.26 s | 245,761 |
| 17 | 0.59 s | 524,289 |
| 18 | 1.32 s | 1,114,113 |
| 19 | 2.93 s | 2,359,297 |
| **20** | **6.58 s** | **4,980,737** |
| 21 | 14.08 s | 10,485,761 |
| 22 | 32.40 s | 22,020,097 |

States settled double with each added location, and the measured runtime follows
— the empirical curve is a straight line on a log scale, which is what `2ⁿ`
looks like. **What runs out is memory, not patience:** peak resident memory is
200 MB at n = 20, 579 MB at n = 21 and 1.18 GB at n = 22. The limit is therefore
set at 20.

#### Scheduling the three productions

| Production | Greedy draft | This method | Saving | Time | Regions |
|---|---|---|---|---|---|
| La La Land | 489.82 | **434.94** | **11.20%** | 10.8 ms | 10 |
| Forrest Gump | 12,556.92 | **11,706.78** | **6.77%** | 10.3 ms | 8 |
| Tenet | 32,710.53 | **30,099.30** | **7.98%** | 39.0 ms | 11 |

All three schedules move between places the minimum possible number of times
(11, 12 and 8 respectively) — the method arrives at block shooting on its own,
without being told to.

The failure it corrects is visible on the map. On *La La Land* the greedy draft
leaves Canoga Park until second-to-last and has to cross the county for it after
already reaching Long Beach; this method picks Canoga Park up second, straight
out of the Burbank base, and finishes at Pasadena — the district closest to the
one genuinely remote location, Big Bear Lake.

#### What the partition costs

The partition is the method's only approximation, so this is the only place it
can lose anything. On the largest subset of each production the solver can still
prove outright (20 locations), the same method is run twice — once with the
partition forced, once without — and both are measured against that proven
optimum:

| Production | Proven optimum | Time to prove | Partitioned | Gap | Greedy draft | Gap |
|---|---|---|---|---|---|---|
| La La Land | 86.97 | 6.50 s | 86.97 (57 ms) | **+0.00%** | 91.65 | +5.38% |
| Forrest Gump | 4,983.92 | 6.49 s | 5,017.47 (1 ms) | **+0.67%** | 5,030.11 | +0.93% |
| Tenet | 13,595.75 | 6.43 s | 13,595.75 (17 ms) | **+0.00%** | 13,603.04 | +0.05% |

**Partitioning found the proven optimum outright in two of three cases and cost
0.67% in the third, while running 100 to 6,000 times faster.**

#### What the partition discovers

The partition sees only the cost matrix — no place names, no coordinates — yet
it recovers the real geography at every scale:

| Production | Regions found | Matching a single real place |
|---|---|---|
| La La Land | 10 | 9 |
| Forrest Gump | 8 | 6 |
| Tenet | 11 | **11** |

The disagreements are informative rather than wrong. On *La La Land* the method
merges Hollywood, West Hollywood and Midtown into one block — three adjacent
districts. On *Forrest Gump* it merges Walterboro, Yemassee, McPhersonville and
Varnville, four rural South Carolina towns within about 30 km of one another,
and separately splits Flagstaff from Monument Valley, which are 290 km apart.
**Where the partition disagrees with the labels, the labels are finer than the
geography warrants.**

#### Why the pipeline needs both layers

| Production | Pairs | No direct road | Share | Detour is cheaper |
|---|---|---|---|---|
| La La Land | 378 | 325 | **86.0%** | 3 |
| Forrest Gump | 465 | 390 | **83.9%** | 10 |
| Tenet | 561 | 457 | **81.5%** | 20 |

Most of this layer's input exists only because shortest paths were computed for
it. Getting from Venice Beach to Central Park, for instance, is a six-hop route
through Downtown LA, Las Vegas, Austin and Atlanta.

#### What the terrain weighting contributes

Each production was scheduled twice — once on the geographic layer's terrain and
elevation weights, once on raw kilometres — and both orders priced with the real
weights:

| Production | Cost of ignoring terrain | Non-urban locations | Distance spread |
|---|---|---|---|
| La La Land | **+2.17%** | 25% | 2,511× |
| Forrest Gump | +0.00% | 48% | 15,536× |
| Tenet | **+2.90%** | 41% | 140,716× |

The terrain model changes the schedule, but by a few percent, and the reason is
a matter of scale: the terrain multiplier tops out at 2×, while the real
distances on these maps span up to five orders of magnitude. **Terrain decides
between locations that are already close — it cannot outweigh a transatlantic
flight.** The contribution is real but second-order, and it decays as the
production spreads out.

#### Choosing the region size cap

Larger regions are solved more exactly, but *finish this region before moving
on* is a constraint, so enlarging regions tightens it. The two effects pull
against each other:

| Cap | La La Land | Forrest Gump | Tenet |
|---|---|---|---|
| 6 | 433.60 | 11,707.64 | *past the region limit* |
| 7–9 | 434.94 | 11,706.78 | 30,101.33 |
| **10** | **434.94** | **11,706.78** | **30,099.30** |
| 11 | 434.94 | 11,706.78 | 30,099.30 |
| 12 | 443.46 | 11,706.78 | 30,099.30 |

No single cap is best everywhere: 6 is marginally best for *La La Land* (by
0.3%) but leaves *Tenet* needing more regions than the region-level DP allows,
and 12 costs *La La Land* 2%. Caps 7–11 form a flat band in which every
production is within 0.3% of its own best. **10 sits inside that band and is the
best and fastest setting for the largest production**, so that is the default.

#### The upper limit

Beyond roughly **125 locations** the partition can no longer be formed within
the solver's limits, and the code falls back to the geographic layer's greedy
draft. Note that `region_cap × MAX_REGIONS` only *bounds* capacity — regions
rarely pack to the cap exactly — so the fallback is triggered by the partition
actually failing rather than predicted from the location count. An earlier
version predicted from the count and crashed between 126 and 130 locations.
None of the three productions comes close to this size.

---

## 3. Conclusion

### Answer to the research question

For a production of up to 20 locations, the optimal shooting order can be
computed and **proved** optimal in about six seconds — verified against
exhaustive search on 560 cases with no disagreement. Beyond that size the
problem is made tractable by one assumption, block shooting, which is what
productions do anyway; every step after that assumption remains exact.

On the three productions studied the resulting schedules cost **6.8% to 11.2%
less** than the greedy draft, and on subsets where a true optimum could still be
proved, partitioning **found that optimum outright in two of three cases and
cost 0.67% in the third** — while running two to four orders of magnitude
faster.

The two layers are genuinely coupled: 81–86% of location pairs have no direct
road, so most of the cost matrix this layer consumes exists only because the
geographic layer computed shortest paths for it.

### Weaknesses and limitations

1. **The partition is unverified above 20 locations.** Its cost can only be
   measured where an exact optimum is still computable. On larger productions —
   which is every production studied here at full size — the reported saving is
   against the greedy draft, not against a proven optimum, because no proven
   optimum exists at that size.

2. **The region count comes from a heuristic rule.** Cutting at the widest ratio
   gap in the MST's sorted edge weights works well on maps with real clusters,
   but it is a rule read off the data, not a method with a guarantee. A
   production whose locations are spread evenly rather than clustered would have
   no such gap to find, and the partition would have no structure to exploit.

3. **All timings are machine-dependent.** The limit of 20 locations, and the
   200 MB / 579 MB / 1.18 GB figures behind it, describe one machine running
   CPython. A faster language or more memory moves the boundary; the doubling
   per location does not.

4. **Location data is reconstructed, not official.** The lists come from
   enthusiast location guides rather than production paperwork, and the real
   shooting orders are unpublished, so these schedules cannot be compared with
   what the crews actually did.

5. **Only transition cost is modelled.** Crew and cast availability, permit
   windows, day-for-night requirements and story continuity all constrain a real
   schedule and none of them appear here. Section 1 shows that per-location
   shooting cost is genuinely irrelevant to the ordering; these other
   constraints are not, and their absence is a modelling choice, not a proof.

6. **The graph is undirected.** Real transit is often asymmetric — uphill
   against downhill, one-way roads, flight schedules — which the cost matrix
   cannot express as it stands.

### Future work

- **Precedence constraints from the script.** Some scenes must be shot before
  others: a building is destroyed, an actor's appearance changes, snow melts.
  These are exactly the constraints a map cannot know and a script can. They fit
  the subset DP directly — an ordering is legal only if a subset is closed under
  its predecessors — and, counter-intuitively, would make the DP *faster* by
  making many subsets illegal.

- **A guaranteed baseline.** CLRS §35.2 gives a 2-approximation for metric TSP
  built from a minimum spanning tree, and the MST is already computed here. The
  cost matrix satisfies the triangle inequality by construction, since it holds
  shortest paths, so the guarantee applies. That would add the one thing this
  layer currently lacks at large sizes: a provable bound rather than a measured
  gap.

- **Verifying the partition at scale** by using that bound, or by branch and
  bound, to establish an optimum for productions of 25–40 locations where the
  subset DP cannot reach.

- **Asymmetric costs**, which would let the model express one-way roads and
  directional travel times, at the price of losing the symmetry the current
  implementation assumes.

---

## Appendix — What runs what

| File | Contents |
|---|---|
| `schedule_dp.py` | Subset DP, the all-entry/exit table, brute-force oracle |
| `clustered_dp.py` | MST partitioning, region-level DP, self-test against brute force |
| `solver.py` | Entry point, timing, guarantee reporting, fallback |
| `road_network.py` | Coordinates, great-circle distance, road-network assembly |
| `film_data.py` | The three productions' locations and provenance |
| `main.py` | End-to-end pipeline: `python main.py la_la_land` |

Reproducing the numbers in Section 2.6: `python schedule_dp.py` (560-case
verification), `python clustered_dp.py` (400-case partition verification),
`python main.py <production>` (schedules).
