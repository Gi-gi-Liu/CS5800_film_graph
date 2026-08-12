# CS5800 — A Dual-Layer Film Production Optimization Framework
## Song's Section: Exact Shooting-Order Scheduling by Partition and Subset DP

---

## 1. Introduction

### Context

A film shoots at many locations, and the crew has to be moved between them.
Once the geographic layer has answered *what does each move cost*, one question
is left, and it is the one that decides the schedule: **in what order should
the locations be shot?**

The two layers form a pipeline. Liu's layer turns filming locations into a
terrain-weighted graph and runs Dijkstra to produce an all-pairs cost matrix —
the true cheapest cost of moving between any two locations, routed through
intermediate stops where that is cheaper. That matrix is the input to this
layer, which chooses the order. Neither half is usable alone: without the cost
matrix there is nothing to order, and without an order the matrix is a table
nobody has acted on.

The dependency is not nominal. Across the three productions studied here,
**81–85% of location pairs have no direct road between them** (Section 2.6), so
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
through all locations — the path variant of the Travelling Salesman Problem.
CLRS 3rd ed. §34.5.4 proves the decision version of the *tour* problem
NP-complete; the path variant reduces to it in the standard way, so the
minimisation problem here is NP-hard. Exact methods are therefore expected to
be exponential, and the interesting question is *how far* they reach.

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

The order itself is recovered by walking `parent` backwards, clearing one bit
of the mask at each step (CLRS 3rd ed. §15.3, reconstructing an optimal
solution from the DP table).

This is the algorithm of Bellman (1962) and Held & Karp (1962). CLRS does not
contain it — the closest is Problem 15-3, a bitonic restriction of TSP — but
the paradigm it is built from is Chapter 15 (3rd ed.; Chapter 14 in the 4th):
optimal substructure, overlapping subproblems, and reconstruction from the
table.

**Time** `O(2ⁿ · n²)`  **Space** `O(2ⁿ · n)`

*Implementation note.* `dp` and `parent` are flat `array` buffers indexed as
`mask · n + v`, not nested Python lists. Nested lists of floats carry
per-object overhead that dominates at these sizes; the flat buffers hold raw
doubles and signed bytes. This is what puts n = 20 within reach on the test
machine rather than several sizes lower — see Section 2.6.

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
Kruskal's algorithm (CLRS 3rd ed. §23.2) and disjoint sets with path
compression (CLRS 3rd ed. Chapter 21). The clustering step itself is not a
separate algorithm: it is Kruskal stopped early. Its optimality (it maximises
the minimum spacing between groups) is the standard result in Kleinberg &
Tardos §4.7.

**How many regions?** The tree's own edge weights decide, with no threshold to
tune: the cut is taken where the ratio between consecutive sorted weights is
largest. The size cap then splits anything still too big for the exact solver.
The rule does most of the work at every scale, and how cleanly it does so
tracks how separated the geography actually is:

| Production | Regions from the ratio rule | Largest ratio, at k | After the cap |
|---|---|---|---|
| La La Land | 7 | 1.75× at k = 7 | 9 |
| Forrest Gump | 8 | 2.81× at k = 8 | 10 |
| Tenet | 10 | **5.24×** at k = 10 | 11 |

*Tenet*'s blocks are separate countries and the break is unmistakable — a
5.24× drop. Inside a single city the same rule still finds 7 of the eventual 9
regions, but on a much shallower break: *La La Land*'s heaviest tree edges run
33.0, 20.5, 14.7, 14.1, and the best ratio is only 1.75×. In every case the cap
adds at most two more regions — two on the US productions, one on *Tenet*.

If a region is still too large for the exact solver, it is split again using
its own heaviest internal edge. Splitting region by region rather than
continuing down the global weight order matters: one outlying Tallinn location
can be peeled off its own block without shattering the cities around it.

**Time** `O(n² log n)` — Kruskal over the dense cost matrix dominates.

#### Solving within a region — every way in and out

A region cannot be routed in isolation, because the cost of covering it depends
on where the crew enters and where it leaves. So for each region the exact
solver is run once per entry point, yielding the cheapest route that starts at
member `a`, covers the region, and finishes at member `b`, **for all pairs (a,
b)**:

```
PATH-COST-TABLE(cost, members):
    for each entry a:
        run DP-SCHEDULE restricted to members, starting at a
        for each exit b:  pc[a][b] ← dp[full][b];  record the path
    return pc, paths
```

