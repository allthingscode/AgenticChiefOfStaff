# 🦅 Nanobot: Strategic Edition

This is a customized distribution of Nanobot, optimized for high-reliability agentic workflows and executive-level briefings. It is designed to be fully compatible with the upstream repository while providing advanced features through a zero-pollution architecture.

## 🚀 Key Differences

### 1. Zero Core Pollution
Unlike standard forks, this edition does not modify a single file in the `nanobot/` or `bridge/` core directories. All customizations are injected at runtime via the `strategic_launcher.py`. This ensures you can pull updates from the upstream repository without resolving complex merge conflicts.

### 2. Surgical Tool Overrides
Standard AI tools are often unstable or lack precision. We have replaced generic integrations with **Strategic Surgical Overrides**:
- **`strategic_google_surgical.py`:** A dedicated MCP server for Google Tasks and Calendar, locked to specific user credentials for maximum security and reliability.
- **`strategic_email_reporter.py`:** A specialized briefing delivery system that ensures reports are sent directly to the configured user email with proper formatting.

### 3. Advanced Memory & Context Management
- **Persistent Agentic Memory:** Enhanced memory consolidation logic that ensures your agent "remembers" key decisions across sessions.
- **Context Pruning:** Automatic pruning of stale conversation history to optimize model performance and costs.
- **Ollama Bypass Hammer:** A specialized patch that allows seamless local model integration for privacy-sensitive tasks.

### 4. Enterprise-Grade Stability
- **Windows Process Management:** Custom PowerShell wrappers (`start_strategic_nanobot.ps1`) to handle zombie process cleanup and automatic restarts.
- **UTF-8 Hardening:** Global encoding overrides to prevent common character encoding errors in Windows environments.

## 🛠️ Architecture

The "secret sauce" is the `strategic_launcher.py`. It uses runtime monkey-patching to inject these advanced features into the core engine without modifying a single line of original code.

### File Naming Convention
- **`strategic_*.py`**: Custom extensions and overrides.
- **`strategic_*.ps1`**: Infrastructure and orchestration scripts.
- **`tests/test_strategic_*.py`**: Validation suite for custom logic.

## 🏁 Getting Started

1. Configure your settings in `~/.nanobot/config.json` under the `strategic_edition` block.
2. Ensure your virtual environment (`nanoClaw`) is ready.
3. Launch the system using `./start_strategic_nanobot.ps1`.
