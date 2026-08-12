# A Dual-Layer Film Production Optimization Framework

CS5800 final project. Moving a film crew between locations costs more than the
distance suggests — terrain, elevation and equipment load all count. The project
asks one question in two halves:

> **Given a set of filming locations, what shooting order minimises the total
> cost of moving the crew between them?**

The first half is *what does each move cost*, a shortest-path problem, since the
cheapest way between two locations often runs through a third. The second is *in
what order should they be visited*, a minimum-cost Hamiltonian path and NP-hard.
Each is one layer.

```
                filming locations
                       │
   ┌───────────────────▼────────────────────┐
   │  liu/  —  geographic layer              │
   │  terrain-weighted graph                 │
   │  Dijkstra, all pairs                    │
   │  greedy nearest-neighbour draft         │
   └───────────────────┬────────────────────┘
                       │   n × n cost matrix
   ┌───────────────────▼────────────────────┐
   │  song/  —  scheduling layer             │
   │  MST partitioning                       │
   │  subset DP, exact within and across     │
   └───────────────────┬────────────────────┘
                       │
                shooting order
```

The data crossing the boundary is one call, `all_pairs_shortest_paths(graph)`,
whose entry *(i, j)* is the cheapest cost of getting from location *i* to *j*.
The scheduling layer also borrows the geographic layer's `Node`/`Edge`/
`SpatialGraph` types to build maps and its greedy routine as a baseline, but the
cost matrix is the only thing the scheduling algorithms read.

On the three productions in `song/film_data.py`, **81–85% of location pairs have
no direct road between them**, so most of that matrix exists only because
shortest paths were computed for it.

## Repository layout

```
.
├── liu/                     Geographic layer — see liu/README.md
│   ├── __init__.py
│   ├── graph.py             Node/Edge schema, adjacency-matrix graph
│   ├── dijkstra.py          Dijkstra (heapq, lazy deletion), all-pairs
│   ├── greedy.py            Greedy nearest-neighbour scheduling heuristic
│   ├── data_gen.py          Seeded graph generators
│   ├── benchmark.py         Runtime comparison
│   ├── visualize.py         Runtime curve and heatmaps
│   ├── plots/
│   └── docs/                REPORT.md, SLIDE_OUTLINE.md, PRESENTATION_SCRIPT.md
│
└── song/                    Scheduling layer — see song/README.md
    ├── schedule_dp.py       Subset DP, entry/exit table, brute-force oracle
    ├── clustered_dp.py      MST partitioning, region-level DP
    ├── solver.py            Entry point, guarantee reporting, fallback
    ├── road_network.py      Coordinates, great-circle distance, assembly
    ├── film_data.py         Locations from three real productions
    ├── main.py              End-to-end pipeline
    ├── reproduce.py         Recomputes every measured table in the report
    ├── visualize.py         Matplotlib figures
    ├── plots/
    └── docs/REPORT.md
```

## Requirements

Python 3.10 or newer. Everything runs on the standard library except the two
plotting scripts:

```bash
pip install matplotlib          # song/visualize.py
pip install matplotlib numpy    # liu/visualize.py also uses numpy
```

## Quick start

From the repository root:

```bash
python3 song/main.py la_la_land   # schedule a production through both layers
python3 song/schedule_dp.py       # 560 cases against exhaustive search
python3 song/clustered_dp.py      # 400 single-region + 200 multi-region cases
python3 song/reproduce.py         # recompute every table in song's report
python3 liu/benchmark.py          # the geographic layer's runtime comparison
```

`python3 song/main.py` with no argument lists the available productions.

## The two layers

**`liu/`** models each location by terrain type and elevation and prices an edge
as `distance × (1 + 0.3 × elevation_factor) × terrain_multiplier`, with the
multiplier averaged over the endpoints (URBAN 1.0 through MOUNTAIN 2.0). Dijkstra
then runs from every node — `O((V + E) log V)` per source — and a greedy
nearest-neighbour pass over the resulting matrix gives a fast baseline schedule.
Details: [`liu/README.md`](liu/README.md) · [`liu/docs/REPORT.md`](liu/docs/REPORT.md)

**`song/`** partitions the locations into regions by cutting a minimum spanning
tree, then solves exactly inside each region and across them, carrying the exit
location in the region-level DP state so the joins are optimised with the
ordering. A production small enough to solve outright skips the partition and
gets a proven optimum. Its data is 90 real filming locations at three scales —
Los Angeles, the United States, seven countries.
Details: [`song/README.md`](song/README.md) · [`song/docs/REPORT.md`](song/docs/REPORT.md)

## Results

Timings were measured on each author's own machine; costs and counts are
deterministic.

| Algorithm | n=10 | n=50 | n=100 | n=500 |
|---|---|---|---|---|
| Dijkstra (all-pairs) | 0.09 ms | 4.25 ms | 29.35 ms | 3,690.40 ms |
| Greedy nearest-neighbour | 0.02 ms | 0.06 ms | 0.21 ms | 4.77 ms |

| Production | Locations | Greedy draft | Scheduled | Saving |
|---|---|---|---|---|
| La La Land (2016) | 26 | 235.86 | **210.68** | **10.7%** |
| Forrest Gump (1994) | 30 | 12,927.26 | **12,124.09** | **6.2%** |
| Tenet (2020) | 34 | 36,203.99 | **34,283.38** | **5.3%** |

**Both layers together.** Running the geographic layer's own benchmarks through
the exact solver answers what neither layer can answer alone — how far the fast
draft lands from the optimum:

| Benchmark | Greedy draft | Proven optimum | Gap |
|---|---|---|---|
| 6 scenes | 332.81 | 304.88 | +9.16% |
| 8 scenes | 123.45 | 123.45 | **+0.00%** |
| 12 scenes | 179.47 | 140.07 | +28.13% |

The draft happens to be optimal on the 8-scene benchmark and 28% off on the
12-scene one. Nearest-neighbour gives no guarantee either way, and only an exact
solver distinguishes the two cases.
