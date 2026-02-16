import os
import sys

# Ensure tools are importable
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from tools.finance_manager import FinanceManager

def run_test():
    print("--- 🦅 Financial Hawk: Scaling Ledger Integration Test ---")
    fm = FinanceManager()
    
    # Run the full scaling workflow
    result = fm.process_latest_file()
    print(f"Result: {result}")

if __name__ == "__main__":
    run_test()