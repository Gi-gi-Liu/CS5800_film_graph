"""
film_data.py — Real filming locations from three real productions.

Three productions were chosen so the same scheduler can be tested at three
different geographic scales:

    scale                     production              locations   groups
    -----------------------   ---------------------   ---------   ----------------
    one city, many districts  La La Land (2016)             28    LA neighbourhoods
    one country, many cities  Forrest Gump (1994)           31    US states/towns
    many countries            Tenet (2020)                  34    countries/cities

The point of the ladder: nothing in the scheduler changes between them.  The
same MST grouping that finds neighbourhoods inside Los Angeles finds cities
across the United States and countries across the world — the algorithm never
knows which scale it is looking at, only what the cost matrix says.

The `group` field on each location records the district / town / city it truly
belongs to.  The scheduler never sees it; it exists only so the grouping step
can be scored against ground truth.

Provenance and its limits
-------------------------
Location lists are transcribed from published location guides (see SOURCES),
which are enthusiast reconstructions, not production paperwork.  Coordinates
are landmark-accurate for named landmarks (Griffith Observatory, the Gateway of
India) and street-accurate for entries given only as an address — an error of a
few hundred metres, immaterial next to the tens of kilometres between districts.

Real shooting order is not published for any of the three, so the schedules
here can be compared with each other but not against what the crews actually
did.

Terrain and elevation feed the geographic layer's weight formula unchanged.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "liu"))

from graph import SpatialGraph, TerrainType           # geographic layer

from road_network import GeoNode, assemble_road_network

U, F, M, C, D = (TerrainType.URBAN, TerrainType.FOREST, TerrainType.MOUNTAIN,
                 TerrainType.COASTAL, TerrainType.DESERT)

SOURCES = {
    "la_la_land": "movie-locations.com/movies/l/La-La-Land.php",
    "forrest_gump": "movie-locations.com/movies/f/Forrest-Gump.php",
    "tenet": "movie-locations.com/movies/t/Tenet-film-locations.php",
}


@dataclass
class Production:
    """One film's shooting locations, ready to be turned into a graph."""
    title: str
    scale: str
    source: str
    # (name, group, terrain, elevation_m, lat, lon) — first entry is the base.
    locations: List[Tuple[str, str, TerrainType, float, float, float]] = \
        field(default_factory=list)


