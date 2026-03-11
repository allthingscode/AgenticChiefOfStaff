import re
from typing import List, Dict, Any, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from strategery.logic.config_logic import StrategicConfig

# --- Constants & Patterns ---

MAIN_AGENT_BLOCKED = [
    "google", "ai-search", "email-reporter", "strategic_", "web_search",
    "search_memory", "nanobot", "filesystem-d", "read_file", "write_file",
    "edit_file", "list_dir", "ls ", "dir ", "D:"
]

SPECIALIST_BLOCKED = ["spawn", "nanobot", "strategic_hello"]

BYPASS_PATTERNS = [
    "nanobot mcp", "nanobot status", "history.md", "findstr ", 
    "grep ", "rg ", "ripgrep ", "fd ", "bat ", "cat ", "type ", "tail ", "get-content", "read-host",
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

class ToolCircuitBreaker:
    """Tracks tool execution patterns to detect and block infinite loops."""
    def __init__(self, limit: int = 3):
        self.limit = limit
        self.history: List[Tuple[str, str]] = []

    def check(self, name: str, args: Any) -> Optional[str]:
        # Serialize args for comparison
        import json
        arg_str = json.dumps(args, sort_keys=True, ensure_ascii=False) if isinstance(args, dict) else str(args)
        call = (name, arg_str)
        
        self.history.append(call)
        
        # Count consecutive identical calls
        consecutive_count = 0
        for h in reversed(self.history):
            if h == call:
                consecutive_count += 1
            else:
                break
        
        if consecutive_count >= self.limit:
            return (
                f"CRITICAL: Tool Loop Detected! You have attempted to call '{name}' with the EXACT same arguments "
                f"{consecutive_count} times in a row. You are stuck in a logic loop.\n\n"
                "### 🛠️ SELF-CORRECTION GUIDANCE (BUG-169)\n"
                "1. **VARY YOUR PARAMS:** Change the arguments. If 'exec' is failing, try a different flag or path.\n"
                "2. **SWITCH TOOLS:** If 'read_file' fails or is blocked, use 'rg' (ripgrep) or 'fd'.\n"
                "3. **VERIFY FIRST:** Use 'list_dir' or 'ls' to confirm the file exists before reading.\n"
                "4. **CHECK DELIMITERS:** Ensure you are using backslashes ('\\') for Windows paths in shell commands.\n"
                "5. **REPORT FAILURE:** If you cannot solve it in 3 attempts, report the specific error to the user.\n\n"
                "Continued identical calls will result in turn termination."
            )
        return None

def check_tool_loop(registry: Any, name: str, args: Any) -> Optional[str]:
    """Circuit breaker for any tool call to prevent repeating identical failures."""
    if not hasattr(registry, "_strategic_circuit_breaker"):
        # Specialists get 3 attempts, Main Agent gets 2
        is_specialist = getattr(registry, "_is_strategic_specialist", False)
        limit = 3 if is_specialist else 2
        registry._strategic_circuit_breaker = ToolCircuitBreaker(limit=limit)
    
    return registry._strategic_circuit_breaker.check(name, args)

def get_specialist_model(specialist_type: str, config: 'StrategicConfig', default_model: str) -> str:
    """Resolves the correct model for a given specialist type from config."""
    # Ensure specialist is valid, default to researcher
    s_type = specialist_type if specialist_type in ["researcher", "architect"] else "researcher"
    
    # Typed access to specialists config
    specialists_cfg = config.agents.specialists
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
        "5. **SPAWN TURN:** When you call 'spawn', your turn ends immediately. Do NOT mention IDs in the initial turn.\n"
        "6. **DEFINITIVE LOG ROOT (BUG-170):** All strategic and session logs reside EXCLUSIVELY in `D:\\Nanobot_Storage\\workspace\\logs\\`. You MUST use this absolute path when assigning log-related tasks to specialists. Do NOT assume logs live in skill folders."
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
        "13. **EFFICIENT EXECUTION:** Do NOT attempt to delegate to other specialists. The 'spawn' tool is restricted.\n"
        "14. **PYTHON EXECUTION (MANDATE - BUG-141):** You MUST use the absolute path to the project's Python executable for ALL Python commands: `C:\\Users\\HayesChiefOfStaff\\Documents\\nanobot\\nanoClaw\\Scripts\\python.exe`. For internal 'strategery' modules, you MUST use the module-style call and set the PYTHONPATH environment variable: `$env:PYTHONPATH=\".\"; C:\\Users\\HayesChiefOfStaff\\Documents\\nanobot\\nanoClaw\\Scripts\\python.exe -m strategery.module_name`.\n"
        "15. **CLEAN COMMANDS (BUG-143):** When reading commands from Markdown lists or text, you MUST strip any trailing punctuation (like a period '.') that is not part of the command itself. Hallucinated dots cause ModuleNotFoundError.\n"
        "16. **LOG AUDIT DEPTH (BUG-144):** When performing a 'Log Audit', you are FORBIDDEN from reporting a 'PASS' based on a truncated snippet. You MUST use the `exec` tool with `Get-Content -Tail 500` or `Select-String` to search for 'ERROR' or 'Exception' across the entire file if it is large.\n"
        "17. **NO ASSUMPTIONS (BUG-146):** You are strictly FORBIDDEN from assuming a task or component has passed based on generic success messages from wrappers or scripts. If you are asked to verify a specific component (e.g., 'Strategic Doctor'), you MUST find explicit evidence for that specific component in the tool output. If the evidence is missing, you MUST run the specific verification command directly (e.g., `python -m strategery.strategic_doctor`).\n"
        "18. **FINALITY MANDATE (BUG-153):** You are FORBIDDEN from ending your turn with a 'plan' or 'promise to act'. A response without tool calls is interpreted as a COMPLETE AND FINAL ANSWER. If you need to retry a command with different syntax, you MUST call the tool in the SAME turn. Do NOT say 'I will now do X' unless you are currently executing the tool call for X.\n"
        "19. **NO HALLUCINATED PATHS (BUG-158):** You are strictly FORBIDDEN from guessing or 'assuming' subdirectories for skills (e.g., assuming a skill has a subdirectory with its name). You MUST use `list_dir` or `mcp_filesystem-d_search_files` to verify the existence of files before attempting to read them. Hallucinated paths lead to task failure.\n"
        "20. **AUTOMATED ENCODING (BUG-155 / BUG-162):** The `exec` tool automatically forces UTF-8 encoding (`chcp 65001` and `[Console]::OutputEncoding`) for all PowerShell sessions. You are FORBIDDEN from manually prepending these encoding fixes to your commands. Cluttering commands with redundant encoding logic leads to syntax errors and degraded telemetry.\n"
        "21. **SURGICAL TOOL MANDATE:** You MUST prioritize high-performance search tools for codebase navigation. Use `rg` (ripgrep) for searching file contents and `fd` for finding files by name. These tools are orders of magnitude faster than standard Windows commands.\n"
        "22. **HIGH-FIDELITY VIEWING:** When inspecting file contents via the shell, use `bat` instead of `cat` or `type`. `bat` provides line numbers and cleaner formatting, which improves your ability to accurately parse and reference code.\n"
        "23. **CONTEXT EFFICIENCY MANDATE (BUG-164):** You are strictly FORBIDDEN from reading entire files that are larger than 10KB using `read_file` if you only need a specific section or search term. You MUST use surgical tools: use `rg` to find specific lines, or use `exec` with `Get-Content -Tail 100` to inspect recent log entries. Wasting context window on large file dumps leads to amnesia and task failure.\n"
        "24. **LOG AUDIT TEMPORALITY (BUG-166):** When performing a 'Log Audit' or searching for errors, you are FORBIDDEN from reporting an error as 'current' without verifying its timestamp. You MUST use `rg` or `Select-String` to filter for the current date (e.g., '2026-03-10') or use `Get-Content -Tail` to ensure you are only seeing active session data. Reporting stale errors from previous days as active issues violates the high-fidelity mandate.\n"
        "25. **DEFINITIVE LOG ROOT (BUG-167):** All strategic logs (e.g., `strategic.log`, `email_reporter.log`) reside EXCLUSIVELY in `D:\\Nanobot_Storage\\workspace\\logs\\`. You are strictly FORBIDDEN from searching for these logs in skill-specific subdirectories or elsewhere. If a log is not in the definitive root, it does not exist."
    )
    return base_prompt + header + strategic_instr

