# skills/finance_skill.py
from tools.finance_manager import FinanceManager

# Singleton instance for the skill
fm = FinanceManager()

def run_finance_processing():
    """
    Scans the Google Drive financial inbox, parses bank statements using Gemini,
    and updates the yearly ledger (e.g., Finance_Ledger_2026).
    """
    return fm.process_financial_inbox()

def get_spending_report(year: int, month: str):
    """
    Retrieves transaction data from the ledger for a specific month and year.
    Use this to answer questions about budget, totals, or specific vendor spending.
    """
    return fm.query_spending(year, month)

FINANCE_TOOLS = [run_finance_processing, get_spending_report]