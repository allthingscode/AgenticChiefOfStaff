import logging
import sys
import os
from pathlib import Path
from datetime import datetime

# --- CONFIGURATION ---
LOG_DIR = Path("D:/Nanobot_Storage/logs")
LOG_FILE = LOG_DIR / "strategic.log"

def setup_strategic_logger(name="StrategicEdition"):
    """
    Sets up a unified logger for all strategic patches.
    Outputs to both a rotating-style file and the console.
    """
    # Create log directory if it doesn't exist
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
    except Exception:
        # Fallback to local logs if D: drive is unavailable
        local_log_dir = Path("./logs")
        local_log_dir.mkdir(parents=True, exist_ok=True)
        global LOG_FILE
        LOG_FILE = local_log_dir / "strategic.log"

    logger = logging.getLogger(name)
    
    # Avoid duplicate handlers if setup is called multiple times
    if logger.hasHandlers():
        return logger

    logger.setLevel(logging.DEBUG)

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

    # 2. Console Handler
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
