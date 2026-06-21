# plan.md — Gridlock AI Final System Audit Plan

## Objective
Coordinate technical execution to align the FastAPI backend with the Next.js frontend, verify mathematical correctness, and ensure all automated tests pass successfully.

## Phase 1: Exploration
- **Subagent**: Explorer (`teamwork_preview_explorer`)
- **Focus**:
  - Inspect backend ML features in `backend/main.py`, `backend/model_training.py`, `backend/data_pipeline.py`. Check the feature count (exactly 6 features).
  - Check the `baseline_risk` scaling and the `rustworkx` Exponential Capacity Decay (`base_hops`) logic.
  - Locate routing code in backend to see how events map and why they might hang or fail.
  - Inspect frontend React files (`frontend/src/components/Map.tsx`, `frontend/src/components/SimulatorHUD.tsx`) to identify where Deck.gl layers are drawn, where pins are colored, and how "Simulate Impact" is invoked.
  - Identify where the "Vehicle Type" control is rendered and how to hide it when placing barricades.

## Phase 2: Execution / Implementation
- **Subagent**: Worker (`teamwork_preview_worker`)
- **Tasks**:
  - Update ML backend to ensure the classifier ingests exactly 6 features.
  - Fix probability scaling (`baseline_risk`) and `rustworkx` base_hops capacity decay.
  - Correct pin colors in frontend (Hazards = Neon Cyan, Barricades = Orange, Police = Royal Blue).
  - Add pulse animation/dynamic radius for Hazards post-simulation, and set a fixed radius of ~30m for mitigations.
  - Hide irrelevant controls (like "Vehicle Type" for barricades).
  - Ensure the simulation is fully deterministic and Strategy HUD recommendations push correctly.
  - Make sure "Simulate Impact" resolves and does not get stuck in a loading state.

## Phase 3: Verification & Auditing
- **Subagents**: Reviewer (`teamwork_preview_reviewer`), Challenger (`teamwork_preview_challenger`), Forensic Auditor (`teamwork_preview_auditor`).
- **Gating**:
  - Reviewers verify code correctness and clean style.
  - Challengers run differential tests on risk scores and verify that barricades reduce risk by 15%.
  - Forensic Auditor runs checks for hardcoding, facades, and other cheating methods.

## Phase 4: Final Acceptance
- **Validation**:
  - Run `pytest backend/test_edge_cases.py` and `python -m pytest tests/` and verify a 100% pass rate.
  - Verify that the frontend map successfully displays JSON paths and that barricade placement reduces risk.
