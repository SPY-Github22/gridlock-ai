# Traffic Simulation (Map) - Bengaluru

A real-time traffic simulation and command center built for Bangalore, tackling event-driven congestion — sudden accidents, political rallies, waterlogging, and vehicle breakdowns that paralyze the city with no warning.

## Live Demo
- **Frontend:** https://traffic-simulation-five.vercel.app
- **Backend API:** https://traffic-simulation-production.up.railway.app

## What It Does

Drop any traffic event (accident, breakdown, protest, waterlogging) on a live Bangalore map and instantly visualize how congestion will spread across the city's road network. Test police interventions like barricades and detour routes in real time.

- **Red lines** — Directly gridlocked roads
- **Purple lines** — Spillover congestion from rerouted traffic
- **Green lines** — Optimal detour routes calculated by Dijkstra's algorithm

## How It Works

1. A **Gradient Boosting ML model (R² = 0.998)** trained on **2,646 real Bangalore police incident records** predicts how severely and how far congestion will spread, based on vehicle type, incident cause, and time of day. SMOTE balancing was used to handle rare road closure events.
2. A **Breadth-First Search (BFS) algorithm** propagates the ML-predicted congestion across a custom OpenStreetMap routing graph of **134,420 nodes and 342,448 edges**.
3. When a police barricade is placed, **Dijkstra's algorithm** instantly recalculates the optimal detour route around the blocked road.
4. The frontend renders all of this live using **Next.js + DeckGL**.

## Tech Stack

| Layer | Technology |
|---|---|
| ML | Gradient Boosting, Scikit-Learn, SMOTE |
| Graph Engine | Rustworkx (134k nodes, real OSM data) |
| Backend | FastAPI + Python |
| Frontend | Next.js + DeckGL + MapLibre |
| Deployment | Railway + Vercel |

## Setup Instructions

### Backend
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8002
```

### Frontend
```bash
cd frontend
npm install
```

Create a `.env.local` file inside the `frontend` folder:
```
NEXT_PUBLIC_API_URL=http://localhost:8002
```

Then run:
```bash
npm run dev
```

Open `http://localhost:3000` in your browser.
