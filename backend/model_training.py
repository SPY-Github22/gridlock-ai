import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import StratifiedKFold, GridSearchCV, learning_curve
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, mean_absolute_error
from sklearn.ensemble import RandomForestRegressor
import rustworkx as rx
from scipy.spatial import KDTree
import pickle
import os
import sys
import polyline

# Ensure backend directory is in sys.path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

def haversine_distance(lat1, lon1, lat2, lon2):
    r = 6371.0  # Earth's radius in km
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat/2.0)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2.0)**2
    c = 2.0 * np.arcsin(np.sqrt(a))
    return r * c

def get_avg_pairwise_distance(lats, lons):
    n = len(lats)
    if n <= 1:
        return 0.0
    total_dist = 0.0
    count = 0
    for i in range(n):
        for j in range(i + 1, n):
            total_dist += haversine_distance(lats[i], lons[i], lats[j], lons[j])
            count += 1
    return total_dist / count if count > 0 else 0.0

def train_risk_model(data_path: str):
    print("Loading cleaned data for training...")
    df = pd.read_csv(data_path)
    
    # 2. Group concurrent events by rounding start_datetime to the nearest hour slot
    df['start_datetime'] = pd.to_datetime(df['start_datetime'])
    df['hour_slot'] = df['start_datetime'].dt.round('h')
    
    print("Engineering group-level features...")
    grouped_records = []
    
    for slot, group in df.groupby('hour_slot'):
        concurrent_count = len(group)
        lats = group['latitude'].values
        lons = group['longitude'].values
        avg_dist = get_avg_pairwise_distance(lats, lons)
        
        # cluster_density: max number of events in a single zone cluster
        cluster_density = int(group['zone_cluster'].value_counts().max())
        
        # Temporal features
        hour = slot.hour
        day_of_week = slot.dayofweek
        is_peak = 1 if (8 <= hour <= 11) or (17 <= hour <= 20) else 0
        
        # Target requires_road_closure: 1 if at least one event in group requires road closure, else 0
        target = 1 if (group['requires_road_closure'] == 1).any() else 0
        
        grouped_records.append({
            'concurrent_event_count': concurrent_count,
            'average_distance_between_events': avg_dist,
            'cluster_density': cluster_density,
            'hour': hour,
            'day_of_week': day_of_week,
            'is_peak': is_peak,
            'requires_road_closure': target
        })
        
    grouped_df = pd.DataFrame(grouped_records)
    print(f"Grouped events dataset created with {len(grouped_df)} rows.")
    
    # Features & Target
    features_list = ['concurrent_event_count', 'average_distance_between_events', 'cluster_density', 'hour', 'day_of_week', 'is_peak']
    X = grouped_df[features_list]
    y = grouped_df['requires_road_closure']
    
    X_arr = X.values
    y_arr = y.values
    
    # 5-Fold Stratified Cross-Validation
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    
    fold_accuracies = []
    fold_precisions = []
    fold_recalls = []
    fold_f1s = []
    fold_train_f1s = []
    
    print("Evaluating baseline XGBoost Classifier using 5-Fold Stratified CV on grouped features...")
    for fold, (train_idx, val_idx) in enumerate(skf.split(X_arr, y_arr)):
        X_train_f, X_val_f = X_arr[train_idx], X_arr[val_idx]
        y_train_f, y_val_f = y_arr[train_idx], y_arr[val_idx]
        
        model_fold = xgb.XGBClassifier(
            use_label_encoder=False, 
            eval_metric='logloss', 
            random_state=42
        )
        model_fold.fit(X_train_f, y_train_f)
        
        # Predictions
        val_preds = model_fold.predict(X_val_f)
        train_preds = model_fold.predict(X_train_f)
        
        # Scoring
        acc = accuracy_score(y_val_f, val_preds)
        prec = precision_score(y_val_f, val_preds, zero_division=0)
        rec = recall_score(y_val_f, val_preds, zero_division=0)
        f1 = f1_score(y_val_f, val_preds, zero_division=0)
        train_f1 = f1_score(y_train_f, train_preds, zero_division=0)
        
        fold_accuracies.append(acc)
        fold_precisions.append(prec)
        fold_recalls.append(rec)
        fold_f1s.append(f1)
        fold_train_f1s.append(train_f1)
        
        print(f"Fold {fold+1} - Val F1: {f1:.4f}, Val Acc: {acc:.4f}, Val Prec: {prec:.4f}, Val Rec: {rec:.4f} | Train F1: {train_f1:.4f}")
        
    mean_val_f1 = np.mean(fold_f1s)
    mean_train_f1 = np.mean(fold_train_f1s)
    mean_acc = np.mean(fold_accuracies)
    mean_prec = np.mean(fold_precisions)
    mean_rec = np.mean(fold_recalls)
    
    print("\nBaseline Model Performance Summary:")
    print(f"Mean Accuracy:  {mean_acc:.4f}")
    print(f"Mean Precision: {mean_prec:.4f}")
    print(f"Mean Recall:    {mean_rec:.4f}")
    print(f"Mean F1-Score:  {mean_val_f1:.4f}")
    print(f"Mean Train F1:  {mean_train_f1:.4f}")
    
    underfitting = mean_val_f1 < 0.60
    overfitting = (mean_train_f1 - mean_val_f1) > 0.12
    
    print(f"Underfitting detected: {underfitting} (threshold: < 0.60)")
    print(f"Overfitting detected: {overfitting} (threshold: > 0.12)")
    
    final_model = None
    
    if underfitting or overfitting:
        if underfitting:
            print("WARNING: Underfitting detected! Validation F1 is below 0.60.")
        if overfitting:
            print("WARNING: Overfitting detected! Train F1 - Validation F1 is above 0.12.")
            
        print("Triggering automated hyperparameter tuning via GridSearchCV...")
        param_grid = {
            'max_depth': [3, 5, 7],
            'learning_rate': [0.01, 0.1, 0.3],
            'n_estimators': [50, 100, 200],
            'min_child_weight': [1, 3, 5],
            'subsample': [0.8, 1.0]
        }
        
        estimator = xgb.XGBClassifier(
            use_label_encoder=False, 
            eval_metric='logloss', 
            random_state=42
        )
        
        grid_search = GridSearchCV(
            estimator=estimator,
            param_grid=param_grid,
            scoring='f1',
            cv=skf,
            n_jobs=-1,
            verbose=1
        )
        
        grid_search.fit(X_arr, y_arr)
        print(f"Best hyperparameters found: {grid_search.best_params_}")
        print(f"Best CV F1 Score: {grid_search.best_score_:.4f}")
        final_model = grid_search.best_estimator_
    else:
        print("No underfitting or overfitting detected. Training final model on entire dataset...")
        final_model = xgb.XGBClassifier(
            use_label_encoder=False, 
            eval_metric='logloss', 
            random_state=42
        )
        final_model.fit(X_arr, y_arr)
        
    # Save the final model
    model_save_path = os.path.join(backend_dir, "risk_model.pkl")
    with open(model_save_path, "wb") as f:
        pickle.dump(final_model, f)
    print(f"Final model saved to {model_save_path}")
    
    # Generate learning curves (using F1-score on train/val sets over sizes from 10% to 100%)
    print("Generating learning curves...")
    train_sizes = np.linspace(0.1, 1.0, 10)
    train_sizes_abs, train_scores, val_scores = learning_curve(
        final_model,
        X_arr,
        y_arr,
        train_sizes=train_sizes,
        cv=skf,
        scoring='f1',
        n_jobs=-1,
        random_state=42
    )
    
    train_scores_mean = np.mean(train_scores, axis=1)
    train_scores_std = np.std(train_scores, axis=1)
    val_scores_mean = np.mean(val_scores, axis=1)
    val_scores_std = np.std(val_scores, axis=1)
    
    # Headless matplotlib plotting
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    
    plt.figure(figsize=(10, 6))
    plt.plot(train_sizes * 100, train_scores_mean, 'o-', color="r", label="Training F1-score")
    plt.plot(train_sizes * 100, val_scores_mean, 'o-', color="g", label="Validation F1-score")
    plt.fill_between(train_sizes * 100, train_scores_mean - train_scores_std, train_scores_mean + train_scores_std, alpha=0.1, color="r")
    plt.fill_between(train_sizes * 100, val_scores_mean - val_scores_std, val_scores_mean + val_scores_std, alpha=0.1, color="g")
    plt.title("XGBoost Learning Curves (F1-score)")
    plt.xlabel("Training Set Size (%)")
    plt.ylabel("F1-score")
    plt.legend(loc="best")
    plt.grid(True)
    
    plot_path = os.path.join(backend_dir, "learning_curves.png")
    plt.savefig(plot_path)
    plt.close()
    print(f"Learning curves saved to {plot_path}")

