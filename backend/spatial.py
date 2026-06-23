"""
spatial.py
----------
Everything related to the street graph:
- Loading the routing graph and KDTree from disk
- ML congestion weight model (GradientBoostingRegressor) for BFS edge weights
- BFS flood-fill to find affected + spillover roads around an event
- Dijkstra detour routing when barricades are placed
- Road coordinate extraction (polyline decoding)

The BFS uses a trained ML model to predict congestion weights per road edge
based on road type, distance from hazard, time of day, incident cause, and
vehicle type — replacing all hardcoded physics constants.
"""

import os
import math
import pickle
from typing import List, Optional, Set, Tuple, Dict, Any

import rustworkx as rx
from scipy.spatial import KDTree

# ---------------------------------------------------------------------------
# Graph singleton — loaded once at startup, shared across all requests
# ---------------------------------------------------------------------------

_backend_dir = os.path.dirname(os.path.abspath(__file__))
_graph_path = os.path.join(_backend_dir, "routing_graph.pkl")

graph: Optional[rx.PyDiGraph] = None
kdtree: Optional[KDTree] = None
node_indices: Optional[Dict] = None
idx_to_node: Optional[Dict] = None

# ---------------------------------------------------------------------------
# ML Congestion weight model — loaded once at startup
# ---------------------------------------------------------------------------

_congestion_model_path   = os.path.join(_backend_dir, "congestion_model.pkl")
_congestion_columns_path = os.path.join(_backend_dir, "congestion_feature_columns.pkl")

congestion_model = None
congestion_feature_columns: Optional[list] = None

# Road type index used by the congestion model
_ROAD_TYPE_IDX = {
    "motorway": 0, "trunk": 0, "primary": 0,
    "secondary": 1, "tertiary": 1,
}

# Cause index flags
_CAUSE_FLAGS = {
    'Accident':          ('cause_accident',  1),
    'Vehicle Breakdown': ('cause_breakdown',  1),
    'Waterlogging':      ('cause_waterlog',   1),
    'Protest / Rally':   ('cause_protest',    1),
}

# Vehicle type flags
_VEH_FLAGS = {
    'Heavy Truck':            'veh_truck',
    'Car/Taxi':               'veh_car',
    'Two-Wheeler':            'veh_two_wheeler',
    'LCV (Light Commercial)': 'veh_lcv',
}


def load_congestion_model() -> bool:
    """Load the ML congestion weight model. Returns True on success."""
    global congestion_model, congestion_feature_columns
    try:
        with open(_congestion_model_path, 'rb') as f:
            congestion_model = pickle.load(f)
        with open(_congestion_columns_path, 'rb') as f:
            congestion_feature_columns = pickle.load(f)
        print(f"Congestion model loaded — {len(congestion_feature_columns)} features")
        return True
    except Exception as e:
        print(f"Could not load congestion model: {e}")
        return False


def _predict_congestion_weight(
    highway_type: str,
    dist_km: float,
    hour: int,
    is_peak: int,
    day_of_week: int,
    zone_cluster: int,
    requires_closure: int,
    duration_norm: float,
    cause: str,
    vehicle_type: str,
) -> float:
    """
    Ask the ML model: given this road edge and this incident's attributes,
    what congestion weight (0..1) should the BFS assign to this edge?
    Returns a float in [0.05, 1.0].
    """
    if congestion_model is None or congestion_feature_columns is None:
        # Fallback to simple hardcoded weights if model not loaded
        rt = _ROAD_TYPE_IDX.get(highway_type, 2)
        return [0.30, 0.60, 1.00][rt]

    road_type_idx = _ROAD_TYPE_IDX.get(highway_type, 2)

    # Build feature vector in the exact order the model was trained on
    vec = {
        'road_type':           road_type_idx,
        'dist_from_hazard_km': dist_km,
        'hour':                hour,
        'day_of_week':         day_of_week,
        'is_peak':             is_peak,
        'zone_cluster':        zone_cluster,
        'requires_closure':    requires_closure,
        'duration_norm':       duration_norm,
        'cause_accident':      0,
        'cause_breakdown':     0,
        'cause_waterlog':      0,
        'cause_protest':       0,
        'veh_truck':           0,
        'veh_car':             0,
        'veh_two_wheeler':     0,
        'veh_lcv':             0,
    }

    # Set cause flag
    cause_entry = _CAUSE_FLAGS.get(cause)
    if cause_entry:
        vec[cause_entry[0]] = cause_entry[1]

    # Set vehicle flag
    veh_key = _VEH_FLAGS.get(vehicle_type, '')
    if veh_key:
        vec[veh_key] = 1

    features = [[vec[col] for col in congestion_feature_columns]]
    weight = float(congestion_model.predict(features)[0])
    return float(max(0.05, min(1.0, weight)))


