import os
import io
import json
import logging
import pandas as pd
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2 import service_account
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

SCOPES = ['https://www.googleapis.com/auth/drive', 'https://www.googleapis.com/auth/spreadsheets']
KEY_PATH = 'secrets/service_account.json'
CONFIG_PATH = 'config.json'

class FinanceReader:
    def __init__(self):
        try:
            with open(CONFIG_PATH, 'r') as f:
                config = json.load(f)
                self.api_key = config.get("gemini", {}).get("api_key")
                drive_config = config.get("finance", {}).get("google_drive", {})
                self.inbox_folder_id = drive_config.get("transaction_inbox_folder_id")
                self.processed_folder_id = drive_config.get("transaction_processed_folder_id")
                self.ledger_sheet_id = drive_config.get("general_ledger_sheet")
        except Exception as e:
            raise FileNotFoundError(f"❌ Could not read {CONFIG_PATH}: {e}")

        if not all([self.api_key, self.inbox_folder_id, self.processed_folder_id, self.ledger_sheet_id]):
            raise ValueError("❌ Missing required finance configuration in config.json")

        try:
            self.creds = service_account.Credentials.from_service_account_file(
                KEY_PATH, scopes=SCOPES
            )
            self.drive_service = build('drive', 'v3', credentials=self.creds)
            self.sheets_service = build('sheets', 'v4', credentials=self.creds)
            self.ai_client = genai.Client(api_key=self.api_key)
        except Exception as e:
            logger.error(f"Initialization failed: {e}")
            raise

    def parse_pdf_with_gemini(self, pdf_bytes):
        """Multimodal PDF parsing using Gemini 2.5 Flash."""
        prompt = """
        Extract all transactions from this bank statement into a JSON array.
        Required keys: "date", "description", "amount", "type" (DEBIT/CREDIT).
        Ignore summaries. Return ONLY raw JSON.
        """
        response = self.ai_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                types.Part.from_bytes(data=pdf_bytes, mime_type='application/pdf'),
                prompt
            ],
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        return json.loads(response.text)

    def append_to_sheet(self, df):
        """Appends a DataFrame to the Google Sheet."""
        values = [df.columns.tolist()] + df.values.tolist()
        body = {'values': values}
        self.sheets_service.spreadsheets().values().append(
            spreadsheetId=self.ledger_sheet_id,
            range='A1',
            valueInputOption='RAW',
            body=body
        ).execute()

    def move_file(self, file_id):
        """Moves a file to the processed folder."""
        file = self.drive_service.files().get(fileId=file_id, fields='parents').execute()
        previous_parents = ",".join(file.get('parents'))
        self.drive_service.files().update(
            fileId=file_id,
            addParents=self.processed_folder_id,
            removeParents=previous_parents,
            fields='id, parents'
        ).execute()

    def process_financial_inbox(self):
        try:
            query = f"'{self.inbox_folder_id}' in parents and (mimeType = 'text/csv' or mimeType = 'application/pdf') and trashed = false"
            results = self.drive_service.files().list(
                q=query, orderBy="createdTime desc", pageSize=1
            ).execute()
            
            files = results.get('files', [])
            if not files: return "No financial files found in inbox."

            file_id, filename, mime_type = files[0]['id'], files[0]['name'], files[0]['mimeType']
            
            request = self.drive_service.files().get_media(fileId=file_id)
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done: _, done = downloader.next_chunk()
            
            fh.seek(0)
            content = fh.read()

            if mime_type == 'application/pdf':
                data = self.parse_pdf_with_gemini(content)
                df = pd.DataFrame(data)
            else:
                df = pd.read_csv(io.BytesIO(content))
            
            self.append_to_sheet(df)
            self.move_file(file_id)

            return {
                "status": "success",
                "filename": filename,
                "count": len(df),
                "message": f"Processed {len(df)} transactions and moved file to processed folder."
            }
        except Exception as e:
            return f"Error: {str(e)}"

def read_financial_inbox():
    """Reads and processes the latest bank statement (PDF/CSV) from Google Drive."""
    return FinanceReader().process_financial_inbox()