"""
Strategic Launcher: Thin entry point for Nanobot Strategic Edition.
This script initializes the environment and applies modular patches before
starting the Nanobot gateway.
"""

import sys
import runpy
import os
from pathlib import Path

# Add project root to the path immediately
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import everything from patches; initialization happens on import!
from strategery.patches import RAW_CONFIG, USER_EMAIL, STORAGE_ROOT

def pre_start_cleanup():
    """Performs necessary cleanup before starting the gateway."""
    try:
        mcp_dir = Path.home() / ".google_workspace_mcp"
        if mcp_dir.exists():
            for item in mcp_dir.glob("*.json"):
                if "credentials" not in str(item):
                    item.unlink()

        workspace_dir = Path.home() / ".nanobot" / "workspace"
        if workspace_dir.exists():
            for item in workspace_dir.glob("*.tmp"):
                item.unlink()
    except Exception as e:
        print(f"[Launcher] Cleanup warning: {e}")

if __name__ == "__main__":
    pre_start_cleanup()

    # Performance Optimization: Proactively warmup the Vector Store
    try:
        from strategery.patches.vector_store import StrategicVectorStore
        # This warms up the ChromaDB connection in the background
        # so the first message doesn't hit a 3-second delay.
        print("[Launcher] Warming up Strategic Vector Store...")
        # Note: We don't need a provider yet just to init the client/collection
        StrategicVectorStore(storage_root=STORAGE_ROOT)
    except Exception as e:
        print(f"[Launcher] Vector Store warmup warning: {e}")
    
    sys.argv = ["nanobot", "gateway"]
    print(f"[Launcher] Starting nanobot Gateway...")
    
    try:
        runpy.run_module("nanobot", run_name="__main__", alter_sys=True)
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        print(f"\n[Launcher] Fatal: {e}")
        sys.exit(1)
