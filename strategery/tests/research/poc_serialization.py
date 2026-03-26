from typing import Annotated, Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field, TypeAdapter


# 1. Define Discriminated Content Types for Multimodal/Thinking
class TextContent(BaseModel):
    type: Literal["text"] = "text"
    text: str

class ThinkingContent(BaseModel):
    type: Literal["thinking"] = "thinking"
    text: str  # Content of the thinking/reasoning block

class ImageURL(BaseModel):
    url: str

class ImageContent(BaseModel):
    type: Literal["image_url"] = "image_url"
    image_url: ImageURL

class ToolCallFunction(BaseModel):
    name: str
    arguments: str  # JSON string

class ToolCallContent(BaseModel):
    type: Literal["tool_call"] = "tool_call"
    id: str
    function: ToolCallFunction

# Discriminated Union for Content
ContentItem = Annotated[
    Union[TextContent, ThinkingContent, ImageContent, ToolCallContent],
    Field(discriminator="type")
]

# 2. Main Message Model
class StrategicMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: Optional[Union[str, List[ContentItem]]] = None
    name: Optional[str] = None
    tool_call_id: Optional[str] = None
    # Support for raw provider fields if needed
    tool_calls: Optional[List[Dict[str, Any]]] = None
    reasoning_content: Optional[str] = None
    thinking_blocks: Optional[List[Dict[str, Any]]] = None

# 3. Checkpoint Schema (The "Snapshot")
class StateCheckpoint(BaseModel):
    version: Literal["1.0"] = "1.0"
    session_id: str
    model: str
    temperature: float
    iteration: int
    messages: List[StrategicMessage]
    metadata: Dict[str, Any] = Field(default_factory=dict)

# --- POC TEST ---
def test_serialization():
    # Simulate a complex history
    messages = [
        {"role": "system", "content": "System prompt"},
        {"role": "user", "content": [{"type": "text", "text": "What is in this image?"}, {"type": "image_url", "image_url": {"url": "data:..."}}]},
        {"role": "assistant", "content": "I see a cat.", "thinking_blocks": [{"text": "Analyzing pixels..."}]},
        {"role": "assistant", "content": None, "tool_calls": [{"id": "call_123", "type": "function", "function": {"name": "read_file", "arguments": '{"path": "test.txt"}'}}]},
        {"role": "tool", "name": "read_file", "tool_call_id": "call_123", "content": "File content here"}
    ]

    # 1. Validate & Serialize
    adapter = TypeAdapter(List[StrategicMessage])
    validated_messages = adapter.validate_python(messages)

    checkpoint = StateCheckpoint(
        session_id="test-123",
        model="gemini-3-flash",
        temperature=0.1,
        iteration=5,
        messages=validated_messages
    )

    json_data = checkpoint.model_dump_json(indent=2)
    print("--- Serialized Checkpoint ---")
    print(json_data)

    # 2. Re-load & Restore
    restored_checkpoint = StateCheckpoint.model_validate_json(json_data)
    print("\n--- Restored Metadata ---")
    print(f"Session: {restored_checkpoint.session_id}, Messages: {len(restored_checkpoint.messages)}")

    # Verify a specific message (the tool call)
    tool_call_msg = restored_checkpoint.messages[3]
    assert tool_call_msg.tool_calls[0]["function"]["name"] == "read_file"
    print("Verification Passed: Complex tool call restored successfully.")

if __name__ == "__main__":
    test_serialization()