def load_graph() -> bool:
    """Load the routing graph from disk. Returns True on success."""
    global graph, kdtree, node_indices, idx_to_node

    if not os.path.exists(_graph_path):
        print(f"Routing graph not found at {_graph_path}")
        return False

    try:
        with open(_graph_path, "rb") as f:
            graph_data = pickle.load(f)

        if isinstance(graph_data, dict):
            graph = graph_data["graph"]
            kdtree = graph_data["kdtree"]
            node_indices = graph_data["node_indices"]
            idx_to_node = {v: k for k, v in node_indices.items()}

        print(f"Routing graph loaded — {graph.num_nodes()} nodes, {graph.num_edges()} edges")
        return True
    except Exception as e:
        print(f"Could not load routing graph: {e}")
        return False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_road_coordinates(edge_data: dict, n1: dict, n2: dict) -> List[List[float]]:
    """
    Return [[lon, lat], ...] coordinates for a road segment.
    Uses the encoded polyline from the graph if present (curved roads),
    otherwise falls back to a straight line between the two nodes.
    """
    try:
        import polyline as pl
        if edge_data and "polyline" in edge_data:
            # polyline stores (lat, lon); Deck.GL wants [lon, lat]
            decoded = pl.decode(edge_data["polyline"])
            return [[pt[1], pt[0]] for pt in decoded]
    except ImportError:
        pass

    # Straight-line fallback
    return [[n1["lon"], n1["lat"]], [n2["lon"], n2["lat"]]]


def _congestion_color(score: float) -> List[int]:
    """Return an RGBA color list based on a congestion score (1–10)."""
    if score >= 7.0:
        return [180, 0, 0, 220]      # Deep red
    elif score >= 5.0:
        return [255, 69, 0, 200]     # Orange-red
    elif score >= 3.0:
        return [255, 165, 0, 180]    # Amber
    else:
        return [50, 205, 50, 150]    # Green


def _build_road_feature(
    current_node: int,
    neighbor: int,
    edge_data: dict,
    final_risk_score: float,
    hazard_coords: List[Tuple[float, float]],
    hour: int,
    decay_factor: float,
    is_spillover: bool,
) -> Dict[str, Any]:
    """Build a fully-formed road GeoJSON feature dict for one edge."""
    n1 = graph.get_node_data(current_node)
    n2 = graph.get_node_data(neighbor)
    road_coords = get_road_coordinates(edge_data, n1, n2)

    avg_lon = sum(pt[0] for pt in road_coords) / len(road_coords)
    avg_lat = sum(pt[1] for pt in road_coords) / len(road_coords)

    # Distance to nearest hazard drives the congestion score
    min_dist = min(
        math.sqrt((avg_lat - h_lat) ** 2 + (avg_lon - h_lon) ** 2)
        for h_lat, h_lon in hazard_coords
    )
    congestion_score = max(1.0, min(10.0, final_risk_score - (min_dist * 20.0)))

    color = [160, 32, 240, 200] if is_spillover else _congestion_color(congestion_score)
    road_id = f"{current_node}_{neighbor}"

    return {
        "road_id": road_id,
        "coordinates": road_coords,
        "congestion_score": congestion_score,
        "dynamic_congestion_score": congestion_score,
        "decay_factor": float(decay_factor),
        "type": "Feature",
        "geometry": {"type": "LineString", "coordinates": road_coords},
        "properties": {
            "color": color,
            "congestion_score": congestion_score,
            "road_id": road_id,
            "dynamic_congestion_score": congestion_score,
            "decay_factor": float(decay_factor),
            # eventHour is stored in properties so the frontend can read it correctly
            "eventHour": hour,
        },
    }


# ---------------------------------------------------------------------------
# BFS flood-fill — finds affected + spillover roads
# ---------------------------------------------------------------------------

