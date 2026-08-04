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

**Left panel — Dijkstra (custom min-heap):**

```
DIJKSTRA(graph, source):
  dist[all] ← ∞;  dist[source] ← 0
  heap.push(0, source)

  while heap not empty:
    (d, u) ← heap.pop()
    if d > dist[u]: continue   // lazy deletion
    for each neighbor v, weight w:
      if dist[u] + w < dist[v]:
        dist[v] ← dist[u] + w
        heap.push(dist[v], v)
```

Min-Heap (from scratch):
- List-based binary tree
- `push` → sift_up O(log n)
- `pop` → sift_down O(log n)
- Decrease-key via **lazy deletion**

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

**Left column — Test data hierarchy:**

```
Level 1: toy_4node.txt (4 nodes)
   → Hand-traceable, unit verification

Level 2: toy_6node.txt (6 nodes)
   → Edge-case coverage

Level 3: scene_8.txt / scene_12.txt
   → Film benchmark, realistic weights

Level 4: Synthetic sparse/grid graphs
   → n = 100 to 10,000 nodes
   → Scalability & stress tests
```

**Center — 4-node adjacency matrix (toy):**
```
         downtown  forest  mountain  coastal
downtown        0       5         0        8
forest          5       0         3        0
mountain        0       3         0        7
coastal         8       0         7        0
```

**Right column — Hand trace of Dijkstra (4-node):**
```
Source: downtown (node 0)

Init:  dist = [0, ∞, ∞, ∞]
Pop (0, downtown):
  → forest: dist[1] = 5   push(5,1)
  → coastal: dist[3] = 8  push(8,3)
Pop (5, forest):
  → mountain: dist[2] = 8 push(8,2)
Pop (8, mountain):
  → coastal: 8+7=15 > 8, skip
Pop (8, coastal):
  done

Final dist: [0, 5, 8, 8]
Greedy order: downtown→forest→mountain→coastal
Total cost: 5 + 3 + 7 = 15  ✓
```

**Speaking note:** Show this matches manual calculation — validates the implementation.

---

## SLIDE 6 — Results & Benchmark Output

**Title:** Results: Schedules, Runtimes & Optimality Gap

**Top left — Greedy schedule output (8 scenes):**
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

**Top right — Runtime table:**

| Algorithm | n=50 | n=100 | n=500 | n=1,000 |
|---|---|---|---|---|
| Dijkstra all-pairs | 3.5 ms | 23.9 ms | 2,613 ms | 19,688 ms |
| Greedy NN | 0.03 ms | 0.10 ms | 2.56 ms | 14.48 ms |

**Bottom left — Optimality gap chart (bar chart image):**
```
           Greedy vs Dijkstra Lower Bound
6 scenes:  ████████████████░░░░  57.65%
8 scenes:  ████████████████████░  64.38%
10 scenes: ████████████████░░░░  59.43%
12 scenes: █████████████████████  71.50%
           (filled = gap above lower bound)
```

**Bottom right — Heatmap thumbnail:**
Reference `liu/plots/scene_8_heatmap.png` — adjacency matrix weight visualization for 8-scene benchmark

**Speaking note:** The 57–71% gap directly motivates why the exact DP solver is needed.

---

## SLIDE 7 — Conclusion & Future Work

**Title:** Conclusions & What Comes Next

**Left column — Summary (3 bullets):**
- Modeled film locations as terrain-weighted spatial graphs using a composite weight formula encoding distance, elevation, and terrain difficulty
- Implemented Dijkstra's algorithm with a custom from-scratch min-heap; all-pairs cost matrix feeds Song's DP solver as C_loc
- Greedy Nearest-Neighbor is fast (O(k²)) but leaves a **57–71% optimality gap** — confirming the necessity of exact DP

**Center column — Limitations:**
- Synthetic data only; real-world GPS/elevation not yet integrated
- Undirected graph; real transit costs are often asymmetric
- All-pairs Dijkstra memory scales as O(n²) — impractical for n > 10,000
- Single crew unit; multi-unit productions require parallel scheduling

**Right column — Future Work:**
- Integrate OpenStreetMap + SRTM elevation data for real terrain weights
- Apply A\* search with geospatial heuristic for large-scale graphs
- 2-opt local search post-greedy to reduce gap without full DP
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
  - Slide 6: `runtime_curves.png`, `optimality_gap.png`, `scene_8_heatmap.png`
  - Slide 3: `toy_4node_heatmap.png` (adjacency matrix heatmap)
- **Code blocks:** Use light gray background boxes, syntax-highlighted pseudocode
- **Transitions:** Fade — no animations that obscure technical content