**Time** `O(2^m · m³)` for a region of `m` locations.

#### Scheduling across regions

The region-level DP carries the exit location in its state, so the joins
between regions are optimised jointly with the region ordering rather than
chosen afterwards:

```
g[R][c][b] = minimum cost to have shot exactly the regions in R,
             standing at location b, the exit of region c

g[R ∪ {d}][d][y] = min over (c, b) ∈ g[R], over entries e of d:
                      g[R][c][b] + cost[b][e] + pc_d[e][y]
```

The inner minimisation over entry points `e` is precomputed once per (exit
location, target region, exit slot) triple, so the transition itself is `O(1)`.

**Time** `O(2^k · k² · m²)` for `k` regions of at most `m` locations.

Both exponents are now on small numbers — region count and region size —
instead of on the location count.

### 2.4 Testing

**Correctness of the exact solver.** Cross-checked against exhaustive
enumeration of every permutation, which is obviously correct and obviously too
slow to use. Random symmetric cost matrices, every size from n = 2 to 8, forty
matrices per size, open and returning-to-base:

> **560 cases, 0 disagreements.**

Reconstructed orders are re-walked and re-costed against the matrix, so a
correct total paired with a wrong path cannot pass.

**Correctness of the partitioned path, one region.** The same comparison, but
forcing the region machinery to run rather than short-circuiting to the exact
solver (`always_partition=True`), sizes n = 2 to 9, twenty-five matrices per
size, additionally requiring the reconstructed order to equal the subset DP's:

> **400 cases, 0 disagreements.**

This is what makes the claim in Section 2.1 checkable rather than asserted:
with one region the partitioned method reproduces the exact optimum, so plain
subset DP really is its degenerate case.

**Correctness of the partitioned path, several regions.** A single region never
reaches the entry/exit table, the region-level transitions or the chain
reconstruction — the parts that are specific to this method. Those are checked
against an oracle that enumerates every region order together with every route
within every region, sizes n = 4 to 8 with caps of 2 and 3, producing between 2
and 7 regions:

> **200 cases, 0 disagreements.**

**Validity on real data.** Every schedule produced for the three productions was
checked to be a permutation of all locations whose leg costs sum to the
reported total.

**Ground truth for the partition.** Each location carries the district, town or
city it truly belongs to. The scheduler never sees this field; it exists only
so the partition can be scored against it (Section 2.6).

### 2.5 Data

Locations come from three real productions, chosen so that the same method can
be tested at three geographic scales:

| Production | Locations | Real places | Scale |
|---|---|---|---|
| La La Land (2016) | 26 | 12 Los Angeles districts | one city |
| Forrest Gump (1994) | 30 | 16 towns across 8 states | one country |
| Tenet (2020) | 34 | 11 cities across 7 countries | the world |

Coordinates are real latitude and longitude; distances are great-circle
kilometres; edge weights come from the geographic layer's own terrain and
elevation formula, unchanged. Locations within a place are all connected to
each other (local roads); places connect only through their first-listed
location and only to their nearest few, so a cross-country move is a genuine
routing problem. A spanning tree over those hubs is laid down first, because a
pure nearest-neighbour long-haul network strands whole coasts.

**Provenance.** Location lists are transcribed from published location guides
(`movie-locations.com`), which are enthusiast reconstructions, not production
paperwork. Coordinates are landmark-accurate for named landmarks and
street-accurate for entries given only as an address — an error of a few
hundred metres, immaterial next to the tens of kilometres between districts.
Real shooting order is not published for any of the three, so these schedules
can be compared with each other but not against what the crews actually did.

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

States settled double with each added location, and the measured runtime
follows — the empirical curve is a straight line on a log scale, which is what
`2ⁿ` looks like. **What runs out is memory, not patience:** peak resident
memory is 200 MB at n = 20, 398 MB at n = 21 and 812 MB at n = 22, each
measured in its own process (measuring several sizes in one process reports the
running peak, not the peak of each). Those figures track the allocation the DP
asks for, 9·n·2ⁿ bytes. The limit is therefore set at 20.

#### Scheduling the three productions

| Production | Greedy draft | This method | Saving | Time | Regions |
|---|---|---|---|---|---|
| La La Land | 235.86 | **210.68** | **10.68%** | 6.1 ms | 9 |
| Forrest Gump | 12,927.26 | **12,124.09** | **6.21%** | 15.9 ms | 10 |
| Tenet | 36,203.99 | **34,283.38** | **5.30%** | 38.7 ms | 11 |

