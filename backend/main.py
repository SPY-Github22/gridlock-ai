from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Union, Literal
import pickle
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
import networkx as nx # Keeping for fallback if needed
import rustworkx as rx
from scipy.spatial import KDTree
import os
import joblib

# Load models safely
backend_dir = os.path.dirname(os.path.abspath(__file__))
model = None
graph = None
kdtree = None
node_indices = None
idx_to_node = None
kmeans_model = None
etr_model = None

model_path = os.path.join(backend_dir, "risk_model.pkl")
graph_path = os.path.join(backend_dir, "routing_graph.pkl")
kmeans_path = os.path.join(backend_dir, "kmeans_model.pkl")
etr_path = os.path.join(backend_dir, "etr_model.pkl")

if os.path.exists(model_path):
    with open(model_path, "rb") as f:
        model = pickle.load(f)
if os.path.exists(graph_path):
    with open(graph_path, "rb") as f:
        graph_data = pickle.load(f)
        if isinstance(graph_data, dict):
            graph = graph_data["graph"]
            kdtree = graph_data["kdtree"]
            node_indices = graph_data["node_indices"]
            idx_to_node = {v: k for k, v in node_indices.items()}
        else:
            graph = graph_data
if os.path.exists(kmeans_path):
    with open(kmeans_path, "rb") as f:
        kmeans_model = pickle.load(f)
if os.path.exists(etr_path):
    with open(etr_path, "rb") as f:
        etr_model = pickle.load(f)

