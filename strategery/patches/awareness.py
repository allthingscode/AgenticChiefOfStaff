"""Patch to provide environmental awareness to Nanobot."""

import os
import platform
import shutil
import subprocess
from pathlib import Path
from datetime import datetime
from loguru import logger

def get_git_status(workspace: Path) -> str:
    """Get a brief summary of the git status."""
    try:
        # Check if it's a git repo
        subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], 
                       cwd=workspace, capture_output=True, check=True)
        
        branch = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], 
                                       cwd=workspace, text=True).strip()
        status = subprocess.check_output(["git", "status", "--short"], 
                                        cwd=workspace, text=True).strip()
        
        if not status:
            return f"On branch {branch} (Clean)"
        return f"""On branch {branch}
Changes:
{status}"""
    except Exception:
        return "Not a git repository or git not found."

def get_disk_usage(path: Path) -> str:
    """Get disk usage for the drive containing the path."""
    try:
        total, used, free = shutil.disk_usage(path)
        return f"{used // (1024**3)}GB used / {free // (1024**3)}GB free (Total: {total // (1024**3)}GB)"
    except Exception:
        return "Unknown"

def update_awareness(workspace: Path):
    """Update the AWARENESS.md file with current environmental context."""
    awareness_file = workspace / "AWARENESS.md"
    
    # Gather data
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    git_info = get_git_status(workspace)
    disk_info = get_disk_usage(workspace)
    load_avg = os.getloadavg() if hasattr(os, 'getloadavg') else "N/A (Windows)"
    
    # Format the content
    content = f"""# Environmental Awareness
*Last Updated: {now}*

## System Status
- **Platform:** {platform.system()} {platform.release()}
- **Disk Usage:** {disk_info}
- **System Load:** {load_avg}

## Project Status (Git)
{git_info}

## Active Strategic Context
This Nanobot is running the **Strategic Edition** with modular patches.
Current Workspace: `{workspace}`
"""
    
    try:
        # Write to file (UTF-8 without BOM)
        awareness_file.write_text(content, encoding="utf-8")
        logger.info("Updated awareness context in AWARENESS.md")
    except Exception as e:
        logger.error(f"Failed to update awareness context: {e}")

def patch_context_builder():
    """Monkey-patch ContextBuilder to include AWARENESS.md in bootstrap files."""
    from nanobot.agent.context import ContextBuilder
    
    if "AWARENESS.md" not in ContextBuilder.BOOTSTRAP_FILES:
        # We insert it at the beginning so it's prioritized
        ContextBuilder.BOOTSTRAP_FILES = ["AWARENESS.md"] + ContextBuilder.BOOTSTRAP_FILES
        logger.info("Patched ContextBuilder to include AWARENESS.md")
