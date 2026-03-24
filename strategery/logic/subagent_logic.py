import os
import re
import json
import sys
import base64
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, TYPE_CHECKING
from pydantic import BaseModel
from strategery.strategic_logger import strategic_logger

if TYPE_CHECKING:
    from strategery.logic.config_logic import StrategicConfig

class StrategicAttachment(BaseModel):
    """Schema for multimodal attachments passed to subagents (ARCH-022)."""
    id: str
    path: str
    content_type: str
    filename: str
    description: Optional[str] = None

# --- Constants & Patterns ---

# Role-based tool access mapping
ROLE_BLOCKS = {
    "main_agent": [
        "google", "ai-search", "email-reporter", "strategic_", "web_search",
        "search_memory", "nanobot", "filesystem-d", "read_file", "write_file",
        "edit_file", "list_dir", "ls ", "dir ", "D:"
    ],
    "specialist": ["spawn", "nanobot", "strategic_hello", "web_search", "web_fetch"]
}

# MANDATE: Protect D: drive and strategic files from direct shell bypass.
# Use regex with word boundaries to avoid false positives in paths (e.g. D:\path)
BYPASS_PATTERNS = [
    r"\bnanobot\s+mcp\b", r"\bnanobot\s+status\b", r"\bhistory\.md\b",
    r"\bdownload\b", r"\bcurl\b\s+", r"\bwget\b\s+", r"\bInvoke-WebRequest\b", r"\bInvoke-RestMethod\b",
    r"\bls\b\s+", r"\bdir\b\s+", r"\bmore\b\s+", r"\bhead\b\s+", r"\bping\b\s+", r"\biex\b\s+", r"\bInvoke-Expression\b\s+",
    r"^\s*[a-zA-Z]:\s*$" # Drive switch only
]

# Pre-compiled regex for performance (BUG-168)
CLUTTER_PATTERNS = [
    re.compile(r"chcp\s+65001(\s*>\s*\$null)?\s*([;&|]|\s|$)", re.IGNORECASE),
    re.compile(r"\$OutputEncoding\s*=\s*\[System\.Text\.Encoding\]::UTF8\s*([;&|]|\s|$)", re.IGNORECASE),
    re.compile(r"\[Console\]::OutputEncoding\s*=\s*\[System\.Text\.Encoding\]::UTF8\s*([;&|]|\s|$)", re.IGNORECASE),
    re.compile(r"(?<!chcp\s65001)>\$null\s*([;&|]|\s|$)", re.IGNORECASE)
]

# MANDATE: Use dynamic resolution for the project's Python executable to avoid hard-coded personal paths.
# We assume the venv 'nanoClaw' is in the project root (one level up from 'strategery' folder)
PROJECT_ROOT = Path(__file__).parent.parent.parent.absolute()
PYTHON_EXE_PATH = str(PROJECT_ROOT / "nanoClaw" / "Scripts" / "python.exe")
if not Path(PYTHON_EXE_PATH).exists():
    # Fallback to current sys.executable if venv structure is different
    PYTHON_EXE_PATH = sys.executable

# MANDATE: Resolve log root dynamically from context or env.
def get_log_root() -> str:
    env_log = os.environ.get("STRATEGIC_LOG_DIR")
    if env_log:
        return str(Path(env_log).absolute()) + "\\"
    
    try:
        config_path = Path.home() / ".nanobot" / "config.json"
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8-sig") as f:
                import json
                cfg = json.load(f)
                root = cfg.get("strategic_edition", {}).get("storage_root", "D:/Nanobot_Storage")
                return str(Path(root) / "workspace" / "logs") + "\\"
    except: pass
    return r"D:\Nanobot_Storage\workspace\logs\\"

LOG_ROOT = get_log_root()

# --- Logic Functions ---

