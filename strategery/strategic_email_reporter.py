"""
STRATEGIC SURGICAL OVERRIDE: Email Report Delivery
Reasoning: Standard channel-based email in Nanobot is for user interaction, 
this script is a dedicated MCP wrapper for automated, high-reliability delivery 
to the configured user email for briefings.
"""
import base64
from email.message import EmailMessage
import json
import os
import sys
import logging
from pathlib import Path
from datetime import datetime

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from fastmcp import FastMCP

# --- Logging Setup ---
# Use the D: drive log directory if available, otherwise local
LOG_DIR = Path(os.environ.get("STRATEGIC_LOG_DIR", "./logs"))
try:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    LOG_DIR = Path("./logs")
    LOG_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("EmailReporter")
logger.setLevel(logging.DEBUG)
log_file = LOG_DIR / "email_reporter.log"
fh = logging.FileHandler(log_file, encoding='utf-8')
fh.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
logger.addHandler(fh)

logger.info("Email Reporter MCP starting up...")

# Detect config path
def get_config():
    # Priority: System config, local fallback
    home_config = Path.home() / ".nanobot" / "config.json"
    if home_config.exists():
        try:
            with open(home_config, "r", encoding="utf-8-sig") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading config: {e}")
    return {}

CONFIG = get_config()
STRATEGIC = CONFIG.get("strategic_edition", {})
USER_EMAIL = STRATEGIC.get("user_email", "admin@example.com")

# Use storage_root if available, fallback to ~/.nanobot
_default_root = str(Path.home() / ".nanobot")
STORAGE_ROOT = Path(STRATEGIC.get("storage_root", _default_root))

# 1. Credentials Setup (Standardized on C: drive for security and idiomatic Windows setup)
SECRETS_ROOT = Path.home() / ".nanobot" / "secrets"
TOKEN_PATH = SECRETS_ROOT / "token.json"
CREDS_PATH = SECRETS_ROOT / "credentials.json"
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

logger.debug(f"Paths: STORAGE_ROOT={STORAGE_ROOT}, TOKEN_PATH={TOKEN_PATH}")

def get_gmail_service():
    creds = None
    if TOKEN_PATH.exists():
        logger.debug(f"Found token at {TOKEN_PATH}")
        try:
            with open(TOKEN_PATH, "r") as token:
                creds_data = json.load(token)
                creds = Credentials.from_authorized_user_info(creds_data, SCOPES)
        except Exception as e:
            logger.error(f"Error loading token.json: {e}")
            
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logger.info("Refreshing Gmail token...")
            try:
                creds.refresh(Request())
                with open(TOKEN_PATH, "w") as token:
                    token.write(creds.to_json())
                logger.info("Token refreshed successfully.")
            except Exception as e:
                logger.error(f"Failed to refresh token: {e}")
                # Don't raise here, allow the tool to catch it and fall back
                return None
        else:
            logger.error(f"No valid credentials found at {TOKEN_PATH}.")
            return None
            
    try:
        return build("gmail", "v1", credentials=creds, static_discovery=True)
    except Exception as e:
        logger.error(f"Failed to build gmail service: {e}")
        return None

mcp = FastMCP("Email Reporter")

def fallback_notify(subject: str, body: str, recipient: str, reason: str = "Unknown error") -> str:
    """Fallback: Writes the notification to a local file in the workspace."""
    notif_file = STORAGE_ROOT / "workspace" / "NOTIFICATIONS.md"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    entry = f"\n---\n### 📬 [{timestamp}] {subject}\n**To:** {recipient}\n**Fallback Reason:** {reason}\n\n{body}\n"
    
    try:
        # Ensure workspace exists
        notif_file.parent.mkdir(parents=True, exist_ok=True)
        
        mode = "a" if notif_file.exists() else "w"
        with open(notif_file, mode, encoding="utf-8") as f:
            if mode == "w":
                f.write("# 📬 Strategic Notifications (Fallback)\n")
            f.write(entry)
            
        msg = f"Gmail unavailable ({reason}). Report saved to fallback: {notif_file}"
        logger.warning(msg)
        return msg
    except Exception as e:
        err = f"CRITICAL: Fallback notification failed entirely. Original error: {reason}. Disk write error: {e}"
        logger.error(err)
        return err