def compute_affected_roads(
    hazard_infos: List[Tuple[float, float, int]],
    barricaded_nodes: Set[int],
    final_risk_score: float,
    cause: str = 'Accident',
    vehicle_type: str = 'Car/Taxi',
    requires_closure: int = 0,
    duration_norm: float = 0.3,
    zone_cluster: int = 0,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    BFS outward from each hazard node to find which roads are congested.
    Uses the ML congestion weight model to predict edge weights based on
    road type, distance from hazard, time of day, cause, and vehicle type.
    Returns (affected_roads_dict, spillover_roads_dict).
    """
    affected: Dict[str, Any] = {}
    spillover: Dict[str, Any] = {}

    if not (graph and isinstance(graph, rx.PyDiGraph) and kdtree):
        return affected, spillover

    base_hops = max(2, int(final_risk_score * 2))
    hazard_coords = [(lat, lon) for lat, lon, _ in hazard_infos]

    for h_lat, h_lon, h_hour in hazard_infos:
        try:
            _, nearest_idx = kdtree.query([h_lat, h_lon])
            nearest_node = int(nearest_idx)

            visited = {nearest_node: 0}
            queue = [(nearest_node, 0)]

            while queue:
                current_node, depth = queue.pop(0)
                if depth >= base_hops:
                    continue

                for source, neighbor, edge_data in graph.out_edges(current_node):
                    if int(neighbor) in barricaded_nodes or int(source) in barricaded_nodes:
                        continue

                    highway_type = edge_data.get("highway", "residential")

                    # --- ML-predicted congestion weight for this edge ---
                    # Get approximate distance from this node to hazard
                    try:
                        n_data = graph.get_node_data(current_node)
                        n_lat, n_lon = n_data["lat"], n_data["lon"]
                        dist_km = math.sqrt(
                            (n_lat - h_lat) ** 2 + (n_lon - h_lon) ** 2
                        ) * 111.0  # rough degrees-to-km conversion
                    except Exception:
                        dist_km = depth * 0.3

                    is_peak = 1 if (7 <= h_hour <= 11 or 16 <= h_hour <= 21) else 0
                    base_cost = _predict_congestion_weight(
                        highway_type=highway_type,
                        dist_km=dist_km,
                        hour=h_hour,
                        is_peak=is_peak,
                        day_of_week=0,  # not available per-edge; model is robust to this
                        zone_cluster=zone_cluster,
                        requires_closure=requires_closure,
                        duration_norm=duration_norm,
                        cause=cause,
                        vehicle_type=vehicle_type,
                    )
                    # Decay factor derived from base_cost: higher weight = decays faster
                    decay_factor = 1.0 + base_cost * 0.6

                    hop_cost = base_cost * (decay_factor ** depth)
                    new_depth = depth + hop_cost

                    if neighbor not in visited or new_depth < visited[neighbor]:
                        visited[neighbor] = new_depth
                        queue.append((neighbor, new_depth))

                        is_spillover = base_cost == 1.0 and new_depth > 3
                        feature = _build_road_feature(
                            current_node, neighbor, edge_data,
                            final_risk_score, hazard_coords,
                            h_hour, decay_factor, is_spillover
                        )
                        road_id = feature["road_id"]

                        if is_spillover:
                            if road_id not in spillover or feature["congestion_score"] > spillover[road_id]["congestion_score"]:
                                spillover[road_id] = feature
                        else:
                            if road_id not in affected or feature["congestion_score"] > affected[road_id]["congestion_score"]:
                                affected[road_id] = feature

        except Exception as e:
            print(f"Error in BFS spatial analysis: {e}")

    return affected, spillover


# ---------------------------------------------------------------------------
# Dijkstra detour routing
# ---------------------------------------------------------------------------

def compute_detour_routes(
    hazard_coords: List[Tuple[float, float]],
    mitigation_coords: List[Tuple[float, float]],
    hour: int,
    green_wave_active: bool = False,
) -> Tuple[List[Dict], bool]:
    """
    Find an alternative route that avoids barricaded nodes.
    Returns (detour_road_features, detour_possible).
    """
    if not (graph and kdtree and mitigation_coords):
        return [], True

    detour_routes: List[Dict] = []
    detour_possible = True

    try:
        temp_graph = graph.copy()
        hazard_nodes: Set[int] = set()

        for h_lat, h_lon in hazard_coords:
            _, h_idx = kdtree.query([h_lat, h_lon])
            hazard_nodes.add(int(h_idx))

        for m_lat, m_lon in mitigation_coords:
            _, m_idx = kdtree.query([m_lat, m_lon])
            m_idx = int(m_idx)
            if m_idx not in hazard_nodes and temp_graph.has_node(m_idx):
                temp_graph.remove_node(m_idx)

        first_lat, first_lon = hazard_coords[0]
        _, first_hazard_idx_raw = kdtree.query([first_lat, first_lon])
        first_hazard_idx = int(first_hazard_idx_raw)

        if not temp_graph.has_node(first_hazard_idx):
            return [], False

        # Query the 80 closest nodes. We pick the furthest one that is still
        # within ~500 m of the hazard to prevent cross-city detour lines.
        MAX_DETOUR_RADIUS_DEG = 0.005  # ~500 m in lat/lon degrees
        dists, nearest_indices = kdtree.query([first_lat, first_lon], k=80)
        target_idx = first_hazard_idx
        for dist, idx in zip(reversed(dists), reversed(nearest_indices)):
            idx = int(idx)
            if dist > MAX_DETOUR_RADIUS_DEG:
                continue
            if idx != first_hazard_idx and temp_graph.has_node(idx):
                target_idx = idx
                break

        paths = rx.dijkstra_shortest_paths(
            temp_graph,
            source=first_hazard_idx,
            target=target_idx,
            weight_fn=lambda e: e.get("weight", 1.0),
        )

        if not paths or target_idx not in paths:
            raise Exception("NoPath")

        path = paths[target_idx]
        for i in range(len(path) - 1):
            u, v = path[i], path[i + 1]
            edge_data = temp_graph.get_edge_data(u, v)
            n1 = temp_graph.get_node_data(u)
            n2 = temp_graph.get_node_data(v)
            road_coords = get_road_coordinates(edge_data, n1, n2)
            road_id = f"{u}_{v}"
            
            # Green Wave visual cue
            color = [0, 255, 127, 255] # Default Green
            if green_wave_active:
                color = [0, 255, 255, 255] # Cyan glow for green wave

            detour_routes.append({
                "road_id": road_id,
                "coordinates": road_coords,
                "congestion_score": 1.0,
                "dynamic_congestion_score": 1.0,
                "decay_factor": 1.0,
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": road_coords},
                "properties": {
                    "color": color,
                    "congestion_score": 1.0,
                    "road_id": road_id,
                    "dynamic_congestion_score": 1.0,
                    "decay_factor": 1.0,
                    "eventHour": hour,
                    "isGreenWave": green_wave_active,
                },
            })

    except Exception as e:
        print(f"Detour exception: {e}")
        detour_possible = False

    return detour_routes, detour_possible


# ---------------------------------------------------------------------------
# Full Network Extraction for Frontend Overlay
# ---------------------------------------------------------------------------

def get_full_network() -> List[Dict]:
    """
    Extract all major roads from the graph to send to the frontend as a static overlay.
    Filters out residential/unclassified roads to save bandwidth and improve FPS.
    """
    if not graph:
        return []
        
    features = []
    # Major roads to keep
    keep_types = {"primary", "secondary", "tertiary", "trunk", "motorway", "primary_link", "secondary_link", "tertiary_link"}
    
    seen_edges = set()
    
    for u, v, edge_data in graph.edge_index_map().values():
        # Avoid duplicate edges for undirected-like rendering
        edge_id = tuple(sorted([u, v]))
        if edge_id in seen_edges:
            continue
            
        highway_type = edge_data.get("highway", "")
        # Handle cases where highway is a list
        if isinstance(highway_type, list):
            highway_type = highway_type[0]
            
        if highway_type not in keep_types:
            continue
            
        seen_edges.add(edge_id)
        
        n1 = graph.get_node_data(u)
        n2 = graph.get_node_data(v)
        road_coords = get_road_coordinates(edge_data, n1, n2)
        
        # Color based on road type
        color = [100, 100, 100, 100] # Default grey for overlay
        if highway_type in {"motorway", "trunk"}:
            color = [80, 80, 80, 200]
        elif highway_type in {"primary", "primary_link"}:
            color = [70, 70, 70, 180]
            
        features.append({
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": road_coords},
            "properties": {
                "color": color,
                "highway": highway_type,
                "road_id": f"{u}_{v}"
            }
        })
        
    return features
