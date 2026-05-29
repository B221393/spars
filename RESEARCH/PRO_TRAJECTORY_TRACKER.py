import cv2
import numpy as np
import csv
import os
import glob
from scipy.optimize import linear_sum_assignment
import matplotlib.pyplot as plt
import sys

# Windows環境での文字コードエラーを防ぐための設定
if sys.platform.startswith('win'):
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# --- 高精度軌跡トラッキング・研究用プロツール (V4) ---
# 1. Kalman Filter実装：一時的に見失った点の位置を物理法則に基づき推定
# 2. オクルージョン対応：重なりや瞬きがあっても軌跡を維持
# 3. 物理量解析（速度・加速度）

class SimpleKalman:
    def __init__(self, initial_pos):
        self.state = np.array([initial_pos[0], initial_pos[1], 0, 0], dtype=np.float32)
        self.F = np.array([[1, 0, 1, 0], [0, 1, 0, 1], [0, 0, 1, 0], [0, 0, 0, 1]], dtype=np.float32)
        self.H = np.array([[1, 0, 0, 0], [0, 1, 0, 0]], dtype=np.float32)
        self.Q = np.eye(4, dtype=np.float32) * 0.1
        self.R = np.eye(2, dtype=np.float32) * 1.0
        self.P = np.eye(4, dtype=np.float32)

    def predict(self):
        self.state = self.F @ self.state
        self.P = self.F @ self.P @ self.F.T + self.Q
        return self.state[:2]

    def update(self, measurement):
        z = np.array(measurement, dtype=np.float32)
        y = z - self.H @ self.state
        S = self.H @ self.P @ self.H.T + self.R
        K = self.P @ self.H.T @ np.linalg.inv(S)
        self.state = self.state + K @ y
        self.P = (np.eye(4) - K @ self.H) @ self.P
        return self.state[:2]

class TrackedPoint:
    def __init__(self, pt_id, initial_pos, frame_idx, fps):
        self.id = pt_id
        self.history = {frame_idx: initial_pos} 
        self.velocities = {}
        self.last_pos = initial_pos
        self.lost_frames = 0
        self.fps = fps
        self.kf = SimpleKalman(initial_pos)

    def update(self, new_pos, frame_idx):
        self.kf.update(new_pos)
        dist = np.sqrt((new_pos[0] - self.last_pos[0])**2 + (new_pos[1] - self.last_pos[1])**2)
        self.velocities[frame_idx] = dist * self.fps
        self.history[frame_idx] = new_pos
        self.last_pos = new_pos
        self.lost_frames = 0

    def predict_next(self, frame_idx):
        pred_pos = self.kf.predict()
        self.history[frame_idx] = (int(pred_pos[0]), int(pred_pos[1]))
        self.last_pos = self.history[frame_idx]
        self.lost_frames += 1

def process_video(video_path, base_output_dir):
    video_name = os.path.splitext(os.path.basename(video_path))[0]
    output_dir = os.path.join(base_output_dir, video_name)
    if not os.path.exists(output_dir): os.makedirs(output_dir)
    output_csv = os.path.join(output_dir, f"{video_name}_data_v4.csv")
    output_video = os.path.join(output_dir, f"{video_name}_tracking_v4.mp4")

    print(f"\n🎬 高度解析開始: {video_path}")
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    out_vid = cv2.VideoWriter(output_video, cv2.VideoWriter_fourcc(*'mp4v'), fps, (w, h))

    tracked_points = []
    next_id = 0
    max_lost_frames = 30
    dist_threshold = 70
    np.random.seed(42)
    colors = np.random.randint(0, 255, (1000, 3)).tolist()

    frame_idx = 0
    while True:
        ret, frame = cap.read()
        if not ret: break
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        curr_centroids = []
        for c in contours:
            if cv2.contourArea(c) > 10:
                M = cv2.moments(c)
                if M["m00"] != 0:
                    curr_centroids.append((int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"])))
        
        if not tracked_points:
            for pt in curr_centroids:
                tracked_points.append(TrackedPoint(next_id, pt, frame_idx, fps))
                next_id += 1
        else:
            if len(curr_centroids) > 0:
                cost_matrix = np.zeros((len(tracked_points), len(curr_centroids)))
                for i, tp in enumerate(tracked_points):
                    pred = tp.kf.predict()
                    for j, cp in enumerate(curr_centroids):
                        dist = np.sqrt((pred[0] - cp[0])**2 + (pred[1] - cp[1])**2)
                        cost_matrix[i, j] = dist
                
                row_ind, col_ind = linear_sum_assignment(cost_matrix)
                matched_t, matched_c = set(), set()
                for r, c in zip(row_ind, col_ind):
                    if cost_matrix[r, c] < dist_threshold:
                        tracked_points[r].update(curr_centroids[c], frame_idx)
                        matched_t.add(r); matched_c.add(c)
                
                for i in range(len(tracked_points)):
                    if i not in matched_t: tracked_points[i].predict_next(frame_idx)
                for j in range(len(curr_centroids)):
                    if j not in matched_c:
                        tracked_points.append(TrackedPoint(next_id, curr_centroids[j], frame_idx, fps))
                        next_id += 1
            else:
                for tp in tracked_points: tp.predict_next(frame_idx)

        display_frame = frame.copy()
        for tp in tracked_points:
            if frame_idx in tp.history:
                curr_pos = tp.history[frame_idx]
                color = colors[tp.id % 1000]
                marker = cv2.MARKER_CROSS if tp.lost_frames > 0 else cv2.MARKER_STAR
                cv2.drawMarker(display_frame, curr_pos, color, marker, 10, 1)
                cv2.putText(display_frame, f"ID:{tp.id}", (curr_pos[0]+5, curr_pos[1]-5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)

        out_vid.write(display_frame)
        frame_idx += 1
        tracked_points = [tp for tp in tracked_points if tp.lost_frames < max_lost_frames]

    cap.release()
    out_vid.release()
    
    # Save CSV
    with open(output_csv, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["frame", "id", "x", "y", "velocity"])
        for tp in tracked_points:
            for f_idx, pos in tp.history.items():
                v = tp.velocities.get(f_idx, 0)
                writer.writerow([f_idx, tp.id, pos[0], pos[1], v])
    print(f"✅ 解析完了(V4 Kalman): {output_video}")

def batch_process(input_dir, output_root):
    video_extensions = ['*.avi', '*.mp4']
    files_to_process = []
    for ext in video_extensions:
        files_to_process.extend(glob.glob(os.path.join(input_dir, ext)))
    
    if not files_to_process:
        print(f"⚠️ 動画ファイルが見つかりません: {input_dir}")
        return

    print(f"🚀 {len(files_to_process)} 個の動画をバッチ処理します...")
    for video in files_to_process:
        process_video(video, output_root)

if __name__ == "__main__":
    TARGET_DIR = r"C:\Users\yu_ci\Desktop\GENRE_FOLDERS\RESEARCH"
    if not os.path.exists(TARGET_DIR): TARGET_DIR = r"C:\Users\yu_ci\Desktop"
    OUTPUT_DIR = r"C:\Users\yu_ci\Desktop\GENRE_FOLDERS\RESEARCH\BATCH_RESULTS"
    batch_process(TARGET_DIR, OUTPUT_DIR)
