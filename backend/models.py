"""
models.py
---------
All Pydantic request/response models and internal dataclasses.
No business logic here — just data shapes and validation.
"""

from pydantic import BaseModel, Field, validator
from typing import List, Optional, Union, Literal
from validators import validate_latitude, validate_longitude


# ---------------------------------------------------------------------------
# Internal dataclasses (not serialised — used inside Python only)
# ---------------------------------------------------------------------------

class HazardItem:
    """Represents a traffic hazard event used inside simulation logic."""

    def __init__(
        self,
        latitude: float,
        longitude: float,
        event_cause: str,
        time_of_day: str,
        vehicle_type: str = "Car/Taxi",
    ):
        self.latitude = latitude
        self.longitude = longitude
        self.event_cause = event_cause
        self.time_of_day = time_of_day
        self.vehicle_type = vehicle_type
        self.density: Optional[float] = None


class MitigationItem:
    """Represents a traffic mitigation resource (barricade, police squad)."""

    def __init__(self, latitude: float, longitude: float, event_cause: str):
        self.latitude = latitude
        self.longitude = longitude
        self.event_cause = event_cause


# ---------------------------------------------------------------------------
# API Request models
# ---------------------------------------------------------------------------

class BarricadeRequest(BaseModel):
    latitude: float
    longitude: float

    _val_lat = validator("latitude", pre=True, allow_reuse=True)(validate_latitude)
    _val_lon = validator("longitude", pre=True, allow_reuse=True)(validate_longitude)


class CrowdRequest(BaseModel):
    latitude: float
    longitude: float
    density: float

    _val_lat = validator("latitude", pre=True, allow_reuse=True)(validate_latitude)
    _val_lon = validator("longitude", pre=True, allow_reuse=True)(validate_longitude)

    @validator("density", pre=True)
    def check_density(cls, v):
        if v is None or not isinstance(v, (int, float)) or isinstance(v, bool):
            raise TypeError("Density must be a float or integer")
        v = float(v)
        if not (0.0 <= v <= 1.0):
            raise ValueError("Density must be between 0.0 and 1.0")
        return v


class EventSimulationRequest(BaseModel):
    latitude: float = Field(..., description="Latitude of the event")
    longitude: float = Field(..., description="Longitude of the event")
    event_cause: Literal[
        "Accident",
        "Vehicle Breakdown",
        "Protest / Rally",
        "Waterlogging",
        "Barricade",
        "Police Squad",
    ] = Field(..., description="Cause of the event")
    time_of_day: Literal[
        "Morning Peak", "Evening Peak", "Off-Peak", "Afternoon", "Night"
    ] = Field(..., description="Time of the event")
    vehicle_type: str = Field(default="Car/Taxi", description="Type of vehicle involved")

    _val_lat = validator("latitude", pre=True, allow_reuse=True)(validate_latitude)
    _val_lon = validator("longitude", pre=True, allow_reuse=True)(validate_longitude)


class ScenarioEventRequest(BaseModel):
    latitude: float
    longitude: float
    event_cause: Literal[
        "Accident", "Vehicle Breakdown", "Protest / Rally", "Waterlogging"
    ]
    time_of_day: Literal[
        "Morning Peak", "Evening Peak", "Off-Peak", "Afternoon", "Night"
    ]
    vehicle_type: str = Field(default="Car/Taxi")

    _val_lat = validator("latitude", pre=True, allow_reuse=True)(validate_latitude)
    _val_lon = validator("longitude", pre=True, allow_reuse=True)(validate_longitude)


class SimulationBatchRequest(BaseModel):
    """Request body for /simulate_event — a list of placed map pins."""
    events: List[EventSimulationRequest]


class SimulateScenarioRequest(BaseModel):
    """Request body for /simulate_scenario — structured multi-mode scenario."""
    scenario_mode: Literal["Baseline", "Future Impact", "Optimized Strategy"]
    barricades: List[BarricadeRequest]
    crowds: List[CrowdRequest]
    events: List[ScenarioEventRequest]


# ---------------------------------------------------------------------------
# API Response models
# ---------------------------------------------------------------------------

class RecommendedAction(BaseModel):
    action_type: str
    latitude: float
    longitude: float
    description: str


class EventSimulationResponse(BaseModel):
    risk_score: float = Field(..., description="Congestion ripple risk score 1-10")
    requires_road_closure: float = Field(..., description="Probability of road closure 0.0-1.0")
    etr_minutes: Optional[float] = Field(None, description="Estimated Time to Resolve in minutes")
    recommended_actions: List[RecommendedAction]
    affected_roads: Union[dict, List[dict]] = Field(default_factory=list)
    spillover_roads: Union[dict, List[dict]] = Field(default_factory=list)
    detour_routes: Union[dict, List[dict]] = Field(default_factory=list)
    detour_possible: bool = Field(True, description="False if barricade blocked a chokepoint")