*La La Land* and *Tenet* move between places the fewest times possible — 11 of
11 and 10 of 10 — so the method arrives at block shooting on its own, without
being told to. *Forrest Gump* takes 16 moves against a floor of 15, and the
extra one is a labelling artefact rather than a detour: Los Angeles, Santa
Monica and Monterey Park are three labels for one metropolitan block, and the
schedule interleaves them as a crew actually would.

The failure it corrects is visible on the map. On *La La Land* the greedy draft
works its way south and east, then discovers it has left West Hills — the
furthest north-west location — for last, and pays **75.5** to cross the county
back to it from Long Beach. That single leg is more than twice any other in its
schedule. This method takes West Hills second as a place — sixth location
overall — straight out of the Burbank base, for **33.7**. It then works east
across Hollywood, Griffith Park and Pasadena before turning south to Downtown,
Hermosa Beach and Long Beach, and never returns to a place it has left. Its
most expensive leg is that same 33.7.

#### What the partition costs

The partition is the method's only approximation, so this is the only place it
can lose anything. On the largest subset of each production the solver can
still prove outright (20 locations), the same method is run twice — once with
the partition forced, once without — and both are measured against that proven
optimum:

| Production | Proven optimum | Time to prove | Partitioned | Gap | Greedy draft | Gap |
|---|---|---|---|---|---|---|
| La La Land | 117.16 | 6.39 s | 117.16 | **+0.00%** | 121.84 | +3.99% |
| Forrest Gump | 6,708.20 | 6.40 s | 6,708.20 | **+0.00%** | 6,715.96 | +0.12% |
| Tenet | 13,600.76 | 6.41 s | 13,600.76 | **+0.00%** | 13,602.93 | +0.02% |

**Partitioning found the proven optimum on all three, in milliseconds against
six and a half seconds.** That is a stronger result than it looks only until
you notice its scope: these are the largest subsets that can still be proved,
and the productions at full size are past that point.

#### What the partition discovers

The partition sees only the cost matrix — no place names, no coordinates — yet
it recovers the real geography at every scale:

| Production | Regions found | Matching a single real place |
|---|---|---|
| La La Land | 9 | 7 |
| Forrest Gump | 10 | 7 |
| Tenet | 11 | **10** |

The disagreements are informative rather than wrong. On *La La Land* the method
merges Hollywood, West Hollywood and Midtown into one block — three adjacent
districts — and merges Pasadena with South Pasadena, which share a border. On
*Forrest Gump* it merges Walterboro, Yemassee, McPhersonville and Varnville,
four rural South Carolina towns all within 39 km of one another, and merges Los
Angeles with Santa Monica and Monterey Park, which is what a production would
call one block regardless of the municipal lines between them.
**Most of the time the partition disagrees with the labels because the labels
are finer than the geography warrants.** Not always: its third *Forrest Gump*
merge joins Cut Bank to Glacier National Park, 82–89 km apart. Those are the
only two Montana entries on a map that otherwise runs from Maine to California,
so the tree has nothing nearer to attach them to — which is the honest limit of
reading regions off distances alone.

#### Why the pipeline needs both layers

| Production | Pairs | No direct road | Share | Detour is cheaper |
|---|---|---|---|---|
| La La Land | 325 | 275 | **84.6%** | 2 |
| Forrest Gump | 435 | 364 | **83.7%** | 16 |
| Tenet | 561 | 458 | **81.6%** | 16 |

Most of this layer's input exists only because shortest paths were computed for
it. Getting from Chippewa Square in Savannah to Marks Hall on the USC campus,
for instance, is a seven-hop route through McPhersonville, Varnville,
Grandfather Mountain, Monument Valley, Flagstaff and Monterey Park.

#### What the terrain weighting contributes

Each production was scheduled twice — once on the geographic layer's terrain
and elevation weights, once on raw kilometres — and both orders priced with the
real weights:

| Production | Cost of ignoring terrain | Non-urban locations | Distance spread |
|---|---|---|---|
| La La Land | +0.00% | 23% | 628× |
| Forrest Gump | +0.00% | 50% | 15,458× |
| Tenet | **+0.54%** | 41% | 136,459× |

