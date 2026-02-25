# Heartbeat Tasks

> **Model Note:** This file is processed by Qwen2.5-Coder (Local). 
> **Current Context:** Always use the `get_current_time` tool before evaluating the tasks below.

## Active Tasks

- [ ] **Memory Maintenance:** - **Condition:** If the current time is after 11:00 PM.
  - **Action:** Read `memory/HISTORY.md`. Summarize new decisions, preferences, or project states into `memory/MEMORY.md`. 
  - **Cleanup:** Clear summarized entries from `HISTORY.md`.

- [ ] **Daily Briefing:** - **Condition:** If the current time is between 8:45 AM and 9:15 AM AND `memory/DAILY_BRIEFING.md` has not been updated today.
  - **Action:** Use the `spawn` tool to create "Morning_Researcher".
  - **Instruction:** "Compile a morning briefing for Matthew. 1. Get today's schedule. 2. Web search: Weather (Sachse & Colorado Springs), Pre-market stocks/sentiment, AI news (local agents/Google), and CO Springs real estate. 3. Format with H2 headers: '📅 Today's Schedule', '🌤️ Weather Outlook', '📈 Market & Finance', '🏡 Real Estate Watch', '🤖 Tech & AI Updates'. 4. Write to `memory/DAILY_BRIEFING.md`."


## Completed

<!-- Move completed tasks here or delete them -->