app = FastAPI(title="Traffic Simulation Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class BarricadeRequest(BaseModel):
    latitude: float
    longitude: float

    @validator('latitude', pre=True)
    def check_lat(cls, v):
        if v is None or not isinstance(v, (int, float)) or isinstance(v, bool):
            raise TypeError("Latitude must be a float or integer")
        if not (12.7 <= float(v) <= 13.2):
            raise ValueError("Latitude must be within Bengaluru bounds [12.7, 13.2]")
        return float(v)

    @validator('longitude', pre=True)
    def check_lon(cls, v):
        if v is None or not isinstance(v, (int, float)) or isinstance(v, bool):
            raise TypeError("Longitude must be a float or integer")
        if not (77.4 <= float(v) <= 77.8):
            raise ValueError("Longitude must be within Bengaluru bounds [77.4, 77.8]")
        return float(v)

class CrowdRequest(BaseModel):
    latitude: float
    longitude: float
    density: float

    @validator('latitude', pre=True)
    def check_lat(cls, v):
        if v is None or not isinstance(v, (int, float)) or isinstance(v, bool):
            raise TypeError("Latitude must be a float or integer")
        if not (12.7 <= float(v) <= 13.2):
            raise ValueError("Latitude must be within Bengaluru bounds [12.7, 13.2]")
        return float(v)

    @validator('longitude', pre=True)
    def check_lon(cls, v):
        if v is None or not isinstance(v, (int, float)) or isinstance(v, bool):
            raise TypeError("Longitude must be a float or integer")
        if not (77.4 <= float(v) <= 77.8):
            raise ValueError("Longitude must be within Bengaluru bounds [77.4, 77.8]")
        return float(v)

    @validator('density', pre=True)
    def check_density(cls, v):
        if v is None or not isinstance(v, (int, float)) or isinstance(v, bool):
            raise TypeError("Density must be a float or integer")
        if not (0.0 <= float(v) <= 1.0):
            raise ValueError("Density must be between 0.0 and 1.0")
        return float(v)

class ScenarioEventRequest(BaseModel):
    latitude: float
    longitude: float
    event_cause: Literal['Accident', 'Vehicle Breakdown', 'Protest / Rally', 'Waterlogging']
    time_of_day: Literal['Morning Peak', 'Evening Peak', 'Off-Peak', 'Afternoon', 'Night']
    vehicle_type: str = Field(default="Car/Taxi")

    @validator('latitude', pre=True)
    def check_lat(cls, v):
        if v is None or not isinstance(v, (int, float)) or isinstance(v, bool):
            raise TypeError("Latitude must be a float or integer")
        if not (12.7 <= float(v) <= 13.2):
            raise ValueError("Latitude must be within Bengaluru bounds [12.7, 13.2]")
        return float(v)

    @validator('longitude', pre=True)
    def check_lon(cls, v):
        if v is None or not isinstance(v, (int, float)) or isinstance(v, bool):
            raise TypeError("Longitude must be a float or integer")
        if not (77.4 <= float(v) <= 77.8):
            raise ValueError("Longitude must be within Bengaluru bounds [77.4, 77.8]")
        return float(v)

class SimulateScenarioRequest(BaseModel):
    scenario_mode: Literal['Baseline', 'Future Impact', 'Optimized Strategy']
    barricades: List[BarricadeRequest]
    crowds: List[CrowdRequest]
    events: List[ScenarioEventRequest]

class EventSimulationRequest(BaseModel):
    latitude: float = Field(..., description="Latitude of the event")
    longitude: float = Field(..., description="Longitude of the event")
    event_cause: Literal['Accident', 'Vehicle Breakdown', 'Protest / Rally', 'Waterlogging', 'Barricade', 'Police Squad'] = Field(..., description="Cause of the event")
    time_of_day: Literal['Morning Peak', 'Evening Peak', 'Off-Peak', 'Afternoon', 'Night'] = Field(..., description="Time of the event")
    vehicle_type: str = Field(default="Car/Taxi", description="Type of vehicle involved")

    @validator('latitude', pre=True)
    def check_lat(cls, v):
        if v is None or not isinstance(v, (int, float)) or isinstance(v, bool):
            raise TypeError("Latitude must be a float or integer")
        if not (12.7 <= float(v) <= 13.2):
            raise ValueError("Latitude must be within Bengaluru bounds [12.7, 13.2]")
        return float(v)

    @validator('longitude', pre=True)
    def check_lon(cls, v):
        if v is None or not isinstance(v, (int, float)) or isinstance(v, bool):
            raise TypeError("Longitude must be a float or integer")
        if not (77.4 <= float(v) <= 77.8):
            raise ValueError("Longitude must be within Bengaluru bounds [77.4, 77.8]")
        return float(v)

class SimulationBatchRequest(BaseModel):
    events: List[EventSimulationRequest]

class RecommendedAction(BaseModel):
    action_type: str
    latitude: float
    longitude: float
    description: str

class EventSimulationResponse(BaseModel):
    risk_score: float = Field(..., description="Congestion ripple risk score from 1-10")
    requires_road_closure: float = Field(..., description="Probability of road closure 0.0-1.0")
    etr_minutes: Optional[float] = Field(None, description="Estimated Time to Resolve in minutes")
    recommended_actions: List[RecommendedAction]
    affected_roads: Union[dict, List[dict]] = Field(default_factory=list)
    spillover_roads: Union[dict, List[dict]] = Field(default_factory=list)
    detour_routes: Union[dict, List[dict]] = Field(default_factory=list)
    detour_possible: bool = Field(True, description="False if barricade blocked a chokepoint")

class HazardItem:
    def __init__(self, latitude: float, longitude: float, event_cause: str, time_of_day: str, vehicle_type: str = "Car/Taxi"):
        self.latitude = latitude
        self.longitude = longitude
        self.event_cause = event_cause
        self.time_of_day = time_of_day
        self.vehicle_type = vehicle_type
        self.density = None

class MitigationItem:
    def __init__(self, latitude: float, longitude: float, event_cause: str):
        self.latitude = latitude
        self.longitude = longitude
        self.event_cause = event_cause

def haversine_distance(lat1, lon1, lat2, lon2):
    r = 6371.0  # Earth's radius in km
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat/2.0)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2.0)**2
    c = 2.0 * np.arcsin(np.sqrt(a))
    return r * c

def get_avg_pairwise_distance(lats, lons):
    n = len(lats)
    if n <= 1:
        return 0.0
    total_dist = 0.0
    count = 0
    for i in range(n):
        for j in range(i + 1, n):
            total_dist += haversine_distance(lats[i], lons[i], lats[j], lons[j])
            count += 1
    return total_dist / count if count > 0 else 0.0

def get_road_coordinates(edge_data, n1, n2):
    import polyline
    if edge_data and 'polyline' in edge_data:
        coords = polyline.decode(edge_data['polyline'])
        return [[pt[1], pt[0]] for pt in coords]
    else:
        return [[n1['lon'], n1['lat']], [n2['lon'], n2['lat']]]

