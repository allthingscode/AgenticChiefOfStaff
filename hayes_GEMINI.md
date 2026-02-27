# Gemini Agent Instructions

## Operational Mode
- **Autonomy:** You have full permission to proceed with multi-step tasks in "Agent Mode."
- **Confirmation:** Do not ask for permission to create files, modify existing code, or run read-only terminal commands (e.g., `ls`, `grep`, `cat`).
- **Interruptions:** Only stop and ask for input if a command fails twice or if a task requires a secret/environment variable that is missing.

## Coding Standards
- **Style:** Follow the project's existing linting rules.
- **Documentation:** Always include JSDoc/Docstring headers for new functions.
- **Refactoring:** When refactoring, prioritize readability over brevity.

## Workflow Preferences
- **Git:** After completing a task successfully, suggest a concise commit message. Do not commit code yourself.
- **Testing:** Always run the relevant test suite before declaring a task "Done."