"""
data_gen.py — Synthetic graph generators for film location scheduling benchmarks.

Provides:
  - generate_toy_graph      : Small dense graph for hand-verification.
  - generate_sparse_graph   : Large sparse connected graph (guaranteed connected).
  - generate_grid_graph     : 2-D grid graph (4-connected) with varied weights.
  - create_film_benchmark   : Realistic film-location graph with named scenes.
  - save_matrix / load_matrix: Plain-text adjacency matrix I/O (.txt).
"""

from __future__ import annotations
import random
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from typing import List, Optional

from graph import Node, SpatialGraph, TerrainType, TERRAIN_MULTIPLIER, Edge

# ---------------------------------------------------------------------------
# Location name pools for realistic benchmarks
# ---------------------------------------------------------------------------

_LOCATION_NAMES = [
    "downtown_plaza", "forest_trail", "mountain_peak", "coastal_cove",
    "desert_dunes", "ancient_ruins", "river_crossing", "cliff_edge",
    "valley_floor", "urban_rooftop", "lighthouse_point", "cave_entrance",
    "bamboo_grove", "snowy_pass", "industrial_port", "vineyard_terrace",
    "lakeside_dock", "canyon_overlook", "old_mill", "waterfall_base",
    "hilltop_castle", "market_square", "harbour_bridge", "jungle_clearing",
    "salt_flats", "ghost_town", "frozen_lake", "volcano_rim",
    "redwood_grove", "tidal_pools",
]

_TERRAIN_SEQUENCE = [
    TerrainType.URBAN,
    TerrainType.FOREST,
    TerrainType.MOUNTAIN,
    TerrainType.COASTAL,
    TerrainType.DESERT,
    TerrainType.MOUNTAIN,
    TerrainType.FOREST,
    TerrainType.COASTAL,
    TerrainType.URBAN,
    TerrainType.DESERT,
]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _make_node(idx: int, name: str, terrain: TerrainType,
               elevation: float, is_basecamp: bool = False) -> Node:
    """Create a Node with the given attributes."""
    return Node(id=idx, name=name, terrain_type=terrain,
                elevation_m=elevation, is_basecamp=is_basecamp)


def _ensure_connected(n: int, rng: random.Random,
                      adj: List[List[float]],
                      nodes: List[Node],
                      weight_lo: float,
                      weight_hi: float) -> None:
    """
    Add a random spanning tree to *adj* (in-place) to guarantee connectivity.

    Uses a random Prüfer-sequence-like construction: shuffle node indices and
    connect each node (in shuffled order) to a random already-connected node.
    Weights are drawn uniformly from [weight_lo, weight_hi].
    """
    order = list(range(n))
    rng.shuffle(order)
    connected = {order[0]}
    for idx in order[1:]:
        u = rng.choice(list(connected))
        v = idx
        if adj[u][v] == 0.0:
            w = round(rng.uniform(weight_lo, weight_hi), 2)
            # Use node terrain for weight formula
            src_node = nodes[u]
            dst_node = nodes[v]
            elev_change = abs(src_node.elevation_m - dst_node.elevation_m)
            terrain_diff = (src_node.terrain_multiplier() +
                            dst_node.terrain_multiplier()) / 2.0
            raw_w = Edge.compute_weight(w, elev_change, terrain_diff)
            raw_w = max(round(raw_w, 2), weight_lo)
            adj[u][v] = raw_w
            adj[v][u] = raw_w
        connected.add(idx)


# ---------------------------------------------------------------------------
# Public generators
# ---------------------------------------------------------------------------

