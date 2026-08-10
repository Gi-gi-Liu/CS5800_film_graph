# Liu's Section — Spatial Graph Modeling, Dijkstra & Greedy Heuristic

Part of the CS5800 **Dual-Layer Film Production Optimization Framework**. This
module covers the geographic/outdoor transition layer: modeling film
locations as a terrain-weighted spatial graph, computing all-pairs shortest
paths with Dijkstra's algorithm, and producing a fast baseline shooting order
with a greedy nearest-neighbor heuristic. The resulting cost matrix feeds
Song's exact DP solver as the transition cost function.

Full write-up, results, and analysis: [`docs/REPORT.md`](docs/REPORT.md).

## Layout

```
liu/
├── graph.py        # Node/Edge schema, SpatialGraph (adjacency-matrix graph)
├── dijkstra.py      # Dijkstra's algorithm using Python's heapq
├── greedy.py         # Greedy nearest-neighbor scheduling heuristic
├── data_gen.py       # Programmatic graph generators (toy / sparse / film benchmarks)
├── benchmark.py       # Simple runtime comparison: Dijkstra vs Greedy
├── visualize.py         # Matplotlib plots (runtime curve, heatmaps)
├── plots/                # Generated PNG output (see visualize.py)
└── docs/
    ├── REPORT.md              # Full analysis report
    ├── SLIDE_OUTLINE.md       # Slide deck outline
    └── PRESENTATION_SCRIPT.md # Presentation script
```

There is no static test-data directory — every graph used anywhere in this
project (toy graphs, sparse runtime-test graphs, film benchmarks) is generated
programmatically by `data_gen.py` with a fixed random seed per size, so any
graph in the docs can be reproduced exactly just by calling the same function
again.

## Requirements

```
pip install matplotlib numpy
```

(`graph.py`, `dijkstra.py`, `greedy.py`, `data_gen.py`, and `benchmark.py`
have no third-party dependencies; only `visualize.py` needs the above.)

## Running

Each module has a self-test / demo entry point:

```bash
python dijkstra.py      # Dijkstra self-test on a toy graph
python greedy.py        # Greedy self-test + 8-scene film benchmark demo
python data_gen.py      # Generator self-test + reproducibility check
python benchmark.py     # Runtime comparison + 8-scene greedy schedule
python visualize.py     # Generates runtime curve + heatmaps into plots/
```

## Key results

For the 8-scene film benchmark (`create_film_benchmark(8)`, seeded), the
greedy schedule totals **123.45**. Runtime scales as expected: Dijkstra
all-pairs grows quickly with n since it reruns single-source Dijkstra from
every node, while greedy stays fast once the cost matrix is precomputed:

| Algorithm | n=10 | n=50 | n=100 | n=500 |
|---|---|---|---|---|
| Dijkstra (all-pairs) | 0.09 ms | 4.25 ms | 29.35 ms | 3,690.40 ms |
| Greedy NN | 0.02 ms | 0.06 ms | 0.21 ms | 4.77 ms |

Greedy is a heuristic — it gives a fast, valid schedule but no optimality
guarantee. Determining exact optimality is Song's DP solver's job for
productions small enough to solve exactly (proven optimal up to ~20 locations;
a partitioning heuristic, or a greedy fallback of its own, takes over above
that) — not something this layer re-derives. See
[`docs/REPORT.md`](docs/REPORT.md) for the full write-up.