def train_etr_model(data_path: str):
    print("Training ETR (Estimated Time to Resolve) model...")
    df = pd.read_csv(data_path)
    
    # Features for ETR
    # We will use hour, day_of_week, is_peak, and zone_cluster
    df = df.dropna(subset=['duration_minutes', 'hour', 'day_of_week', 'is_peak', 'zone_cluster'])
    
    features = ['hour', 'day_of_week', 'is_peak', 'zone_cluster']
    X = df[features]
    y = df['duration_minutes']
    
    etr_model = RandomForestRegressor(n_estimators=100, max_depth=10, random_state=42)
    etr_model.fit(X, y)
    
    preds = etr_model.predict(X)
    mae = mean_absolute_error(y, preds)
    print(f"ETR Model trained. Training MAE: {mae:.2f} minutes")
    
    model_save_path = os.path.join(backend_dir, "etr_model.pkl")
    with open(model_save_path, "wb") as f:
        pickle.dump(etr_model, f)
    print(f"ETR model saved to {model_save_path}")

def build_mock_routing_graph():
    """
    Builds a basic rustworkx graph simulating key traffic nodes in Bengaluru.
    Also builds a KDTree for sub-1ms node snapping.
    """
    G = rx.PyDiGraph()
    # Mock nodes with coordinates
    nodes_info = [
        {"id": "Junction_A", "lat": 12.9716, "lon": 77.5946},
        {"id": "Junction_B", "lat": 12.9720, "lon": 77.5950},
        {"id": "Junction_C", "lat": 12.9710, "lon": 77.5940},
        {"id": "Junction_D", "lat": 12.9730, "lon": 77.5960}
    ]
    
    node_indices = {}
    coords_list = []
    
    for n in nodes_info:
        idx = G.add_node(n)
        node_indices[n["id"]] = idx
        coords_list.append([n["lat"], n["lon"]])
        
    # Build polyline geometries (simulating physical road curves between intersections)
    def make_curve(n1, n2, intermediate_points=3):
        lats = np.linspace(n1["lat"], n2["lat"], intermediate_points + 2)
        lons = np.linspace(n1["lon"], n2["lon"], intermediate_points + 2)
        # Add a slight "curve" offset
        lats[1:-1] += 0.0002
        lons[1:-1] -= 0.0001
        return list(zip(lats, lons))

    c_AB = polyline.encode(make_curve(nodes_info[0], nodes_info[1]))
    c_AC = polyline.encode(make_curve(nodes_info[0], nodes_info[2]))
    c_BD = polyline.encode(make_curve(nodes_info[1], nodes_info[3]))
    c_CD = polyline.encode(make_curve(nodes_info[2], nodes_info[3]))
    
    G.add_edge(node_indices["Junction_A"], node_indices["Junction_B"], {"weight": 5.0, "highway": "primary", "polyline": c_AB})
    G.add_edge(node_indices["Junction_A"], node_indices["Junction_C"], {"weight": 3.0, "highway": "secondary", "polyline": c_AC})
    G.add_edge(node_indices["Junction_B"], node_indices["Junction_D"], {"weight": 4.0, "highway": "residential", "polyline": c_BD})
    G.add_edge(node_indices["Junction_C"], node_indices["Junction_D"], {"weight": 8.0, "highway": "primary", "polyline": c_CD})
    
    # Build KDTree
    tree = KDTree(coords_list)
    
    graph_path = os.path.join(backend_dir, "routing_graph.pkl")
    with open(graph_path, "wb") as f:
        pickle.dump({"graph": G, "kdtree": tree, "node_indices": node_indices}, f)
    print(f"Mock routing graph and KDTree saved to {graph_path}")

if __name__ == '__main__':
    # Ensure raw dataset is cleaned using backend/data_pipeline.py
    from data_pipeline import clean_data
    
    raw_data_path = r'C:\Users\sudpy\.gemini\antigravity\scratch\event_data.csv'
    cleaned_data_path = os.path.join(backend_dir, 'cleaned_events.csv')
    
    print("Cleaning raw data...")
    clean_data(raw_data_path, cleaned_data_path)
    
    # train_risk_model(cleaned_data_path) # Bypassing due to XGBoost Windows App Control Block
    train_etr_model(cleaned_data_path)
    build_mock_routing_graph()
