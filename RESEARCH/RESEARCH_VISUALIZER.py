import pandas as pd
import matplotlib.pyplot as plt
import os

# --- Research: Automated Result Visualizer (V1) ---
# Generates high-quality plots for research papers and presentations.
# Part of the Python Data Pipeline (RESEARCH_TODO.md #3)

def generate_report_plots(csv_path, output_dir):
    if not os.path.exists(csv_path):
        print(f"⚠️ CSV file not found: {csv_path}")
        return

    print(f"📊 Generating visualization for: {csv_path}")
    df = pd.read_csv(csv_path)
    
    # Ensure lowercase columns
    df.columns = [c.lower() for c in df.columns]
    
    # 1. Trajectory Plot (Original vs Refined)
    plt.figure(figsize=(10, 8))
    for pt_id in df['id'].unique()[:5]: # Plot first 5 points
        subset = df[df['id'] == pt_id]
        plt.plot(subset['x'], subset['y'], 'o', alpha=0.3, label=f'ID:{pt_id} (Raw)')
        if 'x_refined' in df.columns:
            plt.plot(subset['x_refined'], subset['y_refined'], '-', linewidth=2, label=f'ID:{pt_id} (Refined)')
    
    plt.title("Trajectory Tracking: Raw vs Physics-Refined")
    plt.xlabel("X Position (px)")
    plt.ylabel("Y Position (px)")
    plt.legend()
    plt.grid(True)
    traj_plot = os.path.join(output_dir, "trajectory_comparison.png")
    plt.savefig(traj_plot)
    print(f"✅ Trajectory plot saved: {traj_plot}")

    # 2. Velocity Distribution
    if 'velocity' in df.columns:
        plt.figure(figsize=(10, 6))
        plt.hist(df[df['velocity'] > 0]['velocity'], bins=30, color='blue', alpha=0.7)
        plt.title("Velocity Distribution Profile")
        plt.xlabel("Velocity (px/sec)")
        plt.ylabel("Frequency")
        plt.grid(True)
        vel_plot = os.path.join(output_dir, "velocity_distribution.png")
        plt.savefig(vel_plot)
        print(f"✅ Velocity plot saved: {vel_plot}")

if __name__ == "__main__":
    TARGET_CSV = r"C:\Users\yu_ci\Desktop\GENRE_FOLDERS\RESEARCH\tracking_data_pro_refined.csv"
    OUTPUT_DIR = r"C:\Users\yu_ci\Desktop\GENRE_FOLDERS\RESEARCH\BATCH_RESULTS"
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    generate_report_plots(TARGET_CSV, OUTPUT_DIR)
