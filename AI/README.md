# 🤖 Core AI Brain Reference Folder

This folder serves as the central hub for core AI logic, virtual input driver, and local task orchestrators.

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

## Contents
- **`CORE/ai_driver.py`**: The high-fidelity virtual mouse/keyboard input emulator featuring Bézier curve paths, randomized typing delay, and GDI crosshair pointer overlays.
- **`brain_switchboard.py`**: Dynamic folder/brain router (loads specialized brains for Shogi, Voice, Research, PowerPoint, Game, and Development).
- **`cowork_chat.py`**: Borderless floating desktop chat widget.
- **`autonomous_orchestrator.py`**: Implements a multi-agent orchestration loop with **AI-to-AI Automated Input**. Automatically decomposes goals and delegates sub-tasks to specialized sub-agents (Vision, Planner, Guard, Verify, and a dedicated Content Writer agent) to automatically generate input text and type into GUI boxes without manual user entry. Includes self-healing correction.
- **`continuous_learning_loop.py`**: A continuous autopilot script that runs a local HTTP server on port 8123, opens the interactive simulator in a web browser, executes GUI clicks physically via PyAutoGUI, crops the visual canvas via OpenCV, and trains a local Ollama model (e.g., `gemma4:latest`) on coordinate safety rules with self-healing correction.
- **`simulator.html`**: A visually stunning dark-mode interactive HTML dashboard featuring real-time coordinate rendering on a grid, custom sliders for margins and offsets, and live JSON output schema.
- **`COWORK_BENCHMARK.py`**: Self-healing input accuracy calibration and benchmark harness.
- **`LOCAL_AI_ORCHESTRATOR.py`**: Local model task automator.
- **`CONTINUOUS_EVOLUTION.py`**: Self-healing system loop.
- **`ERROR_ANALYSIS_HARNESS.py`**: Evolution debugger.
