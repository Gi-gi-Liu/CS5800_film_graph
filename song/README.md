# Song's Section — Shooting-Order Scheduling by Partition and Subset DP

Part of the CS5800 **Dual-Layer Film Production Optimization Framework**. This
module takes the all-pairs cost matrix from Liu's geographic layer and answers
the remaining question: **in what order should the locations be shot?**

That is a minimum-cost Hamiltonian path from a fixed base, which is NP-hard. One
method handles every size: **partition the locations into regions, then solve
exactly inside each region and across them.** A production small enough to solve
outright has nothing to partition, so the method reduces to plain subset DP and
returns a proven optimum.

Full analysis, results and limitations: [`docs/REPORT.md`](docs/REPORT.md).

## Layout

```
song/
├── schedule_dp.py    # Subset DP (Held-Karp), entry/exit table, brute-force oracle
├── clustered_dp.py   # MST partitioning (Kruskal + union-find), region-level DP
├── solver.py         # Entry point: timing, guarantee reporting, greedy fallback
├── road_network.py   # Coordinates, great-circle distance, network assembly
├── film_data.py      # Filming locations from three real productions
├── main.py           # End-to-end pipeline
├── reproduce.py      # Recomputes every measured table in the report
├── visualize.py      # Matplotlib figures (see plots/)
├── plots/
└── docs/REPORT.md
```

## Requirements

No third-party package is needed to run the schedulers — outside the project the
only imports are `array`, `dataclasses`, `itertools`, `math`, `random`, `typing`,
`os`, `sys` and `time`. `visualize.py` is the exception:

```bash
pip install matplotlib    # only for visualize.py
```

## Running

```bash
python3 main.py                  # list the available productions
python3 main.py la_la_land       # schedule one, end to end
python3 main.py tenet --closed   # ... and return to base at wrap

python3 schedule_dp.py           # 560-case check against exhaustive search
python3 clustered_dp.py          # 400 single-region + 200 multi-region cases
python3 reproduce.py             # recompute every table in the report
python3 visualize.py             # redraw the figures in plots/
python3 film_data.py             # location data + network connectivity
python3 road_network.py          # a three-location worked example
```

## The method

**1 — Partition.** Build a minimum spanning tree over the cost matrix and delete
its heaviest edges. The region count is taken at the largest ratio between
consecutive sorted weights, so nothing needs tuning; anything still too big for
the exact solver is split again.

**2 — Solve within each region.** A region's cost depends on where the crew
enters and leaves, so the subset DP runs once per entry point and yields the
cheapest route from every entry to every exit.

**3 — Solve across regions.** A second DP whose state is *(regions finished,
current region, which exit you are standing at)*, so the joins between regions
are optimised together with the region ordering.

| Step | Cost |
|---|---|
| Partitioning | `O(n² log n)` |
| Within a region of `m` locations | `O(2^m · m³)` |
| Across `k` regions | `O(2^k · k² · m²)` |
| Unpartitioned (subset DP alone) | `O(2ⁿ · n²)` time, `O(2ⁿ · n)` space |

The exponents sit on the region size (capped at 10) and the region count (capped
at 13), not on the location count.

## Data

90 locations from three real productions, chosen to test the same method at three
geographic scales:

| Production | Locations | Real places | Scale |
|---|---|---|---|
| La La Land (2016) | 26 | 12 Los Angeles districts | one city |
| Forrest Gump (1994) | 30 | 16 towns across 8 states | one country |
| Tenet (2020) | 34 | 11 cities across 7 countries | the world |

Coordinates are real, distances are great-circle kilometres, and edge weights
come from the geographic layer's terrain and elevation formula unchanged. Lists
are transcribed from published location guides, then checked against
OpenStreetMap and authoritative records; `film_data.py` documents that pass and
what it changed.

## Results

Timings are from the development machine (Apple silicon, CPython 3.14); costs and
counts are deterministic.

**Correctness**, against exhaustive enumeration of every permutation:

| Check | Cases | Disagreements |
|---|---|---|
| Subset DP (n = 2–8) | 560 | **0** |
| One region, and its order against the subset DP's (n = 2–9) | 400 | **0** |
| Several regions, against a block-constrained oracle (n = 4–8, 2–7 regions) | 200 | **0** |

**Scheduling the three productions:**

| Production | Greedy draft | This method | Saving | Time |
|---|---|---|---|---|
| La La Land | 235.86 | **210.68** | **10.7%** | 6.1 ms |
| Forrest Gump | 12,927.26 | **12,124.09** | **6.2%** | 15.9 ms |
| Tenet | 36,203.99 | **34,283.38** | **5.3%** | 38.7 ms |

**What the partition costs**, on the largest subset of each production the exact
solver can still prove:

| Production | Proven optimum | Partitioned | Greedy draft |
|---|---|---|---|
| La La Land | 117.16 (6.39 s) | **117.16 · +0.00%** | 121.84 · +3.99% |
| Forrest Gump | 6,708.20 (6.40 s) | **6,708.20 · +0.00%** | 6,715.96 · +0.12% |
| Tenet | 13,600.76 (6.41 s) | **13,600.76 · +0.00%** | 13,602.93 · +0.02% |

Exact solving reaches 20 locations in 6.6 s and 200 MB; at 22 it needs 812 MB,
which is what sets the ceiling.

The report covers the rest: what the partitioning recovers of the real geography,
what the terrain weighting contributes, why the region cap sits where it does,
and where the method stops working.
