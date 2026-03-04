# Feature Specification: Surgical UI

## **Overview**
- **Feature ID:** F-006
- **Status:** Planning
- **Target Specialist:** Architect
- **High-Level Goal:** Develop a minimal, high-efficiency dashboard for inspecting and managing "Gold Standard" memories, facts, and the strategic knowledge graph.

## **Architectural Design**
- **Component Changes:** New `strategery/ui/` directory with a lightweight web server (e.g., FastAPI, Streamlit, or a simple HTML/JS frontend).
- **Data Flow:** UI queries Vector Store/NanoGraph via strategic APIs -> Renders for human review -> User edits/deletes -> Persistence triggered.
- **Persistence:** Direct connection to `D:\Nanobot_Storage\workspace\memory`.

## **Constraints & Mandates**
- **Zero Core Pollution:** UI must be a standalone component outside of `nanobot/`.
- **Minimalist Aesthetic:** Focus on speed and information density over visual flair.
- **Read-Only by Default:** Ensure accidental deletes are difficult.

## **Implementation Steps**
1. [Planning] Design the UI layout and core interactions.
2. [API] Create a strategic read/write API for the Vector Store.
3. [Frontend] Implement a simple search and list view for memories.
4. [Graph View] Add a basic relationship explorer for the Knowledge Graph.

## **Testing & Validation**
- **Unit Tests:** `strategery/tests/unit/test_ui_api.py`
- **Manual Check:** Run the dashboard, search for a fact, and verify it matches the CLI results.

## **Context & Background**
- Interacting with a vector database via CLI is often slow and lacks visual context. A "Surgical UI" allows for rapid fact-checking and curation, ensuring the agent's long-term memory remains high-quality.