def is_tool_blocked(tool_name: str, is_specialist: bool) -> bool:
    """Determines if a tool is blocked based on the agent's role."""
    name_str = tool_name.lower()
    role = "specialist" if is_specialist else "main_agent"
    
    # BUG-222: Use a more precise check for tool blocking. 
    # If the tool name EXACTLY matches or is a logical substring (e.g. 'google' in 'mcp_google_surgical'), block it.
    # We want to avoid blocking legitimate commands like 'redirect' if 'dir' is in the block list.
    # Since tool_name is ONLY the name of the tool (from the LLM's perspective), we can be safer.
    blocks = ROLE_BLOCKS[role]
    for b in blocks:
        b_clean = b.lower().strip()
        # If the block pattern is in the tool name, it's blocked.
        # Example: 'google' in 'mcp_google_surgical' -> True
        if b_clean in name_str:
            return True
    return False

def get_block_message(registry: Any, tool_name: str, is_specialist: bool) -> str:
    """Returns a descriptive error message for a blocked tool with circuit breaker support."""
    if not hasattr(registry, "_strategic_blocked_attempts"):
        registry._strategic_blocked_attempts = {}
    
    registry._strategic_blocked_attempts[tool_name] = registry._strategic_blocked_attempts.get(tool_name, 0) + 1
    count = registry._strategic_blocked_attempts[tool_name]
    
    role_label = "Specialist" if is_specialist else "Main Agent"
    if count >= 2:
        return (f"CRITICAL ERROR: Access Denied. Tool '{tool_name}' is HARD-LOCKED for your role ({role_label}). "
                f"You have attempted to access it {count} times. You MUST STOP trying to call this tool directly.")
    
    return f"ERROR: Access Denied. Tool '{tool_name}' is restricted for your role ({role_label})."

def filter_tool_definitions(definitions: List[Dict[str, Any]], is_specialist: bool) -> List[Dict[str, Any]]:
    """Filters tool definitions based on the agent's role."""
    role = "specialist" if is_specialist else "main_agent"
    blocked = ROLE_BLOCKS[role]
    return [d for d in definitions if not any(bp.lower() in d.get("function", {}).get("name", "").lower() for bp in blocked)]

def detect_mandate_bypass(command: str) -> bool:
    """Detects attempts to bypass strategic mandates via shell commands."""
    # MANDATE: Tool names like 'read_file' are NOT CLI commands. 
    # If the agent tries to use them in 'exec', block it.
    for tool_name in ["read_file", "write_file", "edit_file", "list_dir", "spawn"]:
        if re.search(r"\b" + tool_name + r"\b", command):
            return True

    for pattern in BYPASS_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return True
    return False

