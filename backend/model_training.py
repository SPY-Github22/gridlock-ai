import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
import networkx as nx
import pickle

def train_risk_model(data_path: str):
    print("Loading cleaned data for training...")
    df = pd.read_csv(data_path)
    
    # Features: hour, day_of_week, is_peak, zone_cluster, event_type (encoded)
    df['event_type_encoded'] = df['event_type'].astype('category').cat.codes
    
    X = df[['hour', 'day_of_week', 'is_peak', 'zone_cluster', 'event_type_encoded']]
    y = df['requires_road_closure']
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    print("Training XGBoost Classifier...")
    model = xgb.XGBClassifier(use_label_encoder=False, eval_metric='logloss', random_state=42)
    model.fit(X_train, y_train)
    
    print("Evaluating Model...")
    preds = model.predict(X_test)
    
    acc = accuracy_score(y_test, preds)
    f1 = f1_score(y_test, preds)
    precision = precision_score(y_test, preds)
    recall = recall_score(y_test, preds)
    
    print(f"Accuracy:  {acc:.4f}")
    print(f"Precision: {precision:.4f}")
    print(f"Recall:    {recall:.4f}")
    print(f"F1-Score:  {f1:.4f}")
    
    # Save the model
    with open("risk_model.pkl", "wb") as f:
        pickle.dump(model, f)
    print("Model saved to risk_model.pkl")

def build_mock_routing_graph():
    """
    Builds a basic NetworkX graph simulating key traffic nodes in Bengaluru.
    We will use this to simulate dynamic diversions.
    """
    G = nx.Graph()
    # Mock nodes with coordinates
    nodes = {
        "Junction_A": (12.9716, 77.5946),
        "Junction_B": (12.9720, 77.5950),
        "Junction_C": (12.9710, 77.5940),
        "Junction_D": (12.9730, 77.5960)
    }
    for node, coords in nodes.items():
        G.add_node(node, pos=coords)
        
    G.add_edge("Junction_A", "Junction_B", weight=5)
    G.add_edge("Junction_A", "Junction_C", weight=3)
    G.add_edge("Junction_B", "Junction_D", weight=4)
    G.add_edge("Junction_C", "Junction_D", weight=8)
    
    with open("routing_graph.pkl", "wb") as f:
        pickle.dump(G, f)
    print("Mock routing graph saved to routing_graph.pkl")

if __name__ == '__main__':
    data_path = r'C:\Users\sudpy\.gemini\antigravity\scratch\gridlock-ai\backend\cleaned_events.csv'
    train_risk_model(data_path)
    build_mock_routing_graph()
