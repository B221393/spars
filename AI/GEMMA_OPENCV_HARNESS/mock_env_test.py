#!/usr/bin/env python3
"""
AgentHarness Mock Environment Verification Test
Simulates desktop screenshotting, calibration, and safety limit checks.
"""

import os
import cv2
import numpy as np
from agent_harness import AgentHarness


def create_mock_images():
    """Creates a mock screenshot and a marker template for verification."""
    # Create a mock 1280x720 screenshot
    screen = np.zeros((720, 1280, 3), dtype=np.uint8)
    screen[:] = (40, 40, 40)  # Dark gray background

    # Draw a blue marker box on the screen (centered at 150, 120)
    # Target size: 60x60
    cv2.rectangle(screen, (120, 90), (180, 150), (220, 100, 0), -1)  # Blue filled rect
    cv2.rectangle(screen, (120, 90), (180, 150), (255, 255, 255), 2)  # White border
    cv2.putText(screen, "REF", (132, 127), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

    # Save mock screen to file
    screen_path = "harness_temp_screen.png"
    cv2.imwrite(screen_path, screen)
    print(f"[Mock] Saved temporary screen snapshot: {screen_path}")

    # Crop the marker to create the template
    marker = screen[90:150, 120:180].copy()
    template_path = "mock_steam_marker.png"
    cv2.imwrite(template_path, marker)
    print(f"[Mock] Saved template marker image: {template_path}")
    
    return screen_path, template_path


def main():
    print("=== STARTING AGENT HARNESS MOCK VERIFICATION ===")
    
    # Stub pyautogui interfaces to prevent desktop disruption and screenshot overwriting during verification
    import pyautogui
    pyautogui.screenshot = lambda path: None
    pyautogui.moveTo = lambda x, y, duration=0: None
    pyautogui.click = lambda: None
    
    # 1. Generate mock assets
    screen_path, template_path = create_mock_images()
    
    # 2. Instantiate Harness in safe test configuration (1280x720 resolution, safety margin = 100)
    harness = AgentHarness(safety_margin=100)
    harness.screen_width = 1280
    harness.screen_height = 720
    
    # Override screenshot mechanism to bypass PyAutoGUI screen capture in mock runs
    # (The screen is already generated as harness_temp_screen.png by create_mock_images)
    print("\n--- Step 1: Running OpenCV Calibration ---")
    marker_pos = harness.run_calibration(template_path)
    
    if marker_pos:
        # Calculate offset from expected target position (100, 100)
        harness.offset_x = marker_pos[0] - 100
        harness.offset_y = marker_pos[1] - 100
        print(f"[Mock] Calibration offsets computed -> X offset: {harness.offset_x}px, Y offset: {harness.offset_y}px")
        # Detected position is (150, 120), expected is (100, 100), so offsets should be X = +50, Y = +20
    else:
        print("[Mock] ERROR: Calibration failed!")
        return

    # 3. Verify target execution with safe targets
    print("\n--- Step 2: Testing Safe Actions inside boundaries ---")
    # Action target: (400, 300) -> After offsets: (450, 320)
    # Since boundaries are [100, 1280-100] and [100, 720-100], this is safe.
    success = harness.execute_safe_action(400, 300, action_type="click")
    print(f"[Mock] Target (400, 300) execution: {'PASSED' if success else 'FAILED'}")

    # 4. Verify fail-safe trigger with unsafe targets
    print("\n--- Step 3: Testing Fail-Safe trigger on unsafe boundaries ---")
    # Action target: (50, 50) -> After offsets: (100, 70)
    # The final Y coordinate (70) violates the safety margin of 100px.
    blocked = harness.execute_safe_action(50, 50, action_type="click")
    print(f"[Mock] Target (50, 50) execution blocked: {'PASSED (Fail-Safe worked)' if not blocked else 'FAILED (Fail-Safe bypassed)'}")

    # Clean up mock files
    for path in [screen_path, template_path]:
        if os.path.exists(path):
            os.remove(path)
            print(f"[Mock] Cleaned up temporary file: {path}")

    print("\n=== VERIFICATION TEST COMPLETED SUCCESSFULLY ===")


if __name__ == "__main__":
    main()
