
import os
import shutil
from pathlib import Path
import logging

# 1. First import (should default to ./logs)
from strategery.strategic_logger import strategic_logger, setup_strategic_logger

def test_logger_segregation():
    log_dir_1 = Path("./test_logs_1")
    log_dir_2 = Path("./test_logs_2")
    
    if log_dir_1.exists(): shutil.rmtree(log_dir_1)
    if log_dir_2.exists(): shutil.rmtree(log_dir_2)
    
    # 2. Test initial state (using default or first setup)
    # We force re-config to log_dir_1
    logger = setup_strategic_logger(log_dir=log_dir_1)
    logger.info("Message 1")
    
    log_file_1 = log_dir_1 / "strategic.log"
    if log_file_1.exists():
        print(f"SUCCESS: Message 1 found in {log_file_1}")
    else:
        print(f"FAILED: Message 1 NOT found in {log_file_1}")

    # 3. Change environment variable (Simulating conftest.py)
    os.environ["STRATEGIC_LOG_DIR"] = str(log_dir_2.absolute())
    
    # 4. Try to get logger again (should re-trigger setup and move to log_dir_2)
    logger_2 = setup_strategic_logger()
    logger_2.info("Message 2")
    
    log_file_2 = log_dir_2 / "strategic.log"
    if log_file_2.exists():
        print(f"SUCCESS: Message 2 found in {log_file_2}")
        with open(log_file_1, "r") as f:
            content_1 = f.read()
            if "Message 2" in content_1:
                print("FAILED: Pollution! Message 2 also found in log 1")
            else:
                print("SUCCESS: No pollution in log 1")
    else:
        print(f"FAILED: Message 2 NOT found in {log_file_2}")

    # Explicitly close and remove handlers to release file locks on Windows
    for handler in list(logger_2.handlers):
        handler.close()
        logger_2.removeHandler(handler)

    # Cleanup
    if log_dir_1.exists(): shutil.rmtree(log_dir_1)
    if log_dir_2.exists(): shutil.rmtree(log_dir_2)

    # Restore the original log dir for subsequent tests
    os.environ["STRATEGIC_LOG_DIR"] = "D:/Test_Workspace/logs"
    setup_strategic_logger()

if __name__ == "__main__":
    test_logger_segregation()
