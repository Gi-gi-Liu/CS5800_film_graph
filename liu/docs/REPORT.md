# CS5800 — A Dual-Layer Film Production Optimization Framework
## Liu's Section: Spatial Graph Modeling, Dijkstra's Algorithm & Greedy Heuristic

---

## 1. Introduction

### Context

Film production is not just a creative process — it is a demanding logistical operation. A crew relocating between filming locations must account for road distance, terrain difficulty, elevation gain, and equipment load. When shooting schedules are determined informally, these transition costs accumulate into significant budget overruns and schedule delays.

This project models film location scheduling as a **graph optimization problem**. Each filming location is a node; each feasible transit route between locations is a weighted edge. Finding the optimal shooting order is equivalent to finding a minimum-cost Hamiltonian path through this graph — a variant of the Travelling Salesman Problem (TSP).

### Research Question

> **Given a set of film locations connected by terrain-weighted transit costs, what shooting order minimizes the total geographic and logistical transition cost?**

### Rationale (Liu's Layer)

My focus addresses the **geographic and outdoor transition layer** of the scheduling problem. Standard navigation tools (Google Maps, etc.) compute driving distance but ignore terrain elevation, equipment-hauling overhead, and terrain difficulty multipliers specific to film crews. I model these as a **weighted spatial graph** and solve the location-ordering subproblem using:

- **Dijkstra's algorithm** — exact shortest paths between all location pairs
- **Greedy Nearest-Neighbor heuristic** — fast approximate schedule ordering

The all-pairs shortest-path cost matrix produced by Dijkstra feeds directly into Song's Dynamic Programming solver as the transition cost function $C_\text{loc}$.

---

## 2. Analysis

### 2.1 Graph Schema

Each filming location is modeled as a **Node**:

| Field | Type | Description |
|---|---|---|
| `id` | int | 0-based index matching matrix row/column |
| `name` | str | Location name (e.g., `mountain_peak`) |
| `terrain_type` | enum | URBAN / FOREST / MOUNTAIN / COASTAL / DESERT |
| `elevation_m` | float | Elevation above sea level (metres) |
| `is_basecamp` | bool | True if this is the production start point |

Each transit route is modeled as an **Edge** with a composite weight formula:

```
w = distance × (1 + 0.3 × elevation_factor) × terrain_multiplier
```

Where:
- `elevation_factor = |Δelevation| / 3000` (normalized, capped at 1.0)
- `terrain_multiplier` = average of the two endpoint multipliers

**Terrain multipliers:**

| Terrain | Multiplier | Rationale |
|---|---|---|
| URBAN | 1.0 | Paved roads, easy crew access |
| COASTAL | 1.2 | Sand, limited vehicle access |
| FOREST | 1.4 | Dirt trails, tree clearance |
| DESERT | 1.6 | Sand dunes, heat stress, equipment risk |
| MOUNTAIN | 2.0 | Steep grades, altitude, unpaved |