PRODUCTIONS: Dict[str, Production] = {

    # -----------------------------------------------------------------------
    # One city, many districts.  Everything inside Los Angeles County except
    # the Big Bear Lake museum, two hours out — a deliberate outlier that any
    # sensible schedule has to handle.
    # -----------------------------------------------------------------------
    "la_la_land": Production(
        title="La La Land (2016)",
        scale="one city, many districts",
        source=SOURCES["la_la_land"],
        locations=[
            ("warner_bros_coffee_shop",  "Burbank",        U,  152, 34.1483, -118.3370),
            ("warner_bros_studio_tour",  "Burbank",        U,  152, 34.1478, -118.3378),
            ("smokehouse_restaurant",    "Burbank",        U,  152, 34.1497, -118.3400),
            ("van_beek_magnolia_blvd",   "Burbank",        U,  158, 34.1665, -118.3520),
            ("retro_dairy_mart",         "Burbank",        U,  158, 34.1663, -118.3525),

            ("liptons_wilcox_ave",       "Hollywood",      U,  105, 34.1010, -118.3330),
            ("you_are_the_star_mural",   "Hollywood",      U,  105, 34.1016, -118.3330),
            ("sebs_club_exterior",       "Hollywood",      U,   90, 34.0900, -118.3230),

            ("griffith_observatory",     "Griffith Park",  M,  351, 34.1184, -118.3004),
            ("cathys_corner",            "Griffith Park",  M,  425, 34.1290, -118.3060),
            ("fern_dell",                "Griffith Park",  F,  180, 34.1090, -118.3100),

            ("grand_central_market",     "Downtown LA",    U,   90, 34.0505, -118.2487),
            ("bradbury_building",        "Downtown LA",    U,   90, 34.0501, -118.2477),
            ("angels_flight_railway",    "Downtown LA",    U,   95, 34.0513, -118.2489),

            ("jar_restaurant",           "Midtown LA",     U,   70, 34.0760, -118.3690),
            ("el_rey_theatre",           "Midtown LA",     U,   60, 34.0624, -118.3510),
            ("fais_do_do",               "Midtown LA",     U,   50, 34.0320, -118.3480),

            ("hermosa_beach_pier",       "Hermosa Beach",  C,    2, 33.8622, -118.4029),
            ("lighthouse_cafe",          "Hermosa Beach",  C,    3, 33.8620, -118.4005),

            ("rose_towers_apartment",    "Long Beach",     U,    8, 33.7710, -118.1810),
            ("the_blind_donkey",         "Long Beach",     U,    8, 33.7690, -118.1890),

            ("rialto_theatre",           "Pasadena",       U,  179, 34.1055, -118.1500),
            ("colorado_street_bridge",   "Pasadena",       U,  210, 34.1444, -118.1650),

            ("freeway_overpass_105_110", "South LA",       U,   30, 33.9280, -118.2820),
            ("watts_towers",             "South LA",       U,   30, 33.9387, -118.2414),

            ("chateau_marmont",          "West Hollywood", U,  100, 34.0977, -118.3717),
            ("orcutt_ranch",             "Canoga Park",    F,  250, 34.2200, -118.6260),
            ("planetarium_museum",       "Big Bear Lake",  M, 2055, 34.2439, -116.9114),
        ],
    ),

    # -----------------------------------------------------------------------
    # One country, many towns.  Two tight clusters (the Beaufort area and
    # Savannah) plus points scattered from Maine to Montana.
    # -----------------------------------------------------------------------
    "forrest_gump": Production(
        title="Forrest Gump (1994)",
        scale="one country, many cities",
        source=SOURCES["forrest_gump"],
        locations=[
            ("chippewa_square",          "Savannah GA",    U,   12, 32.0777, -81.0930),
            ("savannah_history_museum",  "Savannah GA",    U,   12, 32.0770, -81.0990),

            ("uscb_performing_arts",     "Beaufort SC",    U,    5, 32.4316, -80.6698),
            ("woods_memorial_bridge",    "Beaufort SC",    C,    3, 32.4340, -80.6760),
            ("ladys_island_lucy_point",  "Beaufort SC",    C,    4, 32.4200, -80.6100),
            ("chowan_creek_bridge",      "Beaufort SC",    C,    3, 32.4050, -80.6400),
            ("port_royal",               "Beaufort SC",    C,    3, 32.3790, -80.6930),
            ("hunting_island_state_park","Beaufort SC",    C,    3, 32.3750, -80.4400),
            ("fripp_island",             "Beaufort SC",    C,    2, 32.3260, -80.4790),

            ("hampton_street_school",    "Walterboro SC",  U,   25, 32.9050, -80.6670),
            ("bluff_plantation",         "Yemassee SC",    F,    8, 32.7000, -80.8500),
            ("stoney_creek_chapel",      "McPhersonville SC", F, 10, 32.6800, -80.8300),
            ("varnville_route_68",       "Varnville SC",   U,   30, 32.8510, -81.0790),

            ("weingart_stadium",         "Los Angeles CA", U,   60, 34.0440, -118.1490),
            ("usc_marks_hall",           "Los Angeles CA", U,   50, 34.0220, -118.2860),
            ("usc_bovard_building",      "Los Angeles CA", U,   50, 34.0208, -118.2850),
            ("ebell_of_los_angeles",     "Los Angeles CA", U,   60, 34.0610, -118.3210),
            ("coles_pacific_electric",   "Los Angeles CA", U,   90, 34.0440, -118.2500),
            ("santa_monica_yacht_harbor","Los Angeles CA", C,    2, 34.0080, -118.4980),

            ("lincoln_memorial",         "Washington DC",  U,   10, 38.8893,  -77.0502),
            ("reflecting_pool",          "Washington DC",  U,   10, 38.8893,  -77.0430),
            ("jefferson_memorial",       "Washington DC",  U,    5, 38.8814,  -77.0365),
            ("watergate_hotel",          "Washington DC",  U,   10, 38.9000,  -77.0555),

            ("grandfather_mountain",     "Linville NC",    M, 1818, 36.1120,  -81.8090),

            ("downtown_flagstaff",       "Flagstaff AZ",   U, 2106, 35.1980, -111.6510),
            ("twin_arrows_trading_post", "Flagstaff AZ",   D, 1800, 35.2280, -111.2830),
            ("monument_valley",          "Monument Valley AZ", D, 1600, 36.9980, -110.0985),

            ("marshall_point_lighthouse","Port Clyde ME",  C,   10, 43.9180,  -69.2610),

            ("cut_bank",                 "Glacier MT",     U, 1173, 48.6330, -112.3260),
            ("glacier_st_mary_entrance", "Glacier MT",     M, 1370, 48.7470, -113.4370),
            ("going_to_the_sun_road",    "Glacier MT",     M, 2026, 48.6960, -113.7180),
        ],
    ),

    # -----------------------------------------------------------------------
    # Seven countries.  Tallinn alone holds eleven locations, so the shape is
    # one very heavy block plus long intercontinental hops.
    # -----------------------------------------------------------------------
    "tenet": Production(
        title="Tenet (2020)",
        scale="many countries",
        source=SOURCES["tenet"],
        locations=[
            ("linnahall",                "Tallinn EE",     U,    5, 59.4450,  24.7480),
            ("telliskivi_creative_city", "Tallinn EE",     U,   15, 59.4390,  24.7290),
            ("liivalaia_courthouse",     "Tallinn EE",     U,   15, 59.4300,  24.7580),
            ("kumu_art_museum",          "Tallinn EE",     U,   25, 59.4380,  24.7900),
            ("hilton_tallinn_park",      "Tallinn EE",     U,   20, 59.4310,  24.7700),
            ("parnu_maantee_argentiina", "Tallinn EE",     U,   20, 59.4230,  24.7480),
            ("laagna_tee",               "Tallinn EE",     U,   25, 59.4390,  24.8300),
            ("saarepiiga_bridge",        "Tallinn EE",     U,    5, 59.4520,  24.7600),
            ("port_paljassaare",         "Tallinn EE",     C,    3, 59.4640,  24.7220),
            ("suur_paala_ulemiste",      "Tallinn EE",     U,   35, 59.4230,  24.8330),
            ("maarjamae_memorial",       "Tallinn EE",     C,   25, 59.4570,  24.8100),

            ("nysted_wind_farm",         "Lolland DK",     C,    0, 54.5500,  11.7200),

            ("gateway_of_india",         "Mumbai IN",      C,    3, 18.9220,  72.8347),
            ("cafe_mondegar",            "Mumbai IN",      U,    8, 18.9220,  72.8320),
            ("royal_bombay_yacht_club",  "Mumbai IN",      U,    5, 18.9218,  72.8330),
            ("neelam_shree_vardhan",     "Mumbai IN",      U,   10, 18.9680,  72.8060),

            ("villa_cimbrone",           "Amalfi Coast IT", M,  350, 40.6480,  14.6110),
            ("hotel_caruso_ravello",     "Amalfi Coast IT", M,  365, 40.6500,  14.6120),
            ("amalfi_seafront",          "Amalfi Coast IT", C,    3, 40.6340,  14.6030),
            ("bella_baia_beach_maiori",  "Amalfi Coast IT", C,    2, 40.6480,  14.6420),

            ("oslo_opera_house",         "Oslo NO",        C,    3, 59.9075,  10.7530),
            ("tjuvholmen_alle",          "Oslo NO",        C,    3, 59.9080,  10.7210),
            ("the_thief_hotel",          "Oslo NO",        C,    3, 59.9075,  10.7215),

            ("reform_club_pall_mall",    "London UK",      U,   15, 51.5060,   -0.1360),
            ("national_liberal_club",    "London UK",      U,   10, 51.5060,   -0.1240),
            ("cannon_hall_hampstead",    "London UK",      U,  125, 51.5590,   -0.1780),
            ("locanda_locatelli",        "London UK",      U,   25, 51.5140,   -0.1590),
            ("berkeley_mews",            "London UK",      U,   25, 51.5120,   -0.1520),
            ("southampton_sailgp",       "Southampton UK", C,    5, 50.9000,   -1.4040),

            ("hawthorne_plaza_mall",     "Los Angeles US", U,   20, 33.9160, -118.3520),
            ("lax_terminal_connector",   "Los Angeles US", U,   38, 33.9420, -118.4080),
            ("warner_bros_stage_16",     "Los Angeles US", U,  152, 34.1483, -118.3370),
            ("victorville_logistics_airport", "Mojave US", D,  876, 34.5975, -117.3830),
            ("eagle_mountain",           "Mojave US",      D,  300, 33.8500, -115.4800),
        ],
    ),
}


