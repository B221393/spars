#!/usr/bin/env python3
"""
Verification script for 100-Point Calibration Stats & OpenCV Template Button Clicker.
Tests:
1. LightweightCalibrator 100-point rolling statistics, trend detection, and auto-report.
2. Template matching using OpenCV, cropping target snippets, and clicking corrected locations.
"""

import os
import cv2
import json
import numpy as np
import time
import shutil
import pyautogui
from agent_harness import AgentHarness, LightweightCalibrator

def test_calibrator_rolling_stats():
    print("--- Test 1: Calibrator 100-Point Rolling Statistics & Trend Detection ---")
    test_json_path = "test_click_calibration_data.json"
    if os.path.exists(test_json_path):
        os.remove(test_json_path)

    # Initialize calibrator with max_history=100
    calibrator = LightweightCalibrator(max_history=100, report_path=test_json_path)

    # Feed 100 clicks with a constant offset of +15px on X and -12px on Y (e.g. constant shift right and shift up)
    # Target: (x, y), Actual: (x + 15, y - 12) => dx = 15, dy = -12
    # Standard deviation should be near 0 (since it's a constant offset), which will trigger trend "Constant shift Right & Constant shift Up"
    for i in range(105):
        target_x = 100 + i
        target_y = 200 + i
        actual_x = target_x + 15
        actual_y = target_y - 12
        calibrator.record_click_feedback(target_x, target_y, actual_x, actual_y)

    # Check rolling buffer size (should be capped at 100)
    assert len(calibrator.click_history) == 100, f"History length is {len(calibrator.click_history)}, expected 100"
    print(f"✓ History length capped at 100.")

    # Check calculated statistics
    assert abs(calibrator.mean_dx - 15.0) < 1e-5, f"mean_dx is {calibrator.mean_dx}, expected 15.0"
    assert abs(calibrator.mean_dy - (-12.0)) < 1e-5, f"mean_dy is {calibrator.mean_dy}, expected -12.0"
    assert calibrator.std_dx < 1.0, f"std_dx is {calibrator.std_dx}, expected near 0"
    assert calibrator.std_dy < 1.0, f"std_dy is {calibrator.std_dy}, expected near 0"
    print(f"✓ Calculated means (mean_dx={calibrator.mean_dx}, mean_dy={calibrator.mean_dy}) and standard deviations are correct.")

    # Check trend detection
    expected_trend = "Constant shift Right & Constant shift Up"
    assert calibrator.trend == expected_trend, f"Trend is '{calibrator.trend}', expected '{expected_trend}'"
    print(f"✓ Detected trend: '{calibrator.trend}'")

    # Check report JSON file exists
    assert os.path.exists(test_json_path), "JSON report file was not created"
    with open(test_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        assert data["total_clicks"] == 100
        assert data["mean_dx"] == 15.0
        assert data["mean_dy"] == -12.0
        assert data["trend"] == expected_trend
        assert len(data["click_history"]) == 100
    print(f"✓ JSON report successfully persisted and verified.")

    # Test correction application
    corrected_x, corrected_y = calibrator.apply_systematic_correction(500, 500)
    assert corrected_x == 515, f"Expected 515, got {corrected_x}"
    assert corrected_y == 488, f"Expected 488, got {corrected_y}"
    print(f"✓ Corrected coordinates successfully computed: (500, 500) -> ({corrected_x}, {corrected_y})")

    # Cleanup
    if os.path.exists(test_json_path):
        os.remove(test_json_path)
    print("Test 1 PASSED.\n")

def test_template_clicker():
    print("--- Test 2: OpenCV Template Button Clicker & Crop Saving ---")
    
    # 1. Create a mock screen with an arrow marker
    # Resolution: 1280x720
    screen_img = np.zeros((720, 1280, 3), dtype=np.uint8)
    screen_img[:] = (30, 30, 30)  # Dark gray background

    # Let's draw a button box with an arrow "→" at center (600, 350)
    # The box size: 80x40
    bx, by, bw, bh = 560, 330, 80, 40
    cv2.rectangle(screen_img, (bx, by), (bx + bw, by + bh), (50, 150, 50), -1)  # Green filled rect
    cv2.rectangle(screen_img, (bx, by), (bx + bw, by + bh), (255, 255, 255), 2)  # White border
    # Draw an arrow text "->" or "→" inside the button
    cv2.putText(screen_img, "->", (bx + 25, by + 26), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

    # Save mock screen as harness_temp_screen.png
    mock_screenshot_path = "harness_temp_screen.png"
    cv2.imwrite(mock_screenshot_path, screen_img)

    # 2. Save the button template to a file
    # Crop the button area from the screen image
    template_img = screen_img[by:by+bh, bx:bx+bw].copy()
    template_path = "arrow_template.png"
    cv2.imwrite(template_path, template_img)

    # 3. Instantiate AgentHarness and mock pyautogui functions
    harness = AgentHarness(safety_margin=50)
    harness.screen_width = 1280
    harness.screen_height = 720

    # Ensure learning_gallery is clean
    if os.path.exists("learning_gallery"):
        shutil.rmtree("learning_gallery")

    clicked_coords = []
    
    # Stub pyautogui functions
    def mock_screenshot(path):
        # Do not overwrite, we already have our mock screen at harness_temp_screen.png
        pass

    def mock_moveTo(x, y, duration=0):
        pass

    def mock_click():
        pass

    pyautogui.screenshot = mock_screenshot
    pyautogui.moveTo = mock_moveTo
    pyautogui.click = mock_click

    # Pre-seed calibrator with systematic shift so we verify coordinate correction is applied
    # Let's say mean_dx = 10, mean_dy = -10
    harness.calibrator.mean_dx = 10.0
    harness.calibrator.mean_dy = -10.0

    # Overload execute_safe_action to record the coordinates actually clicked
    original_execute = harness.execute_safe_action
    def spy_execute_safe_action(tx, ty, action_type="click", input_text=""):
        # We record target coordinates before and after correction
        corr_x, corr_y = harness.calibrator.apply_systematic_correction(tx, ty)
        clicked_coords.append((tx, ty, corr_x, corr_y))
        return original_execute(tx, ty, action_type, input_text)

    harness.execute_safe_action = spy_execute_safe_action

    # 4. Execute template match and click
    print("Executing click_template_on_screen...")
    success = harness.click_template_on_screen(template_path, confidence_threshold=0.8)

    # Check if matched and clicked
    assert success is True, "Template matching click failed"
    print("✓ click_template_on_screen returned True.")

    # Check matching coordinates (expected center is bx + bw//2 = 600, by + bh//2 = 350)
    # The clicked coordinate should be corrected by mean_dx=10, mean_dy=-10 -> (610, 340)
    assert len(clicked_coords) == 1, "Expected exactly one click execution"
    tx, ty, cx, cy = clicked_coords[0]
    assert tx == 600, f"Detected target X is {tx}, expected 600"
    assert ty == 350, f"Detected target Y is {ty}, expected 350"
    assert cx == 610, f"Corrected clicked X is {cx}, expected 610"
    assert cy == 340, f"Corrected clicked Y is {cy}, expected 340"
    print(f"✓ Coordinates matched: target=({tx}, {ty}) -> clicked=({cx}, {cy}) (correctly applied +10, -10 offset).")

    # Check if crop preview was saved to learning_gallery
    assert os.path.exists("learning_gallery"), "learning_gallery directory not created"
    gallery_files = os.listdir("learning_gallery")
    assert len(gallery_files) == 1, f"Expected 1 saved crop in gallery, found {len(gallery_files)}"
    crop_file = gallery_files[0]
    assert crop_file.startswith("matched_button_") and crop_file.endswith(".png"), f"Unexpected crop filename: {crop_file}"
    print(f"✓ Saved cropped snippet to learning_gallery: {crop_file}")

    # Verify crop image dimensions match the template
    crop_path = os.path.join("learning_gallery", crop_file)
    crop_img = cv2.imread(crop_path)
    assert crop_img is not None, "Failed to load saved crop image"
    assert crop_img.shape == (bh, bw, 3), f"Crop shape is {crop_img.shape}, expected {(bh, bw, 3)}"
    print(f"✓ Saved crop image dimensions {crop_img.shape[1]}x{crop_img.shape[0]} match template {bw}x{bh}.")

    # Cleanup files
    for path in [mock_screenshot_path, template_path]:
        if os.path.exists(path):
            os.remove(path)
    print("Test 2 PASSED.\n")

if __name__ == "__main__":
    print("=== RUNNING AUTO-CALIBRATION & TEMPLATE CLICKER VERIFICATION ===")
    test_calibrator_rolling_stats()
    test_template_clicker()
    print("=== ALL TESTS PASSED SUCCESSFULLY ===")
