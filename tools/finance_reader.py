import io, json, logging
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2 import service_account
from google import genai
from google.genai import types
from tools.constants import MASTER_CATEGORIES  # ✅ Use constants

logger = logging.getLogger(__name__)

class FinanceReader:
    def __init__(self):
        with open('config.json', 'r') as f:
            config = json.load(f)
            self.api_key = config.get("gemini", {}).get("api_key")
            drive_config = config.get("finance", {}).get("google_drive", {})
            self.inbox_id = drive_config.get("transaction_inbox_folder_id")
            self.processed_id = drive_config.get("transaction_processed_folder_id")

        self.creds = service_account.Credentials.from_service_account_file(
            'secrets/service_account.json', 
            scopes=['https://www.googleapis.com/auth/drive', 'https://www.googleapis.com/auth/spreadsheets']
        )
        self.drive_service = build('drive', 'v3', credentials=self.creds)
        self.ai_client = genai.Client(api_key=self.api_key)

    def get_latest_file_from_inbox(self):
        query = f"'{self.inbox_id}' in parents and trashed = false"
        files = self.drive_service.files().list(q=query, orderBy="createdTime desc", pageSize=1).execute().get('files', [])
        if not files: return "Inbox is empty."
        
        f = files[0]
        request = self.drive_service.files().get_media(fileId=f['id'])
        fh = io.BytesIO()
        MediaIoBaseDownload(fh, request).next_chunk()
        return f['id'], f['name'], fh.getvalue(), f['mimeType']

    def parse_pdf_with_gemini(self, pdf_bytes):
        category_list_str = ", ".join(MASTER_CATEGORIES)
        prompt = f"Extract all transactions to JSON. Use these categories: {category_list_str}."
        res = self.ai_client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[types.Part.from_bytes(data=pdf_bytes, mime_type='application/pdf'), prompt],
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        return json.loads(res.text)

    def move_file(self, file_id):
        file = self.drive_service.files().get(fileId=file_id, fields='parents').execute()
        self.drive_service.files().update(
            fileId=file_id, 
            addParents=self.processed_id, 
            removeParents=",".join(file.get('parents'))
        ).execute()