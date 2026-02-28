import base64
from email.message import EmailMessage
import json
import os
import sys
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from fastmcp import FastMCP

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
SECRETS_DIR = Path(r"C:\Users\HayesChiefOfStaff\.nanobot\secrets")
TOKEN_PATH = SECRETS_DIR / "token.json"
CREDS_PATH = SECRETS_DIR / "credentials.json"

def get_gmail_service():
    creds = None
    if TOKEN_PATH.exists():
        with open(TOKEN_PATH, "r") as token:
            creds_data = json.load(token)
            creds = Credentials.from_authorized_user_info(creds_data, SCOPES)
            
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(TOKEN_PATH, "w") as token:
                token.write(creds.to_json())
        else:
            raise Exception("No valid credentials found. Please ensure token.json is valid.")
            
    return build("gmail", "v1", credentials=creds)

mcp = FastMCP("Email Reporter")

@mcp.tool()
def send_email_report(subject: str, body: str, to: str = "allthingscode@gmail.com") -> str:
    """Sends an email report to the user using the configured Gmail account."""
    try:
        service = get_gmail_service()
        
        message = EmailMessage()
        message.set_content(body)
        message["To"] = to
        # Assuming the authenticated user is the sender
        message["From"] = "allthingscode@gmail.com" 
        message["Subject"] = subject
        
        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        create_message = {"raw": encoded_message}
        
        send_message = service.users().messages().send(userId="me", body=create_message).execute()
        return f"Email sent successfully. Message ID: {send_message['id']}"
    except Exception as e:
        return f"Failed to send email: {e}"

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "mcp_wrapper":
        mcp.run()
    else:
        print("Run with 'mcp_wrapper' to start the MCP server.")