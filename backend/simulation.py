"""
simulation.py
-------------
ML model loading and the core risk simulation logic.
No HTTP knowledge here — just takes HazardItem / MitigationItem lists,
runs the models, calls spatial helpers, and returns an EventSimulationResponse.
"""

import os
import pickle
import joblib
from collections import Counter
from typing import List, Optional

import numpy as np
import pandas as pd

from models import (
    HazardItem,
    MitigationItem,
    RecommendedAction,
    EventSimulationResponse,
)
import spatial

# ---------------------------------------------------------------------------
# ML model singletons — loaded once at startup
# ---------------------------------------------------------------------------

_backend_dir = os.path.dirname(os.path.abspath(__file__))

risk_model = None
kmeans_model = None
etr_model = None

# Hour-of-day lookup used for feature engineering
HOUR_MAP = {
    "Morning Peak": 9,
    "Afternoon": 13,
    "Evening Peak": 18,
    "Night": 2,
    "Off-Peak": 12,
}


def load_models() -> None:
    """Load all ML models from disk. Safe to call multiple times."""
    global risk_model, kmeans_model, etr_model

    _load("risk_model.pkl", "Risk model", lambda m: globals().__setitem__("risk_model", m))
    _load("kmeans_model.pkl", "KMeans model", lambda m: globals().__setitem__("kmeans_model", m))
    _load("etr_model.pkl", "ETR model", lambda m: globals().__setitem__("etr_model", m))

    # Simpler direct assignment
    risk_model = _try_load("risk_model.pkl", "Risk model")
    kmeans_model = _try_load("kmeans_model.pkl", "KMeans model")
    etr_model = _try_load("etr_model.pkl", "ETR model")


def _try_load(filename: str, label: str):
    path = os.path.join(_backend_dir, filename)
    if not os.path.exists(path):
        print(f"{label} not found at {path}")
        return None
    try:
        with open(path, "rb") as f:
            m = pickle.load(f)
        print(f"{label} loaded successfully")
        return m
    except Exception as e:
        print(f"Could not load {label}: {e}")
        return None


def _load(filename, label, setter):
    pass  # replaced by direct assignment above


# ---------------------------------------------------------------------------
# Haversine distance
# ---------------------------------------------------------------------------

def haversine_distance(lat1, lon1, lat2, lon2) -> float:
    """Returns distance in km between two lat/lon points."""
    r = 6371.0
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return r * 2.0 * np.arcsin(np.sqrt(a))


def _avg_pairwise_distance(lats, lons) -> float:
    n = len(lats)
    if n <= 1:
        return 0.0
    total, count = 0.0, 0
    for i in range(n):
        for j in range(i + 1, n):
            total += haversine_distance(lats[i], lons[i], lats[j], lons[j])
            count += 1
    return total / count if count > 0 else 0.0


# ---------------------------------------------------------------------------
# Core simulation logic
# ---------------------------------------------------------------------------

