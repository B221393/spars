#!/usr/bin/env python3
"""
UI Contour Extractor
Uses OpenCV classical computer vision to detect candidate UI element bounding boxes
(such as buttons, input bars, and panels) from screen images.
"""

import argparse
import json
import os
import cv2
import numpy as np


def generate_mock_ui(output_path: str):
    """Generates a mock UI screenshot for testing and verification."""
    # Create a 1280x720 dark theme background
    img = np.zeros((720, 1280, 3), dtype=np.uint8)
    img[:] = (30, 30, 30)  # Dark background (#1E1E1E)

    # Draw a top navigation bar (panel)
    cv2.rectangle(img, (0, 0), (1280, 60), (45, 45, 45), -1)
    cv2.rectangle(img, (0, 60), (1280, 62), (60, 60, 60), -1)  # Border line

    # Draw logo button
    cv2.rectangle(img, (20, 15), (120, 45), (100, 50, 200), -1)  # Purple button

    # Draw some text / buttons on nav bar
    for x in range(300, 800, 150):
        cv2.rectangle(img, (x, 15), (x + 100, 45), (70, 70, 70), -1)

    # Draw main dashboard layout (left sidebar, right main panel)
    cv2.rectangle(img, (20, 90), (280, 680), (40, 40, 40), -1)  # Left panel
    cv2.rectangle(img, (310, 90), (1260, 680), (40, 40, 40), -1)  # Main panel

    # Draw interactive buttons inside left sidebar
    for y in range(120, 500, 60):
        cv2.rectangle(img, (40, y), (260, y + 40), (80, 120, 80), -1)  # Greenish buttons

    # Draw inputs and forms inside main panel
    # Input field 1
    cv2.rectangle(img, (350, 150), (750, 190), (50, 50, 50), -1)
    cv2.rectangle(img, (350, 150), (750, 190), (100, 100, 100), 1)  # Border
    # Input field 2
    cv2.rectangle(img, (350, 220), (750, 260), (50, 50, 50), -1)
    cv2.rectangle(img, (350, 220), (750, 260), (100, 100, 100), 1)  # Border

    # Action / Submit Button
    cv2.rectangle(img, (350, 300), (500, 345), (0, 120, 215), -1)  # Blue action button

    # Save mock UI image
    cv2.imwrite(output_path, img)
    print(f"[Generator] Created mock UI screenshot at: {output_path}")


def extract_ui_elements(image_path: str, output_viz_path: str, min_area: int, max_area: int, aspect_ratio_range: tuple):
    """
    Extracts UI element bounding boxes using adaptive thresholding and contour hierarchy.
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Input image not found: {image_path}")

    # Load image
    src = cv2.imread(image_path)
    viz = src.copy()
    gray = cv2.cvtColor(src, cv2.COLOR_BGR2GRAY)

    # Apply bilateral filter / blur to preserve edges while smoothing noise
    blurred = cv2.bilateralFilter(gray, 9, 75, 75)

    # Adaptive Thresholding (handles varying colors/gradients)
    thresh = cv2.adaptiveThreshold(
        blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2
    )

    # Morphological closing to bridge gaps in element borders
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    morphed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

    # Find contours
    contours, hierarchy = cv2.findContours(
        morphed, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE
    )

    detected_elements = []

    if hierarchy is not None:
        hierarchy = hierarchy[0]  # Get outer structure list
        
        for idx, contour in enumerate(contours):
            # Calculate contour bounding box
            x, y, w, h = cv2.boundingRect(contour)
            area = w * h

            # Filter by area constraints
            if not (min_area <= area <= max_area):
                continue

            # Filter by aspect ratio
            aspect_ratio = float(w) / h
            min_ar, max_ar = aspect_ratio_range
            if not (min_ar <= aspect_ratio <= max_ar):
                continue

            # Avoid processing redundant nested contours (e.g. inner text borders of same button)
            # If the current contour has a parent, check if it's very similar in bounding box size
            parent_idx = hierarchy[idx][3]
            if parent_idx != -1:
                px, py, pw, ph = cv2.boundingRect(contours[parent_idx])
                # If parent box is almost identical, skip child to avoid duplicates
                if abs(x - px) < 4 and abs(y - py) < 4 and abs(w - pw) < 8 and abs(h - ph) < 8:
                    continue

            # Calculate center point
            cx = x + w // 2
            cy = y + h // 2

            element = {
                "id": len(detected_elements),
                "bbox": [x, y, w, h],
                "center": [cx, cy],
                "aspect_ratio": round(aspect_ratio, 3),
                "area": area
            }
            detected_elements.append(element)

            # Draw visual highlight on output visualization image
            # Green for general containers, blue for action elements (standardized viz)
            color = (0, 255, 0) if aspect_ratio > 3 else (255, 120, 0)
            cv2.rectangle(viz, (x, y), (x + w, y + h), color, 2)
            cv2.circle(viz, (cx, cy), 3, (0, 0, 255), -1)
            cv2.putText(viz, str(element["id"]), (x + 5, y + 15),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

    # Save visual output
    cv2.imwrite(output_viz_path, viz)
    print(f"[CV Engine] Detected {len(detected_elements)} UI candidate elements.")
    print(f"[CV Engine] Saved visualization image to: {output_viz_path}")

    return detected_elements


def main():
    parser = argparse.ArgumentParser(description="Extract UI element bounding boxes from screenshots.")
    parser.add_argument("--image", type=str, default="mock_screenshot.png", help="Path to input screenshot.")
    parser.add_argument("--viz", type=str, default="contour_viz.png", help="Path to save output visualization.")
    parser.add_argument("--json", type=str, default="detected_ui_coords.json", help="Path to save JSON coordinate outputs.")
    parser.add_argument("--min_area", type=int, default=100, help="Minimum element bounding box area in pixels.")
    parser.add_argument("--max_area", type=int, default=300000, help="Maximum element bounding box area in pixels.")
    parser.add_argument("--min_ar", type=float, default=0.1, help="Minimum aspect ratio (width/height).")
    parser.add_argument("--max_ar", type=float, default=15.0, help="Maximum aspect ratio (width/height).")
    parser.add_argument("--generate_mock", action="store_true", help="Generate a mock UI image for test execution.")

    args = parser.parse_args()

    if args.generate_mock or not os.path.exists(args.image):
        print(f"[Main] Generating test mock image since input '{args.image}' does not exist or --generate_mock was passed.")
        generate_mock_ui(args.image)

    coords = extract_ui_elements(
        args.image,
        args.viz,
        args.min_area,
        args.max_area,
        (args.min_ar, args.max_ar)
    )

    # Write coordinate output to JSON file
    with open(args.json, "w") as f:
        json.dump(coords, f, indent=2)
    print(f"[Main] Successfully exported coordinates database to: {args.json}")


if __name__ == "__main__":
    main()
