from pathlib import Path
from loguru import logger
from . import BasePatch

class TelegramPatch(BasePatch):
    """Handles Telegram Topic support, Media Redirection, and thread-aware message sending."""
    
    @property
    def name(self) -> str:
        return "Telegram Advanced Integration"

    def apply(self, config_data: dict) -> bool:
        try:
            from nanobot.channels.telegram import TelegramChannel
            self._patch_telegram_channel(TelegramChannel)
            return True
        except Exception as e:
            print(f"[Launcher] Telegram patch error: {e}")
            return False

    def _patch_telegram_channel(self, TelegramChannel):
        from nanobot.channels.telegram import _split_message, _markdown_to_telegram_html
        from nanobot.bus.events import OutboundMessage
        from telegram import ReplyParameters

        if not hasattr(TelegramChannel, "_orig_on_message_strategic"):
            TelegramChannel._orig_on_message_strategic = TelegramChannel._on_message
            
            async def _strategic_on_message(self, update, context):
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
                                if custom_path and r".nanobot\media" in str(custom_path):
                                    workspace = Path(getattr(self.config, "workspace_path", Path.home() / ".nanobot" / "workspace"))
                                    custom_path = str(workspace / "media" / Path(custom_path).name)
                                    print(f"[Launcher] Telegram Media Redirection: {custom_path}")
                                return await _orig_download(custom_path=custom_path, *args, **kwargs)
                            file.download_to_drive = _patched_download
                            return file
                        context.bot.get_file = _patched_get_file

                # STRATEGIC EDITION: Handle Telegram Topics (threads)
                if update.message and hasattr(update.message, 'message_thread_id') and update.message.message_thread_id:
                    msg = update.message
                    orig_hm = self._handle_message
                    async def temp_hm(*args, **kwargs):
                        chat_id = kwargs.get("chat_id") or (args[1] if len(args) > 1 else None)
                        metadata = dict(kwargs.get("metadata") or (args[4] if len(args) > 4 else {}))
                        metadata["message_thread_id"] = msg.message_thread_id
                        metadata["session_key_override"] = f"telegram:{chat_id}:{msg.message_thread_id}"
                        kwargs["metadata"] = metadata
                        kwargs["session_key"] = metadata["session_key_override"]
                        return await orig_hm(*args, **kwargs)
                    self._handle_message = temp_hm
                    try:
                        return await self._orig_on_message_strategic(update, context)
                    finally:
                        self._handle_message = orig_hm

                return await self._orig_on_message_strategic(update, context)
            
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
                    from nanobot.channels.telegram import _get_media_type
                    mtype = _get_media_type(media_path)
                    sender = {"photo": self._app.bot.send_photo, "voice": self._app.bot.send_voice, "audio": self._app.bot.send_audio}.get(mtype, self._app.bot.send_document)
                    param = "photo" if mtype == "photo" else mtype if mtype in ("voice", "audio") else "document"
                    with open(media_path, 'rb') as f:
                        kwargs = {param: f, "chat_id": chat_id, "reply_parameters": reply_params}
                        if thread_id: kwargs["message_thread_id"] = int(thread_id)
                        await sender(**kwargs)
                except Exception as e:
                    logger.error("Failed to send media: {}", e)

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