def generate_toy_graph(n: int = 6, seed: int = 42) -> SpatialGraph:
    """
    Generate a small dense graph suitable for hand-verification.

    Edge density is approximately 60 % (each pair is connected with p=0.6).
    Weights are integers in [1, 20].  The first node is always the basecamp.

    Args:
        n   : Number of nodes (default 6).
        seed: Random seed for reproducibility.

    Returns:
        A connected SpatialGraph with n nodes.
    """
    rng = random.Random(seed)
    terrains = [_TERRAIN_SEQUENCE[i % len(_TERRAIN_SEQUENCE)] for i in range(n)]
    names = (_LOCATION_NAMES[:n] if n <= len(_LOCATION_NAMES)
             else [f"loc_{i}" for i in range(n)])

    nodes = [
        _make_node(i, names[i], terrains[i],
                   elevation=rng.uniform(0, 2000),
                   is_basecamp=(i == 0))
        for i in range(n)
    ]
    adj: List[List[float]] = [[0.0] * n for _ in range(n)]

    # Random edges with ~60 % density
    for i in range(n):
        for j in range(i + 1, n):
            if rng.random() < 0.60:
                dist = rng.uniform(1, 20)
                edge = Edge.from_nodes(nodes[i], nodes[j], dist)
                adj[i][j] = round(edge.weight, 2)
                adj[j][i] = adj[i][j]

    # Guarantee connectivity
    _ensure_connected(n, rng, adj, nodes, 1, 20)

    return SpatialGraph.load_from_matrix(adj, nodes)


def generate_sparse_graph(n: int = 100, edge_prob: float = 0.05,
                           seed: int = 0) -> SpatialGraph:
    """
    Generate a large sparse connected graph.

    A random spanning tree is inserted first to ensure connectivity, then
    additional edges are added with probability *edge_prob*.

    Args:
        n        : Number of nodes.
        edge_prob: Probability of each non-tree edge being added (default 0.05).
        seed     : Random seed.

    Returns:
        A connected SpatialGraph with n nodes.
    """
    rng = random.Random(seed)
    terrains = [_TERRAIN_SEQUENCE[i % len(_TERRAIN_SEQUENCE)] for i in range(n)]
    names = ([_LOCATION_NAMES[i % len(_LOCATION_NAMES)] + (f"_{i // len(_LOCATION_NAMES)}"
              if i >= len(_LOCATION_NAMES) else "")
              for i in range(n)])

    nodes = [
        _make_node(i, names[i], terrains[i],
                   elevation=rng.uniform(0, 3000),
                   is_basecamp=(i == 0))
        for i in range(n)
    ]
    adj: List[List[float]] = [[0.0] * n for _ in range(n)]

    # Spanning tree first
    _ensure_connected(n, rng, adj, nodes, 1, 50)

    # Extra random edges
    for i in range(n):
        for j in range(i + 1, n):
            if adj[i][j] == 0.0 and rng.random() < edge_prob:
                dist = rng.uniform(1, 50)
                edge = Edge.from_nodes(nodes[i], nodes[j], dist)
                adj[i][j] = round(edge.weight, 2)
                adj[j][i] = adj[i][j]

    return SpatialGraph.load_from_matrix(adj, nodes)


def generate_grid_graph(rows: int = 5, cols: int = 5) -> SpatialGraph:
    """
    Generate a 2-D grid graph with 4-connectivity (up, down, left, right).

    Each cell becomes a node; edges connect horizontally and vertically adjacent
    cells with varied weights influenced by terrain and elevation.

    Args:
        rows: Number of grid rows.
        cols: Number of grid columns.

    Returns:
        A SpatialGraph with rows*cols nodes.
    """
    rng = random.Random(rows * cols)
    n = rows * cols
    terrains = [_TERRAIN_SEQUENCE[(r + c) % len(_TERRAIN_SEQUENCE)]
                for r in range(rows) for c in range(cols)]

    nodes = [
        _make_node(r * cols + c,
                   f"grid_{r}_{c}",
                   terrains[r * cols + c],
                   elevation=rng.uniform(0, 2500),
                   is_basecamp=(r == 0 and c == 0))
        for r in range(rows) for c in range(cols)
    ]
    adj: List[List[float]] = [[0.0] * n for _ in range(n)]

    def _idx(r: int, c: int) -> int:
        return r * cols + c

    def _add_edge(u: int, v: int) -> None:
        dist = rng.uniform(5, 30)
        edge = Edge.from_nodes(nodes[u], nodes[v], dist)
        w = round(edge.weight, 2)
        adj[u][v] = w
        adj[v][u] = w

    for r in range(rows):
        for c in range(cols):
            u = _idx(r, c)
            if c + 1 < cols:
                _add_edge(u, _idx(r, c + 1))
            if r + 1 < rows:
                _add_edge(u, _idx(r + 1, c))

    return SpatialGraph.load_from_matrix(adj, nodes)


