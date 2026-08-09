"""
road_network.py — Put filming locations on the globe, and wire them into a road network.

The geographic layer models a location by terrain type and elevation but not by
position: its generators draw edge lengths at random, so two "nearby" locations
are nearby only by accident.  That is fine for testing shortest paths, but it
leaves the map with no regions for a region-by-region scheduler to find.

This module supplies the missing piece — coordinates — and turns a set of
located filming sites into the graph both layers run on.  Actual location data
lives in `film_data.py`.

Nothing in the geographic layer is modified.  `GeoNode` subclasses its `Node` to
carry coordinates, edge weights come from its `Edge.from_nodes`, and the
finished adjacency matrix is handed to its `SpatialGraph.load_from_matrix`, so
its Dijkstra runs on these maps unchanged.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from math import asin, cos, radians, sin, sqrt
from typing import Dict, List

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "liu"))

from graph import Edge, Node, SpatialGraph, TerrainType   # geographic layer

EARTH_RADIUS_KM = 6371.0


@dataclass(repr=False)
class GeoNode(Node):
    """
    A filming location that knows where on Earth it is.

    Extends the geographic layer's `Node` with coordinates and the place it
    belongs to.  All inherited behaviour (terrain multipliers, the basecamp
    flag) is untouched, so every function written against `Node` accepts this.

    `city` names the district, town or city the location sits in.  The
    schedulers never read it — it is ground truth, used only to score what the
    grouping step discovered on its own.
    """
    lat: float = 0.0
    lon: float = 0.0
    city: str = ""

    def __repr__(self) -> str:
        flag = " [basecamp]" if self.is_basecamp else ""
        return (f"GeoNode({self.id}, '{self.name}', {self.city}, "
                f"{self.terrain_type.value}, {self.elevation_m:.0f}m, "
                f"{self.lat:.3f}/{self.lon:.3f}{flag})")


def haversine_km(a: GeoNode, b: GeoNode) -> float:
    """Great-circle distance between two locations, in kilometres."""
    lat1, lon1, lat2, lon2 = map(radians, (a.lat, a.lon, b.lat, b.lon))
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * asin(sqrt(h))


def assemble_road_network(nodes: List[GeoNode],
                          inter_hub_links: int = 3) -> SpatialGraph:
    """
    Wire a set of located nodes into the road network the schedulers run on.

    Two kinds of road, matching how a crew actually moves:

      * inside a place — every location connects to every other one, because a
        van can drive straight between any two sites in the same town;
      * between places — only the places' first-listed locations connect, and
        only to the nearest few.  You fly or drive into a place, then work
        locally, so the long-haul network is sparse and getting from one place
        to a distant one is a real routing problem rather than a straight line.

    A pure nearest-neighbour long-haul network strands whole clusters — four
    western US cities, say, are each other's nearest neighbours and close into a
    group with no link east.  So a minimum spanning tree over the hubs goes down
    first (Prim's, on great-circle distance) to guarantee everything is
    reachable, and the nearest-neighbour routes are added on top for realistic
    redundancy.

    Edge weights come from the geographic layer's own formula, so terrain and
    elevation are priced exactly as that layer defines them.

    Args:
        nodes          : Located nodes, already carrying their `city` grouping.
                         Their `id` fields must match their index.
        inter_hub_links: How many nearest places each place connects to.

    Returns:
        A SpatialGraph in the geographic layer's format.

    Raises:
        ValueError: If the resulting network is disconnected.
    """
    n = len(nodes)
    adj: List[List[float]] = [[0.0] * n for _ in range(n)]

    def link(i: int, j: int) -> None:
        km = haversine_km(nodes[i], nodes[j])
        edge = Edge.from_nodes(nodes[i], nodes[j], km)
        adj[i][j] = adj[j][i] = round(edge.weight, 2)

    groups: Dict[str, List[int]] = {}
    for nd in nodes:
        groups.setdefault(nd.city, []).append(nd.id)

    # Local roads.
    for members in groups.values():
        for a in range(len(members)):
            for b in range(a + 1, len(members)):
                link(members[a], members[b])

    # Long haul: spanning tree first for reachability, then nearest neighbours.
    hubs = [members[0] for members in groups.values()]
    if len(hubs) > 1:
        inside, outside = {hubs[0]}, set(hubs[1:])
        while outside:
            _, i, j = min((haversine_km(nodes[i], nodes[j]), i, j)
                          for i in inside for j in outside)
            link(i, j)
            inside.add(j)
            outside.discard(j)

        for hub in hubs:
            others = sorted((haversine_km(nodes[hub], nodes[o]), o)
                            for o in hubs if o != hub)
            for _, other in others[:inter_hub_links]:
                if adj[hub][other] == 0.0:
                    link(hub, other)

    graph = SpatialGraph.load_from_matrix(adj, nodes)
    if not graph.is_connected():
        raise ValueError("Road network is disconnected; raise inter_hub_links.")
    return graph


# ---------------------------------------------------------------------------
# Self-test — a three-location toy, small enough to check by hand
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from dijkstra import all_pairs_shortest_paths

    nodes = [
        GeoNode(0, "downtown_la", TerrainType.URBAN, 89, True,
                lat=34.052, lon=-118.244, city="Los Angeles"),
        GeoNode(1, "griffith_observatory", TerrainType.MOUNTAIN, 351,
                lat=34.118, lon=-118.300, city="Los Angeles"),
        GeoNode(2, "midtown_manhattan", TerrainType.URBAN, 10,
                lat=40.755, lon=-73.985, city="New York"),
    ]
    graph = assemble_road_network(nodes)

    print("=" * 66)
    print("  road_network self-test")
    print("=" * 66)
    for nd in nodes:
        print(f"  {nd}")

    d = haversine_km(nodes[0], nodes[1])
    print(f"\n  downtown_la -> griffith_observatory: {d:.1f} km "
          f"(true straight-line is about 9 km)")
    print(f"  weighted by terrain and elevation:   {graph.weight(0, 1):.1f}")
    print(f"  the mountain multiplier and 262 m of climb make the short hop "
          f"cost {graph.weight(0, 1) / d:.2f}x its distance")

    print(f"\n  connected = {graph.is_connected()}")
    print("  all-pairs cost matrix:")
    for i, row in enumerate(all_pairs_shortest_paths(graph)):
        print(f"    {nodes[i].name:<22s} "
              + "  ".join(f"{v:9,.1f}" for v in row))
