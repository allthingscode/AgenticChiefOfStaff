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

    def get_all_files_from_inbox(self):
        """Retrieves all files from the inbox, sorted by creation date (oldest first)."""
        # ✅ Sort by createdTime ascending to process chronologically
        query = f"'{self.inbox_id}' in parents and trashed = false"
        results = self.drive_service.files().list(
            q=query, 
            orderBy="createdTime", 
            fields="files(id, name, mimeType)"
        ).execute()
        
        files = results.get('files', [])
        if not files:
            return []

        file_list = []
        for f in files:
            file_id, filename, mime_type = f['id'], f['name'], f['mimeType']
            request = self.drive_service.files().get_media(fileId=file_id)
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
            
            file_list.append((file_id, filename, fh.getvalue(), mime_type))
            
        return file_list

    def parse_pdf_with_gemini(self, pdf_bytes):
        category_list_str = ", ".join(MASTER_CATEGORIES)
        
        prompt = (
            f"Extract every transaction to JSON. Use categories: {category_list_str}. "
            f"\n\nCRITICAL DATE LOGIC: "
            f"\n- You MUST return dates as 'YYYY-MM-DD'."
            f"\n- Determine the YEAR based on the statement period. "
            f"\n- Example: If the statement covers Dec of last year to Jan this year, '12/28' is '<last-year>-12-28' and '01/02' is '<this-year>-01-02'."
            f"\n- NEVER return a date in the future."
            f"\n- NEVER return a date that is after the statement date, or statement due date."
            f"\n\nCRITICAL INSTRUCTIONS: "
            f"\n1. SIGN CONVENTION: Preserve mathematical signs as shown. Payments/Credits are typically negative."
            f"\n2. AUDIT TOTAL: You MUST find the 'New Balance' or 'Total Activity' dollar amount. "
            f"\n3. IGNORE POINTS: Do NOT use values from 'Rewards Program', 'Ultimate Rewards', 'Rewards Summary', or 'Point Balance' sections. "
            f"If you see a number labeled as points, IGNORE IT. Look for the dollar amount representing the actual financial balance."
        )

        res = self.ai_client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[types.Part.from_bytes(data=pdf_bytes, mime_type='application/pdf'), prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema={
                    "type": "OBJECT",
                    "properties": {
                        "transactions": {
                            "type": "ARRAY",
                            "items": {
                                "type": "OBJECT",
                                "properties": {
                                    "date": {"type": "STRING"},
                                    "description": {"type": "STRING"},
                                    "amount": {"type": "NUMBER"},
                                    "type": {"type": "STRING"},
                                    "category": {"type": "STRING"}
                                },
                                "required": ["date", "description", "amount", "type", "category"]
                            }
                        },
                        "statement_total": {"type": "NUMBER"}
                    },
                    "required": ["transactions", "statement_total"]
                }
            )
        )
        return json.loads(res.text)

    def move_file(self, file_id):
        file = self.drive_service.files().get(fileId=file_id, fields='parents').execute()
        self.drive_service.files().update(
            fileId=file_id, 
            addParents=self.processed_id, 
            removeParents=",".join(file.get('parents'))
        ).execute()