def run_simulation_logic(hazards: List[HazardItem], mitigations: List[MitigationItem]) -> EventSimulationResponse:
    if not hazards:
        # If there are no hazards but there are mitigations (e.g. barricades),
        # we should still generate recommended actions for the barricades.
        actions = []
        for m in mitigations:
            if m.event_cause == "Barricade":
                actions.append(
                    RecommendedAction(
                        action_type="Barricade",
                        latitude=m.latitude,
                        longitude=m.longitude,
                        description=f"Deploy barricade at ({m.latitude:.4f}, {m.longitude:.4f}) to redirect traffic onto alternative routes."
                    )
                )
        return EventSimulationResponse(
            risk_score=1.0,
            requires_road_closure=0.0,
            recommended_actions=actions,
            affected_roads=[],
            spillover_roads=[],
            detour_routes=[],
            detour_possible=True
        )

    # 1. Temporal features from the first hazard
    first_event = hazards[0]
    hour_map = {"Morning Peak": 9, "Afternoon": 13, "Evening Peak": 18, "Night": 2, "Off-Peak": 12}
    hour = hour_map.get(first_event.time_of_day, 12)
    day_of_week = 2
    is_peak = 1 if first_event.time_of_day in ["Morning Peak", "Evening Peak"] else 0
    concurrent_event_count = len(hazards)

    # 2. Extract lats and lons to calculate average distance
    lats = [event.latitude for event in hazards]
    lons = [event.longitude for event in hazards]
    avg_dist = get_avg_pairwise_distance(lats, lons)

    # 3. Predict zone_cluster for each event and calculate cluster density
    zone_clusters = []
    for event in hazards:
        if kmeans_model:
            cluster = int(kmeans_model.predict([[event.latitude, event.longitude]])[0])
        else:
            cluster = (int(event.latitude * 1000) ^ int(event.longitude * 1000)) % 10
        zone_clusters.append(cluster)
    
    from collections import Counter
    cluster_density = Counter(zone_clusters).most_common(1)[0][1] if zone_clusters else 0

    # 4. Predict baseline closure probability using model
    requires_road_closure = 0.5
    if model:
        features = np.array([[
            concurrent_event_count,
            avg_dist,
            cluster_density,
            hour,
            day_of_week,
            is_peak
        ]])
        with joblib.parallel_backend('sequential'):
            probs = model.predict_proba(features)[0]
        requires_road_closure = float(probs[1])
    
    baseline_risk = min(10.0, (requires_road_closure * 50.0) + 4.0)
    baseline_risk = max(1.0, baseline_risk)

    # 5. Apply Mitigation Logic
    hazard_factors = []
    for h in hazards:
        factor = 1.0
        for m in mitigations:
            dist = haversine_distance(h.latitude, h.longitude, m.latitude, m.longitude)
            if dist <= 5.0:
                if m.event_cause == "Barricade":
                    factor *= 0.85
                elif m.event_cause == "Police Squad":
                    factor *= 0.90
        hazard_factors.append(factor)
        
    avg_mitigation_factor = np.mean(hazard_factors) if hazard_factors else 1.0
    final_risk_score = baseline_risk * avg_mitigation_factor
    
    # Scale risk score based on crowd densities if any
    crowd_densities = [h.density for h in hazards if hasattr(h, 'density') and h.density is not None]
    if crowd_densities:
        avg_density = np.mean(crowd_densities)
        final_risk_score *= (0.7 + 0.6 * avg_density)
        
    final_risk_score = max(1.0, min(final_risk_score, 10.0))
    requires_road_closure = requires_road_closure * avg_mitigation_factor

    # 6. ETR Prediction
    etr_minutes = None
    if etr_model and hazards:
        etr_features = pd.DataFrame([{
            'hour': hour,
            'day_of_week': day_of_week,
            'is_peak': is_peak,
            'zone_cluster': zone_clusters[0] if zone_clusters else 0
        }])
        etr_pred = etr_model.predict(etr_features)[0]
        etr_pred = max(etr_pred * avg_mitigation_factor, 1.0)
        etr_minutes = round(etr_pred, 1)

    # 7. Recommended Actions
    actions = []
    for event in hazards:
        actions.append(
            RecommendedAction(
                action_type="Strategy A (Aggressive)",
                latitude=event.latitude + 0.001,
                longitude=event.longitude + 0.001,
                description=f"Deploy 4 Police Squads from nearest precinct due to {event.event_cause}. Drops ETR to ~{(etr_minutes*0.4 if etr_minutes else 30):.0f} mins. High cost."
            )
        )
        actions.append(
            RecommendedAction(
                action_type="Strategy B (Passive)",
                latitude=event.latitude - 0.001,
                longitude=event.longitude - 0.001,
                description=f"Deploy 1 Barricade due to {event.event_cause}. Risk mitigates slightly. Low resource cost."
            )
        )

    # 8. Spatial affected roads (BFS in rustworkx)
    affected_roads_dict = {}
    spillover_roads_dict = {}
    import math
    
    if graph and isinstance(graph, rx.PyDiGraph) and kdtree and hazards and final_risk_score > 0:
        base_hops = max(2, int(final_risk_score * 2))
        
        barricaded_nodes = set()
        for m in mitigations:
            if m.event_cause == "Barricade":
                _, m_idx = kdtree.query([m.latitude, m.longitude])
                barricaded_nodes.add(int(m_idx))
                
        for event in hazards:
            try:
                dist, nearest_idx = kdtree.query([event.latitude, event.longitude])
                nearest_node = nearest_idx
                
                visited_nodes = {nearest_node: 0}
                queue = [(nearest_node, 0)]
                
                while queue:
                    current_node, depth = queue.pop(0)
                    if depth >= base_hops:
                        continue
                        
                    for edge_idx in graph.out_edges(current_node):
                        source, neighbor, edge_data = edge_idx
                        
                        if neighbor in barricaded_nodes or source in barricaded_nodes:
                            continue
                            
                        highway_type = edge_data.get('highway', 'residential')
                        
                        base_cost = 1.0
                        decay_factor = 1.5
                        if highway_type in ['primary', 'trunk', 'motorway']:
                            base_cost = 0.3
                            decay_factor = 1.1
                        elif highway_type in ['secondary', 'tertiary']:
                            base_cost = 0.6
                            decay_factor = 1.2
                            
                        hop_cost = base_cost * (decay_factor ** depth)
                        new_depth = depth + hop_cost
                        
                        if neighbor not in visited_nodes or new_depth < visited_nodes[neighbor]:
                            visited_nodes[neighbor] = new_depth
                            queue.append((neighbor, int(depth) + 1))
                            
                            n1 = graph.get_node_data(current_node)
                            n2 = graph.get_node_data(neighbor)
                            road_coords = get_road_coordinates(edge_data, n1, n2)
                            
                            avg_lon = sum(pt[0] for pt in road_coords) / len(road_coords)
                            avg_lat = sum(pt[1] for pt in road_coords) / len(road_coords)
                            
                            min_dist = float('inf')
                            for h in hazards:
                                h_dist = math.sqrt((avg_lat - h.latitude)**2 + (avg_lon - h.longitude)**2)
                                if h_dist < min_dist:
                                    min_dist = h_dist
                                    
                            congestion_score = max(1.0, min(10.0, final_risk_score - (min_dist * 20.0)))
                            
                            color = [50, 205, 50, 150]
                            if congestion_score >= 7.0:
                                color = [180, 0, 0, 220]
                            elif congestion_score >= 5.0:
                                color = [255, 69, 0, 200]
                            elif congestion_score >= 3.0:
                                color = [255, 165, 0, 180]
                                
                            road_id = f"{current_node}_{neighbor}"
                            
                            mixed_dict = {
                                "road_id": road_id,
                                "coordinates": road_coords,
                                "congestion_score": congestion_score,
                                "dynamic_congestion_score": congestion_score,
                                "decay_factor": float(decay_factor),
                                "type": "Feature",
                                "geometry": {
                                    "type": "LineString",
                                    "coordinates": road_coords
                                },
                                "properties": {
                                    "color": color,
                                    "congestion_score": congestion_score,
                                    "road_id": road_id,
                                    "dynamic_congestion_score": congestion_score,
                                    "decay_factor": float(decay_factor),
                                    "eventHour": hour
                                }
                            }
                            
                            if base_cost == 1.0 and new_depth > 3:
                                mixed_dict["properties"]["color"] = [160, 32, 240, 200]
                                if road_id not in spillover_roads_dict or congestion_score > spillover_roads_dict[road_id]["congestion_score"]:
                                    spillover_roads_dict[road_id] = mixed_dict
                            else:
                                if road_id not in affected_roads_dict or congestion_score > affected_roads_dict[road_id]["congestion_score"]:
                                    affected_roads_dict[road_id] = mixed_dict
            except Exception as e:
                print(f"Error in spatial analysis: {e}")

    # 9. Detour Routing Mapping
    detour_routes_list = []
    detour_possible = True
    if mitigations:
        try:
            temp_graph = graph.copy()
            hazard_nodes = set()
            for h in hazards:
                dist, h_idx = kdtree.query([h.latitude, h.longitude])
                hazard_nodes.add(int(h_idx))
                
            for m in mitigations:
                dist, m_idx = kdtree.query([m.latitude, m.longitude])
                m_idx = int(m_idx)
                if m_idx not in hazard_nodes:
                    if temp_graph.has_node(m_idx):
                        temp_graph.remove_node(m_idx)
                        
            first_hazard_idx = int(kdtree.query([hazards[0].latitude, hazards[0].longitude])[1])
            if not temp_graph.has_node(first_hazard_idx):
                detour_possible = False
                
            if detour_possible:
                valid_nodes = list(temp_graph.node_indices())
                if not valid_nodes:
                    detour_possible = False
                else:
                    target_idx = None
                    for idx in valid_nodes:
                        if idx != first_hazard_idx:
                            target_idx = idx
                            break
                    if target_idx is None:
                        target_idx = first_hazard_idx
                        
                    paths = rx.dijkstra_shortest_paths(temp_graph, source=first_hazard_idx, target=target_idx, weight_fn=lambda e: e.get('weight', 1.0))
                    
                    if not paths or target_idx not in paths:
                        raise Exception("NoPath")
                        
                    path = paths[target_idx]
                    for i in range(len(path) - 1):
                        u = path[i]
                        v = path[i+1]
                        edge_data_detour = temp_graph.get_edge_data(u, v)
                        n1 = temp_graph.get_node_data(u)
                        n2 = temp_graph.get_node_data(v)
                        road_coords = get_road_coordinates(edge_data_detour, n1, n2)
                        
                        road_id = f"{u}_{v}"
                        mixed_dict = {
                            "road_id": road_id,
                            "coordinates": road_coords,
                            "congestion_score": 1.0,
                            "dynamic_congestion_score": 1.0,
                            "decay_factor": 1.0,
                            "type": "Feature",
                            "geometry": {
                                "type": "LineString",
                                "coordinates": road_coords
                            },
                            "properties": {
                                "color": [0, 255, 127, 255],
                                "congestion_score": 1.0,
                                "road_id": road_id,
                                "dynamic_congestion_score": 1.0,
                                "decay_factor": 1.0,
                                "eventHour": hour
                            }
                        }
                        detour_routes_list.append(mixed_dict)
        except Exception as e:
            print(f"Detour Exception: {e}")
            detour_possible = False

    return EventSimulationResponse(
        risk_score=final_risk_score,
        requires_road_closure=requires_road_closure,
        etr_minutes=etr_minutes,
        recommended_actions=actions,
        affected_roads=list(affected_roads_dict.values()),
        spillover_roads=list(spillover_roads_dict.values()),
        detour_routes=detour_routes_list,
        detour_possible=detour_possible
    )

