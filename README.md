# A Dual-Layer Film Production Optimization Framework

CS5800 final project. Moving a film crew between locations is expensive, and
the cost depends on more than distance — terrain, elevation and equipment load
all matter. This project asks a single question in two halves:

> **Given a set of filming locations, what shooting order minimises the total
> cost of moving the crew between them?**

Answering it needs two things that are usually conflated. First, *what does
each move actually cost* — which is a shortest-path problem, because the
cheapest way between two locations often runs through a third. Second, *in what
order should the locations be visited* — a minimum-cost Hamiltonian path, the
path variant of TSP, which is NP-hard (CLRS 3rd ed. §34.5.4 proves the tour
version's decision problem NP-complete; the path variant reduces to it).

The two are split across two layers with one interface between them.

```
               filming locations
                       │
   ┌───────────────────▼────────────────────┐
   │  liu/  —  geographic layer             │
   │  terrain-weighted graph                │
   │  Dijkstra, all pairs                   │
   │  greedy nearest-neighbour draft        │
   └───────────────────┬────────────────────┘
                       │   n × n cost matrix
   ┌───────────────────▼────────────────────┐
   │  song/  —  scheduling layer            │
   │  MST partitioning                      │
   │  subset DP, exact within and across    │
   └───────────────────┬────────────────────┘
                       │
                shooting order
```

The data that crosses the boundary is one call:
`all_pairs_shortest_paths(graph)`, returning a matrix where entry *(i, j)* is
the true cheapest cost of getting from location *i* to location *j*. The
scheduling layer also reuses the geographic layer's
`Node`/`Edge`/`SpatialGraph` types to build maps, and its greedy
nearest-neighbour routine as the fallback and the baseline to compare against —
but the cost matrix is the only thing the scheduling algorithms themselves
read.

That boundary carries real weight. On the three productions in
`song/film_data.py`,
**81–85% of location pairs have no direct road between them** — most of the
matrix exists only because shortest paths were computed for it.

## Repository layout

```
.
├── liu/                     Geographic layer — see liu/README.md
│   ├── __init__.py
│   ├── graph.py             Node/Edge schema, adjacency-matrix graph
│   ├── dijkstra.py          Dijkstra (heapq, lazy deletion), all-pairs
│   ├── greedy.py            Greedy nearest-neighbour scheduling heuristic
│   ├── data_gen.py          Seeded graph generators (toy / sparse / benchmark)
│   ├── benchmark.py         Runtime comparison
│   ├── visualize.py         Runtime curve and heatmaps
│   ├── plots/
│   └── docs/                REPORT.md, SLIDE_OUTLINE.md, PRESENTATION_SCRIPT.md
│
└── song/                    Scheduling layer — see song/README.md
    ├── schedule_dp.py       Subset DP, entry/exit table, brute-force oracle
    ├── clustered_dp.py      MST partitioning, region-level DP
    ├── solver.py            Entry point, guarantee reporting, fallback
    ├── road_network.py      Coordinates, great-circle distance, network assembly
    ├── film_data.py         Locations from three real productions
    ├── main.py              End-to-end pipeline
    ├── reproduce.py         Recomputes every measured table in the report
    ├── visualize.py         Matplotlib plots
    ├── plots/
    └── docs/REPORT.md
```

## Requirements

Python 3.10 or newer. Everything runs on the standard library except the two
plotting scripts:

```bash
pip install matplotlib          # for song/visualize.py
pip install matplotlib numpy    # liu/visualize.py also uses numpy
```

Commands below use `python3`; use `python` instead if that is what your
installation is called.

## Quick start

All commands run from the repository root.

```bash
# Schedule a real production, end to end through both layers
python3 song/main.py la_la_land

# Correctness: the schedulers against exhaustive search
python3 song/schedule_dp.py      # 560 cases
python3 song/clustered_dp.py     # 400 single-region + 200 multi-region cases

# Recompute every measured table in song/docs/REPORT.md
python3 song/reproduce.py

# Regenerate the figures
python3 song/visualize.py
python3 liu/visualize.py

# The geographic layer on its own
python3 liu/benchmark.py          # runtime comparison + 8-scene schedule
python3 liu/dijkstra.py           # shortest-path self-test
```

`python3 song/main.py` with no argument lists the available productions.

## The geographic layer (`liu/`)

Each filming location is a node carrying a terrain type and an elevation, and
edge weight combines those with the distance between them:

```
w = distance × (1 + 0.3 × elevation_factor) × terrain_multiplier
```

where `elevation_factor = |Δelevation| / 3000` capped at 1.0, and the terrain
multiplier is the average of the two endpoints' — URBAN 1.0, COASTAL 1.2,
FOREST 1.4, DESERT 1.6, MOUNTAIN 2.0.

Dijkstra then runs from every node, using a binary heap with lazy deletion in
place of decrease-key: `O((V + E) log V)` per source, `O(V · (V + E) log V)`
for all pairs. A greedy nearest-neighbour pass over the resulting matrix
produces a fast baseline schedule in `O(k²)`.

Graphs are generated programmatically from seeded generators rather than stored
as data files, so every figure in that layer's report reproduces exactly by
calling the same function again.

Full write-up: [`liu/README.md`](liu/README.md) ·
[`liu/docs/REPORT.md`](liu/docs/REPORT.md)

## The scheduling layer (`song/`)

One method: **partition the locations into regions, then solve exactly — inside
each region and across them.**

Regions come from a minimum spanning tree (Kruskal with union-find) with its
heaviest edges deleted; how many regions is read off the tree's own edge
weights at the widest ratio gap. Within a region, subset DP solves the route
from every entry point to every exit. Across regions, a second DP carries the
exit location in its state, so the joins are optimised together with the region
ordering.

**The partition is the only approximation in the method.** When a production is
small enough to solve outright there is nothing to partition, and the method
reduces to plain subset DP and returns a proven global optimum.

Data is 90 real filming locations from three productions at three geographic
scales — *La La Land* across Los Angeles, *Forrest Gump* across the United
States, *Tenet* across seven countries — with real coordinates, priced by the
geographic layer's formula.

Full write-up: [`song/README.md`](song/README.md) ·
[`song/docs/REPORT.md`](song/docs/REPORT.md)

## Results

Timings are machine-dependent and were measured on each author's own machine;
the costs and counts are deterministic and reproduce anywhere.

**The geographic layer.** All-pairs Dijkstra grows quickly with n since it
reruns single-source Dijkstra from every node, while greedy stays fast once the
matrix exists:

| Algorithm | n=10 | n=50 | n=100 | n=500 |
|---|---|---|---|---|
| Dijkstra (all-pairs) | 0.09 ms | 4.25 ms | 29.35 ms | 3,690.40 ms |
| Greedy nearest-neighbour | 0.02 ms | 0.06 ms | 0.21 ms | 4.77 ms |

**The scheduling layer.** Checked against exhaustive enumeration — 560 cases for
the subset DP, 400 single-region and 200 multi-region cases for the partitioned
path (the latter against an oracle that enumerates every region order and every
route within every region), with **no disagreements**. On the three
productions, against the greedy draft:

| Production | Locations | Greedy draft | Scheduled | Saving |
|---|---|---|---|---|
| La La Land (2016) | 26 | 235.86 | **210.68** | **10.7%** |
| Forrest Gump (1994) | 30 | 12,927.26 | **12,124.09** | **6.2%** |
| Tenet (2020) | 34 | 36,203.99 | **34,283.38** | **5.3%** |

Exact solving reaches 20 locations in about 6.6 s and 200 MB; at 22 it needs
812 MB, which is what sets the limit. The partition has a hard ceiling of 130
locations, though how far it actually reaches depends on how the locations
cluster; past that the system falls back to the geographic layer's greedy
draft.

**Both layers together.** Running the geographic layer's own benchmarks through
the exact solver answers the question neither layer can answer alone — how far
the fast draft actually lands from the optimum:

| Benchmark | Greedy draft | Proven optimum | Gap |
|---|---|---|---|
| 6 scenes | 332.81 | 304.88 | +9.16% |
| 8 scenes | 123.45 | 123.45 | **+0.00%** |
| 12 scenes | 179.47 | 140.07 | +28.13% |

The greedy draft happens to be optimal on the 8-scene benchmark and is 28% off
on the 12-scene one. That spread is the point: nearest-neighbour gives no
guarantee either way, and only an exact solver can say which case you are in.

## Division of work

| | |
|---|---|
| **`liu/`** | Graph model and terrain weighting, Dijkstra and all-pairs shortest paths, greedy nearest-neighbour baseline, generators, runtime benchmarks, plots |
| **`song/`** | Exact subset DP with brute-force verification, MST partitioning and the region-level DP, real filming-location dataset, end-to-end pipeline, plots |

Each layer is documented independently in its own `README.md` and
`docs/REPORT.md`; this file covers only how the two fit together.
