# CS5800 — Presentation Script (Liu's Section)
## Target: 7 minutes total | Approximate pacing noted per section

---

### [SLIDE 1 — Title] (~30 seconds)

"Good [morning/afternoon]. My name is Liu, and today I'll be walking you through my contribution to our dual-layer film production optimization project. My layer covers the geographic side of the problem — how do you model a film crew moving across real physical terrain, and how do you compute the best sequence of shooting locations to minimize total travel cost?"

---

### [SLIDE 2 — Introduction & Research Question] (~60 seconds)

"When a film production moves between locations — say, from a downtown plaza to a mountain peak — that move isn't free. You're hauling cameras, lighting rigs, and a full crew. Standard navigation apps give you driving distance, but they don't account for terrain difficulty, elevation gain, or how much harder it is to push equipment up a mountain road versus an urban street.

My research question is this: **given a set of film locations connected by terrain-weighted transit routes, what shooting order minimizes total geographic transition cost?**

To answer this, I modeled each location as a node in a weighted graph, where edge weights encode distance, elevation change, and terrain type. The goal is then to find an ordering of scenes — a path through that graph — that keeps total cost as low as possible."

---

### [SLIDE 3 — Graph Schema & Weight Formula] (~75 seconds)

"Here is how I structured the graph. Every filming location is a **node** with four attributes: its name, terrain type, elevation in meters, and a flag marking whether it is the production basecamp.

I defined five terrain types, each with a multiplier reflecting real crew transport difficulty:
- Urban roads: 1.0 — easiest
- Coastal: 1.2
- Forest trails: 1.4
- Desert: 1.6
- Mountain: 2.0 — hardest

The edge weight between two locations uses this formula:

    w = distance × (1 + 0.3 × elevation_factor) × terrain_multiplier

The elevation factor is the normalized elevation difference between the two endpoints. The terrain multiplier is the average of both endpoints' multipliers.

So for example, moving from the downtown plaza — urban, 4 meters elevation — to a mountain peak at 1,347 meters: the elevation factor raises the base cost by about 13%, and the mountain multiplier nearly doubles it again. That's a very expensive move.

All edges are stored in an **adjacency matrix**: 0 means no direct route, any positive number is the edge weight. This matrix format was agreed with my partner Song as the interface to his DP solver."

---

### [SLIDE 4 — Algorithms: Dijkstra & Greedy] (~90 seconds)

"I implemented two algorithms from scratch — no external graph libraries.

**Algorithm 1: Dijkstra's shortest path with a custom min-heap.**

I built the min-heap as a list-based binary tree with sift-up and sift-down from scratch. Decrease-key is handled via lazy deletion — when I find a shorter path, I push the new entry and skip the stale one when it's popped. This avoids the complexity of a Fibonacci heap while still achieving O((V + E) log V) per source.

Running Dijkstra from every source gives me an **all-pairs cost matrix** — a table where entry [i][j] is the true shortest-path cost to move from location i to location j, passing through any intermediate nodes. This matrix is what Song's DP solver uses as its transition cost function.

**Algorithm 2: Greedy Nearest-Neighbor heuristic.**

Once I have the all-pairs cost matrix, the greedy solver takes over for schedule ordering. Starting at the basecamp, at each step it simply picks the closest unvisited scene. It's O(k²) where k is the number of scenes — extremely fast.

The key design decision: the greedy solver takes the **Dijkstra cost matrix as input**, not the raw graph. This cleanly separates 'how do we get there' from 'in what order do we go.' Song's DP solver uses the same input format, so both solvers are directly comparable."

---

### [SLIDE 5 — Test Data & Hand Trace] (~60 seconds)

"I tested on three levels of data.

First, **toy graphs** with 4 and 6 nodes — small enough to trace by hand. Let me walk through the 4-node case. The adjacency matrix has four locations: downtown, forest trail, mountain peak, coastal cove. After running Dijkstra, the all-pairs cost matrix reveals that the shortest path from downtown to mountain peak costs 8 — not directly (there's no direct edge), but via the forest trail: 5 + 3 = 8.

The greedy schedule from downtown visits: forest trail (cost 5), then mountain peak (cost 3), then coastal cove (cost 7). Total = 15. This matches the hand-computed optimal for this small case.

Second, **an 8-scene film benchmark** with realistic location names, terrain types, and elevations — this is the primary validation dataset.

Third, **large synthetic graphs** from 100 to 10,000 nodes for scalability testing, generated with a guaranteed-connected spanning tree as the backbone."

---

### [SLIDE 6 — Results & Benchmark Output] (~75 seconds)

"Here are the key results.

For the 8-scene film benchmark, the greedy schedule visits scenes in this order: downtown → desert dunes → forest trail → river crossing → cliff edge → coastal cove → ancient ruins → mountain peak, with a **total cost of 123.45**.

The runtime benchmark confirms the complexity difference between the two algorithms. Dijkstra all-pairs at n=100 takes about 24 milliseconds. Greedy at n=1,000 takes only 14 milliseconds — because once the cost matrix is precomputed, the greedy selection loop is nearly instant.

For the **optimality gap analysis**, I computed a lower bound using the cheapest outgoing edge from each scene in the Dijkstra cost matrix. Across four benchmark sizes — 6, 8, 10, and 12 scenes — the greedy heuristic runs between 57% and 71% above this lower bound. That's a significant gap, which is exactly why an exact solver is needed.

The plots in `liu/plots/` show the runtime curves on a log-log scale, confirming the quadratic growth of Dijkstra all-pairs, and a heatmap of the 8-scene cost matrix, where you can visually see the high-cost mountain transitions."

---

### [SLIDE 7 — Conclusion & Future Work] (~30 seconds)

"To summarize: I modeled film locations as a terrain-weighted spatial graph, implemented Dijkstra's algorithm with a custom min-heap to compute all pairwise shortest-path costs, and implemented a greedy nearest-neighbor heuristic as the scheduling baseline.

The greedy heuristic is fast but leaves a 57–71% gap versus the lower bound. This motivates Song's exact DP solver, which takes my all-pairs cost matrix and computes the globally optimal shooting order.

Future improvements include integrating real GPS and OpenStreetMap elevation data, extending to asymmetric directed graphs, and applying A\* for large-scale instances where all-pairs Dijkstra becomes prohibitive.

Thank you."

---

## Timing Summary

| Section | Slide | Time |
|---|---|---|
| Title | 1 | ~0:30 |
| Introduction & Question | 2 | ~1:30 |
| Graph Schema & Formula | 3 | ~3:00 |
| Algorithms | 4 | ~4:30 |
| Test Data & Hand Trace | 5 | ~5:30 |
| Results | 6 | ~6:45 |
| Conclusion | 7 | ~7:00 |
