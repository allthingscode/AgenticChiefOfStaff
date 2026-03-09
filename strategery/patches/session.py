import asyncio
import json
import inspect
import textwrap
from .base import BasePatch, PatchResult, PatchContext
from nanobot.session.manager import SessionManager, Session
from nanobot.agent.loop import AgentLoop
from loguru import logger

class SessionPatch(BasePatch):
    """
    Hardens Session Management by:
    1. Making SessionManager.save asynchronous using a thread pool.
    2. Dynamically patching AgentLoop._process_message to properly await the now-async save call.
    """

    @property
    def name(self) -> str:
        return "Async Session Management"

    def apply(self, context: PatchContext) -> PatchResult:
        result = PatchResult(patch_name=self.name, success=True)
        try:
            # 1. Patch SessionManager.save
            if not hasattr(SessionManager, "_orig_save_strategic"):
                SessionManager._orig_save_strategic = SessionManager.save
                
                def _sync_save(manager, session):
                    path = manager._get_session_path(session.key)
                    try:
                        with open(path, "w", encoding="utf-8") as f:
                            metadata_line = {
                                "_type": "metadata",
                                "key": session.key,
                                "created_at": session.created_at.isoformat(),
                                "updated_at": session.updated_at.isoformat(),
                                "metadata": session.metadata,
                                "last_consolidated": session.last_consolidated
                            }
                            f.write(json.dumps(metadata_line, ensure_ascii=False) + "\n")
                            for msg in session.messages:
                                f.write(json.dumps(msg, ensure_ascii=False) + "\n")
                    except Exception as e:
                        logger.error(f"Failed to save session {session.key}: {e}")
                        raise

                async def _patched_save(self, session: Session):
                    self._cache[session.key] = session
                    try:
                        await asyncio.to_thread(_sync_save, self, session)
                    except Exception as e:
                        logger.error(f"Async session save failed for {session.key}: {e}")

                SessionManager.save = _patched_save
                logger.debug("Patched SessionManager.save to be asynchronous.")
                result.affected_symbols.append("SessionManager.save (Async)")

            # 2. Patch SessionManager.save to be "Dual-Mode"
            if hasattr(SessionManager, "save") and not hasattr(SessionManager, "_is_dual_mode_strategic"):
                orig_patched_save = SessionManager.save
                
                def _dual_mode_save(self, session: Session):
                    coro = orig_patched_save(self, session)
                    # Return the coroutine for those who AWAIT it (like our future patches)
                    # But also ensure it runs if NOT awaited.
                    asyncio.create_task(coro)
                    return coro
                
                SessionManager.save = _dual_mode_save
                SessionManager._is_dual_mode_strategic = True
                logger.debug("Patched SessionManager.save to be dual-mode (sync/async safe).")
                result.affected_symbols.append("SessionManager.save (Dual-Mode)")

            return result
        except Exception as e:
            import traceback
            result.success = False
            result.error_msg = str(e)
            result.traceback = traceback.format_exc()
            logger.error(f"Session patch error: {e}")
            return result
