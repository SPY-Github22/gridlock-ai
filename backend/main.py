"""
main.py
-------
FastAPI application entry point.
Only responsible for:
  - Creating the app and registering middleware
  - Defining HTTP route handlers (thin — no business logic)
  - Delegating all work to simulation.py

Keep this file short. If you are adding logic here, it belongs in
simulation.py or spatial.py instead.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from models import (
    SimulationBatchRequest,
    SimulateScenarioRequest,
    EventSimulationResponse,
    HazardItem,
    MitigationItem,
)
from simulation import run_simulation_logic, load_models
from spatial import load_graph, load_congestion_model

# ---------------------------------------------------------------------------
# Startup — load all models and graph once
# ---------------------------------------------------------------------------

load_models()
load_graph()
load_congestion_model()

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="Gridlock Traffic Simulation API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/")
def health_check():
    import spatial
    nodes = spatial.graph.num_nodes() if spatial.graph else 0
    return {"message": "Traffic Simulation API is running", "nodes": nodes}


@app.post("/simulate_event", response_model=EventSimulationResponse)
def simulate_event(request: SimulationBatchRequest):
    """
    Main simulation endpoint.
    Accepts a batch of map pins (events) and returns risk scores,
    affected road geometries, spillover roads, and detour routes.
    """
    if not request.events:
        raise HTTPException(status_code=400, detail="No events provided")

    hazards, mitigations = [], []
    for e in request.events:
        if e.event_cause in ("Barricade", "Police Squad", "VMS", "Green Wave"):
            mitigations.append(MitigationItem(
                latitude=e.latitude,
                longitude=e.longitude,
                event_cause=e.event_cause,
            ))
        else:
            hazards.append(HazardItem(
                latitude=e.latitude,
                longitude=e.longitude,
                event_cause=e.event_cause,
                time_of_day=e.time_of_day,
                vehicle_type=e.vehicle_type,
            ))

    return run_simulation_logic(hazards, mitigations)


@app.post("/simulate_scenario", response_model=EventSimulationResponse)
def simulate_scenario(request: SimulateScenarioRequest):
    """
    Scenario comparison endpoint.
    Supports three modes:
      - Baseline:           only base events, no mitigations
      - Future Impact:      base events + crowd congestion
      - Optimized Strategy: base events + crowds + barricades
    """
    first_tod = request.events[0].time_of_day if request.events else "Morning Peak"

    hazards, mitigations = [], []

    # Base hazard events (all modes)
    for e in request.events:
        hazards.append(HazardItem(
            latitude=e.latitude,
            longitude=e.longitude,
            event_cause=e.event_cause,
            time_of_day=e.time_of_day,
            vehicle_type=e.vehicle_type,
        ))

    # Crowd hazards (Future Impact + Optimized Strategy)
    if request.scenario_mode in ("Future Impact", "Optimized Strategy"):
        for c in request.crowds:
            item = HazardItem(
                latitude=c.latitude,
                longitude=c.longitude,
                event_cause="Protest / Rally",
                time_of_day=first_tod,
                vehicle_type="Car/Taxi",
            )
            item.density = c.density
            hazards.append(item)

    # Barricade mitigations (Optimized Strategy only)
    if request.scenario_mode == "Optimized Strategy":
        for b in request.barricades:
            mitigations.append(MitigationItem(
                latitude=b.latitude,
                longitude=b.longitude,
                event_cause="Barricade",
            ))

    return run_simulation_logic(hazards, mitigations)


@app.get("/network")
def get_network():
    """
    Returns a GeoJSON FeatureCollection of the city's major road network
    for the frontend to use as a static overlay.
    """
    from spatial import get_full_network
    features = get_full_network()
    return {
        "type": "FeatureCollection",
        "features": features
    }

