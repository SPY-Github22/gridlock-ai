# Project: Gridlock Advanced ML Simulation Upgrade

## Architecture
- **Frontend**: Next.js 15, React 19, TailwindCSS, Framer Motion, Deck.gl, Mapbox.
- **Backend**: FastAPI, Python 3.11, Scikit-learn, Pandas, XGBoost, NetworkX.
- **Data Flow**: Frontend (Map, SimulatorHUD, Zustand store) -> `/simulate_scenario` (FastAPI backend) -> Classical ML Prediction & Routing (NetworkX) -> Frontend (Rendered road geometries & risk indicators).

## Milestones
| # | Name | Scope | Dependencies | Status | Conversation ID |
|---|------|-------|-------------|--------|-----------------|
| E2E | E2E Testing Track | Design and implement Tier 1-4 tests | None | DONE | 1dc14b80-2e5b-41a0-8625-c8ff446deed6 |
| I1 | ML Pipeline Upgrade | 5-Fold CV, tuning, learning curves, compound event features. NOTE: Git push trigger on completion. | None | DONE | bf886997-8def-40bf-9195-c64a9f6e75e6 |
| I2 | "What-If" Simulation Backend | `/simulate_scenario` endpoint, compound prediction inference, routing engine, edge cases | I1 | DONE | Merged into I4 |
| I3 | Frontend Map & HUD | Map drag/drop, tooltip, blast radius color, time slider, post-sim mitigations, HUD | I2 | DONE | Manually completed |
| I4 | E2E Integration & Hardening | Final E2E pass, Tier 5 adversarial tests, Forensic Audit | E2E, I3 | IN_PROGRESS | b5e94070-513b-4bec-bc25-9e4696193d7c |

## Interface Contracts
### Frontend ↔ Backend (`/simulate_scenario`)
- Request method: POST
- Content-type: application/json
- Request payload:
  ```json
  {
    "scenario_mode": "Baseline", // "Baseline" | "Future Impact" | "Optimized Strategy"
    "scrubber_hour": 8, // current timeline hour (0-23)
    "barricades": [
      { "latitude": 12.9716, "longitude": 77.5946 }
    ],
    "crowds": [
      { "latitude": 12.9720, "longitude": 77.5950, "density": 0.8 }
    ],
    "events": [
      { 
        "latitude": 12.9710, 
        "longitude": 77.5940, 
        "event_cause": "Accident", 
        "time_of_day": "Morning Peak", // legacy fallback
        "event_hour": 8 // specific hour (0-23) of the event
      }
    ]
  }
  ```
- Response payload:
  ```json
  {
    "risk_score": 5.0, // compounded batch-level risk score (1.0-10.0)
    "requires_road_closure": 0.5, // compound probability (0.0-1.0)
    "affected_roads": [
      {
        "road_id": "road_1",
        "coordinates": [[77.5946, 12.9716], [77.5950, 12.9720]],
        "congestion_score": 7.2, // ML-predicted base score
        "dynamic_congestion_score": 5.4, // time-decayed score for scrubber_hour
        "decay_factor": 0.75 // calculated decay multiplier for this road segment
      }
    ],
    "recommended_actions": [
      { "action_type": "Barricade", "latitude": 12.9716, "longitude": 77.5946, "description": "Deploy barricades" }
    ]
  }
  ```

## Code Layout
- `backend/`
  - `main.py` - API endpoints and server setup.
  - `model_training.py` - ML model training scripts.
  - `data_pipeline.py` - Data preprocessing and clustering.
  - `test_main.py` - Backend tests.
- `frontend/`
  - `src/app/page.tsx` - Main page.
  - `src/components/Map.tsx` - Deck.gl map rendering component.
  - `src/components/SimulatorHUD.tsx` - User controls, simulation mode toggle.
  - `src/store/useStore.ts` - Zustand state store.