The adjacency matrix convention (agreed interface with Song's DP solver):
- `matrix[i][j] = 0` → no direct route between locations i and j
- `matrix[i][j] > 0` → edge weight (composite cost)

---

### 2.2 Test Data (Adjacency Matrices)

#### Toy 4-Node Graph (`toy_4node.txt`)
Four locations: downtown, forest_trail, mountain_peak, coastal_cove.
Used for hand-tracing and algorithm verification.

```
         downtown  forest_tr  mountain  coastal_c
downtown        0          5         0          8
forest_tr       5          0         3          0
mountain        0          3         0          7
coastal_c       8          0         7          0
```

#### 8-Scene Film Benchmark (`scene_8.txt`)

```
 0  8  0 15  0  0 12  0
 8  0  5  0 11  0  0  9
 0  5  0  7  0 13  0  0
15  0  7  0  0  6  0 18
 0 11  0  0  0  4 14  0
 0  0 13  6  4  0  0 10
12  0  0  0 14  0  0  3
 0  9  0 18  0 10  3  0
```

Scene node metadata:

| ID | Location | Terrain | Elevation (m) |
|---|---|---|---|
| 0 | downtown_plaza | urban | 4 |
| 1 | forest_trail | forest | 1,737 |
| 2 | mountain_peak | mountain | 1,347 |
| 3 | coastal_cove | coastal | 2,228 |
| 4 | desert_dunes | desert | 2,351 |
| 5 | ancient_ruins | mountain | 1,642 |
| 6 | river_crossing | forest | 1,872 |
| 7 | cliff_edge | coastal | 1,368 |

---

### 2.3 Algorithms

#### Algorithm 1 — Dijkstra's Shortest Path (Custom Min-Heap)

Dijkstra's algorithm computes the shortest path from one source node to all other nodes in a weighted graph with non-negative edge weights.

**Pseudocode:**
```
DIJKSTRA(graph, source):
    dist[v] ← ∞  for all v
    prev[v] ← -1 for all v
    dist[source] ← 0
    heap ← MinHeap()
    heap.push(0, source)

    while heap is not empty:
        (d, u) ← heap.pop()
        if d > dist[u]:          // lazy deletion: stale entry
            continue
        visited_count += 1

        for each neighbor v of u with edge weight w:
            if dist[u] + w < dist[v]:
                dist[v] ← dist[u] + w
                prev[v] ← u
                heap.push(dist[v], v)

    return dist[], prev[]

PATH_RECONSTRUCTION(prev, source, target):
    path ← []
    cur ← target
    while cur ≠ -1:
        path.prepend(cur)
        cur ← prev[cur]
    return path

ALL_PAIRS_DIJKSTRA(graph):
    cost_matrix ← n×n matrix of ∞
    for each source in 0..n-1:
        result ← DIJKSTRA(graph, source)
        cost_matrix[source] ← result.dist
    return cost_matrix
```

**Min-Heap implementation (from scratch, no `heapq`):**
```
MIN_HEAP stored as list-based binary tree:
    parent(i)       = (i - 1) // 2
    left_child(i)   = 2*i + 1
    right_child(i)  = 2*i + 2

push(priority, value):
    append (priority, value) to end
    sift_up from last index

pop():
    swap root with last element
    remove last
    sift_down from root
    return swapped-out item

sift_up(idx):
    while idx > 0 and data[parent] > data[idx]:
        swap data[parent] and data[idx]
        idx ← parent

sift_down(idx):
    while True:
        smallest ← idx
        if left < n and data[left] < data[smallest]: smallest ← left
        if right < n and data[right] < data[smallest]: smallest ← right
        if smallest == idx: break
        swap data[idx] and data[smallest]
        idx ← smallest
```

**Time complexity:** O((V + E) log V) per source  
**All-pairs complexity:** O(V · (V + E) log V)  
**Space complexity:** O(V + E)

---

#### Algorithm 2 — Greedy Nearest-Neighbor Heuristic

After Dijkstra produces the all-pairs cost matrix, the greedy heuristic selects the shooting order.

**Pseudocode:**
```
GREEDY_NEAREST_NEIGHBOR(cost_matrix, start, scenes):
    visited ← {start}
    order   ← [start]
    total   ← 0
    current ← start

    while unvisited scenes remain:
        best_cost ← ∞
        best_node ← -1

        for each candidate in (scenes − visited):
            if cost_matrix[current][candidate] < best_cost:
                best_cost ← cost_matrix[current][candidate]
                best_node ← candidate

        order.append(best_node)
        total += best_cost
        visited.add(best_node)
        current ← best_node

    return order, total
```

**Time complexity:** O(k²) where k = number of scenes  
**Space complexity:** O(k)

---

### 2.4 Testing

**Unit tests (toy graphs):**
- Hand-traced Dijkstra on 4-node graph; verified shortest paths match manual BFS traversal
- Confirmed path reconstruction (`prev[]` backtracking) against known correct paths
- Verified adjacency matrix symmetry and connectivity check

**Integration tests:**
- Ran Dijkstra on connected graphs of n = 10 to 1,000; confirmed `visited_count = n` for fully connected graphs
- Verified greedy never revisits a node and exhausts all scene nodes

**Scalability tests:**
- Sparse graphs (edge_prob = 0.05) from n = 10 to 10,000
- Verified guaranteed connectivity (spanning-tree construction before random edge addition)

---

### 2.5 Results

#### Dijkstra All-Pairs Cost Matrix — 8-Scene Benchmark

```
     Node   0      1      2      3      4      5      6      7
        0   0.00  14.55  52.89  28.61  12.68  42.51  22.01  24.27
        1  14.55   0.00  38.34  14.06  27.23  27.96   7.46   9.72
        2  52.89  38.34   0.00  35.17  48.01  10.38  30.88  36.54
        3  28.61  14.06  35.17   0.00  41.29  24.79  21.52  23.73
        4  12.68  27.23  48.01  41.29   0.00  37.63  34.69  36.95
        5  42.51  27.96  10.38  24.79  37.63   0.00  20.50  37.68
        6  22.01   7.46  30.88  21.52  34.69  20.50   0.00  17.18
        7  24.27   9.72  36.54  23.73  36.95  37.68  17.18   0.00
```

#### Greedy Schedule — 8-Scene Benchmark

```
  Step 0: downtown_plaza    [START — basecamp]
  Step 1: desert_dunes      +12.68  (nearest from downtown)
  Step 2: forest_trail      +27.23
  Step 3: river_crossing    +7.46   (nearest forest neighbor)
  Step 4: cliff_edge        +17.18
  Step 5: coastal_cove      +23.73
  Step 6: ancient_ruins     +24.79
  Step 7: mountain_peak     +10.38
  ─────────────────────────────────
  TOTAL COST: 123.45
```

#### Dijkstra Single-Source Statistics (n=8)

| Metric | Value |
|---|---|
| Nodes visited | 8 |
| Heap operations | 24 |
| Wall-clock time | 0.009 ms |
| Path 0 → 7 | [0, 1, 7], cost = 24.27 |

#### Runtime Benchmark

| Algorithm | n=10 | n=50 | n=100 | n=500 | n=1,000 |
|---|---|---|---|---|---|
| Dijkstra (all-pairs) | 0.08 ms | 3.52 ms | 23.93 ms | 2,612.72 ms | 19,688.15 ms |
| Greedy NN | 0.02 ms | 0.03 ms | 0.10 ms | 2.56 ms | 14.48 ms |

#### Optimality Gap Analysis

| Benchmark | Greedy Cost | Dijkstra Lower Bound | Gap |
|---|---|---|---|
| 6 scenes | 332.81 | 211.11 | **57.65%** |
| 8 scenes | 123.45 | 75.10 | **64.38%** |
| 10 scenes | 250.74 | 157.27 | **59.43%** |
| 12 scenes | 179.47 | 104.65 | **71.50%** |

> **Note:** The Dijkstra lower bound is a *relaxed* bound (sum of cheapest per-node outgoing edges). The true TSP optimum lies between the lower bound and the greedy cost — this is where Song's exact DP solver closes the gap.

#### Generated Plots

All plots saved to `liu/plots/`:

| Plot | File | Description |
|---|---|---|
| Runtime curves | `runtime_curves.png` | Log-log: Dijkstra vs Greedy vs n |
| Memory usage | `memory_usage.png` | Peak KB per algorithm per n |
| Optimality gap | `optimality_gap.png` | % above lower bound, 6–12 scenes |
| Heatmaps (×5) | `*_heatmap.png` | Adjacency matrix weight visualization |

---

## 3. Conclusion

### Answer to Research Question

The greedy nearest-neighbor heuristic produces a valid filming schedule (total cost = 123.45 for 8 scenes starting from the urban basecamp). However, with a 57–71% gap above the Dijkstra-derived lower bound, greedy scheduling consistently leaves substantial cost on the table. The exact DP solver (Song's layer) is needed to close this gap and determine the globally optimal shooting order.

The Dijkstra-computed all-pairs cost matrix is the critical bridge: it translates raw geographic graph structure into a pairwise transition cost table that the DP state machine consumes directly.

### Weaknesses and Limitations

1. **Synthetic data only.** Edge weights are generated from a formula rather than real GPS/elevation data. Real terrain features (road closures, one-way roads, seasonal conditions) would require integration with a real map API.

2. **Greedy is not optimal.** The nearest-neighbor heuristic ignores future consequences — choosing the nearest scene now can strand the crew far from the remaining cluster. The gap of 57–71% confirms this is a significant issue.

3. **Undirected graph assumption.** Real transit costs are often asymmetric (uphill vs. downhill, one-way roads). Extending to directed graphs would increase realism.

4. **Memory scaling.** All-pairs Dijkstra stores an n×n cost matrix: at n=10,000, this is ~781 MB, making it impractical for large location sets.

5. **Single crew unit.** The model handles one crew. Multi-unit productions (simultaneous second units) require a parallel scheduling formulation.

### Future Research Avenues

- **Integrate real map data** (OpenStreetMap elevation API, road network data) to replace synthetic weights
- **Apply A\* search** with a geographic heuristic for single-source pathfinding on large real-world graphs — more practical than full Dijkstra at scale
- **Extend DP solver** to handle multi-unit crews (partition scenes across units, minimize makespan)
- **Simulated annealing or genetic algorithms** as alternative heuristics for larger scene counts where DP becomes intractable
- **2-opt local search** post-greedy to reduce the optimality gap without full DP enumeration
