# 🧠 Gemma 4 8B + OpenCV Agent Harness & Coordinate Simulator

This folder contains the complete design and implementation of an **Agent Harness** that bridges a local lightweight LLM (Gemma 4 8B) with OpenCV visual verification and PyAutoGUI GUI action execution. Additionally, it features an interactive web simulator to visualize and test coordinate scaling, offset calibration, and safety fail-safe boundary controls.

---

## 1. System Architecture

The Agent Harness acts as a middleware layer between the AI model and the OS to prevent incorrect coordinates or accidental operations:

```
[User Request] 
      │
      ▼
┌───────────────┐
│ Gemma 4 8B    │ ◄─── Inputs System Prompt & Screen Element Coordinates
│ (Ollama JSON) │
└──────┬────────┘
       │ Returns target coordinates [tx, ty]
       ▼
┌───────────────┐
│ Agent Harness │ ◄─── Applies OpenCV offsets & checks against safety margin bounds
└──────┬────────┘
       │ Coordinates Validated & Corrected
       ▼
┌───────────────┐
│ PyAutoGUI     │ ◄─── Performs physical mouse movement and clicks
│ Action        │
└───────────────┘
```

### Components
1. **Gemma 4 8B (Thinking Brain):** Determines actions (clicks, key typing) based on current UI lists, outputting pure JSON via Ollama's `format: "json"` mode.
2. **OpenCV Calibration (Vision Core):** Takes screen captures and aligns them to pre-defined reference markers using Normalized Cross-Correlation (NCC) template matching. This measures pixel-level physical offset (caused by DPI scaling, window resizing, or screen resolution shifts).
3. **Safety Validator (Fail-Safe Kill Switch):** Restricts pointer click positions to a safe bounds range (e.g. `[safety_margin, screen_size - safety_margin]`). If a target coordinate violates this range, the harness intercepts the command, cancels execution, and raises a trigger alert.
4. **Lightweight Systematic Calibrator (習性誤差補正器):** A local tracker in `agent_harness.py` that measures systematic deltas (error offsets) between target clicks and actual screen responses. It learns the coordinate shift trend dynamically and automatically corrects subsequent actions locally, offloading complex math from the heavy main LLM.

---

## 2. Directory Layout

- **`agent_harness.py`**: The core Python class implementation of the agent harness. Bridges Ollama, OpenCV matching, and PyAutoGUI clicks.
- **`system_prompt.txt`**: The Japanese system prompt instructions and JSON output schema fed into Gemma 4 8B.
- **`mock_env_test.py`**: A standalone test suite that creates a mock environment with simulated buttons and verifies template calibration and fail-safe triggers.
- **`autonomous_agent_loop.py`**: Runs a single-agent self-healing loop that queries Gemma, catches coordinate checks or click failures, and feeds error logs back into the LLM context.
- **`autonomous_orchestrator.py`**: Implements a multi-agent orchestration loop with **AI-to-AI Automated Input**. Automatically decomposes goals and delegates sub-tasks to specialized sub-agents (Vision, Planner, Guard, Verify, and a dedicated Content Writer agent) to automatically generate input text and type into GUI boxes without manual user entry. Includes self-healing correction.
- **`continuous_learning_loop.py`**: A continuous autopilot script that runs a local HTTP server on port 8123, opens the interactive simulator in a web browser, executes GUI clicks physically via PyAutoGUI, crops the visual canvas via OpenCV, and trains a local Ollama model (e.g., `gemma4:latest`) on coordinate safety rules with self-healing correction.
- **`simulator.html`**: A visually stunning dark-mode interactive HTML dashboard featuring real-time coordinate rendering on a grid, custom sliders for margins and offsets, and live JSON output schema.

---

## 3. How to Run

### Prerequisite Dependencies
Install the required packages in your Python environment:
```bash
pip install opencv-python pyautogui numpy requests
```

### Verification (Mock Environment Test)
Run the verification test script. This generates temporary mock template markers, measures coordinates, and validates boundary checks:
```bash
python mock_env_test.py
```

### Self-Healing Agent Loop
Run the single-agent self-healing test loop:
```bash
python autonomous_agent_loop.py --simulate
```

### Multi-Agent Orchestrator Loop
Run the multi-agent orchestration loop:
```bash
python autonomous_orchestrator.py
```

### Continuous Learning & Practice Autopilot Loop
Ensure your local Ollama server is running with your preferred model (e.g. `gemma4:latest` or `gemma3:4b`), then run the continuous loop:
```bash
python continuous_learning_loop.py
```
This will physically control your cursor to calibrate and randomize parameters on the browser, crop images to the `learning_gallery/` directory, and log Ollama validation metrics to `learning_progress.json`.


### Interactive Simulator
Open **`simulator.html`** in any web browser. 
- Adjust the **Screen Width / Height** and **Safety Margin** sliders to see the red fail-safe zone shrink or expand.
- Move **LLM Target** and **OpenCV Offsets** sliders. The dashboard will compute the corrected coordinate instantly, show the visual path on the canvas grid, and light up the **FAIL-SAFE BLOCKED** warning if it enters the red margin.
