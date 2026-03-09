import re
from typing import List, Dict, Any, Optional, Tuple

# --- Constants & Patterns ---

MAIN_AGENT_BLOCKED = [
    "google", "ai-search", "email-reporter", "strategic_", "web_search",
    "search_memory", "nanobot", "filesystem-d", "read_file", "write_file",
    "edit_file", "list_dir", "ls ", "dir ", "D:"
]

SPECIALIST_BLOCKED = ["spawn", "nanobot", "strategic_hello"]

BYPASS_PATTERNS = [
    "nanobot mcp", "nanobot status", "history.md", "findstr ", 
    "grep ", "cat ", "type ", "tail ", "get-content", "read-host",
    "download", "curl ", "wget ", "Invoke-WebRequest", "Invoke-RestMethod",
    "ls ", "dir ", "more ", "head ", "ping ", "iex ", "Invoke-Expression ",
    "python ", "sh ", "bash ", "powershell ", "cmd ", "Get-ChildItem ",
    "Select-String ", "Get-Item ", "Get-Service ", "start ", "open ", "D:"
]

# --- Logic Functions ---

def is_tool_blocked(tool_name: str, is_specialist: bool) -> bool:
    """Determines if a tool is blocked based on the agent's role."""
    name_str = tool_name.lower()
    blocked_list = SPECIALIST_BLOCKED if is_specialist else MAIN_AGENT_BLOCKED
    return any(bp.lower() in name_str for bp in blocked_list)

def get_block_message(registry: Any, tool_name: str, is_specialist: bool) -> str:
    """Returns a descriptive error message for a blocked tool with circuit breaker support."""
    # Maintain attempts count on the registry instance
    if not hasattr(registry, "_strategic_blocked_attempts"):
        registry._strategic_blocked_attempts = {}
    
    registry._strategic_blocked_attempts[tool_name] = registry._strategic_blocked_attempts.get(tool_name, 0) + 1
    count = registry._strategic_blocked_attempts[tool_name]
    
    role = "Specialist" if is_specialist else "Main Agent"
    base_msg = f"ERROR: Access Denied. Tool '{tool_name}' is restricted for your role ({role})."
    
    if count >= 2:
        return f"CRITICAL ERROR: Access Denied. Tool '{tool_name}' is HARD-LOCKED for your role ({role}). You have attempted to access it {count} times. You MUST STOP trying to call this tool directly. Continued attempts will result in turn termination."
    
    return base_msg

def filter_tool_definitions(definitions: List[Dict[str, Any]], is_specialist: bool) -> List[Dict[str, Any]]:
    """Filters tool definitions based on the agent's role."""
    blocked_list = SPECIALIST_BLOCKED if is_specialist else MAIN_AGENT_BLOCKED
    filtered = []
    for d in definitions:
        name = d.get("function", {}).get("name", "").lower()
        if not any(bp.lower() in name for bp in blocked_list):
            filtered.append(d)
    return filtered

def detect_mandate_bypass(command: str) -> bool:
    """Detects attempts to bypass strategic mandates via shell commands."""
    cmd_lower = command.lower() + " "
    return any(p.lower() in cmd_lower for p in BYPASS_PATTERNS)

def get_bypass_message(command: str) -> str:
    """Returns a descriptive error message for a mandate bypass."""
    if "history.md" in command.lower():
        return "CRITICAL ERROR: Access Denied. Bypass pattern detected. HISTORY.md is RETIRED; use chronological journals instead."
    if "nanobot mcp" in command.lower():
        return "CRITICAL ERROR: Access Denied. Bypass pattern detected. CLI bypass of MCP tools is forbidden."
    return "CRITICAL ERROR: Access Denied. Bypass pattern detected. This command violates Strategic Mandates."

def check_exec_loop(registry: Any, command: str) -> Optional[str]:
    """Detects and blocks repeated shell commands (polling loops)."""
    if "status" not in command.lower():
        return None
        
    # Maintain loop count on the registry instance
    if not hasattr(registry, "_strategic_exec_loop_count"):
        registry._strategic_exec_loop_count = 0
    
    registry._strategic_exec_loop_count += 1
    
    # Mandate: Specialists get 5 attempts (for health checks), Main Agent gets 3
    is_specialist = getattr(registry, "_is_strategic_specialist", False)
    limit = 5 if is_specialist else 3
    
    if registry._strategic_exec_loop_count > limit:
        return f"CRITICAL: Loop Detected. You have called 'exec status' {registry._strategic_exec_loop_count} times. You MUST stop polling and proceed with other tools or report the final outcome."
    
    return None

def get_specialist_model(specialist_type: str, config_data: Dict[str, Any], default_model: str) -> str:
    """Resolves the correct model for a given specialist type from config."""
    # Ensure specialist is valid, default to researcher
    s_type = specialist_type if specialist_type in ["researcher", "architect"] else "researcher"
    
    specialists_cfg = config_data.get("agents", {}).get("specialists", {})
    selected_model = specialists_cfg.get(s_type, {}).get("model")
    
    return selected_model or default_model

