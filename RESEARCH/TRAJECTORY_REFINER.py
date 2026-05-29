import pandas as pd
import numpy as np
import os

# --- Research: Physics-Based Trajectory Refiner (V1) ---
# Uses Moving Average and Uncertainty data to filter out jitter/noise.

def refine_trajectories(csv_path, window_size=5):
    if not os.path.exists(csv_path):
        print(f"⚠️ CSV file not found: {csv_path}")
        return

    print(f"🧹 Refining trajectories for: {csv_path}")
    df = pd.read_csv(csv_path)
    df.columns = [c.lower() for c in df.columns]
    id_col = 'dotid' if 'dotid' in df.columns else 'id'

    refined_data = []
    for pt_id in df[id_col].unique():
        subset = df[df[id_col] == pt_id].sort_values('frame')
        if len(subset) >= window_size:
            # Apply Moving Average for X and Y
            subset['x_refined'] = subset['x'].rolling(window=window_size, center=True).mean().fillna(subset['x'])
            subset['y_refined'] = subset['y'].rolling(window=window_size, center=True).mean().fillna(subset['y'])
        else:
            subset['x_refined'] = subset['x']
            subset['y_refined'] = subset['y']
        refined_data.append(subset)

    final_df = pd.concat(refined_data)
    output_path = csv_path.replace(".csv", "_refined.csv")
    final_df.to_csv(output_path, index=False)
    print(f"✅ Refined data saved to: {output_path}")

if __name__ == "__main__":
    # GENRE_FOLDERS/RESEARCH 内のCSVを優先的に探す
    TARGET_CSV = r"C:\Users\yu_ci\Desktop\GENRE_FOLDERS\RESEARCH\tracking_data_pro.csv"
    if not os.path.exists(TARGET_CSV):
        TARGET_CSV = "tracking_data_export.csv"
    
    refine_trajectories(TARGET_CSV)
