# CS5800 — Slide Deck Outline (Liu's Section)
## 7 Slides | 7-Minute Presentation

---

## SLIDE 1 — Title

**Title:** A Dual-Layer Film Production Optimization Framework
**Subtitle:** Liu's Layer: Spatial Graph Modeling, Dijkstra's Algorithm & Greedy Heuristic

**Visual:**
- Clean split-layout: left side shows a simplified node-edge graph diagram (4 location nodes connected by weighted edges), right side shows a crew silhouette at a mountain location
- CS5800 course label + presenter name

**Speaking note:** Introduce yourself and the geographic layer of the project.

---

## SLIDE 2 — Introduction & Research Question

**Title:** The Problem: Moving a Film Crew Across Terrain

**Left column — Context bullets:**
- Film crews haul cameras, lighting rigs, and equipment across diverse terrain
- Standard maps calculate driving distance — not terrain difficulty, elevation, or crew load
- Transition costs compound across a full shooting schedule

**Center — Research Question (large, boxed):**
> Given a set of film locations connected by terrain-weighted transit routes,  
> what shooting order minimizes total geographic transition cost?

**Right column — Two-layer diagram:**
```
┌─────────────────────────┐
│  Song's Layer           │
│  On-Set Continuity      │
│  (DP State Machine)     │
└────────────┬────────────┘
             │  cost_matrix[i][j]
┌────────────▼────────────┐
│  Liu's Layer            │
│  Spatial Graph Model    │
│  Dijkstra + Greedy      │
└─────────────────────────┘
```

**Speaking note:** Explain how Liu's cost matrix feeds Song's DP solver.

---

## SLIDE 3 — Graph Schema & Weight Formula

**Title:** Modeling Locations as a Weighted Spatial Graph

**Top half — Node & Edge schema (two side-by-side tables):**

| Node Field | Type | Example |
|---|---|---|
| `id` | int | 0 |
| `name` | str | `mountain_peak` |
| `terrain_type` | enum | MOUNTAIN |
| `elevation_m` | float | 1347 m |
| `is_basecamp` | bool | False |

| Terrain | Multiplier |
|---|---|
| URBAN | 1.0 |
| COASTAL | 1.2 |
| FOREST | 1.4 |
| DESERT | 1.6 |
| MOUNTAIN | 2.0 |

**Bottom half — Weight formula (large, centered):**
```
w = distance × (1 + 0.3 × elevation_factor) × terrain_multiplier

elevation_factor = |Δelevation| / 3000   (normalized, capped at 1.0)
terrain_multiplier = avg(src_multiplier, dst_multiplier)
```

**Inset — adjacency matrix convention:**
```
matrix[i][j] = 0   →  no direct route
matrix[i][j] > 0   →  edge weight (composite cost)
```

**Speaking note:** Walk through one concrete weight calculation: downtown (urban, 4m) → mountain_peak (mountain, 1347m).

---

## SLIDE 4 — Algorithms: Dijkstra & Greedy

**Title:** Two Algorithms: Exact Paths + Fast Scheduling

**Left panel — Dijkstra (Python `heapq`):**

```
DIJKSTRA(graph, source):
  dist[all] ← ∞;  dist[source] ← 0
  heap ← [(0, source)]           // heapq

  while heap not empty:
    (d, u) ← heappop(heap)
    if d > dist[u]: continue   // lazy deletion
    for each neighbor v, weight w:
      if dist[u] + w < dist[v]:
        dist[v] ← dist[u] + w
        heappush(heap, (dist[v], v))
```

Priority queue: standard library `heapq` binary heap
- Decrease-key handled via **lazy deletion** (push new entry, skip stale pops)
- No custom data structure needed — keeps the algorithm code focused on the graph logic

Time: O((V + E) log V) per source
All-pairs: O(V · (V + E) log V)

**Right panel — Greedy Nearest-Neighbor:**

```
GREEDY(cost_matrix, start, scenes):
  current ← start
  while unvisited scenes remain:
    next ← argmin cost_matrix[current][v]
               for v in unvisited
    visit next; current ← next
```

Time: O(k²) where k = scenes
Input: all-pairs cost matrix from Dijkstra

**Bottom banner:**
`all_pairs_shortest_paths(graph)` → n×n cost matrix → Song's DP solver

**Speaking note:** Emphasize the clean interface between Liu's output and Song's input.

---

## SLIDE 5 — Test Data & Hand Trace

**Title:** Testing: From Toy Graphs to Film Benchmarks

**Left column — Test data hierarchy (all generated programmatically by `data_gen.py`, fixed seeds for reproducibility — no static matrix files):**

```
Level 1: generate_toy_graph(4, seed=1)
   → Hand-traceable, unit verification

Level 2: generate_toy_graph(6, seed=2)
   → Edge-case coverage

Level 3: create_film_benchmark(n)
   → Film benchmark, realistic weights (used for the n=8 results)

Level 4: generate_sparse_graph(n)
   → n = 10 to 500 nodes
   → Runtime comparison
```

