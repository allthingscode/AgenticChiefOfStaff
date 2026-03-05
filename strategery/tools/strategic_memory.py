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
            "and project context. Supports both semantic (meaning-based) and keyword (exact match) search. "
            "Use this tool when you need more background than what's available in current context."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query or keyword (e.g., 'database schema' or 'BUG-042')."
                },
                "search_type": {
                    "type": "string",
                    "enum": ["hybrid", "keyword", "semantic"],
                    "description": "The search strategy. 'hybrid' (default) combines both. 'keyword' is best for exact IDs. 'semantic' is best for concepts.",
                    "default": "hybrid"
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
        search_type = kwargs.get("search_type", "hybrid")

        if not query:
            return "Error: Search query is required."

        try:
            store = VectorStoreFactory.get_store()
            
            # HybridStore supports 'query' which is already hybrid.
            # We can expose explicit keyword/semantic if needed, but for now 
            # let's just use the store's unified query.
            # If search_type is explicit, we could filter but 'hybrid' is usually best.
            
            if search_type == "keyword" and hasattr(store, "_keyword_search"):
                results = store._keyword_search(query, n_results=n_results)
            elif search_type == "semantic" and hasattr(store, "vector_store"):
                results = await store.vector_store.query(query, n_results=n_results)
            else:
                results = await store.query(query, n_results=n_results)
            
            if not results:
                return f"No relevant memories found for query: '{query}' (type: {search_type})"

            formatted_output = [f"Found {len(results)} relevant memories (Strategy: {search_type}):"]
            for i, res in enumerate(results, 1):
                content = res.get("content", "(empty)")
                metadata = res.get("metadata", {})
                dist = res.get("distance", 0.0)
                res_type = res.get("type", "semantic")
                
                timestamp = metadata.get("timestamp", "unknown")
                source = metadata.get("source", "unknown")
                
                # Format relevance based on type
                relevance = f"Rank: {dist:.2f}" if res_type == "keyword" else f"Relevance: {1.0 - dist:.2f}"
                
                formatted_output.append(
                    f"[{i}] [{timestamp}] (Source: {source}, {relevance}, Type: {res_type})\n{content}\n"
                )

            return "\n".join(formatted_output)

        except Exception as e:
            from strategery.strategic_logger import strategic_logger
            strategic_logger.error(f"SearchMemoryTool error: {e}")
            return f"Error querying memory: {str(e)}"
