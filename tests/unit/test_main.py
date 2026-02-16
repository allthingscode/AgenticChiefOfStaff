import unittest
import json
from unittest.mock import patch, MagicMock, AsyncMock
import main as main_module
from telegram import Update
from telegram.ext import ContextTypes

class TestMain(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        """Mock the skills and config before each test."""
        # 1. Mock Config
        self.config_data = {
            "telegram": {"authorized_user_id": 123, "bot_token": "token"},
            "gemini": {"api_key": "test_key"},
            "user": {"location": "Sachse, TX"}
        }
        self.patcher_open = patch('builtins.open', MagicMock())
        self.patcher_json = patch('json.load', return_value=self.config_data)
        self.patcher_open.start()
        self.patcher_json.start()

        # 2. Mock the Skills (This is the important part)
        # We patch where they are IMPORTED into main.py
        self.patcher_finance = patch('main.FINANCE_TOOLS', [MagicMock(__name__='run_finance_processing')])
        self.patcher_system = patch('main.SYSTEM_TOOLS', [MagicMock(__name__='get_system_status')])
        self.patcher_fm = patch('main.fm')
        
        self.mock_finance = self.patcher_finance.start()
        self.mock_system = self.patcher_system.start()
        self.mock_fm = self.patcher_fm.start()

        # 3. Mock the Gemini Client
        self.patcher_client = patch('main.client')
        self.mock_client = self.patcher_client.start()

        main_module.AUTH_USER_ID = 123
        self.addCleanup(patch.stopall)

    async def test_handle_message_tool_composition(self):
        """Verify that Gemini is initialized with BOTH finance and system tools."""
        update = AsyncMock(spec=Update)
        update.effective_user.id = 123
        update.message.text = "How much did I spend and how is the CPU?"
        update.message.reply_text = AsyncMock()

        # Mock the Gemini response
        mock_res = MagicMock()
        mock_res.text = "I've checked both for you."
        self.mock_client.models.generate_content.return_value = mock_res

        await main_module.handle_message(update, None)

        # Assert tool composition
        args, kwargs = self.mock_client.models.generate_content.call_args
        actual_tools = kwargs['config'].tools
        
        # Verify both skills are present in the list passed to Gemini
        self.assertIn(self.mock_finance[0], actual_tools)
        self.assertIn(self.mock_system[0], actual_tools)

    async def test_process_inbox_command_via_fm(self):
        """Verify the Telegram /process_inbox command calls the new inbox method."""
        update = AsyncMock(spec=Update)
        update.effective_user.id = 123
        update.message.reply_text = AsyncMock()
        
        # ✅ Point to the renamed method
        self.mock_fm.process_financial_inbox.return_value = "Successfully processed 1 files."

        await main_module.process_inbox_command(update, None)
        
        update.message.reply_text.assert_any_call("✅ Successfully processed 1 files.")
        self.mock_fm.process_financial_inbox.assert_called_once()

    async def test_process_inbox_command_return_string(self):
        """Verify the Telegram command handles the 'multiple tabs' success message."""
        update = AsyncMock(spec=Update)
        update.effective_user.id = 123
        update.message.reply_text = AsyncMock()
        
        self.mock_fm.process_financial_inbox.return_value = "Successfully processed 1 files across multiple tabs."

        await main_module.process_inbox_command(update, None)
        
        update.message.reply_text.assert_any_call("✅ Successfully processed 1 files across multiple tabs.")