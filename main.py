import json, psutil, logging, sys, io
from google import genai
from google.genai import types
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes
from googleapiclient.http import MediaIoBaseUpload

from tools.sys_monitor import get_system_metrics
from tools.finance_reader import read_financial_inbox, FinanceReader

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

def load_config():
    with open('config.json', 'r', encoding='utf-8-sig') as f:
        return json.load(f)

config = load_config()

# CONSISTENT NESTED ACCESS
AUTH_USER_ID = int(config['telegram']['authorized_user_id'])
BOT_TOKEN = config['telegram']['bot_token']
LOCATION = config.get('user', {}).get('location', 'Sachse, TX')

client = genai.Client(api_key=config['gemini']['api_key'])

SYSTEM_PROMPT = f"You are the 'Chief of Staff' for Matthew in {LOCATION}."

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != AUTH_USER_ID: return
    
    doc = update.message.document
    await update.message.reply_text(f"🦅 Financial Hawk: Receiving {doc.file_name}...")

    try:
        tg_file = await context.bot.get_file(doc.file_id)
        file_stream = io.BytesIO()
        await tg_file.download_to_memory(file_stream)
        file_stream.seek(0)

        reader = FinanceReader()
        media = MediaIoBaseUpload(file_stream, mimetype=doc.mime_type)
        reader.drive_service.files().create(
            body={'name': doc.file_name, 'parents': [reader.inbox_folder_id]},
            media_body=media
        ).execute()

        await update.message.reply_text(f"✅ Uploaded {doc.file_name} to the financial inbox. Run /process_inbox to process it.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != AUTH_USER_ID: return
    cpu = psutil.cpu_percent(interval=0.1)
    await update.message.reply_text(f"🖥️ Status: ONLINE | CPU: {cpu}%")

async def process_inbox_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != AUTH_USER_ID: return
    await update.message.reply_text("⏳ Processing financial inbox...")
    try:
        result = read_financial_inbox()
        if isinstance(result, dict):
            await update.message.reply_text(f"✅ {result.get('message', 'Processing complete.')}")
        else:
            await update.message.reply_text(f"✅ {result}")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != AUTH_USER_ID: return
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=update.message.text,
        config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT, tools=[get_system_metrics, read_financial_inbox, process_inbox_command])
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