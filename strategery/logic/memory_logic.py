import re
import json
from datetime import datetime, timedelta
from typing import Any, Optional, Tuple, List
from strategery.strategic_logger import strategic_logger

def prune_context(messages: List[dict], ttl_hours: int, keep_last_assistants: int) -> List[dict]:
    """
    Prunes a list of messages based on TTL and mandatory retention of recent assistant turns.
    Returns: A new list of pruned messages.
    """
    cutoff = datetime.now() - timedelta(hours=ttl_hours)
    
    new_msgs = []
    assistant_count = 0
    needed_tool_ids = set()
    
    # Pass 1: Identification (Reverse to find newest first)
    for m in reversed(messages):
        role = m.get("role")
        
        # Ensure timestamp is parsed
        if "_parsed_ts" not in m and m.get("timestamp"):
            try: m["_parsed_ts"] = datetime.fromisoformat(m["timestamp"])
            except: m["_parsed_ts"] = None
        
        is_old = m.get("_parsed_ts") and m["_parsed_ts"] < cutoff
        
        keep = False
        if role == "user":
            keep = True
        elif role == "assistant":
            assistant_count += 1
            if not is_old or assistant_count <= keep_last_assistants:
                keep = True
                for tc in (m.get("tool_calls") or []):
                    if tid := tc.get("id"): needed_tool_ids.add(tid)
        
        if keep:
            new_msgs.append(m)
            
    # Pass 2: Tool Resolution (Forward to preserve order)
    final_msgs = []
    for m in messages:
        role = m.get("role")
        if m in new_msgs:
            final_msgs.append(m)
        elif role == "tool" and m.get("tool_call_id") in needed_tool_ids:
            final_msgs.append(m)
            
    # Cleanup temporary metadata
    for m in final_msgs:
        m.pop("_parsed_ts", None)
        
    return final_msgs

def format_consolidation_messages(messages: List[dict]) -> str:
    """Formats a list of messages into a string for the consolidator prompt."""
    lines = []
    for m in messages:
        if not m.get("content"): continue
        role = m["role"].upper()
        content = m["content"]
        lines.append(f"[{m.get('timestamp', '?')[:16]}] {role}: {content}")
    return "\n".join(lines)

def parse_consolidation_response(content: Any, has_tool_calls: bool, tool_arguments: Any, current_memory: str) -> Optional[dict]:
    """
    Parses the LLM response (from tool calls or raw text) and applies regex recovery.
    Returns: A dict with 'history_entry' and 'memory_update' or None if invalid.
    """
    args = None
    if has_tool_calls:
        args = tool_arguments
        if isinstance(args, str):
            try: args = json.loads(args)
            except: pass

    # Regex Recovery if tool call failed or we have raw text
    if not args or not isinstance(args, dict):
        try:
            match = re.search(r"\{.*\}", str(content), re.DOTALL)
            if match:
                candidate = json.loads(match.group(0))
                args = {
                    "history_entry": candidate.get("history_entry") or candidate.get("summary") or "No summary available.",
                    "memory_update": candidate.get("memory_update") or candidate.get("facts") or current_memory
                }
        except: pass

    if args and isinstance(args, dict) and ("history_entry" in args or "memory_update" in args):
        return args
    return None

def get_journal_continuity(storage_root: Any, max_chars: int = 1000) -> str:
    """
    Reads the last N characters from the current day's journal for chronological continuity.
    """
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        journal_path = storage_root / "workspace" / "memory" / f"{today}.md"

        if not journal_path.exists() or journal_path.stat().st_size == 0:
            try:
                journal_path.parent.mkdir(parents=True, exist_ok=True)
                with open(journal_path, "w", encoding="utf-8-sig") as f:
                    f.write(f"# {today}\n\n")
            except Exception as e:
                strategic_logger.error(f"Failed to initialize daily journal: {e}")
            return ""

        with open(journal_path, "r", encoding="utf-8-sig") as f:
            content = f.read()
            
        if not content:
            return ""
            
        snippet = content[-max_chars:]
        if len(content) > max_chars:
            nl_pos = snippet.find("\n")
            if nl_pos != -1:
                snippet = snippet[nl_pos+1:]
                
        return f"\n### RECENT CONTINUITY (FROM DAILY JOURNAL):\n...{snippet}\n"
    except Exception as e:
        strategic_logger.error(f"Error reading rolling journal: {e}")
        return ""

def write_journal_entry(storage_root: Any, entry: str) -> bool:
    """Writes a consolidation entry to the daily journal."""
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        journal_path = storage_root / "workspace" / "memory" / f"{today}.md"
        journal_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(journal_path, "a", encoding="utf-8-sig") as f:
            ts = datetime.now().strftime("%H:%M:%S")
            f.write(f"\n### CONSOLIDATION [{ts}]\n{entry}\n")
        return True
    except Exception as e:
        strategic_logger.error(f"Failed to write journal entry: {e}")
        return False

def filter_rag_results(results: List[dict], threshold: float = 0.7) -> List[dict]:
    """Filters out noise and low-relevance matches from RAG results."""
    valid_results = []
    noise_patterns = [
        "spawned subagent", 
        "i have spawned", 
        "specialist has been assigned id",
        "your turn is now over",
        "provide a single brief acknowledgement"
    ]
    
    for r in results:
        content = r.get('content', '')
        if not content or "No summary available" in content:
            continue
        
        # Check semantic distance/score if available from the vector store
        # In Chroma, results often include a 'distance' or 'score'
        score = r.get('score', 1.0) # Default to 1.0 if not provided
        if score < threshold:
            continue

        lower_content = content.lower()
        if any(pattern in lower_content for pattern in noise_patterns):
            continue
            
        valid_results.append(r)
    return valid_results

def should_skip_rag(content: str) -> bool:
    """Determines if RAG should be skipped for the given content."""
    is_generic = content.lower().strip() in ["yes", "no", "ok", "okay", "hello", "hi", "thanks", "thank you", "confirmed"]
    return len(content) <= 10 or is_generic or content == "[empty message]"

def format_rag_block(valid_results: List[dict]) -> Tuple[Optional[str], int]:
    """Formats the valid RAG results into a prompt block."""
    if not valid_results:
        return None, 0
        
    context_lines = []
    for r in valid_results:
        context_lines.append(f"- {r['content']}")
    
    warning = "[STRATEGIC MEMORY - MAY BE STALE OR OUTDATED. USE RESEARCH TOOLS TO VERIFY.]\n"
    mem_block = "### RETRIEVED HISTORICAL CONTEXT:\n" + warning + "\n".join(context_lines)
    return mem_block, len(valid_results)
