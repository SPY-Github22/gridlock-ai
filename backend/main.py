from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional
import pickle
import numpy as np
import networkx as nx
import os
import joblib

# Load models safely
backend_dir = os.path.dirname(os.path.abspath(__file__))
model = None
graph = None
kmeans_model = None

model_path = os.path.join(backend_dir, "risk_model.pkl")
graph_path = os.path.join(backend_dir, "routing_graph.pkl")
kmeans_path = os.path.join(backend_dir, "kmeans_model.pkl")

if os.path.exists(model_path):
    with open(model_path, "rb") as f:
        model = pickle.load(f)
if os.path.exists(graph_path):
    with open(graph_path, "rb") as f:
        graph = pickle.load(f)
if os.path.exists(kmeans_path):
    with open(kmeans_path, "rb") as f:
        kmeans_model = pickle.load(f)

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
    recommended_actions: List[RecommendedAction]
    affected_roads: dict = Field(default_factory=lambda: {"type": "FeatureCollection", "features": []})

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

    # 8. Determine recommended actions
    actions = []
    
    # If risk is still high after mitigations, recommend more
    if final_risk_score > 6.0:
        for event in hazards:
            actions.append(
                RecommendedAction(
                    action_type="Barricade",
                    latitude=event.latitude + 0.001,
                    longitude=event.longitude + 0.001,
                    description=f"Risk is still critical ({final_risk_score:.1f}). Deploy more barricades near the {event.event_cause} epicenter to forcefully divert traffic."
                )
            )
    elif mitigations:
        actions.append(
            RecommendedAction(
                action_type="Success",
                latitude=mitigations[0].latitude,
                longitude=mitigations[0].longitude,
                description=f"Mitigation deployed successfully. Risk reduced to {final_risk_score:.1f}. Maintain current diversion routing."
            )
        )

    # 9. Extract Road Geometries via BFS
    affected_roads_geojson = {"type": "FeatureCollection", "features": []}
    
    if graph and hazards and final_risk_score > 0:
        # Define max hops based on risk score (1 hop roughly equals 1 block/intersection)
        base_hops = int(final_risk_score * 2) 
        
        for event in hazards:
            # Find the nearest node in the graph
            # osmnx nodes usually have 'x' and 'y' attributes
            try:
                # Basic nearest node approximation (Euclidean on lat/lng)
                nearest_node = min(
                    graph.nodes(data=True),
                    key=lambda n: (n[1].get('y', 0) - event.latitude)**2 + (n[1].get('x', 0) - event.longitude)**2
                )[0]
                
                # BFS Traversal
                visited_edges = set()
                queue = [(nearest_node, 0)] # (node, current_hop_depth)
                visited_nodes = {nearest_node: 0}
                
                while queue:
                    current_node, depth = queue.pop(0)
                    
                    if depth >= base_hops:
                        continue
                        
                    for neighbor in graph.neighbors(current_node):
                        edge_data = graph.get_edge_data(current_node, neighbor)
                        # MultiDiGraph returns a dict of edges between nodes
                        if edge_data:
                            # Usually edge key 0 is the primary segment
                            edge = edge_data[0]
                            
                            # Capacity Scaling: If it's a primary road, the blast travels faster/farther
                            highway_type = edge.get('highway', 'residential')
                            # If it's a major road, it "costs" less hops to travel down it, expanding the radius along arteries!
                            hop_cost = 1
                            if isinstance(highway_type, list):
                                highway_type = highway_type[0]
                                
                            if highway_type in ['primary', 'trunk', 'motorway']:
                                hop_cost = 0.5 # Travels twice as far down main roads!
                            elif highway_type in ['secondary', 'tertiary']:
                                hop_cost = 0.8
                                
                            new_depth = depth + hop_cost
                            
                            if neighbor not in visited_nodes or new_depth < visited_nodes[neighbor]:
                                visited_nodes[neighbor] = new_depth
                                queue.append((neighbor, new_depth))
                                
                            # Avoid processing the same edge twice
                            edge_key = tuple(sorted([current_node, neighbor]))
                            if edge_key not in visited_edges:
                                visited_edges.add(edge_key)
                                
                                # Determine Color based on depth (Distance from epicenter)
                                # Depth 0 = Red [255, 50, 50]
                                # Depth max = Green [50, 255, 50]
                                # Middle = Yellow [255, 255, 50]
                                ratio = depth / float(base_hops)
                                if ratio < 0.33:
                                    color = [255, 50, 50, 200] # Red
                                elif ratio < 0.66:
                                    color = [255, 165, 0, 180] # Orange/Yellow
                                else:
                                    color = [50, 255, 50, 150] # Green
                                
                                # Get Line Geometry
                                # If 'geometry' exists (shapely LineString), use it, otherwise draw a straight line
                                coords = []
                                if 'geometry' in edge:
                                    coords = [[pt[0], pt[1]] for pt in edge['geometry'].coords]
                                else:
                                    n1 = graph.nodes[current_node]
                                    n2 = graph.nodes[neighbor]
                                    coords = [[n1['x'], n1['y']], [n2['x'], n2['y']]]
                                
                                feature = {
                                    "type": "Feature",
                                    "geometry": {
                                        "type": "LineString",
                                        "coordinates": coords
                                    },
                                    "properties": {
                                        "color": color,
                                        "eventHour": hour_map.get(event.time_of_day, 12)
                                    }
                                }
                                affected_roads_geojson["features"].append(feature)
                                
            except Exception as e:
                print(f"Error in road extraction: {e}")
                pass

    return EventSimulationResponse(
        risk_score=final_risk_score,
        requires_road_closure=requires_road_closure,
        recommended_actions=actions,
        affected_roads=affected_roads_geojson
    )
