from typing import Any, List, Dict
from nanobot.agent.tools.base import Tool
from strategery.patches.vsa import VectorStoreFactory

class SearchMemoryTool(Tool):
    """
    Tool for agents to proactively search their long-term memory.
    Queries the StrategicVectorStore (ChromaDB) for semantically similar historical entries.
    """
    
    @property
    def name(self) -> str:
        return "search_memory"

    @property
    def description(self) -> str:
        return (
            "Search your long-term memory for relevant historical information, past decisions, "
            "and project context. Use this tool when you need more background than what's "
            "available in the current conversation context."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The semantic search query (e.g., 'What was decided about the database schema?')."
                },
                "n_results": {
                    "type": "integer",
                    "description": "Number of memory entries to retrieve (default: 5).",
                    "minimum": 1,
                    "maximum": 10
                }
            },
            "required": ["query"]
        }

    async def execute(self, **kwargs: Any) -> str:
        query = kwargs.get("query")
        n_results = kwargs.get("n_results", 5)

        if not query:
            return "Error: Search query is required."

        try:
            # Get the store (it should already be initialized by the agent/patch)
            store = VectorStoreFactory.get_store()
            
            results = await store.query(query, n_results=n_results)
            
            if not results:
                return "No relevant memories found for that query."

            # Format results for the LLM
            formatted_output = [f"Found {len(results)} relevant memories:"]
            for i, res in enumerate(results, 1):
                content = res.get("content", "(empty)")
                metadata = res.get("metadata", {})
                distance = res.get("distance", 0.0)
                
                # We can refine the output format here
                timestamp = metadata.get("timestamp", "unknown")
                source = metadata.get("source", "unknown")
                
                formatted_output.append(
                    f"[{i}] [{timestamp}] (Source: {source}, Relevance: {1.0 - distance:.2f})\n{content}\n"
                )

            return "\n".join(formatted_output)

        except Exception as e:
            from strategery.strategic_logger import strategic_logger
            strategic_logger.error(f"SearchMemoryTool error: {e}")
            return f"Error querying memory: {str(e)}"
