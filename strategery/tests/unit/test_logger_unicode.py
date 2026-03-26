import logging
from unittest.mock import MagicMock, patch

import pytest

from strategery.strategic_logger import setup_strategic_logger


def test_logger_unicode_handling():
    """Verify that logging Unicode characters doesn't crash on Windows."""
    # 1. Setup a mock stream with cp1252 encoding
    mock_stdout = MagicMock()
    # We mock write to raise UnicodeEncodeError for emojis
    def side_effect(text):
        if "\U0001f680" in text:
            raise UnicodeEncodeError('cp1252', text, 0, 1, 'character maps to <undefined>')
        return len(text)

    mock_stdout.write.side_effect = side_effect
    mock_stdout.encoding = 'cp1252'

    # 2. Re-configure logger to use this mock stdout
    with patch("sys.stdout", mock_stdout), patch("sys.platform", "win32"):
        logger = setup_strategic_logger(name="UnicodeTest", log_dir="./test_logs_unicode")

        # 3. Log a message with an emoji
        # If the fix works, this should NOT raise UnicodeEncodeError because
        # UnicodeSafeStreamHandler catches it and uses fallback.
        try:
            logger.info("Test message with emoji: \U0001f680")
        except UnicodeEncodeError as e:
            pytest.fail(f"Logger crashed on Unicode character: {e}")

        # 4. Verify that the console handler is the correct type
        console_handler = next((h for h in logger.handlers if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)), None)
        from strategery.strategic_logger import UnicodeSafeStreamHandler
        assert isinstance(console_handler, UnicodeSafeStreamHandler)

        # 5. Verify that fallback was used (it should have called write again with escaped text)
        # The fallback should have written the escaped version
        calls = mock_stdout.write.call_args_list
        escaped_found = any("\\U0001f680" in call[0][0] for call in calls)
        assert escaped_found

    # Cleanup - Close handlers first!
    for handler in list(logger.handlers):
        handler.close()
        logger.removeHandler(handler)

    import shutil
    from pathlib import Path
    if Path("./test_logs_unicode").exists():
        shutil.rmtree("./test_logs_unicode")

if __name__ == "__main__":
    test_logger_unicode_handling()
