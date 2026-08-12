# Song's Section — Shooting-Order Scheduling by Partition and Subset DP

Part of the CS5800 **Dual-Layer Film Production Optimization Framework**. This
module takes the all-pairs cost matrix produced by Liu's geographic layer and
answers the remaining question: **in what order should the locations be shot?**

The problem is a minimum-cost Hamiltonian path from a fixed base — the path
variant of TSP. CLRS 3rd ed. §34.5.4 proves the tour version's decision problem
NP-complete and the path variant reduces to it, so this is NP-hard. The
approach here is a single method: **partition the locations into regions, then
solve exactly, both inside each region and across them.** When a production is
small enough to solve outright there is nothing to partition, and the method
returns a proven global optimum.

Full write-up, results, and analysis: [`docs/REPORT.md`](docs/REPORT.md).

## Layout

```
song/
├── schedule_dp.py    # Subset DP (Held-Karp), entry/exit table, brute-force oracle
├── clustered_dp.py   # MST partitioning (Kruskal + union-find), region-level DP
├── solver.py         # Entry point: timing, guarantee reporting, greedy fallback
├── road_network.py   # Coordinates, great-circle distance, road-network assembly
├── film_data.py      # Filming locations from three real productions
├── main.py           # End-to-end pipeline
├── reproduce.py      # Recomputes every measured table in the report
├── visualize.py      # Matplotlib plots (see plots/)
├── plots/            # Generated PNG output
└── docs/
    └── REPORT.md     # Full analysis report
```

## Requirements

No third-party package is needed to run the schedulers. Outside the project the
only imports are `array`, `dataclasses`, `itertools`, `math`, `random`,
`typing`, `os`, `sys` and `time` — no NumPy, no graph libraries, and no `heapq`
(the only heap in the pipeline is the one inside the geographic layer's
Dijkstra).

`visualize.py` is the one exception, since it draws the figures:

```bash
pip install matplotlib    # only needed for visualize.py
```

## Running

```bash
python3 main.py                  # list the available productions
python3 main.py la_la_land       # schedule one, end to end
python3 main.py tenet --closed   # ... and return to base at wrap

python3 schedule_dp.py           # 560-case check against exhaustive search
python3 clustered_dp.py          # 400 single-region + 200 multi-region cases
python3 reproduce.py             # recompute every measured table in the report
python3 film_data.py             # location data + road-network connectivity
python3 road_network.py          # a three-location worked example
python3 visualize.py             # regenerate the plots in plots/
```

Every table in "Key results" below is recomputed by `reproduce.py`, except the
two correctness checks, which print their own verdicts, and the n = 21–22 rows
and memory figures, which need `EXACT_LIMIT` raised above the shipped ceiling of
20 and were measured separately.

## The method

**1 — Partition.** Build a minimum spanning tree over the cost matrix (Kruskal
with union-find) and delete its heaviest edges. What is left are groups of
locations that are cheap to reach from one another; a long haul between cities
is exactly the sort of edge that gets cut. How many regions is read off the
tree's own edge weights, at the widest ratio gap between consecutive sorted
weights. The rule does most of the work at every scale — 7 of the final 9
regions on *La La Land*, 8 of 10 on *Forrest Gump*, 10 of 11 on *Tenet* — and
how cleanly it separates them tracks the geography: the decisive ratio is 5.24×
on *Tenet*, whose blocks are separate countries, against 1.75× inside Los
Angeles. If a region is still too large for the exact solver, it is split again
on its own heaviest internal edge.

**2 — Solve within each region.** A region's cost depends on where the crew
enters and where it leaves, so the subset DP is run once per entry point,
giving the cheapest route from every entry to every exit.

**3 — Solve across regions.** A second DP whose state is *(regions finished,
current region, which exit you are standing at)*. Carrying the exit location in
the state means the joins between regions are optimised together with the
region ordering, rather than chosen after the fact.

**The partition is the only approximation in the method.** Everything after it —
the route inside each region, the order of the regions, and the entry and exit
points — is exact.

### Complexity

| Step | |
|---|---|
| Partitioning | `O(n² log n)` |
| Within a region of `m` locations | `O(2^m · m³)` |
| Across `k` regions | `O(2^k · k² · m²)` |
| Unpartitioned (subset DP alone) | `O(2ⁿ · n²)` time, `O(2ⁿ · n)` space |

The exponents sit on the region size (capped at 10) and the region count
(capped at 13) rather than on the location count.

## Data

Locations come from three real productions, chosen to test the same method at
three geographic scales:

| Production | Locations | Real places | Scale |
|---|---|---|---|
| La La Land (2016) | 26 | 12 Los Angeles districts | one city |
| Forrest Gump (1994) | 30 | 16 towns across 8 states | one country |
| Tenet (2020) | 34 | 11 cities across 7 countries | the world |