The terrain model barely changes the schedule at all, and the reason is a
matter of scale: the terrain multiplier tops out at 2×, while the real
distances on these maps span up to five orders of magnitude. **Terrain can only
decide between locations that are already close — it cannot outweigh a
transatlantic flight.** On the two US productions the schedule costs exactly
the same with and without it — the orders differ, but not in a way that changes
the total; only *Tenet*, where four locations sit on Amalfi cliffs and two in
desert, comes out any different at all, and that is half a percent. The
geographic layer's terrain weighting is a real part of the cost model, but on
this data it is not what decides the order.

#### Choosing the region size cap

Larger regions are solved more exactly, but *finish this region before moving
on* is a constraint, so enlarging regions tightens it. The two effects pull
against each other:

| Cap | La La Land | Forrest Gump | Tenet |
|---|---|---|---|
| ≤ 2 | *past the region limit* | *past the region limit* | *past the region limit* |
| 3–4 | 210.68 | *past the region limit* | *past the region limit* |
| 5 | 210.68 | 12,131.85 | *past the region limit* |
| 6 | 210.68 | 12,131.85 | 34,284.59 |
| 7–9 | 210.68 | 12,124.09 | 34,284.59 |
| **10** | **210.68** | **12,124.09** | **34,283.38** |
| 11 | 210.68 | 12,124.09 | 34,283.38 |
| 12 | 217.73 | 12,124.09 | 34,283.38 |

No single cap is best everywhere. Below 6, *Tenet* needs more regions than the
region-level DP allows and cannot be partitioned at all; *Forrest Gump* needs
at least 5 and *La La Land* at least 3. At 12, *La La Land* costs 3.3% more,
because a cap that large stops splitting a block the schedule would rather
interleave. Caps 7 through 11 form a flat band in which all three productions
sit at their own best, or within 0.01% of it. **10 is inside that band and is
the smallest cap at which the largest production reaches its best cost**, so it
is the default.

#### The upper limit

`region_cap × MAX_REGIONS` puts a hard ceiling of **130 locations** on the
partition, but the count alone does not decide it — the geometry does. Thirteen
tight clusters of ten succeed all the way to 130 and fail at 131; eight
clusters succeed to 80; uniformly scattered points, with no cluster structure
for the tree to find, first fail around n = 40 and essentially always fail by
80 — the exact onset moves with the seed. When no partition can be formed the
code falls back to the geographic layer's greedy draft, and it does so because
the partition actually failed rather than because a location count was exceeded
— an earlier version predicted from the count and crashed in the 126–130 range.
The largest production here is 34 locations, below every one of these
thresholds.

---

## 3. Conclusion

### Answer to the research question

For a production of up to 20 locations, the optimal shooting order can be
computed and **proved** optimal in about six seconds — verified against
exhaustive search on 560 cases with no disagreement. Beyond that size the
problem is made tractable by one assumption, block shooting, which is what
productions do anyway; every step after that assumption remains exact.

On the three productions studied the resulting schedules cost **5.3% to 10.7%
less** than the greedy draft, and on the largest subsets where a true optimum
could still be proved, partitioning **found that optimum on all three** — in
milliseconds against six and a half seconds.

The two layers are genuinely coupled: 81–85% of location pairs have no direct
road, so most of the cost matrix this layer consumes exists only because the
geographic layer computed shortest paths for it.

### Weaknesses and limitations

1. **The partition is unverified above 20 locations.** Its cost can only be
   measured where an exact optimum is still computable. On larger productions —
   which is every production studied here at full size — the reported saving is
   against the greedy draft, not against a proven optimum, because no proven
   optimum exists at that size.

2. **The region count comes from a heuristic rule.** Cutting at the widest
ratio
   gap in the MST's sorted edge weights works well on maps with real clusters,
   but it is a rule read off the data, not a method with a guarantee. A
   production whose locations are spread evenly rather than clustered would have
   no such gap to find, and the partition would have no structure to exploit.

3. **All timings are machine-dependent.** The limit of 20 locations, and the
   200 MB / 398 MB / 812 MB figures behind it, describe one machine running
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
| `reproduce.py` | Recomputes every measured table in Section 2.6 |
| `visualize.py` | Draws the figures in `plots/` (needs matplotlib) |

Reproducing the numbers: `python reproduce.py` recomputes every table in
Section 2.6. The correctness counts print their own verdicts — `python
schedule_dp.py` for the 560 subset-DP cases and `python clustered_dp.py` for
the 400 single-region and 200 multi-region cases. The n = 21–22 rows and the
memory figures are the one exception: they need `EXACT_LIMIT` raised above the
shipped ceiling of 20, and were measured separately.