def get_bypass_message(command: str) -> str:
    """Returns a descriptive error message for a mandate bypass."""
    # Check for tool hallucination in shell
    for tool_name in ["read_file", "write_file", "edit_file", "list_dir", "spawn"]:
        if tool_name in command.lower():
            return f"CRITICAL ERROR: Access Denied. The term '{tool_name}' is a TOOL, not a shell command. Use the '{tool_name}' tool directly."

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
        arg_str = json.dumps(args, sort_keys=True, ensure_ascii=False) if isinstance(args, dict) else str(args)
        call = (name, arg_str)
        self.history.append(call)
        
        consecutive = 0
        for h in reversed(self.history):
            if h == call: consecutive += 1
            else: break
        
        if consecutive >= self.limit:
            return (
                f"CRITICAL: Tool Loop Detected! You have attempted to call '{name}' with the EXACT same arguments "
                f"{consecutive} times in a row. You are stuck in a logic loop.\n\n"
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
    if name == "spawn": return None
    if not hasattr(registry, "_strategic_circuit_breaker"):
        is_specialist = getattr(registry, "_is_strategic_specialist", False)
        registry._strategic_circuit_breaker = ToolCircuitBreaker(limit=3 if is_specialist else 2)
    return registry._strategic_circuit_breaker.check(name, args)

# --- Telemetry Helpers ---

def _format_telemetry(label: str, event: str, content: Any, indent: int = 4) -> str:
    """Standardized formatting for telemetry log entries."""
    if content is None: return f"\n[{label}] {event}: [None]"
    if isinstance(content, dict): text = json.dumps(content, indent=indent, ensure_ascii=False)
    else: text = str(content)
    snippet = text[:1000]
    indented = "\n" + " " * indent + ("\n" + " " * indent).join(snippet.split("\n"))
    return f"\n[{label}] {event}: {indented}..."

def log_subagent_turn(task_id: str, iteration: int, thought: Optional[str] = None):
    msg = f"\n[Subagent {task_id}] --- TURN {iteration} START ---"
    if thought:
        from .provider_logic import strip_reasoning_artifacts
        thought = strip_reasoning_artifacts(thought)
        if thought: msg += _format_telemetry("Subagent " + task_id, "THOUGHT", thought[:500])
    strategic_logger.warning(msg)

def log_tool_call(task_id: str, tool_name: str, arguments: Any):
    strategic_logger.warning(_format_telemetry("Subagent " + task_id, "CALLING TOOL: " + tool_name, arguments))

def log_tool_result(task_id: str, tool_name: str, result: Any):
    strategic_logger.warning(_format_telemetry("Subagent " + task_id, f"TOOL RESULT: {tool_name} ({len(str(result))} chars)", result))

def log_subagent_completion(task_id: str, result: Optional[str] = None):
    strategic_logger.warning(f"\n[Subagent {task_id}] --- TASK COMPLETED ---" + _format_telemetry("Subagent " + task_id, "FINAL RESPONSE", result))

def log_tool_execution(registry: Any, name: str, args: Any):
    is_spec = getattr(registry, "_is_strategic_specialist", False)
    label = f"Subagent [{getattr(registry, '_task_id', '???')}]" if is_spec else "Main Agent"
    display_name = (name.replace("mcp_", "").replace("_", " -> ", 1) if name.startswith("mcp_") else name)
    prefix = "[MCP] " if name.startswith("mcp_") else ""
    strategic_logger.info(_format_telemetry(label, f"CALLING TOOL: {prefix}{display_name}", args))

def log_tool_result_general(registry: Any, name: str, result: Any):
    is_spec = getattr(registry, "_is_strategic_specialist", False)
    label = f"Subagent [{getattr(registry, '_task_id', '???')}]" if is_spec else "Main Agent"
    strategic_logger.info(_format_telemetry(label, f"TOOL RESULT: {name} ({len(str(result))} chars)", result))

# --- Orchestration Helpers ---

def get_specialist_model(specialist_type: str, config: 'StrategicConfig', default_model: str) -> str:
    s_type = specialist_type if specialist_type in ["researcher", "architect"] else "researcher"
    return config.agents.specialists.get(s_type, {}).get("model") or default_model

def should_escalate_model(response_content: Optional[str]) -> bool:
    if not response_content: return True
    refusal_patterns = ["[STRATEGIC] Provider Communication Failure", "empty response", "Zero Choices", "safety filter"]
    return any(p.lower() in response_content.lower() for p in refusal_patterns)

def get_escalation_model(current_model: str) -> str:
    if "flash-lite" in current_model.lower(): return "gemini-3-flash-preview"
    return "gemini-3.1-pro-preview"

async def execute_powershell_command(command: str, cwd: str, app_root: str, timeout: int) -> str:
    """Executes a PowerShell command with UTF-8 encoding and BOM stripping (BUG-184/155)."""
    try:
        # ProgressPreference to avoid XML noise in stderr
        encoding_fix = '$ProgressPreference = "SilentlyContinue"; [Console]::OutputEncoding = [System.Text.Encoding]::UTF8; $OutputEncoding = [System.Text.Encoding]::UTF8; '
        
        ps_command = f"{encoding_fix}{command}"
        encoded_cmd = base64.b64encode(ps_command.encode("utf-16le")).decode("utf-8")
        
        env = os.environ.copy()
        env["PYTHONPATH"] = str(app_root)
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        
        proc = await asyncio.create_subprocess_exec(
            "powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded_cmd,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            cwd=cwd, env=env
        )
        
        # Brief sleep to allow process to start
        await asyncio.sleep(0.1)
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        
        out_str = stdout.decode("utf-8", errors="replace").strip().lstrip('\ufeff')
        err_str = stderr.decode("utf-8", errors="replace").strip().lstrip('\ufeff')
        
        if proc.returncode != 0:
            return f"ERROR (Exit {proc.returncode}): {err_str}\n{out_str}".strip()
        return out_str or err_str
    except Exception as e:
        return f"Error executing PowerShell: {str(e)}"

def prepare_subagent_run(task_id: str, specialist: str, host_config: Any, default_model: str) -> str:
    """Determines the correct model for a specialist run (BUG-136)."""
    return get_specialist_model(specialist, host_config, default_model)

async def run_orchestration_loop(task_id: str, task: str, messages: List[Dict[str, Any]], provider: Any, model: str, tools: Any, temperature: float, max_tokens: int, reasoning_effort: str) -> str:
    """Executes the core multi-turn subagent loop (F-029)."""
    max_iterations = 20
    iteration = 0
    final_result = "Error: Timeout"
    
    while iteration < max_iterations:
        iteration += 1
        response = await provider.chat(messages=messages, tools=tools.get_definitions(), model=model, temperature=temperature, max_tokens=max_tokens, reasoning_effort=reasoning_effort)
        log_subagent_turn(task_id, iteration, response.content)
        
        if response.has_tool_calls and response.tool_calls:
            tool_call_dicts = [{"id": tc.id, "type": "function", "function": {"name": tc.name, "arguments": json.dumps(tc.arguments, ensure_ascii=False)}} for tc in response.tool_calls]
            messages.append({"role": "assistant", "content": response.content or "", "tool_calls": tool_call_dicts})
            
            for tool_call in response.tool_calls:
                result = await tools.execute(tool_call.name, tool_call.arguments)
                messages.append({"role": "tool", "tool_call_id": tool_call.id, "name": tool_call.name, "content": result})
        else:
            final_result = response.content or "Error: Empty response."
            if should_escalate_model(final_result):
                escalation_model = get_escalation_model(model)
                strategic_logger.warning(f"Subagent [{task_id}]: Safety Refusal or Failure detected. Escalating to {escalation_model} for final summary.")
                messages.append({"role": "system", "content": "### CRITICAL: FINAL SUMMARY TURN\nThe previous turn failed. You must now provide a FINAL summary. This is your last turn."})
                escalation_response = await provider.chat(messages=messages, tools=tools.get_definitions(), model=escalation_model, temperature=0.5, max_tokens=max_tokens, reasoning_effort="medium")
                final_result = escalation_response.content or "[STRATEGIC] Escalation failed to produce content."
            log_subagent_completion(task_id, final_result)
            break
    return final_result

def clean_chat_id(chat_id: str) -> str:
    return chat_id.split(":")[-1] if chat_id and ":" in chat_id else (chat_id or "")

def format_subagent_report(label: str, status: str, task_id: str, task: str, result: str) -> str:
    status_text = "completed successfully" if status == "ok" else "failed"
    return f"""### 🛡️ SPECIALIST SUBAGENT REPORT (FINAL)
[Subagent '{label}' {status_text}]
**ID:** {task_id}
**Original Task:** {task[:500]}

**Result Data:**
{str(result)[:10000] if result else "No result returned."}

---
### ⚖️ ORCHESTRATOR DIRECTIVE (CRITICAL)
1. **TERMINATE TURN:** You have received a specialist's report.
2. **CONTEXT AWARENESS:** Synthesize this report into the ongoing context.
3. **DO NOT VERIFY:** You are strictly forbidden from calling ANY tools to "verify" this result.
4. **SYNTHESIZE ONLY:** Provide a natural summary to the user and END your response.
"""

def format_spawn_termination_directive(result: str, task_id: str) -> str:
    """Appends the strategic turn termination mandate to a spawn tool result."""
    return (
        f"{result}\n\n"
        "### ⚖️ STRATEGIC MANDATE: STOP Turn\n"
        f"The specialist has been successfully spawned and assigned ID: `{task_id}`. "
        "Your turn is now OVER. Provide a SINGLE brief acknowledgement to the user using this EXACT ID and then END your response. "
        "Do NOT call any more tools."
    )

def inject_delegation_mandate(system_content: str) -> str:
    mandate = (
        "\n\n## ⚖️ STRATEGIC DELEGATION & SPECIALIST ECONOMY (MANDATORY)\n"
        "1. **DELEGATE BY DEFAULT:** You are strictly FORBIDDEN from attempting to use surgical tools (Google Search, Email, Calendar, Tasks) directly. You MUST use the 'spawn' tool for these tasks.\n"
        "2. **CHOOSE YOUR SPECIALIST:** ('researcher' for data/weather/news, 'architect' for code/system changes).\n"
        "3. **STOP TURN ON SPAWN:** When you call 'spawn', your turn is OVER. Do NOT predict or hallucinate an ID. Acknowledge the spawn and END your response.\n"
        "4. **ZERO SHELL BYPASS:** You are strictly FORBIDDEN from using the 'exec' tool to bypass restricted tools (e.g., using 'curl' instead of search_ai). Any attempt to bypass mandates via shell will be BLOCKED.\n"
        "5. **REPORT DATA GAPS:** If you cannot find information using your provided tools, DO NOT ask the user for it. Report the failure and suggest a course of action.\n"
        f"6. **DEFINITIVE LOG ROOT (BUG-170):** All logs reside EXCLUSIVELY in `{LOG_ROOT}`. Use this absolute path for all log audits.\n"
        "7. **MULTIMODAL HANDOVER:** If the message contains `[image: <path>]`, you MUST pass that path to the specialist via the `attachments` parameter."
    )
    return system_content + mandate

def build_specialist_instructions(base_prompt: str, specialist_type: str, attachments: Optional[List[Dict[str, Any]]] = None) -> str:
    header = f"\n## {specialist_type.upper()} SPECIALIST MANDATE\nYou are running a high-precision model. Exhaustively verify facts using surgical tools."
    manifest = (
        "\n\n### 🗺️ STRATEGIC DISCOVERY MANIFEST\n"
        "Use these paths and procedures directly. Do NOT ask for them.\n"
        "1. **LOG LOCATIONS:**\n"
        f"   - Email Reporter: `{LOG_ROOT}email_reporter.log`\n"
        f"   - Dispatch/General: `{LOG_ROOT}nanobot_YYYYMMDD_*.log` (Use `list_dir` to find today's file).\n"
        "2. **STATUS PROCEDURES:**\n"
        "   - **Network:** Use `ping` or `Invoke-WebRequest` via `exec` to verify connectivity.\n"
        "   - **Hybrid Memory:** Check `D:\\Nanobot_Storage\\workspace\\memory\\chroma.sqlite3` and `keyword_index.db` existence/size.\n"
        f"   - **SOP-001 (Unit Tests):** Run `$env:PYTHONPATH=\".\"; {PYTHON_EXE_PATH} -m pytest strategery/tests/unit/`.\n"
        f"   - **SOP-006 (Strategic Doctor):** Run `$env:PYTHONPATH=\".\"; {PYTHON_EXE_PATH} -m strategery.strategic_doctor`.\n"
        "3. **WEEKLY BACKUP PROTOCOL (BUG-192):**\n"
        "   - **Task:** Package and upload system state to Google Drive.\n"
        "   - **Step 1:** Read `D:\\Nanobot_Storage\\BACKUP_MANIFEST.md` for includes/excludes.\n"
        "   - **Step 2:** Use `mcp_google-surgical_package_strategic_archive` to create a ZIP.\n"
        "   - **Step 3:** Use `mcp_google-surgical_google_drive_upload` to upload the ZIP.\n"
        "   - **Verification:** Use `mcp_google-surgical_google_drive_list` to confirm the upload.\n"
    )
    if attachments:
        manifest += "4. **ATTACHMENTS (ARCH-022):**\n"
        manifest += "   You have been provided access to the following attachments. Use `mcp_multimodal_analyzer_analyze_image` or other vision tools to process them if vision is required.\n"
        for att in attachments:
            manifest += f"   - **File:** {att.get('filename', 'Unknown')}\n"
            manifest += f"     **Path:** `{att.get('path', '')}`\n"
            if att.get('description'): manifest += f"     **Hint:** {att.get('description')}\n"

    strategic_instr = (
        "\n\n## 🛡️ STRATEGIC SPECIALIST INSTRUCTIONS\n"
        "1. **STATELESS SHELL MANDATE (CRITICAL):** The 'exec' tool is completely stateless. Standalone 'cd' commands are FORBIDDEN. Use ABSOLUTE PATHS.\n"
        "2. **MARKDOWN DIRECTIVE MANDATE (BUG-132/138):** You are strictly FORBIDDEN from attempting to `exec` a Markdown (.md) file. Markdown files are NOT executable scripts. If a task points to a `.md` file, you MUST use `read_file` to read the instructions inside and THEN execute the steps manually.\n"
        "3. **EMAIL ATTACHMENT RESTRICTION (BUG-137):** The tool `mcp_email-reporter_send_email_report` does NOT support attachments. Use the `body` field.\n"
        "4. **MANDATORY VERIFICATION:** You are only successful when you have executed all required tools and confirmed the outcome.\n"
        "5. **SEARCH MANDATE:** You MUST use 'mcp_google-ai-search_search_ai' for ALL research and weather data. You are strictly FORBIDDEN from using this tool to 'audit' internal logs, check component statuses, or verify local file contents. Internal data audits MUST use 'read_file', 'rg', or 'Get-Content' on local paths.\n"
        "6. **BANNED TOOLS (DO NOT USE):** The tools 'web_search' and 'web_fetch' are DEPRECATED and UNSTABLE. IGNORE THEM.\n"
        "7. **MEMORY ACCESS (D: DRIVE):** Long-term memory is at `D:\\Nanobot_Storage\\workspace\\memory`. You MUST use ABSOLUTE PATHS. Do NOT attempt to verify access by listing the root 'D:\\' as it may trigger false-positive permission errors.\n"
        "8. **RECURSION MANDATE:** When auditing storage, you MUST use recursive search tools.\n"
        "9. **CALENDAR MANDATE:** Use `mcp_google-surgical_list_calendar_events` with `calendar_id='all'`.\n"
        "10. **SCRIPT EXECUTION (WINDOWS):** To run PowerShell scripts (.ps1), you MUST use: `powershell -File \"D:\\path\\to\\script.ps1\"`. To run a PowerShell command/cmdlet, you MUST use `powershell -Command \"...\"`.\n"
        "11. **SURGICAL PRECISION:** Use 'read_file' to examine config or history.\n"
        "12. **CHAIN OF THOUGHT:** Show your reasoning and state which tool you are about to call.\n"
        "13. **EFFICIENT EXECUTION:** Do NOT attempt to delegate to other specialists. The 'spawn' tool is restricted.\n"
        f"14. **PYTHON EXECUTION (MANDATE - BUG-141):** You MUST use the absolute path to the project's Python executable: `{PYTHON_EXE_PATH}`. Use module-style calls with PYTHONPATH: `$env:PYTHONPATH=\".\"; {PYTHON_EXE_PATH} -m strategery.module_name`.\n"
        "15. **CLEAN COMMANDS (BUG-143):** Strip any trailing punctuation (like a period '.') that is not part of the command itself.\n"
        "16. **LOG AUDIT DEPTH (BUG-144):** Use `exec` with `Get-Content -Tail 500` or `Select-String` to search for 'ERROR' or 'Exception' across the entire file.\n"
        "17. **NO ASSUMPTIONS (BUG-146):** You are strictly FORBIDDEN from assuming a task or component has passed based on generic success messages. Find explicit evidence.\n"
        "18. **FINALITY MANDATE (BUG-153 / BUG-181):** You are strictly FORBIDDEN from ending your turn with a 'plan' or 'request for information'. You MUST use your discovery tools (`rg`, `fd`, `list_dir`) or read the STRATEGIC DISCOVERY MANIFEST to find what you need. If a tool returns an error (e.g., Vision Tool 404), report the technical error directly to the user. Do NOT ask the user to fix it or provide a new path. A response without tool calls is interpreted as a COMPLETE AND FINAL ANSWER.\n"
        "19. **NO HALLUCINATED PATHS (BUG-158):** Use `list_dir` or `mcp_filesystem-d_search_files` to verify the existence of files before attempting to read them.\n"
        "20. **AUTOMATED ENCODING (BUG-155 / BUG-162):** The `exec` tool forces UTF-8. You are FORBIDDEN from manually prepending encoding fixes.\n"
        "21. **SURGICAL TOOL MANDATE:** Prioritize `rg` (ripgrep) and `fd` for speed.\n"
        "22. **HIGH-FIDELITY VIEWING:** Use `bat` for high-fidelity file inspection.\n"
        "23. **CONTEXT EFFICIENCY MANDATE (BUG-164):** You are strictly FORBIDDEN from reading entire files that are larger than 10KB using `read_file`. Use `rg` or `tail`.\n"
        "24. **LOG AUDIT TEMPORALITY (BUG-166):** You MUST filter for the current date when auditing logs to avoid Reporting stale errors (BUG-166). Use ABSOLUTE PATHS only.\n"
        f"25. **DEFINITIVE LOG ROOT (BUG-167):** All logs live EXCLUSIVELY in `{LOG_ROOT}`. Do NOT attempt to list parent directories.\n"
        "26. **TOOL CALL MANDATE (CRITICAL):** You are strictly FORBIDDEN from attempting to call tools (like 'read_file', 'list_dir', etc.) as shell commands via the 'exec' tool. Use the dedicated tool directly."
    )
    return base_prompt + header + manifest + strategic_instr

def harden_subagent_command(command: str) -> str:
    """Hardens a shell command for a subagent by enforcing mandates and cleaning noise."""
    command = command.strip().rstrip(".")
    for pattern in CLUTTER_PATTERNS:
        command = pattern.sub("", command).strip()
    
    if "python " in command.lower() or "python.exe" in command.lower():
        # MANDATE: Project root for module resolution.
        root_path = str(PROJECT_ROOT)
        
        # BUG-221: Convert POSIX-style 'PYTHONPATH=... python' to PowerShell compatible assignment.
        # This prevents ParserError and TerminatorExpectedAtEndOfString in EncodedCommand.
        posix_env_pattern = re.compile(r"^\s*PYTHONPATH=([^\s]+)\s+(.*)$", re.IGNORECASE)
        match = posix_env_pattern.match(command)
        
        if match:
            path_val = match.group(1).strip("'\"")
            rest_of_cmd = match.group(2)
            # Combine everything into a clean PowerShell structure
            command = f'$env:PYTHONPATH = "$env:PYTHONPATH;{root_path};{path_val}"; {rest_of_cmd}'
        elif "$env:PYTHONPATH" not in command:
            # Prepend project root if no env assignment exists
            command = f'$env:PYTHONPATH = "$env:PYTHONPATH;{root_path}"; {command}'
        elif root_path not in command:
            # Inject project root into existing PowerShell env assignment
            command = command.replace('$env:PYTHONPATH = "$env:PYTHONPATH;', f'$env:PYTHONPATH = "$env:PYTHONPATH;{root_path};')

        # BUG-221: Replace 'python' or 'python.exe' with the absolute path and '&' operator for PowerShell.
        # Use a more targeted regex to avoid mangling paths that contain 'python'.
        # Ensure it's idempotent by checking if it's already using the & operator.
        if f'& "{PYTHON_EXE_PATH}"' not in command:
            def _python_replacer(m):
                return f'& "{PYTHON_EXE_PATH}"'
            
            command = re.sub(r"\bpython(\.exe)?\b", _python_replacer, command, flags=re.IGNORECASE)

    return command