Coordinates are real latitude and longitude, distances are great-circle
kilometres, and edge weights come from the geographic layer's terrain and
elevation formula unchanged. Location lists are transcribed from published
location guides (`movie-locations.com`), which are enthusiast reconstructions
rather than production paperwork. Every entry was then checked against
OpenStreetMap, a terrain model and, where one exists, an authoritative record:
three entries were dropped for not being filming locations at all, and
twenty-three coordinates and nine group labels were corrected. After that pass
the median coordinate error is 0.18 km, and the handful above 500 m are area
features — a wind farm, an island, a park entrance — where a single coordinate
is inherently approximate. `film_data.py` documents the pass in full.

Each location also records the district, town or city it truly belongs to. The
scheduler never reads that field — it exists only so the partition can be
scored against ground truth.

## Key results

Timings are wall-clock on the development machine (Apple silicon, CPython 3.14)
and are machine-dependent; the growth rates are not.

**Correctness.** Checked against exhaustive enumeration of every permutation,
on random cost matrices, open and returning-to-base:

| Check | Cases | Disagreements |
|---|---|---|
| Subset DP vs exhaustive search (n = 2–8) | 560 | **0** |
| One region — partitioned path vs exhaustive search, and its order vs the subset DP's (n = 2–9) | 400 | **0** |
| Several regions — vs an oracle enumerating every region order and every route within every region (n = 4–8, 2–7 regions) | 200 | **0** |

Reconstructed orders are re-walked and re-costed, so a correct total paired
with a wrong path cannot pass. The multi-region check is the one that exercises
the entry/exit table, the region-level transitions and the chain reconstruction
— the parts a single region never reaches.

**How far the exact solver reaches.** States double with each added location,
and memory runs out before patience does:

| Locations | Time | Peak memory |
|---|---|---|
| 18 | 1.32 s | 60 MB |
| **20** | **6.58 s** | **200 MB** |
| 21 | 14.08 s | 398 MB |
| 22 | 32.40 s | 812 MB |

The limit is therefore set at 20 locations.

**Scheduling the three productions.**

| Production | Greedy draft | This method | Saving | Time |
|---|---|---|---|---|
| La La Land | 235.86 | **210.68** | **10.7%** | 6.1 ms |
| Forrest Gump | 12,927.26 | **12,124.09** | **6.2%** | 15.9 ms |
| Tenet | 36,203.99 | **34,283.38** | **5.3%** | 38.7 ms |

*La La Land* and *Tenet* move between places the fewest times possible (11 of 11
and 10 of 10) — the method arrives at block shooting on its own. *Forrest Gump*
takes one move more than the floor, because Los Angeles, Santa Monica and
Monterey Park are three labels for one metropolitan block and the schedule
interleaves them as a crew would.

**What the partition costs.** On the largest subset of each production the
solver can still prove outright (20 locations), the same method is run twice,
once with the partition forced and once without, and both measured against that
proven optimum:

| Production | Proven optimum | Partitioned | Greedy draft |
|---|---|---|---|
| La La Land | 117.16 (6.39 s) | **117.16 · +0.00%** | 121.84 · +3.99% |
| Forrest Gump | 6,708.20 (6.40 s) | **6,708.20 · +0.00%** | 6,715.96 · +0.12% |
| Tenet | 13,600.76 (6.41 s) | **13,600.76 · +0.00%** | 13,602.93 · +0.02% |

Partitioning found the proven optimum on all three, in milliseconds against six
and a half seconds. Note the scope: these are the largest subsets that can
still be proved, and the productions at full size are past that point.

**What the partition discovers.** It sees only the cost matrix — no place names,
no coordinates — and still recovers the real geography at every scale:

| Production | Regions found | Matching a single real place |
|---|---|---|
| La La Land | 9 | 7 |
| Forrest Gump | 10 | 7 |
| Tenet | 11 | **10** |

Most disagreements are labels finer than the geography warrants: it merges
Hollywood, West Hollywood and Midtown into one block, merges Pasadena with
South Pasadena, and merges four rural South Carolina towns that all sit within
39 km of each other. One is a genuine stretch — Cut Bank and Glacier National
Park, 82–89 km apart, joined because they are the only two Montana entries on
the map.

## Limitations

- Above 20 locations the partition's cost cannot be measured, because no proven
  optimum exists at that size. The savings reported for the full productions are
  against the greedy draft, not against a proven optimum.
- The region count comes from a rule read off the data — the widest gap in the
  MST's sorted edge weights. It works on maps with real clusters; a production
  whose locations are spread evenly would offer no such gap.
- The partition has a hard ceiling of 130 locations (`region_cap × MAX_REGIONS`),
  but geometry decides long before the count does: tight clusters reach 130,
  while uniformly scattered points first fail around 40 and essentially always
  fail by 80. When no partition can be formed the code falls back to the
  geographic layer's greedy draft.
- Only transition cost is modelled. Cast availability, permit windows and story
  continuity all constrain a real schedule and none of them appear here.

See [`docs/REPORT.md`](docs/REPORT.md) for the full analysis, including what
the terrain weighting contributes, why the region size cap is set where it is,
and how much of the cost matrix exists only because of shortest paths.