def should_escalate_model(response_content: Optional[str]) -> bool:
    """
    Analyzes response content to determine if a model escalation is required.
    Triggered by empty responses, safety filters, or specific [STRATEGIC] error markers.
    """
    if not response_content:
        return True
    
    # Check for our strategic error markers that indicate provider-level refusal
    refusal_patterns = [
        "[STRATEGIC] Provider Communication Failure",
        "empty response",
        "Zero Choices",
        "safety filter"
    ]
    return any(p.lower() in response_content.lower() for p in refusal_patterns)

def get_escalation_model(current_model: str) -> str:
    """Returns a more robust model if the current one is failing/refusing."""
    if "flash-lite" in current_model.lower():
        return "gemini-3-flash-preview"
    if "flash" in current_model.lower():
        return "gemini-3.1-pro-preview"
    return "gemini-3.1-pro-preview" # Final fallback for deepest reasoning

def format_spawn_termination_directive(result: str, task_id: str) -> str:
    """Appends the strategic turn termination mandate to a spawn tool result."""
    return (
        f"{result}\n\n"
        "### ⚖️ STRATEGIC MANDATE: STOP Turn\n"
        f"The specialist has been successfully spawned and assigned ID: `{task_id}`. "
        "Your turn is now OVER. Provide a SINGLE brief acknowledgement to the user using this EXACT ID and then END your response. "
        "Do NOT call any more tools."
    )

from strategery.strategic_logger import strategic_logger

def log_subagent_turn(task_id: str, iteration: int, thought: Optional[str] = None):
    """Logs the start of a subagent turn with its reasoning."""
    msg = f"\n[Subagent {task_id}] --- TURN {iteration} START ---"
    if thought:
        from .provider_logic import strip_reasoning_artifacts
        clean_thought = strip_reasoning_artifacts(thought)
        if clean_thought:
            # Format thought with indentation for clarity
            indented_thought = "\n    ".join(clean_thought[:500].split("\n"))
            msg += f"\n  THOUGHT:\n    {indented_thought}..."
    strategic_logger.warning(msg)

def log_tool_call(task_id: str, tool_name: str, arguments: Any):
    """Logs a subagent tool call with arguments."""
    import json
    arg_str = json.dumps(arguments, indent=4, ensure_ascii=False) if isinstance(arguments, dict) else str(arguments)
    # Indent arguments
    indented_args = "\n    ".join(arg_str[:1000].split("\n"))
    strategic_logger.warning(f"\n  CALLING TOOL: {tool_name}\n    ARGS: {indented_args}...")

def log_tool_result(task_id: str, tool_name: str, result: Any):
    """Logs the result of a subagent tool call with a snippet."""
    res_str = str(result)
    # Indent result snippet
    snippet = res_str[:1000]
    indented_snippet = "\n    ".join(snippet.split("\n"))
    strategic_logger.warning(f"\n  TOOL RESULT: {tool_name} ({len(res_str)} chars)\n    DATA: {indented_snippet}...\n")

def log_subagent_completion(task_id: str, result: Optional[str] = None):
    """Logs subagent task completion with final result snippet."""
    msg = f"\n[Subagent {task_id}] --- TASK COMPLETED ---"
    if result:
        indented_res = "\n    ".join(str(result)[:1000].split("\n"))
        msg += f"\n  FINAL RESPONSE:\n    {indented_res}..."
    strategic_logger.warning(msg + "\n")

def log_tool_execution(registry: Any, name: str, args: Any):
    """Logs a tool call for any agent (Main or Specialist)."""
    import json
    is_specialist = getattr(registry, "_is_strategic_specialist", False)
    label = f"Subagent [{getattr(registry, '_task_id', '???')}]" if is_specialist else "Main Agent"
    
    # Identify MCP tools
    prefix = "[MCP] " if name.startswith("mcp_") else ""
    display_name = name.replace("mcp_", "").replace("_", " -> ", 1) if name.startswith("mcp_") else name
    
    arg_str = json.dumps(args, indent=4, ensure_ascii=False) if isinstance(args, dict) else str(args)
    indented_args = "\n    ".join(arg_str[:1000].split("\n"))
    
    msg = f"\n[{label}] CALLING TOOL: {prefix}{display_name}\n    ARGS: {indented_args}..."
    strategic_logger.info(msg)

def log_tool_result_general(registry: Any, name: str, result: Any):
    """Logs a tool result for any agent."""
    is_specialist = getattr(registry, "_is_strategic_specialist", False)
    label = f"Subagent [{getattr(registry, '_task_id', '???')}]" if is_specialist else "Main Agent"
    
    res_str = str(result)
    indented_snippet = "\n    ".join(res_str[:1000].split("\n"))
    
    msg = f"\n[{label}] TOOL RESULT: {name} ({len(res_str)} chars)\n    DATA: {indented_snippet}...\n"
    strategic_logger.info(msg)

def clean_chat_id(chat_id: str) -> str:
    """Removes redundant channel prefixes from a chat ID."""
    if not chat_id:
        return ""
    # If it's something like "telegram:8431594039", return "8431594039"
    if ":" in chat_id:
        return chat_id.split(":")[-1]
    return chat_id

