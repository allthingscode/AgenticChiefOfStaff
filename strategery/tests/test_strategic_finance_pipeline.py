import pytest
import main
from unittest.mock import AsyncMock, MagicMock, patch

@pytest.mark.asyncio
async def test_pdf_upload_workflow():
    test_id = 123456789
    mock_update = MagicMock()
    mock_update.effective_user.id = test_id
    mock_update.message.document.file_name = "test.pdf"
    mock_update.message.reply_text = AsyncMock()

    mock_context = MagicMock()
    mock_context.bot.get_file = AsyncMock()

    # ✅ Patch FinanceManager, which is what main.py actually uses
    with patch("main.AUTH_USER_ID", test_id), \
         patch("main.fm") as mock_fm:
        
        mock_fm.drive.files().create.return_value.execute.return_value = {"id": "123"}
        await main.handle_document(mock_update, mock_context)

    # Verify response
    mock_update.message.reply_text.assert_any_call("✅ Uploaded test.pdf. Run /process_inbox to log it.")