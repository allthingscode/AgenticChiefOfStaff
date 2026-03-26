import json

MOCK_CONFIG_DATA = {
    "user": {
        "location": "Sachse, TX"
    },
    "gemini": {
        "api_key": "mock_gemini_key",
        "model": "gemini-2.5-flash"
    },
    "telegram": {
        "bot_token": "mock_bot_token",
        "authorized_user_id": 123456789  # THIS MUST MATCH THE TEST
    },
    "google_drive": {
        "finance_folder_id": "mock_folder_id"
    }
}

def get_mock_config_json():
    return json.dumps(MOCK_CONFIG_DATA)
