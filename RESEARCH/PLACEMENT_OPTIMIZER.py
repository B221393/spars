import numpy as np

# --- Research: Target Placement Simulator & Optimizer (V2) ---
# Goal: Find the configuration that minimizes overall uncertainty.
# V2: Implements a simple random search to find optimal coordinates.

def calculate_coverage(targets):
    grid_x, grid_y = np.mgrid[0:1000:50, 0:1000:50]
    grid_points = np.vstack([grid_x.ravel(), grid_y.ravel()]).T
    
    max_dists = []
    for gp in grid_points:
        dists = np.linalg.norm(targets - gp, axis=1)
        max_dists.append(np.min(dists))
    
    return np.mean(max_dists)

def optimize_placement(n_targets, iterations=100):
    print(f"🔭 Optimizing placement for {n_targets} targets (Random Search)...")
    best_targets = None
    best_score = float('inf')
    
    for _ in range(iterations):
        current_targets = np.random.rand(n_targets, 2) * 1000
        score = calculate_coverage(current_targets)
        if score < best_score:
            best_score = score
            best_targets = current_targets
            
    print(f"✅ Optimization Complete: Best Mean Coverage Distance = {best_score:.2f} px")
    return best_targets, best_score

if __name__ == "__main__":
    for n in [4, 9, 16]:
        best_t, best_s = optimize_placement(n, iterations=200)
