import os
import pickle
import rustworkx as rx
import networkx as nx
import numpy as np
from scipy.spatial import KDTree
import osmnx as ox
import polyline

def generate_graph():
    print("Downloading street network for Central Bangalore...")
    # Bounding box for central Bangalore
    north, south, east, west = 13.05, 12.90, 77.65, 77.50
    
    # Download drive network
    # osmnx < 1.3: graph_from_bbox(north, south, east, west, network_type="drive")
    # osmnx >= 1.3: graph_from_bbox(bbox=(north, south, east, west), network_type="drive")
    # Actually wait, ox.graph_from_bbox(north, south, east, west, network_type="drive") works in older, but new osmnx uses bbox=(n,s,e,w).
    # To be safe, I'll use ox.graph_from_point with dist.
    
    center_point = (12.9716, 77.5946)
    G_nx = ox.graph_from_point(center_point, dist=8000, network_type="drive")
    print(f"Downloaded network with {len(G_nx.nodes)} nodes and {len(G_nx.edges)} edges.")

    # Convert to rustworkx
    print("Converting to rustworkx graph...")
    G_rx = rx.PyDiGraph()
    
    node_mapping = {}
    node_indices = {}
    
    for n, data in G_nx.nodes(data=True):
        idx = G_rx.add_node({
            'osmid': n,
            'lat': data.get('y', 0.0),
            'lon': data.get('x', 0.0)
        })
        node_mapping[n] = idx
        node_indices[n] = idx
        
    for u, v, key, data in G_nx.edges(keys=True, data=True):
        # Calculate weight (length in meters)
        weight = data.get('length', 10.0)
        
        edge_attr = {
            'weight': weight,
            'highway': data.get('highway', 'unclassified'),
            'osmid': data.get('osmid', 0)
        }
        
        # If the edge has a complex geometry (curved road), encode it as a polyline
        if 'geometry' in data:
            coords = list(data['geometry'].coords)
            # coords are (lon, lat) from shapely
            # polyline encodes (lat, lon)
            lat_lon_coords = [(pt[1], pt[0]) for pt in coords]
            encoded = polyline.encode(lat_lon_coords)
            edge_attr['polyline'] = encoded
            
        G_rx.add_edge(node_mapping[u], node_mapping[v], edge_attr)

    print("Building KDTree for spatial indexing...")
    # Build KDTree for quick spatial lookups
    coords = []
    ordered_nodes = sorted(node_indices.keys(), key=lambda n: node_indices[n])
    for n in ordered_nodes:
        data = G_nx.nodes[n]
        coords.append([data.get('y', 0.0), data.get('x', 0.0)]) # [lat, lon]
        
    kdtree = KDTree(np.array(coords))

    # Save everything
    output_data = {
        "graph": G_rx,
        "kdtree": kdtree,
        "node_indices": node_indices
    }
    
    output_path = "routing_graph.pkl"
    print(f"Saving to {output_path}...")
    with open(output_path, "wb") as f:
        pickle.dump(output_data, f)
        
    print("Done! Real graph generated successfully.")

if __name__ == "__main__":
    generate_graph()
