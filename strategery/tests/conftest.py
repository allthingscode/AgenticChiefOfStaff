import pytest
from unittest.mock import patch, MagicMock

# Use absolute imports based on the project root
from tests.mocks.config_mock import get_mock_config_json

@pytest.fixture(autouse=True)
def global_config_patch():
    with patch("builtins.open", MagicMock()) as mock_open:
        mock_open.return_value.__enter__.return_value.read.return_value = get_mock_config_json()
        yield mock_open

@pytest.fixture
def drive_service():
    from tests.mocks.drive_mock import get_mock_drive_service
    mock_svc = get_mock_drive_service()
    with patch("googleapiclient.discovery.build", return_value=mock_svc):
        yield mock_svc