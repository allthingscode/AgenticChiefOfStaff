from pathlib import Path
from functools import wraps
from .base import BasePatch
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
    from nanobot.channels.telegram import TelegramChannel
    mtype = TelegramChannel._get_media_type(media_path)
    sender = {
        "photo": bot.send_photo, 
        "voice": bot.send_voice, 
        "audio": bot.send_audio
    }.get(mtype, bot.send_document)
    
    param = "photo" if mtype == "photo" else mtype if mtype in ("voice", "audio") else "document"
    return sender, param, mtype

class TelegramPatch(BasePatch):
    """Handles Telegram Topic support, Media Redirection, and thread-aware message sending."""
    
    @property
    def name(self) -> str:
        return "Telegram Advanced Integration"

    def apply(self, config_data: dict) -> bool:
        try:
            from nanobot.channels.telegram import TelegramChannel
            self._patch_telegram_channel(TelegramChannel, config_data)
            return True
        except Exception as e:
            strategic_logger.error(f"Telegram patch error: {e}")
            return False

    def _patch_telegram_channel(self, TelegramChannel, config_data):
        from nanobot.channels.telegram import _split_message, _markdown_to_telegram_html
        from nanobot.bus.events import OutboundMessage
        from telegram import ReplyParameters
        from telegram.ext import CommandHandler

        # 1. Handle command registration (clean interface)
        disable_commands = config_data.get("strategic_edition", {}).get("disable_bot_commands", False)
        
        if not hasattr(TelegramChannel, "_orig_start_strategic"):
            TelegramChannel._orig_start_strategic = TelegramChannel.start
            
            async def _strategic_start(self):
                strategic_logger.info(f"Telegram: Starting strategic channel (disable_commands={disable_commands})...")
                if disable_commands:
                    strategic_logger.debug("Telegram: Disabling default bot commands...")
                    # We patch the CommandHandler class temporarily during start!
                    _orig_init = CommandHandler.__init__
                    def _patched_init(handler_self, command, callback, *args, **kwargs):
                        if command in ["start", "new", "help"]:
                            # Force a dummy callback or make it do nothing
                            return _orig_init(handler_self, "disabled_cmd_" + command, lambda u, c: None, *args, **kwargs)
                        return _orig_init(handler_self, command, callback, *args, **kwargs)
                    
                    CommandHandler.__init__ = _patched_init
                    try:
                        return await self._orig_start_strategic()
                    except Exception as e:
                        strategic_logger.error(f"Telegram: FATAL during start (with suppression): {e}")
                        raise
                    finally:
                        CommandHandler.__init__ = _orig_init
                else:
                    try:
                        return await self._orig_start_strategic()
                    except Exception as e:
                        strategic_logger.error(f"Telegram: FATAL during start: {e}")
                        raise
            
            TelegramChannel.start = _strategic_start

        if not hasattr(TelegramChannel, "_orig_on_message_strategic"):
            TelegramChannel._orig_on_message_strategic = TelegramChannel._on_message
            
            async def _strategic_on_message(self, update, context):
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
                                workspace = getattr(self.config, "workspace_path", None)
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
                    
                    # Instead of patching self._handle_message, we just call orig_on_message
                    # and ensure the session_key is passed correctly.
                    # This relies on core TelegramChannel._on_message using self._handle_message.
                    orig_hm = self._handle_message
                    async def temp_hm(msg, chat_id, text=None, session_key=None, metadata=None):
                        metadata = dict(metadata or {})
                        metadata.update(thread_meta)
                        return await orig_hm(msg, chat_id, text=text, session_key=thread_meta["session_key_override"], metadata=metadata)
                    
                    self._handle_message = temp_hm
                    try:
                        return await self._orig_on_message_strategic(update, context)
                    finally:
                        self._handle_message = orig_hm
                else:
                    # Fallback for standard messages (non-thread)
                    try:
                        return await self._orig_on_message_strategic(update, context)
                    except Exception as e:
                        strategic_logger.error(f"Telegram: Error in original _on_message: {e}")
                        raise
            
            TelegramChannel._on_message = _strategic_on_message

        # Complete rewrite of send to handle message_thread_id
        async def _thread_aware_send(self, msg: OutboundMessage) -> None:
            if not self._app: return
            self._stop_typing(msg.chat_id)
            try: chat_id = int(msg.chat_id)
            except: return

            thread_id = msg.metadata.get("message_thread_id")
            reply_params = None
            if self.config.reply_to_message:
                if reply_to_id := msg.metadata.get("message_id"):
                    reply_params = ReplyParameters(message_id=reply_to_id, allow_sending_without_reply=True)

            # Send media
            for media_path in (msg.media or []):
                try:
                    sender, param, mtype = strategic_prepare_telegram_media(media_path, self._app.bot)
                    with open(media_path, 'rb') as f:
                        kwargs = {param: f, "chat_id": chat_id, "reply_parameters": reply_params}
                        if thread_id: kwargs["message_thread_id"] = int(thread_id)
                        await sender(**kwargs)
                except Exception as e:
                    strategic_logger.error(f"Failed to send media: {e}")

            # Send text
            if msg.content and msg.content != "[empty message]":
                for chunk in _split_message(msg.content):
                    try:
                        html = _markdown_to_telegram_html(chunk)
                        kwargs = {"chat_id": chat_id, "text": html, "parse_mode": "HTML", "reply_parameters": reply_params}
                        if thread_id: kwargs["message_thread_id"] = int(thread_id)
                        await self._app.bot.send_message(**kwargs)
                    except Exception as e:
                        kwargs = {"chat_id": chat_id, "text": chunk, "reply_parameters": reply_params}
                        if thread_id: kwargs["message_thread_id"] = int(thread_id)
                        await self._app.bot.send_message(**kwargs)

        TelegramChannel.send = _thread_aware_send