def harden_subagent_command(command: str) -> str:
    """Hardens a shell command for a subagent by enforcing mandates and cleaning noise."""
    python_abs = r"C:\Users\HayesChiefOfStaff\Documents\nanobot\nanoClaw\Scripts\python.exe"
    
    # 1. Clean hallucinated dots from end of command (BUG-143)
    command = command.strip()
    if command.endswith("."):
        command = command[:-1].strip()

    # 2. Strip Redundant Encoding Clutter (BUG-168)
    # Specialists sometimes manually prepend chcp or OutputEncoding fixes despite Mandate 20
    clutter_patterns = [
        r"chcp\s+65001(\s*>\s*\$null)?\s*([;&|]|\s|$)",
        r"\$OutputEncoding\s*=\s*\[System\.Text\.Encoding\]::UTF8\s*([;&|]|\s|$)",
        r"\[Console\]::OutputEncoding\s*=\s*\[System\.Text\.Encoding\]::UTF8\s*([;&|]|\s|$)",
        r"(?<!chcp\s65001)>\$null\s*([;&|]|\s|$)" # Fixed-width look-behind is fine
    ]
    for pattern in clutter_patterns:
        command = re.sub(pattern, "", command, flags=re.IGNORECASE).strip()
    
    # 3. Inject environment and ensure absolute path if 'python' is used (BUG-141 / BUG-160)
    if "python " in command.lower() or "python.exe" in command.lower():
        # Prepend PYTHONPATH and replace relative python with absolute if necessary
        # Mandate (BUG-160): Use quotes for the PYTHONPATH value to avoid parser errors
        prefix = '$env:PYTHONPATH="."; '
        if not python_abs.lower() in command.lower():
            command = re.sub(r"\bpython(\.exe)?\b", lambda m: f'"{python_abs}"', command, flags=re.IGNORECASE)
        
        if not prefix in command:
            command = prefix + command
            
    return command
