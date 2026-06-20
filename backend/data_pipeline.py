import pandas as pd
from sklearn.cluster import KMeans
import os

def clean_data(input_path: str, output_path: str):
    print("Loading dataset...")
    df = pd.read_csv(input_path)
    
    # 1. Clean Geospatial Data
    print("Cleaning geospatial coordinates...")
    # Drop rows without lat/long
    df = df.dropna(subset=['latitude', 'longitude'])
    # Filter roughly for Bengaluru bounding box
    df = df[(df['latitude'] > 12.7) & (df['latitude'] < 13.2) & 
            (df['longitude'] > 77.4) & (df['longitude'] < 77.8)]
    
    # 2. Extract Temporal Features
    print("Extracting temporal features...")
    df['start_datetime'] = pd.to_datetime(df['start_datetime'], errors='coerce')
    df = df.dropna(subset=['start_datetime'])
    df['hour'] = df['start_datetime'].dt.hour
    df['day_of_week'] = df['start_datetime'].dt.dayofweek
    df['is_peak'] = df['hour'].apply(lambda x: 1 if (8 <= x <= 11) or (17 <= x <= 20) else 0)
    
    # 3. Handle Missing Values
    print("Handling missing values...")
    # Fill categorical missing values
    df['event_cause'] = df['event_cause'].fillna('Unknown')
    df['priority'] = df['priority'].fillna('Medium')
    
    # Target variables mapping
    # requires_road_closure is boolean, convert to int
    df['requires_road_closure'] = df['requires_road_closure'].astype(int)
    
    # 4. K-Means Clustering for Functional Zones
    print("Clustering coordinates to find functional zones...")
    coords = df[['latitude', 'longitude']]
    # Assuming ~15 distinct choke point zones in Bengaluru
    kmeans = KMeans(n_clusters=15, random_state=42, n_init=10)
    df['zone_cluster'] = kmeans.fit_predict(coords)
    
    # Save cleaned dataset
    df.to_csv(output_path, index=False)
    print(f"Data pipeline complete! Saved {len(df)} cleaned rows to {output_path}")

if __name__ == '__main__':
    input_file = r'C:\Users\sudpy\.gemini\antigravity\scratch\event_data.csv'
    output_file = r'C:\Users\sudpy\.gemini\antigravity\scratch\gridlock-ai\backend\cleaned_events.csv'
    
    if os.path.exists(input_file):
        clean_data(input_file, output_file)
    else:
        print(f"Error: {input_file} not found. Please ensure the EDA script ran successfully.")
