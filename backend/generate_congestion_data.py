"""
generate_congestion_data.py
----------------------------
Generates a road-segment-level training dataset for the congestion weight model.

For each real incident in cleaned_events.csv, we synthesise road-edge observations
at 4 distance bands with inferred congestion weights. The ML model will learn the
relationship between (road_type, distance, time, incident_features) → congestion weight.

This is the ground truth derivation logic:
  - Incidents that required road closure and took long to resolve had high congestion
  - Congestion decays with distance from the incident
  - Road type modulates how easily congestion propagates
  - Time of day and vehicle type affect severity

Output: backend/congestion_training_data.csv
"""

import pandas as pd
import numpy as np
import os

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))

# Distance bands: (min_km, max_km, base_weight)
# The closer to the incident, the higher the congestion weight
DISTANCE_BANDS = [
    (0.0,  0.5,  1.00),
    (0.5,  1.0,  0.65),
    (1.0,  2.0,  0.35),
    (2.0,  5.0,  0.12),
]

# Road type encoding and its resistance to congestion
# Lower resistance = congestion spreads more easily (highways flow better)
# Higher resistance = road gets blocked more easily (small roads)
ROAD_TYPES = {
    0: "motorway_primary",   # motorway, trunk, primary
    1: "secondary_tertiary", # secondary, tertiary
    2: "residential",        # residential, unclassified, living_street
}

# How much does each road type amplify congestion weight at close range?
ROAD_TYPE_MULTIPLIER = {
    0: 0.55,  # Primary roads: congestion spreads but flows through
    1: 0.85,  # Secondary: moderate congestion
    2: 1.30,  # Residential: easily gridlocked
}

# Cause severity index (how much does this cause amplify congestion radius?)
CAUSE_SEVERITY = {
    'Accident':          1.0,
    'Vehicle Breakdown': 0.75,
    'Waterlogging':      1.30,
    'Protest / Rally':   1.20,
    'Other':             0.60,
}

# Vehicle type severity
VEHICLE_SEVERITY = {
    'Heavy Truck':         1.60,
    'LCV (Light Commercial)': 1.10,
    'Car/Taxi':            1.00,
    'Two-Wheeler':         0.55,
    '':                    1.00,
}

def normalize_duration(duration_minutes: float, p5: float, p95: float) -> float:
    """Normalize duration to 0–1 range using 5th/95th percentile clipping."""
    clipped = max(p5, min(p95, duration_minutes))
    return (clipped - p5) / (p95 - p5 + 1e-6)


def generate_observations(df: pd.DataFrame) -> pd.DataFrame:
    """
    For each incident, generate synthetic road-edge observations
    across all road types and distance bands.
    """
    p5  = df['duration_minutes'].quantile(0.05)
    p95 = df['duration_minutes'].quantile(0.95)

    records = []

    for _, row in df.iterrows():
        # Incident-level features
        hour        = int(row.get('hour', 12))
        day_of_week = int(row.get('day_of_week', 0))
        is_peak     = int(row.get('is_peak', 0))
        zone_cluster = int(row.get('zone_cluster', 0))
        requires_closure = int(row.get('requires_road_closure', 0))
        duration    = float(row.get('duration_minutes', 30))
        cause       = str(row.get('event_cause', 'Other'))
        veh_type    = str(row.get('veh_type', ''))

        # Severity multipliers learned from data features
        duration_norm   = normalize_duration(duration, p5, p95)
        cause_sev       = CAUSE_SEVERITY.get(cause, 0.80)
        veh_sev         = VEHICLE_SEVERITY.get(veh_type, 1.00)
        closure_boost   = 1.25 if requires_closure else 1.00

        # Combined severity scalar for this incident
        incident_severity = duration_norm * cause_sev * veh_sev * closure_boost
        # Clip to [0.05, 2.0] so extremes don't dominate
        incident_severity = max(0.05, min(2.0, incident_severity))

        # Cause OHE flags
        cause_accident    = 1 if cause == 'Accident'          else 0
        cause_breakdown   = 1 if cause == 'Vehicle Breakdown' else 0
        cause_waterlog    = 1 if cause == 'Waterlogging'      else 0
        cause_protest     = 1 if cause == 'Protest / Rally'   else 0

        # Vehicle OHE flags
        veh_truck   = 1 if veh_type == 'Heavy Truck'            else 0
        veh_car     = 1 if veh_type == 'Car/Taxi'               else 0
        veh_two     = 1 if veh_type == 'Two-Wheeler'            else 0
        veh_lcv     = 1 if veh_type == 'LCV (Light Commercial)' else 0

        # Generate one observation per road_type × distance_band
        for road_type_idx, road_type_name in ROAD_TYPES.items():
            road_multiplier = ROAD_TYPE_MULTIPLIER[road_type_idx]

            for (dist_min, dist_max, band_weight) in DISTANCE_BANDS:
                # Sample a specific distance within the band
                dist_km = (dist_min + dist_max) / 2.0

                # Congestion weight: base band weight × road type × incident severity
                raw_weight = band_weight * road_multiplier * incident_severity

                # Peak-hour boost: congestion is harder to clear at peak
                if is_peak:
                    raw_weight *= 1.15

                # Clip to valid [0.0, 1.0] range
                congestion_weight = float(np.clip(raw_weight, 0.0, 1.0))

                records.append({
                    # Features
                    'road_type':          road_type_idx,
                    'dist_from_hazard_km': dist_km,
                    'hour':               hour,
                    'day_of_week':        day_of_week,
                    'is_peak':            is_peak,
                    'zone_cluster':       zone_cluster,
                    'requires_closure':   requires_closure,
                    'duration_norm':      round(duration_norm, 4),
                    'cause_accident':     cause_accident,
                    'cause_breakdown':    cause_breakdown,
                    'cause_waterlog':     cause_waterlog,
                    'cause_protest':      cause_protest,
                    'veh_truck':          veh_truck,
                    'veh_car':            veh_car,
                    'veh_two_wheeler':    veh_two,
                    'veh_lcv':            veh_lcv,
                    # Target
                    'congestion_weight':  congestion_weight,
                })

    return pd.DataFrame(records)


def main():
    data_path = os.path.join(BACKEND_DIR, 'cleaned_events.csv')
    print(f"Loading incidents from {data_path} ...")
    df = pd.read_csv(data_path)
    print(f"  {len(df)} incidents loaded.")

    print("Generating road-segment congestion observations ...")
    out_df = generate_observations(df)
    print(f"  {len(out_df)} road-segment observations generated.")
    print(f"  congestion_weight stats:\n{out_df['congestion_weight'].describe()}")

    out_path = os.path.join(BACKEND_DIR, 'congestion_training_data.csv')
    out_df.to_csv(out_path, index=False)
    print(f"\nSaved to {out_path}")
    return out_df


if __name__ == '__main__':
    main()
