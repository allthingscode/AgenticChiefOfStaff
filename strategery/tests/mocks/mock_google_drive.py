from unittest.mock import MagicMock


def get_mock_drive_service():
    """
    Simulates Google Drive API for listing and downloading bank statements.
    """
    mock_service = MagicMock()

    # Mock the .list().execute() chain
    mock_files = {
        'files': [
            {'id': 'file_1', 'name': 'Chase_Oct_2025.pdf', 'mimeType': 'application/pdf'}
        ]
    }
    mock_service.files().list().execute.return_value = mock_files

    # Mock the .get_media() request
    mock_request = MagicMock()
    mock_service.files().get_media.return_value = mock_request

    return mock_service