@mcp.tool()
def send_email_report(subject: str, body: str, to: str = None) -> str:
    """Sends an email report to the user. Supports HTML formatting. Falls back to local disk if Gmail fails."""
    try:
        recipient = to if to else USER_EMAIL
        logger.info(f"Tool Call: send_email_report(subject='{subject}', recipient='{recipient}')")
        
        service = None
        service_error = None
        try:
            service = get_gmail_service()
        except Exception as e:
            service_error = str(e)
            logger.error(f"get_gmail_service exception: {e}")

        if not service:
            return fallback_notify(subject, body, recipient, reason=service_error or "Service failed to initialize (Token expired?)")

        try:
            logger.debug("Gmail service initialized.")
            
            message = EmailMessage()
            message["To"] = recipient
            message["Subject"] = subject
            
            # F-014: High-Readability HTML Reports
            is_html = "<html" in body.lower() or "<body>" in body.lower() or "<h1" in body.lower() or "<p>" in body.lower()
            
            if is_html:
                # Provide a plain text fallback (stripping basic tags is complex here, so we just send raw as text fallback)
                message.set_content("This report requires an HTML-compatible email client to view correctly.\n\n" + body)
                
                # Inject high-readability Matte Obsidian Dark CSS
                style_block = """
                <style>
                  body {
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    line-height: 1.6;
                    color: #d1d1d1; 
                    background-color: #0a0b10; 
                    margin: 0;
                    padding: 20px;
                  }
                  .container {
                    max-width: 800px;
                    margin: 0 auto;
                    background: #161b22; 
                    padding: 40px;
                    border: 1px solid #30363d; 
                    border-radius: 4px;
                  }
                  h1, h2, h3 { 
                    color: #58a6ff; 
                    text-transform: uppercase;
                    letter-spacing: 1px;
                    border-bottom: 2px solid #30363d;
                    padding-bottom: 10px;
                    margin-top: 30px;
                  }
                  .vitality, .quote { 
                    font-style: italic;
                    color: #79c0ff; 
                    font-size: 1.1em;
                    margin: 20px 0;
                    border-left: 4px solid #388bfd;
                    padding-left: 15px;
                  }
                  .schedule-item {
                    padding: 12px 0;
                    border-bottom: 1px solid #21262d; 
                  }
                  .time {
                    font-weight: bold;
                    color: #58a6ff;
                    min-width: 180px;
                  }
                  .goal-card {
                    margin-top: 20px;
                    padding: 15px;
                    background-color: #0d1117;
                    border-left: 5px solid #30363d;
                  }
                  .on-track {
                    border-left-color: #238636;
                  }
                  .needs-attention {
                    border-left-color: #d29922;
                  }
                  .status-label {
                    font-weight: bold;
                    margin-bottom: 5px;
                  }
                  .footer {
                    font-size: 0.85em;
                    color: #8b949e;
                    text-align: center;
                    margin-top: 40px;
                    font-style: italic;
                  }
                  ul { list-style-type: square; }
                  li { margin-bottom: 10px; }
                  strong { color: #58a6ff; }
                  a { color: #58a6ff; text-decoration: none; border-bottom: 1px dotted #58a6ff; }
                  hr { border: 0; border-top: 1px solid #30363d; margin: 40px 0; }
                  code { background: #0d1117; padding: 2px 5px; color: #79c0ff; }
                </style>
                """
                # Simple wrapper if not a full HTML document
                if "<html" not in body.lower():
                    html_content = f"<!DOCTYPE html><html><head>{style_block}</head><body><div class='container'>{body}</div></body></html>"
                else:
                    # Inject into existing head if possible
                    if "</head>" in body.lower():
                        html_content = body.replace("</head>", f"{style_block}</head>", 1)
                        html_content = body.replace("</HEAD>", f"{style_block}</HEAD>", 1) if html_content == body else html_content
                    else:
                        html_content = f"{style_block}\n{body}"
                    
                    # Wrap existing body content if container class is missing
                    if "class='container'" not in html_content and 'class="container"' not in html_content:
                        if "<body>" in html_content:
                            html_content = html_content.replace("<body>", "<body><div class='container'>", 1).replace("</body>", "</div></body>", 1)
                        elif "<BODY>" in html_content:
                            html_content = html_content.replace("<BODY>", "<BODY><div class='container'>", 1).replace("</BODY>", "</div></BODY>", 1)
                        
                message.add_alternative(html_content, subtype='html')
            else:
                message.set_content(body)
            
            encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
            create_message = {"raw": encoded_message}
            
            logger.debug("Sending message via Gmail API...")
            send_message = service.users().messages().send(userId="me", body=create_message).execute()
            
            result = f"Email sent successfully to {recipient}. Message ID: {send_message['id']}"
            logger.info(result)
            return result
        except Exception as e:
            logger.error(f"Gmail delivery failed: {e}")
            return fallback_notify(subject, body, recipient, reason=str(e))
    except Exception as fatal_e:
        err = f"FATAL ERROR in MCP Tool (send_email_report): {fatal_e}"
        logger.error(err)
        return err

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "mcp_wrapper":
        logger.info("Starting FastMCP runner...")
        try:
            mcp.run()
        except Exception as startup_err:
            logger.critical(f"FastMCP runner crashed: {startup_err}", exc_info=True)
            # Re-raise to ensure the process actually exits and doesn't hang
            raise
    else:
        print("Run with 'mcp_wrapper' to start the MCP server.")
