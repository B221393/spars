#!/usr/bin/env python3
"""
UI Template Matcher
Uses OpenCV matchTemplate with Normalized Cross-Correlation (NCC) and
Non-Maximum Suppression (NMS) to localize template coordinates on screen.
"""

import argparse
import json
import os
import cv2
import numpy as np


def generate_mock_files(screen_path: str, template_path: str):
    """Generates a mock screenshot and a cropped template image for testing."""
    # Create screen image (1280x720 dark theme)
    img = np.zeros((720, 1280, 3), dtype=np.uint8)
    img[:] = (35, 35, 35)

    # Draw top navbar
    cv2.rectangle(img, (0, 0), (1280, 60), (50, 50, 50), -1)

    # Draw three identical target icon buttons (a blue circle inside a white box)
    # Target positions
    positions = [(100, 100), (500, 250), (900, 450)]
    for idx, (x, y) in enumerate(positions):
        # White card background
        cv2.rectangle(img, (x, y), (x + 80, y + 80), (240, 240, 240), -1)
        # Blue circle icon inside card
        cv2.circle(img, (x + 40, y + 40), 20, (220, 100, 0), -1)
        # Border
        cv2.rectangle(img, (x, y), (x + 80, y + 80), (150, 150, 150), 2)
        # Add index text
        cv2.putText(img, f"Card {idx}", (x + 10, y + 70),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (50, 50, 50), 1)

    cv2.imwrite(screen_path, img)
    print(f"[Generator] Created mock screenshot at: {screen_path}")

    # Generate template image by cropping the first card from the screenshot
    template = img[100:180, 100:180].copy()
    cv2.imwrite(template_path, template)
    print(f"[Generator] Created template image at: {template_path}")


def non_max_suppression(boxes, overlap_thresh=0.3):
    """
    Applies Non-Maximum Suppression to remove overlapping bounding box predictions.
    """
    if len(boxes) == 0:
        return []

    # If the bounding boxes are integers, convert them to floats
    if boxes.dtype.kind == "i":
        boxes = boxes.astype("float")

    pick = []

    # Grab coordinates
    x1 = boxes[:, 0]
    y1 = boxes[:, 1]
    x2 = boxes[:, 2]
    y2 = boxes[:, 3]
    scores = boxes[:, 4]

    # Compute areas and sort indices by scores (descending)
    area = (x2 - x1 + 1) * (y2 - y1 + 1)
    idxs = np.argsort(scores)[::-1]

    while len(idxs) > 0:
        last = len(idxs) - 1
        i = idxs[last]
        pick.append(i)

        # Find largest coordinates for start of overlap
        xx1 = np.maximum(x1[i], x1[idxs[:last]])
        yy1 = np.maximum(y1[i], y1[idxs[:last]])
        # Find smallest coordinates for end of overlap
        xx2 = np.minimum(x2[i], x2[idxs[:last]])
        yy2 = np.minimum(y2[i], y2[idxs[:last]])

        # Compute width and height of overlap
        w = np.maximum(0, xx2 - xx1 + 1)
        h = np.maximum(0, yy2 - yy1 + 1)

        # Compute ratio of overlap
        overlap = (w * h) / area[idxs[:last]]

        # Delete all indexes from index list that overlap too much
        idxs = np.delete(idxs, np.concatenate(([last], np.where(overlap > overlap_thresh)[0])))

    return boxes[pick].astype("int")


def match_template_ui(screen_path: str, template_path: str, output_viz_path: str, threshold: float):
    """
    Matches template against screenshot and runs NMS.
    """
    if not os.path.exists(screen_path):
        raise FileNotFoundError(f"Screenshot image not found: {screen_path}")
    if not os.path.exists(template_path):
        raise FileNotFoundError(f"Template image not found: {template_path}")

    # Load images
    src = cv2.imread(screen_path)
    viz = src.copy()
    template = cv2.imread(template_path)

    # Convert to grayscale
    gray_src = cv2.cvtColor(src, cv2.COLOR_BGR2GRAY)
    gray_template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)

    t_h, t_w = gray_template.shape[:2]

    # Perform template matching
    res = cv2.matchTemplate(gray_src, gray_template, cv2.TM_CCOEFF_NORMED)

    # Locate coordinates where correlation exceeds threshold
    loc = np.where(res >= threshold)
    
    candidates = []
    for pt in zip(*loc[::-1]):  # Switch columns and rows to (x, y)
        x, y = pt
        score = res[y, x]
        # Box format: [x1, y1, x2, y2, score]
        candidates.append([x, y, x + t_w, y + t_h, score])

    candidates = np.array(candidates)
    
    # Apply Non-Maximum Suppression to keep only distinct best matches
    matches = non_max_suppression(candidates, overlap_thresh=0.3)

    detected_targets = []
    for idx, match in enumerate(matches):
        x1, y1, x2, y2 = match[:4]
        score = res[y1, x1]
        w = x2 - x1
        h = y2 - y1
        cx = x1 + w // 2
        cy = y1 + h // 2

        target = {
            "id": int(idx),
            "bbox": [int(x1), int(y1), int(w), int(h)],
            "center": [int(cx), int(cy)],
            "confidence": round(float(score), 4)
        }
        detected_targets.append(target)

        # Draw matches
        cv2.rectangle(viz, (x1, y1), (x2, y2), (0, 0, 255), 2)  # Red box
        cv2.circle(viz, (cx, cy), 4, (0, 255, 0), -1)  # Green center dot
        cv2.putText(viz, f"{idx} ({target['confidence']:.2f})", (x1, y1 - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)

    # Save visual output
    cv2.imwrite(output_viz_path, viz)
    print(f"[Matcher Engine] Found {len(detected_targets)} matching elements above threshold {threshold}.")
    print(f"[Matcher Engine] Saved matching visualization to: {output_viz_path}")

    return detected_targets


def main():
    parser = argparse.ArgumentParser(description="Find templates in screenshots.")
    parser.add_argument("--image", type=str, default="mock_screenshot.png", help="Path to input screenshot.")
    parser.add_argument("--template", type=str, default="mock_template.png", help="Path to template icon.")
    parser.add_argument("--viz", type=str, default="match_viz.png", help="Path to save output visualization.")
    parser.add_argument("--json", type=str, default="matched_coords.json", help="Path to save JSON match coordinates.")
    parser.add_argument("--threshold", type=float, default=0.85, help="Matching similarity confidence threshold.")
    parser.add_argument("--generate_mock", action="store_true", help="Generate mock screenshot and template.")

    args = parser.parse_args()

    if args.generate_mock or not os.path.exists(args.image) or not os.path.exists(args.template):
        print("[Main] Mock files missing or requested. Generating mock templates...")
        generate_mock_files(args.image, args.template)

    matches = match_template_ui(
        args.image,
        args.template,
        args.viz,
        args.threshold
    )

    with open(args.json, "w") as f:
        json.dump(matches, f, indent=2)
    print(f"[Main] Output matched coordinates database: {args.json}")


if __name__ == "__main__":
    main()