def run_simulation_logic(
    hazards: List[HazardItem],
    mitigations: List[MitigationItem],
) -> EventSimulationResponse:
    """
    Given a list of hazard events and mitigation items, compute:
    - risk_score
    - road_closure probability
    - ETR
    - recommended actions
    - affected / spillover / detour road geometries
    """

    # ── No hazards: only mitigations (barricades etc.) ──────────────────────
    if not hazards:
        actions = [
            RecommendedAction(
                action_type="Barricade",
                latitude=m.latitude,
                longitude=m.longitude,
                description=(
                    f"Deploy barricade at ({m.latitude:.4f}, {m.longitude:.4f}) "
                    "to redirect traffic onto alternative routes."
                ),
            )
            for m in mitigations
            if m.event_cause == "Barricade"
        ]
        return EventSimulationResponse(
            risk_score=1.0,
            requires_road_closure=0.0,
            recommended_actions=actions,
            affected_roads=[],
            spillover_roads=[],
            detour_routes=[],
            detour_possible=True,
        )

    # ── Temporal features ────────────────────────────────────────────────────
    first = hazards[0]
    hour = HOUR_MAP.get(first.time_of_day, 12)
    day_of_week = 2
    is_peak = 1 if first.time_of_day in ("Morning Peak", "Evening Peak") else 0
    concurrent_count = len(hazards)

    lats = [h.latitude for h in hazards]
    lons = [h.longitude for h in hazards]
    avg_dist = _avg_pairwise_distance(lats, lons)

    # ── Zone cluster prediction ──────────────────────────────────────────────
    zone_clusters = []
    for h in hazards:
        if kmeans_model:
            # Wrap in DataFrame with the same column names used during training
            X_km = pd.DataFrame(
                [[h.latitude, h.longitude]], columns=["latitude", "longitude"]
            )
            cluster = int(kmeans_model.predict(X_km)[0])
        else:
            cluster = (int(h.latitude * 1000) ^ int(h.longitude * 1000)) % 10
        zone_clusters.append(cluster)

    cluster_density = Counter(zone_clusters).most_common(1)[0][1] if zone_clusters else 0

    # ── Baseline closure probability ─────────────────────────────────────────
    requires_road_closure = 0.5
    if risk_model:
        features = np.array([[
            concurrent_count, avg_dist, cluster_density,
            hour, day_of_week, is_peak,
        ]])
        with joblib.parallel_backend("sequential"):
            probs = risk_model.predict_proba(features)[0]
        requires_road_closure = float(probs[1])

    baseline_risk = max(1.0, min(10.0, requires_road_closure * 50.0 + 4.0))

    # ── Mitigation dampening ─────────────────────────────────────────────────
    hazard_factors = []
    for h in hazards:
        factor = 1.0
        for m in mitigations:
            dist = haversine_distance(h.latitude, h.longitude, m.latitude, m.longitude)
            if dist <= 5.0:
                factor *= 0.85 if m.event_cause == "Barricade" else 0.90
        hazard_factors.append(factor)

    avg_mitigation_factor = float(np.mean(hazard_factors)) if hazard_factors else 1.0
    final_risk_score = baseline_risk * avg_mitigation_factor

    # Scale by crowd density if present
    crowd_densities = [h.density for h in hazards if h.density is not None]
    if crowd_densities:
        final_risk_score *= 0.7 + 0.6 * float(np.mean(crowd_densities))

    final_risk_score = max(1.0, min(10.0, final_risk_score))
    requires_road_closure *= avg_mitigation_factor

    # ── ETR prediction ───────────────────────────────────────────────────────
    etr_minutes: Optional[float] = None
    if etr_model:
        etr_features = pd.DataFrame([{
            "hour": hour,
            "day_of_week": day_of_week,
            "is_peak": is_peak,
            "zone_cluster": zone_clusters[0] if zone_clusters else 0,
        }])
        etr_pred = float(etr_model.predict(etr_features)[0])
        etr_minutes = round(max(etr_pred * avg_mitigation_factor, 1.0), 1)

    # ── Recommended actions ──────────────────────────────────────────────────
    actions = []
    for h in hazards:
        etr_display = round(etr_minutes * 0.4, 0) if etr_minutes else 30
        actions.append(RecommendedAction(
            action_type="Strategy A (Aggressive)",
            latitude=h.latitude + 0.001,
            longitude=h.longitude + 0.001,
            description=(
                f"Deploy 4 Police Squads from nearest precinct due to {h.event_cause}. "
                f"Drops ETR to ~{etr_display:.0f} mins. High cost."
            ),
        ))
        actions.append(RecommendedAction(
            action_type="Strategy B (Passive)",
            latitude=h.latitude - 0.001,
            longitude=h.longitude - 0.001,
            description=(
                f"Deploy 1 Barricade due to {h.event_cause}. "
                "Risk mitigates slightly. Low resource cost."
            ),
        ))

    # ── Spatial analysis (BFS road spreading + detour routing) ───────────────
    hazard_coords = [(h.latitude, h.longitude) for h in hazards]
    barricaded_nodes = set()
    if spatial.kdtree:
        for m in mitigations:
            if m.event_cause == "Barricade":
                _, m_idx = spatial.kdtree.query([m.latitude, m.longitude])
                barricaded_nodes.add(int(m_idx))

    affected_dict, spillover_dict = spatial.compute_affected_roads(
        hazard_coords, barricaded_nodes, final_risk_score, hour
    )

    mitigation_coords = [(m.latitude, m.longitude) for m in mitigations]
    detour_routes, detour_possible = spatial.compute_detour_routes(
        hazard_coords, mitigation_coords, hour
    )

    return EventSimulationResponse(
        risk_score=final_risk_score,
        requires_road_closure=requires_road_closure,
        etr_minutes=etr_minutes,
        recommended_actions=actions,
        affected_roads=list(affected_dict.values()),
        spillover_roads=list(spillover_dict.values()),
        detour_routes=detour_routes,
        detour_possible=detour_possible,
    )
