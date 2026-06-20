from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
import pickle
import numpy as np
import networkx as nx
import os

# Load models safely
model = None
graph = None
if os.path.exists("risk_model.pkl"):
    with open("risk_model.pkl", "rb") as f:
        model = pickle.load(f)
if os.path.exists("routing_graph.pkl"):
    with open("routing_graph.pkl", "rb") as f:
        graph = pickle.load(f)

app = FastAPI(title="Gridlock AI Backend")

class EventSimulationRequest(BaseModel):
    latitude: float = Field(..., description="Latitude of the event")
    longitude: float = Field(..., description="Longitude of the event")
    event_cause: str = Field(..., description="Cause of the event (e.g., Accident, Protest)")
    time_of_day: str = Field(..., description="Time of the event (e.g., Morning Peak)")

class RecommendedAction(BaseModel):
    action_type: str
    latitude: float
    longitude: float
    description: str

class EventSimulationResponse(BaseModel):
    risk_score: float = Field(..., description="Congestion ripple risk score from 1-10")
    requires_road_closure: float = Field(..., description="Probability of road closure 0.0-1.0")
    recommended_actions: List[RecommendedAction]

@app.get("/")
def read_root():
    return {"message": "Gridlock AI API is running"}

@app.post("/simulate_event", response_model=EventSimulationResponse)
def simulate_event(request: EventSimulationRequest):
    # Validate bounds (Rough bounding box for Bengaluru)
    if not (12.7 < request.latitude < 13.2 and 77.4 < request.longitude < 77.8):
        raise HTTPException(status_code=422, detail="Coordinates are out of bounds for Bengaluru")

    # TODO: Refine mappings for real zones
    zone_cluster = 1
    event_type_encoded = 2
    hour = 9 if request.time_of_day == "Morning Peak" else 15
    day_of_week = 2
    is_peak = 1 if request.time_of_day == "Morning Peak" else 0
    
    requires_road_closure = 0.5
    risk_score = 5.0
    
    if model:
        # Predict probability
        features = np.array([[hour, day_of_week, is_peak, zone_cluster, event_type_encoded]])
        probs = model.predict_proba(features)[0]
        requires_road_closure = float(probs[1])
        risk_score = requires_road_closure * 10
        
    actions = []
    if graph and requires_road_closure > 0.5:
        # Mock route diversion logic
        actions.append(
            RecommendedAction(
                action_type="Barricade",
                latitude=request.latitude + 0.001,
                longitude=request.longitude + 0.001,
                description="Deploy 10 barricades. Route traffic to alternate nodes."
            )
        )
    
    return EventSimulationResponse(
        risk_score=risk_score,
        requires_road_closure=requires_road_closure,
        recommended_actions=actions
    )
