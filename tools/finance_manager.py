import os
import json
import io
import pandas as pd
from datetime import datetime
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2 import service_account
from google import genai
from google.genai import types

# ✅ Import categories from the centralized constants file
from tools.constants import MASTER_CATEGORIES

class FinanceManager:
    def __init__(self):
        # 1. Load Config
        with open('config.json', 'r') as f:
            config = json.load(f)
            self.api_key = config.get("gemini", {}).get("api_key")
            drive_config = config.get("finance", {}).get("google_drive", {})
            self.inbox_id = drive_config.get("transaction_inbox_folder_id")
            self.processed_id = drive_config.get("transaction_processed_folder_id")
            self.root_finance_id = drive_config.get("root_finance_folder_id")

        self.creds = service_account.Credentials.from_service_account_file(
            'secrets/service_account.json', 
            scopes=['https://www.googleapis.com/auth/drive', 'https://www.googleapis.com/auth/spreadsheets']
        )
        self.drive = build('drive', 'v3', credentials=self.creds)
        self.sheets = build('sheets', 'v4', credentials=self.creds)

    def get_or_create_yearly_ledger(self, year):
        query = f"name = 'Finance_Ledger_{year}' and '{self.root_finance_id}' in parents and trashed = false"
        results = self.drive.files().list(q=query, fields="files(id)").execute()
        files = results.get('files', [])
        if files: return files[0]['id']

        meta = {'name': f'Finance_Ledger_{year}', 'parents': [self.root_finance_id], 'mimeType': 'application/vnd.google-apps.spreadsheet'}
        return self.drive.files().create(body=meta, fields='id').execute().get('id')

    def ensure_tab(self, ss_id, month):
        ss = self.sheets.spreadsheets().get(spreadsheetId=ss_id).execute()
        if not any(s['properties']['title'] == month for s in ss.get('sheets', [])):
            self.sheets.spreadsheets().batchUpdate(spreadsheetId=ss_id, body={'requests': [{'addSheet': {'properties': {'title': month}}}]}).execute()
            headers = [["Date", "Description", "Amount", "Type", "Category", "Source"]]
            self.sheets.spreadsheets().values().update(spreadsheetId=ss_id, range=f"'{month}'!A1", valueInputOption='RAW', body={'values': headers}).execute()

    def process_latest_file(self):
        """Orchestrates the workflow: Download -> Parse -> Scale -> Move."""
        reader = FinanceReader()
        file_data = reader.get_latest_file_from_inbox()
        if isinstance(file_data, str): return file_data

        file_id, filename, content, mime_type = file_data
        
        # Determine metadata
        source = "Chase" if "chase" in filename.lower() else "Bank Statement"
        now = datetime.now()
        year, month = now.year, now.strftime('%b')

        # Parse and Log
        data = reader.parse_with_gemini(content) if mime_type == 'application/pdf' else pd.read_csv(io.BytesIO(content)).to_dict(orient='records')
        
        rows = [[i.get('date'), i.get('description'), i.get('amount'), i.get('type'), i.get('category', 'Other'), source] for i in data]
        
        ss_id = self.get_or_create_yearly_ledger(year)
        self.ensure_tab(ss_id, month)
        self.sheets.spreadsheets().values().append(spreadsheetId=ss_id, range=f"'{month}'!A2", valueInputOption='USER_ENTERED', body={'values': rows}).execute()
        
        reader.move_file(file_id)
        return f"Successfully filed {len(rows)} transactions from {filename} into {month} {year}."

    def query_spending(self, year, month):
        try:
            ss_id = self.get_or_create_yearly_ledger(year)
            res = self.sheets.spreadsheets().values().get(spreadsheetId=ss_id, range=f"'{month}'!A:F").execute()
            rows = res.get('values', [])
            return pd.DataFrame(rows[1:], columns=rows[0]).to_json(orient="records") if rows else "No data."
        except Exception as e: return f"Error: {e}"