def format_subagent_report(label: str, status: str, task_id: str, task: str, result: str) -> str:
    """Formats the final report from a subagent for the orchestrator."""
    status_text = "completed successfully" if status == "ok" else "failed"
    # Ensure result is a string and not too long for the system message
    res_str = str(result)[:10000] if result else "No result returned."
    
    return f"""### 🛡️ SPECIALIST SUBAGENT REPORT (FINAL)
[Subagent '{label}' {status_text}]
**ID:** {task_id}
**Original Task:** {task[:500]}

**Result Data:**
{res_str}

---
### ⚖️ ORCHESTRATOR DIRECTIVE (CRITICAL)
1. **TERMINATE TURN:** You have received a specialist's report.
2. **CONTEXT AWARENESS:** Synthesize this report into the ongoing context.
3. **DO NOT VERIFY:** You are strictly forbidden from calling ANY tools to "verify" this result.
4. **SYNTHESIZE ONLY:** Provide a natural summary to the user and END your response.
"""

def inject_delegation_mandate(system_content: str) -> str:
    """Injects the Specialist Economy mandates into a system prompt."""
    mandate = (
        "\n\n## ⚖️ DELEGATION & SPECIALIST ECONOMY\n"
        "1. **DELEGATE BY DEFAULT:** For any background, research, or complex architectural task, use the 'spawn' tool.\n"
        "2. **CHOOSE YOUR SPECIALIST:**\n"
        "   - **'researcher' (DEFAULT):** Use for general facts, search, data collection, and simple file operations.\n"
        "   - **'architect':** Use for design, NanoGraph extraction, high-level structural planning, or complex reasoning.\n"
        "3. **NO MODEL CONTROL:** You choose the TYPE of specialist, but you have NO say in which AI model is used.\n"
        "4. **WHEN IN DOUBT, ASK:** If the task's complexity is unclear, STOP and ask the user.\n"
        "5. **SPAWN TURN:** When you call 'spawn', your turn ends immediately. Do NOT mention IDs in the initial turn."
    )
    return system_content + mandate

def build_specialist_instructions(base_prompt: str, specialist_type: str) -> str:
    """Builds the extended system prompt for a specialist subagent."""
    header = f"\n## {specialist_type.upper()} SPECIALIST MANDATE\nYou are running a high-precision model. Exhaustively verify facts using surgical tools."
    
    strategic_instr = (
        "\n\n## 🛡️ STRATEGIC SPECIALIST INSTRUCTIONS\n"
        "1. **STATELESS SHELL MANDATE (CRITICAL):** The 'exec' tool is completely stateless. STANDALONE 'cd' COMMANDS ARE FORBIDDEN as they do not persist across turns. You MUST use ABSOLUTE PATHS for all file operations and script executions.\n"
        "2. **MARKDOWN DIRECTIVE MANDATE (BUG-132/138):** You are strictly FORBIDDEN from attempting to `exec` a Markdown (.md) file. Markdown files are NOT executable scripts. If a task points to a `.md` file, you MUST use `read_file` to read the instructions inside and THEN execute the steps manually. DO NOT try to 'run' the file first to see if it works; it will not. Use `read_file` immediately.\n"
        "3. **EMAIL ATTACHMENT RESTRICTION (BUG-137):** The tool `mcp_email-reporter_send_email_report` does NOT support attachments, media, or file paths. You MUST include the full content of your report/briefing directly in the `body` field. Do NOT attempt to attach files.\n"
        "4. **MANDATORY VERIFICATION:** You are only successful when you have executed all required tools and confirmed the outcome.\n"
        "5. **SEARCH MANDATE:** You MUST use 'mcp_google-ai-search_search_ai' for ALL research and weather data. \n"
        "6. **BANNED TOOLS (DO NOT USE):** The tools 'web_search' and 'web_fetch' are DEPRECATED and UNSTABLE. Do NOT attempt to use them. If you see them in your tool list, IGNORE them and use the equivalent MCP tools instead.\n"
        "7. **MEMORY ACCESS (D: DRIVE):** Long-term memory is at `D:\\Nanobot_Storage\\workspace\\memory`. Use ABSOLUTE PATHS.\n"
        "8. **RECURSION MANDATE:** When auditing storage, you MUST use recursive search tools.\n"
        "9. **CALENDAR MANDATE:** Use `mcp_google-surgical_list_calendar_events` with `calendar_id='all'`.\n"
        "10. **SCRIPT EXECUTION (WINDOWS):** To run PowerShell scripts (.ps1), you MUST use: `powershell -File \"D:\\path\\to\\script.ps1\"`. To run a PowerShell command/cmdlet, you MUST use `powershell -Command \"...\"`. Do not attempt to execute .ps1 files or cmdlets directly in the shell.\n"
        "11. **SURGICAL PRECISION:** Use 'read_file' to examine config or history.\n"
        "12. **CHAIN OF THOUGHT:** Show your reasoning and state which tool you are about to call.\n"
        "13. **EFFICIENT EXECUTION:** Do NOT attempt to delegate to other specialists. The 'spawn' tool is restricted."
    )
    return base_prompt + header + strategic_instr
