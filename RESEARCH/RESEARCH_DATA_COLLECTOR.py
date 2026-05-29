import cv2
import numpy as np
import csv
import os

# --- 研究用：完璧なPython画像トラッキング＆データ収集アプリ ---
# 動画からドットの軌跡を抽出し、大量のデータをCSVにまとめます。
# MATLABのアルゴリズムと同等のアプローチをPython (OpenCV) で実装しています。

def track_and_collect(video_path):
    print(f"🎥 動画を読み込んでいます: {video_path}")
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print("❌ 動画が開けません。パスを確認してください。")
        return

    all_points = []
    
    ret, frame = cap.read()
    if not ret: return
    canvas = np.zeros_like(frame)

    frame_idx = 0
    print("⏳ トラッキングを実行中... (別ウィンドウで進捗が表示されます)")
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret: break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        # 二値化
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        
        # 輪郭（ドット）の抽出
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        for i, c in enumerate(contours):
            if cv2.contourArea(c) > 10: # ノイズ除去
                M = cv2.moments(c)
                if M["m00"] != 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])
                    
                    # データを収集
                    all_points.append({"frame": frame_idx, "id": i, "x": cx, "y": cy})
                    
                    # 軌跡を描画
                    cv2.circle(canvas, (cx, cy), 2, (0, 255, 0), -1)

        # 映像と軌跡を合成して表示
        display_frame = cv2.addWeighted(frame, 0.7, canvas, 0.3, 0)
        cv2.imshow("Data Collection Tracker", display_frame)
        
        # Qキーで中断可能
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
        frame_idx += 1

    cap.release()
    cv2.destroyAllWindows()

    # 収集したデータをCSVに出力
    output_csv = "tracking_data_export.csv"
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["frame", "id", "x", "y"])
        writer.writeheader()
        writer.writerows(all_points)
    
    print(f"\n✅ 完璧にデータを収集しました！")
    print(f"📊 保存先: {os.path.abspath(output_csv)}")

if __name__ == "__main__":
    # 対象の動画ファイルパスを指定 (デスクトップのRESEARCHフォルダまたはカレントディレクトリのファイルを想定)
    RESEARCH_VIDEO = r"C:\Users\yu_ci\Desktop\GENRE_FOLDERS\RESEARCH\99920250703172334.avi"
    if not os.path.exists(RESEARCH_VIDEO):
        # フォールバック: デスクトップに直接ある場合
        RESEARCH_VIDEO = r"C:\Users\yu_ci\Desktop\99920250703172334.avi"
        
    track_and_collect(RESEARCH_VIDEO)
