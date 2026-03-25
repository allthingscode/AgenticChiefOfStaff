import os
import re
from typing import Type
from pydantic import BaseModel, Field
from crewai.tools import BaseTool

class LocalFileReadToolInput(BaseModel):
    """Input for LocalFileReadTool."""
    file_path: str = Field(..., description="The absolute path to the file to read.")

class LocalFileReadTool(BaseTool):
    name: str = "local_file_read_tool"
    description: str = "Reads the content of a local file. Use this to analyze codebase files."
    args_schema: Type[BaseModel] = LocalFileReadToolInput

    def _run(self, file_path: str) -> str:
        try:
            # Resolve home directory dynamically
            home_dir = os.path.expanduser("~")
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
            
            # MANDATE: Resolve storage root dynamically from config if possible
            # Default to D: for this machine but support portability
            storage_root = r"D:\Nanobot_Storage"
            config_path = os.path.join(home_dir, ".nanobot", "config.json")
            if os.path.exists(config_path):
                try:
                    import json
                    with open(config_path, "r", encoding="utf-8-sig") as f:
                        cfg = json.load(f)
                        storage_root = cfg.get("strategic_edition", {}).get("storage_root", storage_root)
                except: pass

            allowed_roots = [
                project_root,
                storage_root
            ]
            abs_path = os.path.abspath(file_path)
            if not any(abs_path.startswith(root) for root in allowed_roots):
                return f"Error: Access denied to path {file_path}. Stay within project roots."
            
            with open(abs_path, 'r', encoding='utf-8-sig') as f:
                return f.read()
        except Exception as e:
            return f"Error reading file: {str(e)}"

class FeatureBacklogToolInput(BaseModel):
    """Input for FeatureBacklogTool."""
    action: str = Field(..., description="The action to perform: 'get_next_id', 'read_template', or 'write_feature'.")
    feature_name: str = Field(None, description="The name of the feature (required for 'write_feature').")
    content: str = Field(None, description="The full markdown content of the feature (required for 'write_feature').")

class FeatureBacklogTool(BaseTool):
    name: str = "feature_backlog_tool"
    description: str = (
        "Interacts with the project's feature backlog. "
        "Can 'read_template' to get the structure, 'get_next_id' to find the next F-XXX ID, "
        "and 'write_feature' to save a new specification."
    )
    args_schema: Type[BaseModel] = FeatureBacklogToolInput
    
    # Dynamically resolve paths relative to the project root
    @property
    def project_root(self) -> str:
        return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

    @property
    def backlog_dir(self) -> str:
        return os.path.join(self.project_root, "strategery", "private", "feature_backlog")

    @property
    def template_path(self) -> str:
        return os.path.join(self.backlog_dir, "TEMPLATE.md")

    def _run(self, action: str, feature_name: str = None, content: str = None) -> str:
        if action == "read_template":
            try:
                with open(self.template_path, 'r', encoding='utf-8') as f:
                    return f.read()
            except Exception as e:
                return f"Error reading template: {str(e)}"

        elif action == "get_next_id":
            try:
                files = os.listdir(self.backlog_dir)
                ids = []
                for f in files:
                    match = re.match(r"F-(\d+)", f)
                    if match:
                        ids.append(int(match.group(1)))
                next_id = max(ids) + 1 if ids else 1
                return f"F-{next_id:03d}"
            except Exception as e:
                return f"Error determining next ID: {str(e)}"

        elif action == "write_feature":
            if not feature_name or not content:
                return "Error: feature_name and content are required for 'write_feature'."
            
            try:
                # Find the next ID again to be safe
                next_id_str = self._run("get_next_id")
                # Clean feature name for filename
                safe_name = re.sub(r'[^\w\s-]', '', feature_name).strip().replace(' ', '_')
                filename = f"{next_id_str}_{safe_name}.md"
                file_path = os.path.join(self.backlog_dir, filename)
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                return f"Successfully wrote feature specification to {file_path}"
            except Exception as e:
                return f"Error writing feature: {str(e)}"
        
        return f"Unknown action: {action}"
