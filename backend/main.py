from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional
import pickle
import numpy as np
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

class EventSimulationRequest(BaseModel):
    latitude: float = Field(..., description="Latitude of the event")
    longitude: float = Field(..., description="Longitude of the event")
    event_cause: str = Field(..., description="Cause of the event (e.g., Accident, Protest)")
    time_of_day: str = Field(..., description="Time of the event (e.g., Morning Peak)")
    vehicle_type: str = Field(default="Car/Taxi", description="Type of vehicle involved")

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
    affected_roads: dict = Field(default_factory=lambda: {"type": "FeatureCollection", "features": []})
    spillover_roads: dict = Field(default_factory=lambda: {"type": "FeatureCollection", "features": []})
    detour_routes: dict = Field(default_factory=lambda: {"type": "FeatureCollection", "features": []})
    detour_possible: bool = Field(True, description="False if barricade blocked a chokepoint")

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

@app.get("/")
def read_root():
    return {"message": "Traffic Simulation API is running"}

@app.post("/simulate_event", response_model=EventSimulationResponse)
def simulate_event(request: SimulationBatchRequest):
    if not request.events:
        raise HTTPException(status_code=400, detail="No events provided")

    # 1. Validate bounds (Rough bounding box for Bengaluru)
    for event in request.events:
        if not (12.7 < event.latitude < 13.2 and 77.4 < event.longitude < 77.8):
            raise HTTPException(status_code=422, detail="Coordinates are out of bounds")

    # 2. Extract lats and lons to calculate average distance
    lats = [event.latitude for event in request.events]
    lons = [event.longitude for event in request.events]
    avg_dist = get_avg_pairwise_distance(lats, lons)

    # 3. Predict zone_cluster for each event and calculate cluster density
    from collections import Counter
    zone_clusters = []
    for event in request.events:
        if kmeans_model:
            cluster = int(kmeans_model.predict([[event.latitude, event.longitude]])[0])
        else:
            cluster = (int(event.latitude * 1000) ^ int(event.longitude * 1000)) % 10
        zone_clusters.append(cluster)
    
    cluster_density = Counter(zone_clusters).most_common(1)[0][1] if zone_clusters else 0

    # 4. Separate hazards from mitigation resources
    hazards = [e for e in request.events if e.event_cause not in ["Barricade", "Police Squad"]]
    mitigations = [e for e in request.events if e.event_cause in ["Barricade", "Police Squad"]]
    
    if not hazards:
        # If there are only barricades/police and no actual accidents, risk is 0
        return EventSimulationResponse(risk_score=0.0, requires_road_closure=0.0, recommended_actions=[])

    # 5. Temporal features from the first hazard
    first_event = hazards[0]
    hour_map = {"Morning Peak": 9, "Afternoon": 13, "Evening Peak": 18, "Night": 2}
    hour = hour_map.get(first_event.time_of_day, 12)
    day_of_week = 2
    is_peak = 1 if first_event.time_of_day in ["Morning Peak", "Evening Peak"] else 0

    concurrent_event_count = len(hazards)

    # 6. Predict baseline closure probability using updated model
    requires_road_closure = 0.5
    baseline_risk = 5.0

    if model:
        event_type_map = {"Accident": 0, "Protest": 1, "Waterlogging": 2}
        event_type_encoded = event_type_map.get(first_event.event_cause, 0)
        
        features = np.array([[
            hour,
            day_of_week,
            is_peak,
            zone_clusters[0] if zone_clusters else 0,
            event_type_encoded
        ]])
        with joblib.parallel_backend('sequential'):
            probs = model.predict_proba(features)[0]
        requires_road_closure = float(probs[1])
        baseline_risk = requires_road_closure * 10.0

    # 7. Apply Mitigation Logic (Barricades & Police reduce risk)
    mitigation_factor = 1.0
    for m in mitigations:
        if m.event_cause == "Barricade":
            mitigation_factor *= 0.85 # 15% reduction per barricade
        elif m.event_cause == "Police Squad":
            mitigation_factor *= 0.90 # 10% reduction per police squad

    final_risk_score = baseline_risk * mitigation_factor
    final_risk_score = min(final_risk_score, 10.0)
    requires_road_closure = requires_road_closure * mitigation_factor

    # 8. ETR Prediction
    etr_minutes = None
    if etr_model and hazards:
        etr_features = pd.DataFrame([{
            'hour': hour,
            'day_of_week': day_of_week,
            'is_peak': is_peak,
            'zone_cluster': zone_clusters[0] if zone_clusters else 0
        }])
        etr_pred = etr_model.predict(etr_features)[0]
        etr_pred = max(etr_pred * mitigation_factor, 1.0)
        etr_minutes = round(etr_pred, 1)

    # 9. Dynamic Mitigation Strategies & Actions
    actions = []
    
    if final_risk_score > 6.0:
        for event in hazards:
            # Dynamic Strategy Proposals
            actions.append(
                RecommendedAction(
                    action_type="Strategy A (Aggressive)",
                    latitude=event.latitude + 0.001,
                    longitude=event.longitude + 0.001,
                    description=f"Deploy 4 Police Squads from nearest precinct. Drops ETR to ~{(etr_minutes*0.4 if etr_minutes else 30):.0f} mins. High cost."
                )
            )
            actions.append(
                RecommendedAction(
                    action_type="Strategy B (Passive)",
                    latitude=event.latitude - 0.001,
                    longitude=event.longitude - 0.001,
                    description=f"Deploy 1 Barricade. Risk mitigates slightly. Low resource cost."
                )
            )
    elif mitigations:
        actions.append(
            RecommendedAction(
                action_type="Success",
                latitude=mitigations[0].latitude,
                longitude=mitigations[0].longitude,
                description=f"Mitigation deployed. Risk reduced to {final_risk_score:.1f}."
            )
        )

    # 10. Advanced Spatial Algorithms (Rustworkx)
    affected_roads_geojson = {"type": "FeatureCollection", "features": []}
    spillover_roads_geojson = {"type": "FeatureCollection", "features": []}
    detour_routes_geojson = {"type": "FeatureCollection", "features": []}
    detour_possible = True
    
    if graph and isinstance(graph, rx.PyDiGraph) and kdtree and hazards and final_risk_score > 0:
        base_hops = int(final_risk_score * 2)
        
        for event in hazards:
            try:
                # O(log N) Nearest Node Snapping via KDTree
                dist, nearest_idx = kdtree.query([event.latitude, event.longitude])
                # The index from KDTree corresponds to the node indices if ordered. 
                # Let's assume KDTree was built with same order as `graph.nodes()`.
                nearest_node = nearest_idx
                
                # BFS Traversal for Blast Radius
                visited_nodes = {nearest_node: 0}
                queue = [(nearest_node, 0)]
                
                while queue:
                    current_node, depth = queue.pop(0)
                    if depth >= base_hops:
                        continue
                        
                    for edge_idx in graph.out_edges(current_node):
                        # In rustworkx: out_edges returns (source, target, data)
                        source, neighbor, edge_data = edge_idx
                        
                        highway_type = edge_data.get('highway', 'residential')
                        hop_cost = 1
                        if highway_type in ['primary', 'trunk', 'motorway']:
                            hop_cost = 0.5
                        elif highway_type in ['secondary', 'tertiary']:
                            hop_cost = 0.8
                            
                        new_depth = depth + hop_cost
                        
                        if neighbor not in visited_nodes or new_depth < visited_nodes[neighbor]:
                            visited_nodes[neighbor] = new_depth
                            queue.append((neighbor, new_depth))
                            
                            ratio = depth / float(base_hops)
                            color = [255, 50, 50, 200] if ratio < 0.33 else ([255, 165, 0, 180] if ratio < 0.66 else [50, 255, 50, 150])
                            
                            # Draw feature
                            n1 = graph.get_node_data(current_node)
                            n2 = graph.get_node_data(neighbor)
                            
                            # Determine if this is Spillover (residential hit by high depth)
                            if hop_cost == 1 and new_depth > 3:
                                target_geojson = spillover_roads_geojson
                                color = [160, 32, 240, 200] # Purple for spillover
                            else:
                                target_geojson = affected_roads_geojson
                                
                            target_geojson["features"].append({
                                "type": "Feature",
                                "geometry": {"type": "LineString", "coordinates": [[n1['lat'], n1['lon']], [n2['lat'], n2['lon']]]},
                                "properties": {"color": color, "eventHour": hour_map.get(event.time_of_day, 12)}
                            })
                            
            except Exception as e:
                print(f"Error in rx blast radius: {e}")
                
        # Detour Mapping: Sever Barricade Nodes
        if mitigations:
            try:
                temp_graph = graph.copy()
                for m in mitigations:
                    dist, m_idx = kdtree.query([m.latitude, m.longitude])
                    temp_graph.remove_node(m_idx)
                
                # Dijkstra Shortest Path from Hazard to a random far node
                h_dist, h_idx = kdtree.query([hazards[0].latitude, hazards[0].longitude])
                target_idx = (h_idx + 2) % temp_graph.num_nodes() # Mock target
                
                paths = rx.dijkstra_shortest_paths(temp_graph, source=h_idx, target=target_idx, weight_fn=lambda e: e.get('weight', 1.0))
                
                if not paths or target_idx not in paths:
                    raise Exception("NoPath")
                    
                path = paths[target_idx]
                for i in range(len(path) - 1):
                    n1 = graph.get_node_data(path[i])
                    n2 = graph.get_node_data(path[i+1])
                    detour_routes_geojson["features"].append({
                        "type": "Feature",
                        "geometry": {"type": "LineString", "coordinates": [[n1['lat'], n1['lon']], [n2['lat'], n2['lon']]]},
                        "properties": {"color": [0, 255, 127, 255]} # Bright Spring Green
                    })
            except Exception as e:
                print(f"Detour Exception: {e}")
                detour_possible = False
                
    return EventSimulationResponse(
        risk_score=final_risk_score,
        requires_road_closure=requires_road_closure,
        etr_minutes=etr_minutes,
        recommended_actions=actions,
        affected_roads=affected_roads_geojson,
        spillover_roads=spillover_roads_geojson,
        detour_routes=detour_routes_geojson,
        detour_possible=detour_possible
    )
