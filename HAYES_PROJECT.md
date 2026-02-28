# 🦅 Nanobot: The Hayes Strategic Edition

This repository is a highly specialized fork of the [Nanobot AI](https://github.com/mizhuo/nanobot) framework. While it maintains compatibility with the core upstream engine, it has been engineered into a "Strategic OS" designed for high-reliability, automated decision-making and long-term memory persistence.

TLDR:  This is my Nanobot.  There are many like it, but this one is mine.  ... Without my nanobot, I am ... you get the idea.

## 🚀 What Makes This Edition Special?

Unlike a standard Nanobot installation, this project implements a **Modular "Surgical" Architecture**. We never pollute the core engine; instead, we wrap it in high-precision logic to handle enterprise-grade tasks without sacrificing the ability to pull in the latest upstream features.

### 1. Surgical Tool Overrides
Standard AI tools are often unstable or lack precision. We have replaced generic integrations with **Hayes Surgical Overrides**:
- **`mcp_google-surgical_`**: A custom high-reliability wrapper for Google Calendar and Tasks that ensures zero-fail scheduling and perfect credential alignment.
- **`mcp_email-reporter_`**: A dedicated briefing engine that formats and delivers strategic reports directly to the user's primary inbox, bypassing the noise of standard chat channels.

### 2. Specialist Model Routing
Not all models are created equal. This project implements an automated **Specialist Router**:
- **The Architect/Researcher**: High-depth tasks (planning, research, coding) are automatically routed to `gemini-1.5-pro` for maximum reasoning.
- **The Dispatcher**: Fast, everyday interactions use `gemini-3-flash-preview` for near-instant response times.
- *Value:* This balances cognitive depth with cost and speed efficiency automatically.

### 3. Infinite Storage & Log persistence
Standard bots often eat up system drive space or lose history. 
- We have re-engineered the storage layer to move all **Logs, Media, and Workspace data** to a dedicated high-capacity drive (`D:\Nanobot_Storage`).
- This ensures that years of historical data can be kept for AI review without impacting the host system's performance.

### 4. The Gateway Launcher (Modularity King)
The "secret sauce" is the `hayes_gateway_launcher.py`. It uses runtime monkey-patching to inject these advanced features into the core engine without modifying a single line of original code.
- *Value:* This makes the project **future-proof**. You can update the core `nanobot/` folder today, and all our strategic customizations will still work perfectly.

## 🛠 Strategic Architecture
- **Zero Core Pollution:** Customizations live in `hayes_` prefixed files.
- **Advanced Memory:** Implements multi-layer memory (History + Facts) with automated daily compaction.
- **Cross-Platform Readiness:** Specialized fixes for Windows process management and UTF-8 encoding.

---
*This is not just an AI bot; it is a persistent, strategic agent designed to act as a digital Chief of Staff.*
