"""
STRATEGIC CHECKPOINT LOGIC: Durable Execution Layer (ARCH-024)
Goal: Provide ACID-compliant state persistence for AgentLoop and SubagentManager.
Storage: SQLite (WAL Mode) on D: Drive.
"""
import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal, Union, List, Optional, Dict, Any
from pydantic import BaseModel, Field, TypeAdapter, ConfigDict
from loguru import logger

# --- 1. SCHEMAS (Pydantic v2) ---

class TextContent(BaseModel):
    type: Literal["text"] = "text"
    text: str

class ThinkingContent(BaseModel):
    type: Literal["thinking"] = "thinking"
    text: str

class ImageURL(BaseModel):
    url: str

class ImageContent(BaseModel):
    type: Literal["image_url"] = "image_url"
    image_url: ImageURL

class ToolCallFunction(BaseModel):
    name: str
    arguments: str

class ToolCallContent(BaseModel):
    type: Literal["tool_call"] = "tool_call"
    id: str
    function: ToolCallFunction

ContentItem = Annotated[
    Union[TextContent, ThinkingContent, ImageContent, ToolCallContent],
    Field(discriminator="type")
]

class StrategicMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: Optional[Union[str, List[ContentItem]]] = None
    name: Optional[str] = None
    tool_call_id: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    reasoning_content: Optional[str] = None
    thinking_blocks: Optional[List[Dict[str, Any]]] = None

# --- 2. DATABASE LOGIC ---

class CheckpointManager:
    """Manages SQLite-based durability for Nanobot Strategic Edition."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(CheckpointManager, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, storage_root: str):
        if self._initialized:
            return
            
        self.db_path = Path(storage_root) / "workspace" / "checkpoints.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._initialized = True

    def _get_connection(self):
        """Returns a connection with WAL mode enabled."""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Initializes the SQLite schema."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS threads (
                    thread_id TEXT PRIMARY KEY,
                    status TEXT DEFAULT 'active',
                    model TEXT,
                    metadata JSON,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS checkpoints (
                    checkpoint_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    thread_id TEXT,
                    iteration INTEGER,
                    state JSON,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (thread_id) REFERENCES threads(thread_id)
                )
            """)
            conn.commit()

    def create_thread(self, thread_id: str, model: str, metadata: Dict[str, Any] = None):
        """Initializes a new durable thread."""
        with self._get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO threads (thread_id, model, status, metadata, updated_at) VALUES (?, ?, 'active', ?, CURRENT_TIMESTAMP)",
                (thread_id, model, json.dumps(metadata or {}))
            )
            conn.commit()

    def save_snapshot(self, thread_id: str, iteration: int, messages: List[Dict[str, Any]]):
        """Atomic snapshot of the current agent state."""
        try:
            # 1. Validate via Pydantic
            adapter = TypeAdapter(List[StrategicMessage])
            validated = adapter.validate_python(messages)
            state_json = adapter.dump_json(validated).decode('utf-8')
            
            # 2. Persist
            with self._get_connection() as conn:
                conn.execute(
                    "INSERT INTO checkpoints (thread_id, iteration, state) VALUES (?, ?, ?)",
                    (thread_id, iteration, state_json)
                )
                conn.execute(
                    "UPDATE threads SET updated_at = CURRENT_TIMESTAMP WHERE thread_id = ?",
                    (thread_id,)
                )
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Checkpoint failed for thread {thread_id}: {e}")
            return False

    def load_latest(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """Loads the most recent valid snapshot for a thread."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM checkpoints WHERE thread_id = ? ORDER BY iteration DESC, checkpoint_id DESC LIMIT 1",
                (thread_id,)
            ).fetchone()
            
            if not row:
                return None
            
            thread_row = conn.execute("SELECT * FROM threads WHERE thread_id = ?", (thread_id,)).fetchone()
            
            return {
                "iteration": row["iteration"],
                "messages": json.loads(row["state"]),
                "model": thread_row["model"] if thread_row else None,
                "metadata": json.loads(thread_row["metadata"]) if thread_row and thread_row["metadata"] else {}
            }

    def complete_thread(self, thread_id: str):
        """Marks a thread as completed (prevents further resumes unless forced)."""
        with self._get_connection() as conn:
            conn.execute("UPDATE threads SET status = 'completed', updated_at = CURRENT_TIMESTAMP WHERE thread_id = ?", (thread_id,))
            conn.commit()

    def list_resumable(self) -> List[Dict[str, Any]]:
        """Finds all active threads with valid snapshots."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT t.thread_id, t.model, t.updated_at, MAX(c.iteration) as latest_iteration
                FROM threads t
                JOIN checkpoints c ON t.thread_id = c.thread_id
                WHERE t.status != 'completed'
                GROUP BY t.thread_id
                ORDER BY t.updated_at DESC
            """)
            return [dict(row) for row in cursor.fetchall()]

# --- GLOBAL FACTORY ---
def get_checkpoint_manager(storage_root: str) -> CheckpointManager:
    return CheckpointManager(storage_root)
