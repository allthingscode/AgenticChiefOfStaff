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

def pre_start_cleanup(config=None, storage_root=None):
    """Performs necessary cleanup before starting."""
    config = config or RAW_CONFIG
    storage_root = storage_root or STORAGE_ROOT
    try:
        # 1. Determine workspace path
        workspace_path = Path(config.get("agents", {}).get("defaults", {}).get("workspace", str(storage_root / "workspace")))
        
        # 2. Workspace cleanup (Google Workspace MCP temp files)
        mcp_dir = Path.home() / ".google_workspace_mcp"
        if mcp_dir.exists():
            for item in mcp_dir.glob("*.json"):
                if "credentials" not in str(item):
                    item.unlink()

        # 3. Cleanup temporary files in workspace
        if workspace_path.exists():
            for item in workspace_path.glob("*.tmp"):
                item.unlink()
        return True
    except Exception as e:
        print(f"[Launcher] Cleanup warning: {e}")
        return False

def warmup_vector_store(storage_root=None):
    """Proactively warms up the Vector Store connection to reduce initial latency."""
    storage_root = storage_root or STORAGE_ROOT
    try:
        from strategery.patches.vector_store import StrategicVectorStore
        # This warms up the ChromaDB connection in the background
        # so the first message doesn't hit a 3-second delay.
        print("[Launcher] Warming up Strategic Vector Store...")
        StrategicVectorStore(storage_root=storage_root)
        return True
    except Exception as e:
        print(f"[Launcher] Vector Store warmup warning: {e}")
        return False

def transform_args(argv):
    """Transforms launcher arguments into core nanobot CLI arguments."""
    new_argv = list(argv)
    if len(new_argv) > 1:
        # Pass through all arguments to the core nanobot CLI
        # e.g., 'python strategic_launcher.py status' becomes 'nanobot status'
        new_argv[0] = "nanobot"
    else:
        # Default behavior: start the gateway
        new_argv = ["nanobot", "gateway"]
    return new_argv

def main():
    """Main entry point for the launcher."""
    pre_start_cleanup()
    warmup_vector_store()
    
    sys.argv = transform_args(sys.argv)
    print(f"[Launcher] Running: {' '.join(sys.argv)}")
    
    try:
        runpy.run_module("nanobot", run_name="__main__", alter_sys=True)
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        print(f"\n[Launcher] Fatal: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
