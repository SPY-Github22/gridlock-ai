from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Traffic Simulation API is running"}

def test_simulate_event_valid():
    payload = {
        "latitude": 12.9716, # valid Bengaluru lat
        "longitude": 77.5946, # valid Bengaluru long
        "event_cause": "Accident",
        "time_of_day": "Morning Peak"
    }
    response = client.post("/simulate_event", json={"events": [payload]})
    assert response.status_code == 200
    data = response.json()
    assert "risk_score" in data
    assert "requires_road_closure" in data
    assert "recommended_actions" in data

def test_simulate_event_out_of_bounds():
    payload = {
        "latitude": 40.7128, # New York lat
        "longitude": -74.0060, # New York long
        "event_cause": "Accident",
        "time_of_day": "Morning Peak"
    }
    response = client.post("/simulate_event", json={"events": [payload]})
    assert response.status_code == 422
    assert "Coordinates are out of bounds" in response.json()["detail"]

