# Gridlock AI - Bangalore Event & Traffic Simulation

Gridlock AI is an interactive geospatial intelligence platform built for predicting and managing traffic impact during major events in Bangalore. It uses advanced spatial modeling, real-time data integration, and a high-performance 3D mapping interface to empower city planners and law enforcement with actionable insights.

## Core Features
*   **Spatial Prediction**: Predicts zones of impact along actual Bangalore roads with colored separation for easy visualization.
*   **3D Interactive Map**: Powered by Deck.gl and Mapbox, rendering thousands of data points with glassmorphism UI.
*   **Event Impact Analysis**: Dynamically estimates crowds, group movements, and destinations.
*   **Simulation Engine**: Allows interactive placement of barricades, diversions, and resource deployment, calculating real-time impact.

## Architecture
*   **Frontend**: Next.js 15, React 19, TailwindCSS, Framer Motion, Deck.gl, Mapbox.
*   **Backend**: FastAPI, Python 3.11, Scikit-learn, Pandas.

## Setup Instructions

### Backend
1. Navigate to the `backend` directory.
2. Install dependencies: `pip install -r requirements.txt`
3. Run the server: `uvicorn main:app --reload`

### Frontend
1. Navigate to the `frontend` directory.
2. Install dependencies: `npm install`
3. Start the dev server: `npm run dev`
4. Access at `http://localhost:3000`
