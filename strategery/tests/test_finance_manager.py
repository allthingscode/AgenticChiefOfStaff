import unittest
import json
from unittest.mock import patch, MagicMock, mock_open
from tools.finance_manager import FinanceManager

class TestFinanceManager(unittest.TestCase):

    def setUp(self):
        """Mock all external dependencies for FinanceManager."""
        self.config_data = {
            "gemini": {"api_key": "test_api_key"},
            "finance": {
                "google_drive": {
                    "transaction_inbox_folder_id": "inbox_id",
                    "transaction_processed_folder_id": "processed_id",
                    "root_finance_folder_id": "root_id"
                }
            }
        }

        # Start Patches
        self.patcher_open = patch('builtins.open', mock_open(read_data=json.dumps(self.config_data)))
        self.patcher_creds = patch('google.oauth2.service_account.Credentials.from_service_account_file')
        self.patcher_build = patch('tools.finance_manager.build')
        self.patcher_genai = patch('tools.finance_manager.genai.Client')
        self.patcher_reader = patch('tools.finance_manager.FinanceReader')

        self.mock_open = self.patcher_open.start()
        self.mock_creds = self.patcher_creds.start()
        self.mock_build = self.patcher_build.start()
        self.mock_genai = self.patcher_genai.start()
        self.mock_reader_class = self.patcher_reader.start()

        # Setup internal service mocks
        self.mock_drive = MagicMock()
        self.mock_sheets = MagicMock()
        self.mock_build.side_effect = lambda service, version, credentials: {
            'drive': self.mock_drive,
            'sheets': self.mock_sheets
        }[service]
        self.mock_reader_inst = self.mock_reader_class.return_value

        self.addCleanup(self.stop_patches)

    def stop_patches(self):
        self.patcher_open.stop()
        self.patcher_creds.stop()
        self.patcher_build.stop()
        self.patcher_genai.stop()

    def test_init_success(self):
        manager = FinanceManager()
        self.assertEqual(manager.root_finance_id, "root_id")
        self.mock_creds.assert_called_once()

    def test_get_or_create_ledger_finds_existing(self):
        manager = FinanceManager()
        self.mock_drive.files().list().execute.return_value = {'files': [{'id': 'existing_id'}]}
        
        ledger_id = manager.get_or_create_yearly_ledger(2026)
        self.assertEqual(ledger_id, 'existing_id')
        self.mock_drive.files().create.assert_not_called()

    def test_get_or_create_ledger_creates_new(self):
        manager = FinanceManager()
        self.mock_drive.files().list().execute.return_value = {'files': []}
        
        # ✅ FIX: Do not use () after .create. This sets up the return value without calling it.
        self.mock_drive.files().create.return_value.execute.return_value = {'id': 'new_id'}
        
        ledger_id = manager.get_or_create_yearly_ledger(2026)
        self.assertEqual(ledger_id, 'new_id')
        self.mock_drive.files().create.assert_called_once()

    def test_process_financial_inbox_success(self):
        """Verifies the batch processing loop and chronological filing."""
        manager = FinanceManager()
        
        # 1. Mock the Reader to return a LIST of files (Batch Logic)
        self.mock_reader_inst.get_all_files_from_inbox.return_value = [
            ('id1', 'Stmt1.pdf', b'content', 'application/pdf')
        ]
        
        # 2. Mock the Parser to return the Transaction/Audit dict
        self.mock_reader_inst.parse_pdf_with_gemini.return_value = {
            'transactions': [{'date': '2026-02-01', 'description': 'First Watch', 'amount': 25.0, 'type': 'DEBIT'}],
            'statement_total': 25.0
        }
        
        # 3. Mock Sheets responses
        self.mock_sheets.spreadsheets().get().execute.return_value = {
            'sheets': [{'properties': {'title': 'Feb', 'sheetId': 0}}]
        }

        # ✅ Call the renamed method
        result = manager.process_financial_inbox()
        
        self.assertIn("Successfully processed 1 files", result)
        self.mock_reader_inst.get_all_files_from_inbox.assert_called_once()

    def test_process_financial_inbox_multi_month_routing(self):
        """Verify transactions are routed to different months based on transaction date."""
        manager = FinanceManager()

        # 1. Mock file containing cross-month transactions
        self.mock_reader_inst.get_all_files_from_inbox.return_value = [
            ('file_id', 'Chase_Jan_Feb.pdf', b'content', 'application/pdf')
        ]

        # 2. Mock transactions spanning Jan and Feb
        self.mock_reader_inst.parse_pdf_with_gemini.return_value = {
            'transactions': [
                {'date': '2026-01-30', 'description': 'Jan Expense', 'amount': 10.0, 'type': 'DEBIT'},
                {'date': '2026-02-01', 'description': 'Feb Expense', 'amount': 20.0, 'type': 'DEBIT'}
            ],
            'statement_total': 30.0
        }

        # 3. Mock Sheets to allow get/append for both months
        self.mock_sheets.spreadsheets().get().execute.return_value = {
            'sheets': [
                {'properties': {'title': 'Jan', 'sheetId': 101}},
                {'properties': {'title': 'Feb', 'sheetId': 102}}
            ]
        }

        # Run the manager
        result = manager.process_financial_inbox()

        # 4. Verify orchestration
        self.assertIn("Successfully processed 1 files", result)

        # Ensure append was called twice (once for Jan, once for Feb)
        self.assertEqual(self.mock_sheets.spreadsheets().values().append.call_count, 2)

        # ✅ FIXED ASSERTION:
        # Total batchUpdate calls = 4
        # (1 Formatting + 1 Sorting) * 2 Months
        self.assertEqual(self.mock_sheets.spreadsheets().batchUpdate.call_count, 4)