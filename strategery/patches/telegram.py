from pathlib import Path
from functools import wraps
import asyncio
from strategery.strategic_logger import strategic_logger

def strategic_get_media_path(base_workspace, original_path):
    """Calculates the strategic redirection path for Telegram media."""
    if not original_path or ".nanobot\\media" not in str(original_path):
        return original_path
        
    workspace = Path(base_workspace or Path.home() / ".nanobot" / "workspace")
    filename = Path(original_path).name
    return str(workspace / "media" / filename)

def strategic_detect_thread_metadata(message, chat_id):
    """Detects message_thread_id and returns a session_key_override if applicable."""
    if hasattr(message, 'message_thread_id') and message.message_thread_id:
        return {
            "message_thread_id": message.message_thread_id,
            "session_key_override": f"telegram:{chat_id}:{message.message_thread_id}"
        }
    return None

def strategic_prepare_telegram_media(media_path, bot):
    """
    Selects the correct sender method and parameter name based on media type.
    Returns: (sender_func, param_name, media_type)
    """
    # Core import locally to avoid bootstrap failure
    from nanobot.channels.telegram import TelegramChannel
    mtype = TelegramChannel._get_media_type(media_path)
    sender = {
        "photo": bot.send_photo, 
        "voice": bot.send_voice, 
        "audio": bot.send_audio
    }.get(mtype, bot.send_document)
    
    param = "photo" if mtype == "photo" else mtype if mtype in ("voice", "audio") else "document"
    return sender, param, mtype

async def strategic_telegram_polling_loop(channel):
    """Resilience Loop for Telegram start_polling."""
    from telegram.error import NetworkError
    retry_delay = 5
    while channel._running:
        try:
            if channel._app and channel._app.updater and not channel._app.updater.running:
                strategic_logger.info("Telegram: (Re)starting polling loop...")
                await channel._app.updater.start_polling(
                    allowed_updates=["message"],
                    drop_pending_updates=True
                )
                retry_delay = 5 # Reset on success
            
            await asyncio.sleep(1)
        except NetworkError as e:
            strategic_logger.warning(f"Telegram: Network error during polling: {e}. Retrying in {retry_delay}s...")
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, 60) # Exponential backoff
        except Exception as e:
            strategic_logger.error(f"Telegram: Unexpected error in polling loop: {e}")
            await asyncio.sleep(5)

async def strategic_telegram_on_message(channel, update, context, orig_on_message):
    """Patched message handler with Media Redirection and Topic support."""
    strategic_logger.debug(f"Telegram: Received update {update.update_id}")
    if update.message:
        # Media Redirection
        media_file = None
        if update.message.photo: media_file = update.message.photo[-1]
        elif update.message.voice: media_file = update.message.voice
        elif update.message.audio: media_file = update.message.audio
        elif update.message.document: media_file = update.message.document
        
        if media_file:
            _orig_get_file = context.bot.get_file
            async def _patched_get_file(file_id, *args, **kwargs):
                file = await _orig_get_file(file_id, *args, **kwargs)
                _orig_download = file.download_to_drive
                async def _patched_download(custom_path=None, *args, **kwargs):
                    workspace = getattr(channel.config, "workspace_path", None)
                    new_path = strategic_get_media_path(workspace, custom_path)
                    if new_path != custom_path:
                        strategic_logger.info(f"Telegram Media Redirection: {new_path}")
                    return await _orig_download(custom_path=new_path, *args, **kwargs)
                file.download_to_drive = _patched_download
                return file
            context.bot.get_file = _patched_get_file

    # STRATEGIC EDITION: Handle Telegram Topics (threads)
    thread_meta = strategic_detect_thread_metadata(update.message, update.message.chat_id if update.message else None)
    if thread_meta:
        strategic_logger.debug(f"Telegram: Thread ID detected: {thread_meta['message_thread_id']}")
        orig_hm = channel._handle_message
        async def temp_hm(msg, chat_id, text=None, session_key=None, metadata=None):
            metadata = dict(metadata or {})
            metadata.update(thread_meta)
            return await orig_hm(msg, chat_id, text=text, session_key=thread_meta["session_key_override"], metadata=metadata)
        
        channel._handle_message = temp_hm
        try:
            return await orig_on_message(update, context)
        finally:
            channel._handle_message = orig_hm
    else:
        try:
            return await orig_on_message(update, context)
        except Exception as e:
            strategic_logger.error(f"Telegram: Error in original _on_message: {e}")
            raise

