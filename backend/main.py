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
model = None
graph = None
if os.path.exists("risk_model.pkl"):
    with open("risk_model.pkl", "rb") as f:
        model = pickle.load(f)
if os.path.exists("routing_graph.pkl"):
    with open("routing_graph.pkl", "rb") as f:
        graph = pickle.load(f)

app = FastAPI(title="Gridlock AI Backend")

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

@app.get("/")
def read_root():
    return {"message": "Gridlock AI API is running"}

@app.post("/simulate_event", response_model=EventSimulationResponse)
def simulate_event(request: SimulationBatchRequest):
    if not request.events:
        raise HTTPException(status_code=400, detail="No events provided")

    total_risk = 0.0
    max_closure = 0.0
    actions = []

    for event in request.events:
        # Validate bounds (Rough bounding box for Bengaluru)
        if not (12.7 < event.latitude < 13.2 and 77.4 < event.longitude < 77.8):
            continue # Skip out of bounds

        # Hash coordinates to simulate different zones
        zone_cluster = (int(event.latitude * 1000) ^ int(event.longitude * 1000)) % 10
        
        # Map event cause
        cause_map = {"Accident": 2, "Vehicle Breakdown": 1, "Protest / Rally": 3, "Waterlogging": 4}
        event_type_encoded = cause_map.get(event.event_cause, 2)
        
        hour = 9 if event.time_of_day == "Morning Peak" else 15
        day_of_week = 2
        is_peak = 1 if event.time_of_day == "Morning Peak" else 0
        
        requires_road_closure = 0.5
        risk_score = 5.0
        
        if model:
            # Predict probability forcing single-thread to avoid Windows multiprocessing deadlocks
            features = np.array([[hour, day_of_week, is_peak, zone_cluster, event_type_encoded]])
            with joblib.parallel_backend('sequential'):
                probs = model.predict_proba(features)[0]
            requires_road_closure = float(probs[1])
            risk_score = requires_road_closure * 10
        
        total_risk += risk_score
        max_closure = max(max_closure, requires_road_closure)

        if graph and requires_road_closure > 0.5:
            actions.append(
                RecommendedAction(
                    action_type="Barricade",
                    latitude=event.latitude + 0.001,
                    longitude=event.longitude + 0.001,
                    description=f"Deploy barricades near {event.event_cause}. Route traffic to alternate nodes."
                )
            )
            
    # Cap total risk at 10
    final_risk = min(total_risk, 10.0)
    
    return EventSimulationResponse(
        risk_score=final_risk,
        requires_road_closure=max_closure,
        recommended_actions=actions
    )
