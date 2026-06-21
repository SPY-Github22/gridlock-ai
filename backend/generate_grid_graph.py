"""
generate_grid_graph.py
----------------------
Generates a dense synthetic street-grid graph covering all of Bangalore.
Uses ONLY numpy, scipy, rustworkx — no osmnx or internet required.

Grid: 30x30 = 900 nodes covering lat[12.85,13.05], lon[77.50,77.70]
Each node is connected to its 4 cardinal neighbours (N, S, E, W).
Resulting graph: ~900 nodes, ~3400 edges — enough for realistic BFS routing.

Run from the backend/ directory:
    python generate_grid_graph.py
"""

import pickle
import math
import numpy as np
from scipy.spatial import KDTree
import rustworkx as rx

# ---------------------------------------------------------------------------
# Grid parameters — tweak STEPS to increase/decrease density
# ---------------------------------------------------------------------------
LAT_MIN, LAT_MAX = 12.85, 13.05   # North-South span of Bangalore
LON_MIN, LON_MAX = 77.50, 77.70   # East-West span

STEPS = 35          # 35x35 = 1225 nodes
LATS = np.linspace(LAT_MIN, LAT_MAX, STEPS)
LONS = np.linspace(LON_MIN, LON_MAX, STEPS)


def haversine_m(lat1, lon1, lat2, lon2):
    """Returns distance in metres between two lat/lon points."""
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


def classify_highway(i, j):
    """Give major roads a realistic highway type based on position in the grid."""
    # Every 7th row/column acts like a primary arterial road
    if i % 7 == 0 or j % 7 == 0:
        return "primary"
    if i % 4 == 0 or j % 4 == 0:
        return "secondary"
    if i % 2 == 0 or j % 2 == 0:
        return "tertiary"
    return "residential"


def main():
    G = rx.PyDiGraph()
    coords = []   # (lat, lon) per node index — for KDTree
    node_map = {} # (i, j) -> rustworkx node index

    print(f"Creating {STEPS}x{STEPS} = {STEPS*STEPS} node grid over Bangalore…")

    # ── Add all nodes ────────────────────────────────────────────────────────
    for i, lat in enumerate(LATS):
        for j, lon in enumerate(LONS):
            idx = G.add_node({"lat": float(lat), "lon": float(lon)})
            node_map[(i, j)] = idx
            coords.append([float(lat), float(lon)])

    # ── Add edges: each node connects to its 4 cardinal neighbours ───────────
    edge_count = 0
    for i in range(STEPS):
        for j in range(STEPS):
            src = node_map[(i, j)]
            lat1, lon1 = LATS[i], LONS[j]
            highway = classify_highway(i, j)

            neighbours = []
            if i + 1 < STEPS: neighbours.append((i+1, j))  # South
            if i - 1 >= 0:    neighbours.append((i-1, j))  # North
            if j + 1 < STEPS: neighbours.append((i, j+1))  # East
            if j - 1 >= 0:    neighbours.append((i, j-1))  # West

            for ni, nj in neighbours:
                dst = node_map[(ni, nj)]
                lat2, lon2 = LATS[ni], LONS[nj]
                dist = haversine_m(lat1, lon1, lat2, lon2)

                # Encode a straight polyline for this edge (two endpoints)
                import polyline as pl
                encoded = pl.encode([(lat1, lon1), (lat2, lon2)])

                G.add_edge(src, dst, {
                    "weight": dist,
                    "highway": highway,
                    "length": dist,
                    "polyline": encoded
                })
                edge_count += 1

    print(f"Added {edge_count} directed edges.")

    # ── Build KDTree ─────────────────────────────────────────────────────────
    kdtree = KDTree(np.array(coords))
    print(f"KDTree built with {len(coords)} nodes.")

    # node_indices: maps a unique node identifier (int index) → rustworkx index
    # Here they are identical since we added nodes sequentially.
    node_indices = {idx: idx for idx in G.node_indices()}

    # ── Save ─────────────────────────────────────────────────────────────────
    output = {
        "graph": G,
        "kdtree": kdtree,
        "node_indices": node_indices
    }
    with open("routing_graph.pkl", "wb") as f:
        pickle.dump(output, f)

    print("routing_graph.pkl saved successfully!")
    print(f"  Nodes : {G.num_nodes()}")
    print(f"  Edges : {G.num_edges()}")
    print(f"  Bounds: lat [{LAT_MIN}, {LAT_MAX}], lon [{LON_MIN}, {LON_MAX}]")


if __name__ == "__main__":
    main()
