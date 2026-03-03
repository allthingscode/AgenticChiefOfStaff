import logging
import sys
import os
from pathlib import Path
from datetime import datetime

# --- CONFIGURATION ---
# Default to current directory if not set by launcher
LOG_DIR = Path(os.environ.get("STRATEGIC_LOG_DIR", "./logs"))
LOG_FILE = LOG_DIR / "strategic.log"

def setup_strategic_logger(name="StrategicEdition", log_dir=None):
    """
    Sets up a unified logger for all strategic patches.
    Outputs to both a rotating-style file and the console.
    If log_dir is provided or STRATEGIC_LOG_DIR is changed, it re-configures the file logger.
    """
    global LOG_DIR, LOG_FILE
    
    # 1. Determine target log directory
    env_log_dir = os.environ.get("STRATEGIC_LOG_DIR")
    target_dir = Path(log_dir or env_log_dir or "./logs")
    target_file = target_dir / "strategic.log"

    # 2. Check if we need to re-configure (log_dir changed)
    needs_reconfig = False
    if target_file != LOG_FILE:
        needs_reconfig = True
        LOG_DIR = target_dir
        LOG_FILE = target_file

    # Create log directory if it doesn't exist
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
    except Exception:
        # Fallback to local logs if drive is unavailable/restricted
        local_log_dir = Path("./logs")
        local_log_dir.mkdir(parents=True, exist_ok=True)
        LOG_DIR = local_log_dir
        LOG_FILE = local_log_dir / "strategic.log"

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # Avoid duplicate handlers unless re-configuring
    if logger.hasHandlers() and not needs_reconfig:
        return logger

    # If we are re-configuring (due to change in log_dir/env), 
    # we MUST remove old file handlers to prevent pollution.
    if needs_reconfig:
        handlers = logger.handlers[:]
        for handler in handlers:
            if isinstance(handler, logging.FileHandler):
                logger.removeHandler(handler)
                handler.close()

    # 1. File Handler (UTF-8 safe)
    try:
        file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
        file_formatter = logging.Formatter(
            '%(asctime)s [PID:%(process)d] [%(levelname)s] [%(name)s] %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        file_handler.setLevel(logging.DEBUG)
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"[Strategic] Warning: Could not initialize file logger: {e}")

    # 2. Console Handler (only add if not already present)
    has_console = any(isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler) for h in logger.handlers)
    if not has_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_formatter = logging.Formatter(
            '[Strategic] [PID:%(process)d] %(levelname)s: %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(logging.INFO)
        logger.addHandler(console_handler)

    return logger

# Global singleton logger
_logger = None

def get_logger():
    """Always returns the latest correctly-configured logger."""
    global _logger
    _logger = setup_strategic_logger()
    return _logger

# Legacy compatibility (initialized once, but can be updated via setup_strategic_logger)
strategic_logger = get_logger()