**Center — 4-node adjacency matrix (`generate_toy_graph(4, seed=1)`):**
```
      0       1       2       3
0   0.00   13.08    0.00   21.36
1  13.08    0.00    2.66   21.39
2   0.00    2.66    0.00   27.29
3  21.36   21.39   27.29    0.00
```

**Right column — Hand trace of Dijkstra (4-node, source = node 0):**
```
Init:  dist = [0, ∞, ∞, ∞]
Pop (0, 0):
  → 1: dist[1] = 13.08   push(13.08, 1)
  → 3: dist[3] = 21.36   push(21.36, 3)
Pop (13.08, 1):
  → 2: dist[2] = 15.74   push(15.74, 2)
  → 3: 13.08+21.39=34.47 > 21.36, skip
Pop (15.74, 2):
  → 3: 15.74+27.29=43.03 > 21.36, skip
Pop (21.36, 3):
  done

Final dist: [0, 13.08, 15.74, 21.36]

Greedy (on the all-pairs cost matrix, not raw edges):
Greedy order: 0 → 1 → 2 → 3
Step costs: 13.08 + 2.66 + 24.05
Total cost: 39.79
```

**Speaking note:** Show this matches the matrix produced by the actual code (`generate_toy_graph(4, seed=1)`) — validates the implementation against a hand trace, not a separately hand-picked example.

---

## SLIDE 6 — Results & Benchmark Output

**Title:** Results: Schedules & Runtime

**Left — Greedy schedule output (8 scenes):**
```
Step 0: downtown_plaza    [START]
Step 1: desert_dunes      +12.68
Step 2: forest_trail      +27.23
Step 3: river_crossing    + 7.46
Step 4: cliff_edge        +17.18
Step 5: coastal_cove      +23.73
Step 6: ancient_ruins     +24.79
Step 7: mountain_peak     +10.38
──────────────────────────────────
TOTAL COST:  123.45
```

**Right — Runtime table:**

| Algorithm | n=10 | n=50 | n=100 | n=500 |
|---|---|---|---|---|
| Dijkstra all-pairs | 0.09 ms | 4.25 ms | 29.35 ms | 3,690 ms |
| Greedy NN | 0.02 ms | 0.06 ms | 0.21 ms | 4.77 ms |

**Bottom — Heatmap thumbnail:**
Reference `liu/plots/film_benchmark_8_heatmap.png` — adjacency matrix weight visualization for the 8-scene benchmark (same generated graph used for the results, not a separate hand-made example)

**Speaking note:** Greedy stays fast because it only makes one O(k²) pass once Dijkstra's cost matrix already exists; Dijkstra all-pairs is the expensive part since it reruns single-source Dijkstra from every node. Greedy gives a fast, valid schedule but no optimality guarantee — Song's exact DP layer proves optimality for productions up to about 20 locations, and falls back to a partitioning heuristic (or greedy itself, at very large scale) beyond that.

---

## SLIDE 7 — Conclusion & Future Work

**Title:** Conclusions & What Comes Next

**Left column — Summary (3 bullets):**
- Modeled film locations as terrain-weighted spatial graphs using a composite weight formula encoding distance, elevation, and terrain difficulty
- Implemented Dijkstra's algorithm with Python's `heapq`; all-pairs cost matrix feeds Song's DP solver as C_loc
- Greedy Nearest-Neighbor is fast (O(k²)) and gives a valid schedule, but no optimality guarantee — Song's exact DP layer proves optimality up to ~20 locations, and falls back to partitioning (or greedy) beyond that

**Center column — Limitations:**
- Synthetic data only; real-world GPS/elevation not yet integrated
- Undirected graph; real transit costs are often asymmetric
- All-pairs Dijkstra memory scales as O(n²) — impractical for very large n
- Single crew unit; multi-unit productions require parallel scheduling

**Right column — Future Work:**
- Integrate OpenStreetMap + SRTM elevation data for real terrain weights
- Apply A\* search with geospatial heuristic for large-scale graphs
- 2-opt local search post-greedy to improve on the nearest-neighbor schedule
- Extend to directed graphs for asymmetric transit costs
- Multi-unit crew formulation (partition scenes, minimize makespan)

**Bottom banner — Project interface summary:**
```
Liu produces:   all_pairs_cost_matrix[n×n]
                     ↓
Song consumes:  C_loc in DP transition cost
                dp[S][v] = min over u of dp[S\{v}][u] + cost[u][v]
```

**Speaking note:** End by tying back to the research question — greedy gives a good starting schedule, DP gives the optimal one.

---

## Design Notes for Slides

- **Color scheme:** Dark navy background with white text and amber/gold accents for code blocks; matches film production aesthetic
- **Font:** Monospace for all code/matrices; sans-serif for body text
- **Plots to embed (from `liu/plots/`):**
  - Slide 6: `runtime_curves.png`, `film_benchmark_8_heatmap.png`
  - Slide 3: `film_benchmark_6_heatmap.png` (adjacency matrix heatmap)
- **Code blocks:** Use light gray background boxes, syntax-highlighted pseudocode
- **Transitions:** Fade — no animations that obscure technical content