async def strategic_telegram_send(channel, msg):
    """Thread-aware message and media sender."""
    from nanobot.channels.telegram import _markdown_to_telegram_html, TELEGRAM_MAX_MESSAGE_LEN
    from nanobot.utils.helpers import split_message
    from telegram import ReplyParameters
    
    if not channel._app: return
    channel._stop_typing(msg.chat_id)
    try: chat_id = int(msg.chat_id)
    except: return

    thread_id = msg.metadata.get("message_thread_id")
    reply_params = None
    if channel.config.reply_to_message:
        if reply_to_id := msg.metadata.get("message_id"):
            reply_params = ReplyParameters(message_id=reply_to_id, allow_sending_without_reply=True)

    # Send media
    for media_path in (msg.media or []):
        try:
            sender, param, mtype = strategic_prepare_telegram_media(media_path, channel._app.bot)
            with open(media_path, 'rb') as f:
                kwargs = {param: f, "chat_id": chat_id, "reply_parameters": reply_params}
                if thread_id: kwargs["message_thread_id"] = int(thread_id)
                await sender(**kwargs)
        except Exception as e:
            strategic_logger.error(f"Failed to send media: {e}")

    # Send text
    if msg.content and msg.content != "[empty message]":
        for chunk in split_message(msg.content, TELEGRAM_MAX_MESSAGE_LEN):
            try:
                html = _markdown_to_telegram_html(chunk)
                kwargs = {"chat_id": chat_id, "text": html, "parse_mode": "HTML", "reply_parameters": reply_params}
                if thread_id: kwargs["message_thread_id"] = int(thread_id)
                await channel._app.bot.send_message(**kwargs)
            except Exception as e:
                kwargs = {"chat_id": chat_id, "text": chunk, "reply_parameters": reply_params}
                if thread_id: kwargs["message_thread_id"] = int(thread_id)
                await channel._app.bot.send_message(**kwargs)

from .base import BasePatch, PatchResult

class TelegramPatch(BasePatch):
    """Handles Telegram Topic support, Media Redirection, and thread-aware message sending."""
    
    @property
    def name(self) -> str:
        return "Telegram Advanced Integration"

    def apply(self, config_data: dict) -> PatchResult:
        result = PatchResult(patch_name=self.name, success=True)
        try:
            from nanobot.channels.telegram import TelegramChannel
            self._patch_telegram_channel(TelegramChannel, config_data)
            result.affected_symbols.extend([
                "TelegramChannel.start", 
                "TelegramChannel._on_message", 
                "TelegramChannel.send",
                "TelegramChannel._on_error"
            ])
            return result
        except Exception as e:
            import traceback
            result.success = False
            result.error_msg = str(e)
            result.traceback = traceback.format_exc()
            strategic_logger.error(f"Telegram patch error: {e}")
            return result

    def _patch_telegram_channel(self, TelegramChannel, config_data):
        from telegram.ext import CommandHandler

        disable_commands = config_data.get("strategic_edition", {}).get("disable_bot_commands", False)
        
        if not hasattr(TelegramChannel, "_orig_start_strategic"):
            TelegramChannel._orig_start_strategic = TelegramChannel.start
            
            async def _strategic_start(self):
                strategic_logger.info(f"Telegram: Starting strategic channel (disable_commands={disable_commands})...")
                
                if disable_commands:
                    strategic_logger.debug("Telegram: Disabling default bot commands...")
                    _orig_init = CommandHandler.__init__
                    def _patched_init(handler_self, command, callback, *args, **kwargs):
                        if command in ["start", "new", "help"]:
                            return _orig_init(handler_self, "disabled_cmd_" + command, lambda u, c: None, *args, **kwargs)
                        return _orig_init(handler_self, command, callback, *args, **kwargs)
                    
                    CommandHandler.__init__ = _patched_init
                    try:
                        asyncio.create_task(self._orig_start_strategic())
                    finally:
                        CommandHandler.__init__ = _orig_init
                else:
                    asyncio.create_task(self._orig_start_strategic())

                await strategic_telegram_polling_loop(self)

            TelegramChannel.start = _strategic_start

        if not hasattr(TelegramChannel, "_orig_on_message_strategic"):
            TelegramChannel._orig_on_message_strategic = TelegramChannel._on_message
            
            async def _strategic_on_message(self, update, context):
                return await strategic_telegram_on_message(self, update, context, self._orig_on_message_strategic)
            
            TelegramChannel._on_message = _strategic_on_message

        async def _thread_aware_send_wrapper(self, msg):
            return await strategic_telegram_send(self, msg)

        TelegramChannel.send = _thread_aware_send_wrapper

        if not hasattr(TelegramChannel, "_orig_on_error_strategic"):
            TelegramChannel._orig_on_error_strategic = TelegramChannel._on_error
            
            async def _strategic_on_error(self, update, context):
                from telegram.error import NetworkError, TimedOut
                err_str = str(context.error)
                
                # SUPPRESS NOISY TRANSIENT NETWORK ERRORS (BUG-060, BUG-092)
                # These often happen during polling and produce massive multi-page tracebacks.
                suppress_patterns = [
                    "ReadError", 
                    "RemoteProtocolError", 
                    "Timed out", 
                    "ConnectError",
                    "Connection reset by peer"
                ]
                
                if isinstance(context.error, (NetworkError, TimedOut)) or any(p in err_str for p in suppress_patterns):
                    strategic_logger.warning(f"Telegram: Transient network noise suppressed: {err_str}")
                    return
                
                return await self._orig_on_error_strategic(update, context)
                
            TelegramChannel._on_error = _strategic_on_error
