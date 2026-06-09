# PS5 Remote Play & Game Grinding Background Automation Guide

This document describes how the Task Tray OS Agent is configured to perform fully automated background operations (such as infinite grinding in PC games or PS5 games) using background window messages, virtual gamepad emulation, and Remote Play configurations.

---

## 1. Background Window Input Emulation (How it works)

Typical automation tools (like PyAutoGUI) simulate OS-level physical input, which requires the target window to be active and in the foreground. This blocks you from using your PC while the agent runs.

To solve this, our agent implements **Win32 Background Input Emulation** using Windows API calls via `ctypes`.
- **Target Window Handle (`hwnd`):** The system scans running applications for a title match (e.g. "PS Remote Play", "Slay the Spire 2").
- **Window Message Injection:** It posts standard mouse click (`WM_LBUTTONDOWN`, `WM_LBUTTONUP`) and key (`WM_KEYDOWN`, `WM_KEYUP`) events directly into the target window's event queue.
- **Benefits:** The target application receives and processes these commands even when minimized, covered by other windows, or running in the background. You can browse the web or watch a video concurrently without interruption.

---

## 2. Automating PS5 Games via PC

To automate PlayStation 5 games, you can bridge your PC and PS5 console using a **Remote Play client**:

1. **PS Remote Play (Official):** Download and install the official PlayStation Remote Play application on your PC, log in to your PSN account, and connect to your PS5.
2. **Chiaki (Open Source alternative):** Chiaki is an unofficial, high-performance, open-source PlayStation Remote Play client that is highly lightweight and works exceptionally well for automation because it does not enforce strict window restrictions.

Once the Remote Play screen is running on your PC:
- Open the **Visual Memory Manager** on the Task Tray Agent.
- Scan and select `"PS Remote Play"` or `"Chiaki"` as the target window.
- Enable **Background Mode**. The agent's OpenCV templates will search the captured window frame, calculate coordinates, and send clicks directly to the remote stream.

---

## 3. Game Grinding & Controller/Gamepad Emulation

Some games (especially PS5 games on Remote Play or certain PC ports) only accept controller/gamepad input (XInput/DirectInput) and ignore window keyboard messages. For these scenarios, you can simulate gamepad inputs:

### A. Virtual Gamepad Drivers
- **ViGEmBus (Virtual Gamepad Emulation Bus):** The industry standard Windows kernel driver that emulates Xbox 360 and DualShock 4 controllers.
- **vJoy:** A virtual joystick driver useful for emulating generic DirectInput gamepads.

### B. Python Integration
Using the virtual controller driver, you can emulate gamepad buttons and analog sticks directly from Python. For example, using `vgamepad` (which utilizes ViGEmBus):
```bash
pip install vgamepad
```
```python
import vgamepad as vg
import time

# Create a virtual Xbox 360 controller
gamepad = vg.VX360Gamepad()

# Press Button A
gamepad.press_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_A)
gamepad.update()
time.sleep(0.1)

# Release Button A
gamepad.release_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_A)
gamepad.update()
```
Since the virtual gamepad controller is recognized by Windows at the driver level, the Remote Play application or PC game will capture the gamepad inputs globally, allowing the grinding script to run flawlessly in the background.

---

## 4. Best Practices for Safe Grinding

- **Randomized Delays:** Add a slight randomized delay (e.g., `time.sleep(1.0 + random.uniform(0.1, 0.4))`) between inputs to prevent anti-cheat algorithms from flags.
- **Window Boundaries:** When using background clicks, the coordinates are relative to the client window (`0, 0` is the top-left of the target window's client area). The agent automatically scales visual matches to the window's client size.
- **Visual Failure Check:** If the screen becomes static (no change detected after button inputs), the agent's *Implicit Self-Learning* feature will automatically crop the target zone and alert the logs, preventing the agent from infinitely spamming the same button and getting flagged.
