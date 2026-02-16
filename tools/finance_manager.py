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

# ✅ Import the Reader class
from tools.finance_reader import FinanceReader

class FinanceManager:
    def __init__(self):
        # 1. Load Config
        with open('config.json', 'r') as f:
            config = json.load(f)
            drive_config = config.get("finance", {}).get("google_drive", {})
            self.inbox_id = drive_config.get("transaction_inbox_folder_id")
            self.processed_id = drive_config.get("transaction_processed_folder_id")
            self.root_finance_id = drive_config.get("root_finance_folder_id")

        # 2. Initialize the Reader Instance
        # ✅ This fixes the "name 'reader' is not defined" error
        self.reader = FinanceReader()

        # 3. Setup Google Services
        self.creds = service_account.Credentials.from_service_account_file(
            'secrets/service_account.json', 
            scopes=['https://www.googleapis.com/auth/drive', 'https://www.googleapis.com/auth/spreadsheets']
        )
        self.drive = build('drive', 'v3', credentials=self.creds)
        self.sheets = build('sheets', 'v4', credentials=self.creds)

    def get_or_create_yearly_ledger(self, year):
        """Finds or creates 'Finance_Ledger_YYYY' in the root finance folder."""
        query = f"name = 'Finance_Ledger_{year}' and '{self.root_finance_id}' in parents and trashed = false"
        results = self.drive.files().list(q=query, fields="files(id)").execute()
        files = results.get('files', [])
        if files: return files[0]['id']

        meta = {
            'name': f'Finance_Ledger_{year}', 
            'parents': [self.root_finance_id], 
            'mimeType': 'application/vnd.google-apps.spreadsheet'
        }
        return self.drive.files().create(body=meta, fields='id').execute().get('id')

    def ensure_tab(self, ss_id, month_name):
        ss = self.sheets.spreadsheets().get(spreadsheetId=ss_id).execute()
        sheets = [s['properties']['title'] for s in ss.get('sheets', [])]
        
        if month_name not in sheets:
            # 1. Create the tab
            body = {'requests': [{'addSheet': {'properties': {'title': month_name}}}]}
            self.sheets.spreadsheets().batchUpdate(spreadsheetId=ss_id, body=body).execute()
            
            # 2. Add and Bold the Headers
            headers = [["Date", "Description", "Amount", "Type", "Category", "Source"]]
            self.sheets.spreadsheets().values().update(
                spreadsheetId=ss_id, range=f"'{month_name}'!A1",
                valueInputOption='USER_ENTERED', body={'values': headers}
            ).execute()
            
            # Format headers: Bold + Center
            tab_id = self.get_tab_id(ss_id, month_name)
            header_format = {
                'requests': [{
                    'repeatCell': {
                        'range': {'sheetId': tab_id, 'startRowIndex': 0, 'endRowIndex': 1},
                        'cell': {'userEnteredFormat': {
                            'textFormat': {'bold': True},
                            'horizontalAlignment': 'CENTER'
                        }},
                        'fields': 'userEnteredFormat(textFormat,horizontalAlignment)'
                    }
                }]
            }
            self.sheets.spreadsheets().batchUpdate(spreadsheetId=ss_id, body=header_format).execute()

    def process_financial_inbox(self):
        """Processes all pending files, grouping transactions by their actual dates."""
        all_files = self.reader.get_all_files_from_inbox()
        
        if not all_files:
            return "Inbox is empty. No new files to process."

        processed_count = 0
        total_audit_msg = ""
        # Track every (year, month) combination touched across all files
        touched_ledgers = set() 

        for file_id, filename, content, mime_type in all_files:
            # 1. Parse Data
            if mime_type == 'application/pdf':
                parsed_data = self.reader.parse_pdf_with_gemini(content)
                transactions = parsed_data.get('transactions', [])
                statement_total = parsed_data.get('statement_total', 0)
            else:
                transactions = pd.read_csv(io.BytesIO(content)).to_dict(orient='records')
                statement_total = sum(i.get('amount', 0) for i in transactions)

            # 2. Audit Check (Check the file's integrity before splitting)
            extracted_sum = sum(i.get('amount', 0) for i in transactions)
            if abs(round(extracted_sum, 2) - round(statement_total, 2)) > 0.01:
                total_audit_msg += f"\n⚠️ {filename}: Sum ({extracted_sum:.2f}) != Total ({statement_total:.2f})"

            # 3. Group transactions by (Year, Month)
            grouped_rows = {}
            for tx in transactions:
                try:
                    # Expecting YYYY-MM-DD from our Gemini Schema
                    dt = datetime.strptime(tx['date'], '%Y-%m-%d')
                    year_key = dt.year
                    month_key = dt.strftime('%b')
                    
                    target = (year_key, month_key)
                    if target not in grouped_rows:
                        grouped_rows[target] = []
                    
                    grouped_rows[target].append([
                        tx.get('date'), tx.get('description'), tx.get('amount'), 
                        tx.get('type'), tx.get('category', 'Other'), filename
                    ])
                except Exception as e:
                    print(f"Skipping row due to date error: {tx.get('date')} - {e}")

            # 4. File each group into its respective Tab/Yearly Doc
            for (y, m), rows in grouped_rows.items():
                ss_id = self.get_or_create_yearly_ledger(y)
                self.ensure_tab(ss_id, m)
                touched_ledgers.add((ss_id, m)) # Store for final formatting/sorting

                self.sheets.spreadsheets().values().append(
                    spreadsheetId=ss_id, range=f"'{m}'!A2", 
                    valueInputOption='USER_ENTERED', body={'values': rows}
                ).execute()
            
            # 5. Cleanup file
            self.reader.move_file(file_id)
            processed_count += 1

        # 6. Final Formatting & Sorting for every tab affected
        for ss_id, month_name in touched_ledgers:
            tab_id = self.get_tab_id(ss_id, month_name)
            
            # Formatting batch
            fmt_reqs = [
                { # Currency Column C
                    'repeatCell': {
                        'range': {'sheetId': tab_id, 'startRowIndex': 1, 'startColumnIndex': 2, 'endColumnIndex': 3},
                        'cell': {'userEnteredFormat': {'numberFormat': {'type': 'CURRENCY'}}},
                        'fields': 'userEnteredFormat.numberFormat'
                    }
                },
                { # Auto-resize A-F
                    'autoResizeDimensions': {
                        'dimensions': {'sheetId': tab_id, 'dimension': 'COLUMNS', 'startIndex': 0, 'endIndex': 6}
                    }
                }
            ]
            self.sheets.spreadsheets().batchUpdate(spreadsheetId=ss_id, body={'requests': fmt_reqs}).execute()
            
            # Final Sort
            self.sort_tab_by_date(ss_id, month_name)

        return f"Successfully processed {processed_count} files across multiple tabs.{total_audit_msg}"
    
    def get_tab_id(self, ss_id, month_name):
        ss = self.sheets.spreadsheets().get(spreadsheetId=ss_id).execute()
        for s in ss.get('sheets', []):
            if s['properties']['title'] == month_name:
                return s['properties']['sheetId']
        return 0

    def sort_tab_by_date(self, ss_id, month_name):
        """Sorts the specified tab by Date (Column A) in ascending order."""
        tab_id = self.get_tab_id(ss_id, month_name)
        
        sort_request = {
            'requests': [{
                'sortRange': {
                    'range': {
                        'sheetId': tab_id,
                        'startRowIndex': 1,  # Skip the bold header row
                        'startColumnIndex': 0,
                        'endColumnIndex': 6   # Covers A through F
                    },
                    'sortSpecs': [{
                        'dimensionIndex': 0, # Sort by Column A (Date)
                        'sortOrder': 'ASCENDING'
                    }]
                }
            }]
        }
        self.sheets.spreadsheets().batchUpdate(spreadsheetId=ss_id, body=sort_request).execute()

    def query_spending(self, year, month):
        # ... (keep existing query logic)
        pass