# C:\Users\HayesChiefOfStaff\Documents\nanobot\finance_server.py

from mcp.server.fastmcp import FastMCP
from tools.finance_manager import FinanceManager

mcp = FastMCP("FinanceAutomator")

# Initialize with your folder IDs
manager = FinanceManager(
    key_path="secrets/service_account.json", 
    parent_folder_id="YOUR_FOLDER_ID"
)

@mcp.tool()
def run_finance_inbox_processing() -> str:
    """
    Scans GDrive _inbox, parses PDFs with Gemini, and updates the ledger.
    """
    # Notice: NO 'update' or 'context' arguments here!
    return str(manager.process_financial_inbox())

@mcp.tool()
def add_manual_entry(year: int, month: str, date: str, desc: str, amount: float):
    """Adds a single manual transaction to the monthly ledger."""
    rows = [[date, desc, amount, "DEBIT", "Manual"]]
    return manager.append_data(year, month, rows)

if __name__ == "__main__":
    mcp.run()