def create_film_benchmark(n_scenes: int = 8) -> SpatialGraph:
    """
    Create a realistic film-location graph with named scenes and metadata.

    The graph is sparse (~15 % edge density) and guaranteed to be connected.
    Weights reflect terrain types and elevation differences to simulate real
    production logistics.

    Args:
        n_scenes: Number of filming scenes / locations (default 8).

    Returns:
        A connected SpatialGraph with named nodes and realistic weights.
    """
    rng = random.Random(n_scenes * 17 + 3)
    names = _LOCATION_NAMES[:n_scenes]
    terrains = [_TERRAIN_SEQUENCE[i % len(_TERRAIN_SEQUENCE)]
                for i in range(n_scenes)]
    elevations = [rng.uniform(0, 2500) for _ in range(n_scenes)]

    nodes = [
        _make_node(i, names[i], terrains[i], elevations[i],
                   is_basecamp=(i == 0))
        for i in range(n_scenes)
    ]
    adj: List[List[float]] = [[0.0] * n_scenes for _ in range(n_scenes)]

    # Sparse random edges (~15 % density)
    for i in range(n_scenes):
        for j in range(i + 1, n_scenes):
            if rng.random() < 0.15:
                dist = rng.uniform(2, 30)
                edge = Edge.from_nodes(nodes[i], nodes[j], dist)
                adj[i][j] = round(edge.weight, 2)
                adj[j][i] = adj[i][j]

    # Guarantee connectivity via spanning tree
    _ensure_connected(n_scenes, rng, adj, nodes, 2, 30)

    return SpatialGraph.load_from_matrix(adj, nodes)


# ---------------------------------------------------------------------------
# Matrix I/O
# ---------------------------------------------------------------------------

def save_matrix(matrix: List[List[float]], filepath: str) -> None:
    """
    Save an adjacency matrix to a plain-text file.

    Format: space-separated floats, one row per line.
    Integer-valued weights are written without a decimal point for readability.

    Args:
        matrix  : 2-D list of floats (square).
        filepath: Destination file path (created or overwritten).
    """
    os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
    lines = []
    for row in matrix:
        tokens = []
        for v in row:
            if v == int(v):
                tokens.append(str(int(v)))
            else:
                tokens.append(f"{v:.4f}")
        lines.append(" ".join(tokens))

    with open(filepath, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def load_matrix(filepath: str) -> List[List[float]]:
    """
    Load an adjacency matrix from a plain-text file.

    Each line is a space-separated row of numbers.  Empty lines are ignored.

    Args:
        filepath: Path to the .txt matrix file.

    Returns:
        2-D list of floats.

    Raises:
        ValueError: If rows have inconsistent lengths.
        FileNotFoundError: If *filepath* does not exist.
    """
    matrix: List[List[float]] = []
    with open(filepath, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            matrix.append([float(x) for x in line.split()])

    n = len(matrix)
    for i, row in enumerate(matrix):
        if len(row) != n:
            raise ValueError(
                f"Row {i} has {len(row)} columns, expected {n} (square matrix).")
    return matrix


# ---------------------------------------------------------------------------
# Self-test / matrix file generation
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import os

    test_dir = os.path.join(os.path.dirname(__file__), "test_data")

    print("=== data_gen self-test ===\n")

    # Toy graphs
    g4 = generate_toy_graph(4, seed=1)
    print(g4.summary())

    g6 = generate_toy_graph(6, seed=2)
    print(g6.summary())

    # Sparse graph
    gs = generate_sparse_graph(20, edge_prob=0.08, seed=99)
    print(f"\nSparse graph: {gs}")

    # Grid graph
    gg = generate_grid_graph(3, 3)
    print(f"Grid graph  : {gg}")

    # Film benchmark
    fb8 = create_film_benchmark(8)
    print(f"Film bench 8: {fb8}")
    fb12 = create_film_benchmark(12)
    print(f"Film bench12: {fb12}")

    # Save / reload round-trip
    tmp = "/tmp/test_roundtrip.txt"
    save_matrix(fb8.to_matrix(), tmp)
    loaded = load_matrix(tmp)
    assert len(loaded) == 8, "Round-trip size mismatch"
    print("\nMatrix round-trip: OK")
