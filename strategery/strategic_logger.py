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
    If log_dir is provided, it re-configures the file logger.
    """
    global LOG_DIR, LOG_FILE
    
    if log_dir:
        LOG_DIR = Path(log_dir)
        LOG_FILE = LOG_DIR / "strategic.log"

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

    # Avoid duplicate handlers
    if logger.hasHandlers():
        # If we are re-configuring with a specific log_dir, 
        # we need to remove old file handlers
        if log_dir:
            handlers = logger.handlers[:]
            for handler in handlers:
                if isinstance(handler, logging.FileHandler):
                    logger.removeHandler(handler)
                    handler.close()
        else:
            return logger

    # 1. File Handler (UTF-8 safe)
    try:
        file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
        file_formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] [%(name)s] %(message)s'
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
            '[Strategic] %(levelname)s: %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(logging.INFO)
        logger.addHandler(console_handler)

    return logger

# Global singleton logger
strategic_logger = setup_strategic_logger()
