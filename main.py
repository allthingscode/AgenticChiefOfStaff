import json, psutil, logging, sys, io
from google import genai
from google.genai import types
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes
from googleapiclient.http import MediaIoBaseUpload

from tools.finance_manager import FinanceManager 

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

def load_config():
    with open('config.json', 'r', encoding='utf-8-sig') as f:
        return json.load(f)

config = load_config()
AUTH_USER_ID = int(config['telegram']['authorized_user_id'])
BOT_TOKEN = config['telegram']['bot_token']
LOCATION = config.get('user', {}).get('location', 'Sachse, TX')

client = genai.Client(api_key=config['gemini']['api_key'])
SYSTEM_PROMPT = f"You are the 'Chief of Staff' for Matthew in {LOCATION}."

# 1. Initialize the Scaling Finance Manager
fm = FinanceManager()

# --- ✅ CLEAN TOOLS FOR GEMINI (Defined before usage) ---

def run_finance_processing():
    """Scans the GDrive inbox, parses statements with Gemini, and updates the yearly ledger."""
    return fm.process_latest_file()

def get_system_status():
    """Returns the current CPU usage of the agent's dedicated machine."""
    return f"CPU Usage: {psutil.cpu_percent()}%"

def get_spending_report(year: int, month: str):
    """
    Retrieves transaction data for a specific month/year.
    The AI uses this to answer questions about spending.
    """
    return fm.query_spending(year, month)

# --- 🛰️ TELEGRAM COMMAND HANDLERS ---

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != AUTH_USER_ID: return
    doc = update.message.document
    await update.message.reply_text(f"🦅 Financial Hawk: Receiving {doc.file_name}...")
    try:
        tg_file = await context.bot.get_file(doc.file_id)
        file_stream = io.BytesIO()
        await tg_file.download_to_memory(file_stream)
        file_stream.seek(0)

        media = MediaIoBaseUpload(file_stream, mimetype=doc.mime_type)
        fm.drive.files().create(
            body={'name': doc.file_name, 'parents': [fm.inbox_id]},
            media_body=media
        ).execute()
        await update.message.reply_text(f"✅ Uploaded {doc.file_name}. Run /process_inbox to log it.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != AUTH_USER_ID: return
    cpu = psutil.cpu_percent(interval=0.1)
    await update.message.reply_text(f"🖥️ Status: ONLINE | CPU: {cpu}%")

async def process_inbox_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != AUTH_USER_ID: return
    await update.message.reply_text("⏳ Scaling Manager: Processing financial inbox...")
    try:
        result = fm.process_latest_file()
        await update.message.reply_text(f"✅ {result}")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

# --- 🧠 THE BRAIN: AI MESSAGE HANDLER ---

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != AUTH_USER_ID: return
    
    response = client.models.generate_content(
        model='gemini-2.0-flash',
        contents=update.message.text,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT, 
            tools=[get_system_status, run_finance_processing, get_spending_report] 
        )
    )
    await update.message.reply_text(response.text)

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("process_inbox", process_inbox_command))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()