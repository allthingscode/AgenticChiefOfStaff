import asyncio
from typing import List, TYPE_CHECKING
from .base import BasePatch, PatchResult, PatchContext
from .config import load_strategic_context
from .vsa import VectorStoreFactory
from strategery.strategic_logger import strategic_logger
from strategery.logic import memory_logic

if TYPE_CHECKING:
    from strategery.logic.config_logic import StrategicConfig

async def strategic_inject_rag_context(content, provider, config: 'StrategicConfig', vec_store_factory=VectorStoreFactory):
    """Bridge to semantic retrieval logic."""
    if memory_logic.should_skip_rag(content):
        return None, 0

    try:
        rag_cfg = config.strategic_edition.memory_rag
        vec_store = vec_store_factory.get_store(provider=provider)
        
        # Use max_results from config
        results = await vec_store.query(content, n_results=rag_cfg.max_results)
        
        if results:
            # Pass threshold to the filtering logic
            valid = memory_logic.filter_rag_results(results, threshold=rag_cfg.threshold)
            return memory_logic.format_rag_block(valid)
    except Exception as re:
        strategic_logger.error(f"Semantic Retrieval error: {re}")
    return None, 0

class MemoryPatch(BasePatch):
    """Thin Bridge for memory consolidation and context management."""
    
    @property
    def name(self) -> str:
        return "Memory & Context Management"

    def apply(self, context: PatchContext) -> PatchResult:
        result = PatchResult(patch_name=self.name, success=True)
        try:
            self._patch_memory_consolidation(context.config)
            result.affected_symbols.append("MemoryStore.consolidate")
            self._patch_context_pruning(context.config)
            result.affected_symbols.append("AgentLoop._process_message (Memory/RAG)")
            return result
        except Exception as e:
            import traceback
            result.success = False
            result.error_msg = str(e)
            result.traceback = traceback.format_exc()
            strategic_logger.error(f"Memory patch error: {e}")
            return result

    def _patch_memory_consolidation(self, config: 'StrategicConfig'):
        from nanobot.agent.memory import MemoryStore, _SAVE_MEMORY_TOOL
        
        if not hasattr(MemoryStore, "_orig_consolidate_strategic"):
            MemoryStore._orig_consolidate_strategic = MemoryStore.consolidate

            async def _patched_consolidate(self, session, provider, model, **kwargs):
                config_model = None
                if config.agents.consolidator:
                    config_model = config.agents.consolidator.get("model")
                model = config_model or model
                
                archive_all = kwargs.get("archive_all", False)
                memory_window = kwargs.get("memory_window", 50)

                if archive_all:
                    old_messages = session.messages
                    keep_count = 0
                else:
                    keep_count = memory_window // 2
                    if len(session.messages) <= keep_count: return True
                    old_messages = session.messages[session.last_consolidated:-keep_count]
                    if not old_messages: return True

                lines_str = memory_logic.format_consolidation_messages(old_messages)
                current_memory = self.read_long_term()

                prompt = f"""You are a senior memory consolidation specialist.
### CURRENT LONG-TERM MEMORY:
{current_memory or "(empty)"}
### NEW CONVERSATION SEGMENT:
{lines_str}
"""
                try:
                    response = await provider.chat(
                        messages=[
                            {"role": "system", "content": "JSON-only response agent. Schema: {history_entry, memory_update}"},
                            {"role": "user", "content": prompt},
                        ],
                        tools=_SAVE_MEMORY_TOOL,
                        model=model,
                    )

                    tool_args = response.tool_calls[0].arguments if response.has_tool_calls else None
                    args = memory_logic.parse_consolidation_response(response.content, response.has_tool_calls, tool_args, current_memory)

                    if not args: return False

                    try:
                        vec_store = VectorStoreFactory.get_store(provider=provider)
                        entry = args.get("history_entry", "No summary available.")
                        update = args.get("memory_update", current_memory)
                        
                        asyncio.create_task(vec_store.add_entry(str(entry), {"type": "history_summary"}))
                        _, _, storage_root = load_strategic_context()
                        memory_logic.write_journal_entry(storage_root, entry)
                        
                        if update and update != current_memory:
                            self.write_long_term(str(update))
                            asyncio.create_task(vec_store.add_entry(f"UPDATED CORE MEMORY:\n{update}", {"type": "memory_fact_sheet"}))
                    except Exception as ve:
                        strategic_logger.error(f"Strategic Memory persistence error: {ve}")

                    session.last_consolidated = 0 if archive_all else len(session.messages) - keep_count
                    return True
                except Exception as e:
                    strategic_logger.error(f"Memory consolidation error: {e}")
                    return False

            MemoryStore.consolidate = _patched_consolidate

    def _patch_context_pruning(self, config: 'StrategicConfig'):
        from nanobot.agent.loop import AgentLoop
        
        if not hasattr(AgentLoop, "_orig_process_message_strategic"):
            AgentLoop._orig_process_message_strategic = AgentLoop._process_message

            async def _patched_process_message(self, msg, session_key=None, on_progress=None):
                is_internal = msg.channel in {"system", "cron", "heartbeat"} or msg.sender_id == "subagent"
                original_content = msg.content or ""

                if not is_internal:
                    _, _, storage_root = load_strategic_context()
                    journal_snippet = memory_logic.get_journal_continuity(storage_root)
                    if journal_snippet:
                        msg.content = journal_snippet + "\n" + msg.content

                prune_cfg = config.agents.defaults.context_pruning
                if prune_cfg and prune_cfg.enabled:
                    key = session_key or msg.session_key
                    session = self.sessions.get_or_create(key)
                    ttl_str = prune_cfg.ttl
                    hours = int(ttl_str[:-1]) if ttl_str.endswith("h") else 6
                    keep_last = prune_cfg.keep_last_assistants
                    session.messages = memory_logic.prune_context(session.messages, hours, keep_last)

                rag_cfg = config.strategic_edition.memory_rag
                if rag_cfg.enabled and not is_internal:
                    rag_block, count = await strategic_inject_rag_context(original_content, self.provider, config)
                    if rag_block:
                        msg.content = rag_block + "\n\n" + msg.content

                return await self._orig_process_message_strategic(msg, session_key, on_progress)

            AgentLoop._process_message = _patched_process_message
