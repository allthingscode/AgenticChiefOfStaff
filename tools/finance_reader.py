import datetime
import io, json, logging
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2 import service_account
from google import genai
from google.genai import types
from tools.constants import MASTER_CATEGORIES
from tools.prompts import get_prompt, SYSTEM_IDENTITY

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
        # 1. Fetch the instructions from our new prompts.py
        category_list_str = ", ".join(MASTER_CATEGORIES)
        task_instructions = get_prompt('FINANCIAL_INGESTION', categories=category_list_str)
        
        # 2. Combine with System Identity
        full_prompt = f"{SYSTEM_IDENTITY}\n\n{task_instructions}"

        # 3. Call Gemini with the STRICT SCHEMA intact
        res = self.ai_client.models.generate_content(
            model="models/gemini-2.5-pro",
            contents=[types.Part.from_bytes(data=pdf_bytes, mime_type='application/pdf'), full_prompt],
            config=types.GenerateContentConfig(
                temperature=0.0,        # Forces deterministic output
                response_mime_type="application/json",
                # ✅ THIS IS THE SAFETY NET
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
    
    def get_universal_finance_prompt(self, current_year, categories):
        return f"""
        TASK: Convert this financial statement into a structured JSON ledger.
        CONTEXT: Today's date is in the year {current_year}.
        
        DATA EXTRACTION GUIDELINES:
        1. SCOPE: Extract every individual transaction (money moving in or out). 
        2. IGNORE SUMMARIES: Do not extract category sub-totals, statement summaries, or "total for this period" rows. 
        3. DESCRIPTIONS: If a description spans multiple lines, merge it into a single clean string. Remove trailing reference numbers or unique transaction IDs where possible to keep descriptions human-readable.
        
        DATE NORMALIZATION:
        - Format: 'YYYY-MM-DD'.
        - YEAR INFERENCE: If the document lists dates without years (e.g., '12/25'), use the statement's metadata to infer the correct year.
        - BOUNDARY RULE: Never return a date in the future. If a transaction date would fall in the future based on the current year, it likely belongs to the previous calendar year.
        
        FINANCIAL LOGIC:
        - SIGN CONVENTION: Expenses/Purchases must be POSITIVE. Credits/Payments/Refunds must be NEGATIVE.
        - CATEGORIZATION: Use ONLY these categories: {categories}.
        
        AUDIT FIELD:
        - Find the 'New Balance', 'Closing Balance', or 'Total Amount Due' and put it in the 'statement_total' field. 
        - EXCLUSION: Completely ignore any "Points," "Rewards," or non-currency balances.
        
        JSON SCHEMA:
        {{
        "transactions": [
            {{ "date": "YYYY-MM-DD", "description": "STRING", "amount": FLOAT, "type": "DEBIT|CREDIT", "category": "STRING" }}
        ],
        "statement_total": FLOAT
        }}
        """

    def move_file(self, file_id):
        file = self.drive_service.files().get(fileId=file_id, fields='parents').execute()
        self.drive_service.files().update(
            fileId=file_id, 
            addParents=self.processed_id, 
            removeParents=",".join(file.get('parents'))
        ).execute()