@app.get("/")
def read_root():
    return {"message": "Traffic Simulation API is running"}

@app.post("/simulate_event", response_model=EventSimulationResponse)
def simulate_event(request: SimulationBatchRequest):
    if not request.events:
        raise HTTPException(status_code=400, detail="No events provided")

    # Separate hazards and mitigations
    hazards = []
    mitigations = []
    for e in request.events:
        if e.event_cause in ["Barricade", "Police Squad"]:
            mitigations.append(
                MitigationItem(
                    latitude=e.latitude,
                    longitude=e.longitude,
                    event_cause=e.event_cause
                )
            )
        else:
            hazards.append(
                HazardItem(
                    latitude=e.latitude,
                    longitude=e.longitude,
                    event_cause=e.event_cause,
                    time_of_day=e.time_of_day,
                    vehicle_type=e.vehicle_type
                )
            )
            
    return run_simulation_logic(hazards, mitigations)

@app.post("/simulate_scenario", response_model=EventSimulationResponse)
def simulate_scenario(request: SimulateScenarioRequest):
    # Separate hazards and mitigations based on scenario_mode
    # 'Baseline': Hazards are only 'events'. Mitigations are empty.
    # 'Future Impact': Hazards are 'events' + 'crowds'. Mitigations are empty.
    # 'Optimized Strategy': Hazards are 'events' + 'crowds'. Mitigations are 'barricades' + event barricades/police.
    
    first_tod = request.events[0].time_of_day if request.events else "Morning Peak"
    
    hazards = []
    mitigations = []
    
    # 1. Base events hazards
    for e in request.events:
        hazards.append(
            HazardItem(
                latitude=e.latitude,
                longitude=e.longitude,
                event_cause=e.event_cause,
                time_of_day=e.time_of_day,
                vehicle_type=e.vehicle_type
            )
        )
        
    # 2. Crowds (as hazards under Future Impact & Optimized Strategy)
    if request.scenario_mode in ['Future Impact', 'Optimized Strategy']:
        for c in request.crowds:
            item = HazardItem(
                latitude=c.latitude,
                longitude=c.longitude,
                event_cause='Protest / Rally',
                time_of_day=first_tod,
                vehicle_type='Car/Taxi'
            )
            item.density = c.density
            hazards.append(item)
            
    # 3. Barricades (as mitigations under Optimized Strategy)
    if request.scenario_mode == 'Optimized Strategy':
        for b in request.barricades:
            mitigations.append(
                MitigationItem(
                    latitude=b.latitude,
                    longitude=b.longitude,
                    event_cause='Barricade'
                )
            )
            
    return run_simulation_logic(hazards, mitigations)

