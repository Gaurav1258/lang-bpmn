"""
AgentBPMN Studio Runner
Starts the FastAPI server on port 8000 and launches the browser to http://localhost:8000.
"""

import sys
import time
import webbrowser
import uvicorn

from agent_bpmn.server.app import app

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

if __name__ == "__main__":
    port = 8000
    host = "127.0.0.1"
    url = f"http://localhost:{port}"

    line = "=" * 76
    print(f"\n{line}")
    print("  🚀 AGENT-BPMN ENTERPRISE STUDIO GATEWAY")
    print(f"  🌐 Visual Studio Web Canvas: {url}")
    print(f"  📑 Interactive API Docs:     {url}/docs")
    print("  💡 Press Ctrl+C in this terminal window to stop the server.")
    print(f"{line}\n")

    # Automatically launch user browser after brief delay
    def open_browser():
        time.sleep(1.2)
        try:
            webbrowser.open(url)
        except Exception:
            pass

    import threading
    threading.Thread(target=open_browser, daemon=True).start()

    # Run Uvicorn server with app instance
    uvicorn.run(app, host=host, port=port, log_level="info")
