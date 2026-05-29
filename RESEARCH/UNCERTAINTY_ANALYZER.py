import numpy as np
import pandas as pd
import os

# --- Research: Measurement Uncertainty Analyzer (V1) ---
# This script calculates the uncertainty (standard deviation, error range) 
# of the tracked positions to evaluate the system's reliability.

def analyze_uncertainty(csv_path):
    if not os.path.exists(csv_path):
        print(f"⚠️ CSV file not found: {csv_path}")
        return
    
    print(f"📊 Analyzing uncertainty for: {csv_path}")
    df = pd.read_csv(csv_path)
    
    # Normalize column names to lowercase for consistency
    df.columns = [c.lower() for c in df.columns]
    id_col = 'dotid' if 'dotid' in df.columns else 'id'
    x_col = 'x'
    y_col = 'y'

    if id_col not in df.columns:
        print(f"❌ Error: Required ID column not found in {df.columns}")
        return

    # Calculate standard deviation of coordinates for each ID
    results = []
    for pt_id in df[id_col].unique():
        subset = df[df[id_col] == pt_id]
        if len(subset) > 1:
            std_x = subset[x_col].std()
            std_y = subset[y_col].std()
            results.append({
                'id': pt_id,
                'std_x': std_x,
                'std_y': std_y,
                'samples': len(subset)
            })
    
    if results:
        res_df = pd.DataFrame(results)
        print("\n--- Uncertainty Summary ---")
        print(res_df)
        
        # Save analysis
        output_path = csv_path.replace(".csv", "_uncertainty.csv")
        res_df.to_csv(output_path, index=False)
        print(f"✅ Uncertainty analysis saved to: {output_path}")
        
        avg_noise = (res_df['std_x'].mean() + res_df['std_y'].mean()) / 2
        print(f"💡 Average System Noise Estimate: {avg_noise:.4f} pixels")
    else:
        print("⚠️ Not enough data points to calculate uncertainty.")

if __name__ == "__main__":
    TARGET_CSV = r"C:\Users\yu_ci\Desktop\GENRE_FOLDERS\RESEARCH\tracking_data_pro.csv"
    if not os.path.exists(TARGET_CSV):
        TARGET_CSV = "tracking_data_export.csv"
    
    analyze_uncertainty(TARGET_CSV)