def build_production(key: str, inter_hub_links: int = 3
                     ) -> Tuple[SpatialGraph, List[GeoNode], Production]:
    """
    Turn one production's location list into a graph the schedulers can run on.

    Locations sharing a `group` are wired to each other directly; groups reach
    each other only through their first-listed location, so cross-country moves
    have to be routed.  Weights come from the geographic layer's formula.

    Args:
        key            : One of the keys in PRODUCTIONS.
        inter_hub_links: How many nearest groups each group connects to.

    Returns:
        (graph, nodes, production) — the graph in the geographic layer's format,
        the located nodes (with coordinates and true group), and the metadata.

    Raises:
        KeyError  : If `key` is not a known production.
        ValueError: If the resulting road network is disconnected.
    """
    prod = PRODUCTIONS[key]
    nodes = [
        GeoNode(id=i, name=name, terrain_type=terrain, elevation_m=elev,
                is_basecamp=(i == 0), lat=lat, lon=lon, city=group)
        for i, (name, group, terrain, elev, lat, lon) in enumerate(prod.locations)
    ]
    return assemble_road_network(nodes, inter_hub_links), nodes, prod


def true_groups(nodes: List[GeoNode]) -> Dict[str, List[int]]:
    """Ground-truth grouping, for scoring what the MST step discovered."""
    groups: Dict[str, List[int]] = {}
    for nd in nodes:
        groups.setdefault(nd.city, []).append(nd.id)
    return groups


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from dijkstra import shortest_path

    for key in PRODUCTIONS:
        graph, nodes, prod = build_production(key)
        groups = true_groups(nodes)
        edges = sum(1 for i in range(graph.n) for j in range(i + 1, graph.n)
                    if graph.weight(i, j) > 0)
        print("=" * 72)
        print(f"  {prod.title} — {prod.scale}")
        print("=" * 72)
        print(f"  {graph.n} locations, {len(groups)} groups, {edges} roads, "
              f"connected = {graph.is_connected()}")
        for name, members in groups.items():
            print(f"    {name:<22s} {len(members):>2d}  "
                  f"{', '.join(nodes[i].name for i in members[:3])}"
                  f"{' ...' if len(members) > 3 else ''}")
        far = max(range(graph.n),
                  key=lambda v: shortest_path(graph, 0, v)[1])
        path, cost = shortest_path(graph, 0, far)
        print(f"  furthest from base: {nodes[far].name} (cost {cost:,.0f}) via")
        print(f"    {' -> '.join(nodes[v].city for v in path)}")
        print()
