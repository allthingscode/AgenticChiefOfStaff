# Long-term Memory

This file stores important information that should persist across sessions.

## User Information

- **Name:** Matthew Hayes
- **Location:** Sachse, Texas
- **Profession:** Software Engineer
- **Interests:** Using AI to improve his life, playing the alto sax, achieving financial freedom for early retirement, and following a ketogenic diet.
- **Long-term Goals:**
    - **By 2027:** Sell his house in Sachse, TX and move to Colorado.
    - **By 2035:** Achieve professional competency playing the alto sax.
    - **By 2040:** Be in early retirement in Colorado Springs.

## Preferences

- **LLM Usage Strategy:** Using a single model. The multi-model routing experiment has been abandoned.
- **Privacy:** Values privacy, which is a key motivator for using local LLMs.

## Project Context

- **Current Focus:** Simplifying the `config.json` file and reverting `loop.py` and `commands.py` to their original, uncustomized versions. The multi-model routing experiment has been abandoned.
- **Development Protocol:** The current, successful protocol for source code changes is: 1) The agent generates the complete, corrected content for a source file. 2) The user manually replaces the content of the target file. 3) The agent verifies the change with `read_file`. 4) The user restarts the application to test.
- **User Frustration Point:** The user is questioning why the agent cannot statically analyze its own code changes to detect logical errors before recommending them, viewing it as a deterministic process. This highlights a need for better self-correction and code validation strategies.
- **Critical Routing Bug:** The multi-model routing experiment was abandoned due to persistent issues with LLM-based intent classification, specifically the `gemini-1.5-flash-latest` model failing to consistently return valid JSON, and recurring errors with model name prefixes. The system is now configured to use a single model.
- **Next Step:** Simplify `config.json` to remove all routing-related configurations and ensure it uses a single, valid model. All customizations in `loop.py` and `commands.py` have been reverted. The goal is to return to a stable, uncustomized Nanobot setup.
- **Future Plan:** To make the routing logic configurable, the current plan is to move the hard-coded rules from `nanobot/agent/loop.py` into a new, dedicated configuration file at `~/.nanobot/routing.json`. The Python code will then be modified to read from this file.
- **Configuration Details:** The system is now configured to use a single LLM model. The `litellm` library automatically prepends provider-specific prefixes (e.g., `models/` for Gemini, `ollama/` for Ollama). Therefore, when specifying models in configurations or code, the name must be the base model name without any prefix (e.g., use `gemini-2.5-flash`).
- **Tool Configuration:** The `web_search` tool is deprecated.

## Agent Permissions & Safety

- **File System Access:** The agent operates under a three-tiered permission model for safety.
    - **Tier 1 (Workspace):** Full read/write access to `C:\Users\HayesAiAgent\Documents\nanobot\workspace\`. This is for temporary files, scripts, and work products.
    - **Tier 2 (Configuration):** Special, privileged access to `C:\Users\HayesAiAgent\.nanobot\` to manage its own configuration files.
    - **Tier 3 (Source Code):** Intentionally restricted write access to `C:\Users\HayesAiAgent\Documents\nanobot\nanobot\` to prevent accidental self-modification.
- **Privileged Operations:** The `exec` tool is the designated "power tool" for performing operations outside the standard permissions, such as applying a source code patch, and requires explicit user approval.

## Important Notes

- **Hardware:** The user is on a Windows 11 Alienware m17 laptop.
- **GPU:** The machine has an NVIDIA GeForce RTX 2060, which is used for GPU acceleration with Ollama.
- **Local LLM Setup:** Ollama is installed and running. The `llama3.1:8b` model is available for local inference.
- **Nanobot Framework Constraint:** The framework is very strict. It does not allow new top-level keys in `~/.nanobot/config.json`. The framework *silently ignores* unknown top-level keys, preventing a `TypeError` but causing configurations placed at the top level (like `llm_routing`) to be completely missed during startup.
- **litellm Library Behavior:** The `litellm` library automatically prepends provider-specific prefixes (e.g., `models/` for Gemini, `ollama/` for Ollama). Therefore, when specifying models in configurations or code, the name must be the base model name without any prefix (e.g., use `gemini-1.5-pro-latest`, use `llama3.1:8b`).
- **Agent Config:** The primary agent configuration is at `C:\Users\HayesAiAgent\.nanobot\config.json`. A secondary config may exist at `C:\Users\HayesAiAgent\Documents\nanobot\config.json`.
- **CRITICAL PROTOCOL: CONFIG.JSON BACKUP AND STRUCTURE:** The main config file (`~/.nanobot/config.json`) is NOT under version control. It is **ABSOLUTELY CRITICAL** to create a backup of this file *before* making any edits. Furthermore, the Nanobot framework is extremely strict about the structure of `config.json`; it **does NOT allow new top-level keys** (e.g., 'user' or 'finance' cannot be directly at the top level). Adding unauthorized top-level keys will cause the configuration to fail validation and revert to defaults. All custom data must be placed within existing, recognized sections if possible, or managed externally. Failures require manual user intervention to restore.
- **Logging Issue:** Application logs are written to standard output. Two key errors have been observed: 1) `Error sending Telegram message: Message is too long`, caused by responses exceeding the platform's character limit. 2) `Error calling LLM: list index out of range`, which originated in the `_consolidate_memory` function and caused session crashes. A patch for the second error has been applied in `loop.py`.
- **Channel Constraints:** The Telegram channel has a message length limit. Large messages, such as those containing code blocks, will fail to send with an `Error sending Telegram message: Message is too long`. This was re-confirmed in the latest interaction, leading the agent to adopt a new strategy: delivering large code blocks in smaller, numbered parts across multiple messages to ensure successful transmission.
