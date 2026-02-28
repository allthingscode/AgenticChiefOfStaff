import unittest
from unittest.mock import patch, MagicMock, mock_open
from tools.finance_reader import FinanceReader
import json

class TestFinanceReader(unittest.TestCase):
    def setUp(self):
        # 1. Mock Config
        self.config_data = {
            "gemini": {"api_key": "test_key"},
            "finance": {
                "google_drive": {
                    "transaction_inbox_folder_id": "inbox_id",
                    "transaction_processed_folder_id": "processed_id"
                }
            }
        }
        self.mock_open = patch('builtins.open', mock_open(read_data=json.dumps(self.config_data)))
        self.mock_open.start()

        # 2. Mock Google/GenAI/Downloader
        self.patcher_creds = patch('google.oauth2.service_account.Credentials.from_service_account_file')
        self.patcher_build = patch('tools.finance_reader.build')
        self.patcher_genai = patch('tools.finance_reader.genai.Client')
        self.patcher_download = patch('tools.finance_reader.MediaIoBaseDownload') # ✅ Added patch
        
        self.mock_creds = self.patcher_creds.start()
        self.mock_build = self.patcher_build.start()
        self.mock_genai = self.patcher_genai.start()
        self.mock_download = self.patcher_download.start()
        
        self.addCleanup(self.stop_patches)

    def stop_patches(self):
        self.mock_open.stop()
        self.patcher_creds.stop()
        self.patcher_build.stop()
        self.patcher_genai.stop()
        self.patcher_download.stop()

    def test_get_all_files_from_inbox(self):
        """Verify it returns a list of files for batch processing."""
        reader = FinanceReader()
        self.mock_build.return_value.files().list().execute.return_value = {
            'files': [{'id': '123', 'name': 'test.pdf', 'mimeType': 'application/pdf'}]
        }
        
        # ✅ Mock the downloader to return "done" immediately
        mock_dl_instance = self.mock_download.return_value
        mock_dl_instance.next_chunk.return_value = (None, True)
        
        files = reader.get_all_files_from_inbox()
        self.assertIsInstance(files, list)
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0][1], 'test.pdf')

    def test_parse_pdf_with_gemini_schema(self):
        """Verify the parser returns the structured dict required for date-grouping."""
        reader = FinanceReader()
        mock_response = MagicMock()
        # Note the valid YYYY-MM-DD format for the strptime logic in the manager
        mock_response.text = json.dumps({
            "transactions": [
                {"date": "2026-01-28", "description": "Amazon", "amount": 45.0, "type": "DEBIT", "category": "Shopping"},
                {"date": "2026-02-02", "description": "First Watch", "amount": 20.0, "type": "DEBIT", "category": "Food"}
            ],
            "statement_total": 65.0
        })
        self.mock_genai.return_value.models.generate_content.return_value = mock_response
        
        result = reader.parse_pdf_with_gemini(b"fake_pdf")
        self.assertIn('transactions', result)
        self.assertEqual(len(result['transactions']), 2)