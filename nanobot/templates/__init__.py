"""
This module provides the core functionality for managing Nanobot templates.

It includes functions for:
- Discovering available templates
- Loading template metadata
- Rendering templates
"""

import importlib.resources
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

logger = logging.getLogger(__name__)


class Template:
    """Represents a single Nanobot template."""

    def __init__(self, name: str, path: Path, metadata: Dict[str, Any]):
        self.name = name
        self.path = path
        self.metadata = metadata

    def __repr__(self):
        return f"<Template: {self.name}>"

    def render(self, data: Dict[str, Any]) -> str:
        """Renders the template with the given data."""
        env = Environment(
            loader=FileSystemLoader(self.path),
            autoescape=select_autoescape(["html", "xml"]),
        )
        template = env.get_template("template.j2")  # Assuming main template file is template.j2
        return template.render(data)


def discover_templates() -> List[Template]:
    """Discovers all available Nanobot templates."""
    templates: List[Template] = []
    template_dir = importlib.resources.files("nanobot.templates")

    for path in template_dir.iterdir():
        if path.is_dir() and (path / "template.j2").exists():
            metadata_path = path / "template.json"
            metadata: Dict[str, Any] = {}
            if metadata_path.exists():
                try:
                    metadata = json.loads(metadata_path.read_text())
                except json.JSONDecodeError as e:
                    logger.warning(f"Could not parse metadata for template {path.name}: {e}")
            templates.append(Template(path.name, path, metadata))
    return templates


def get_template(name: str) -> Optional[Template]:
    """Retrieves a template by its name."""
    for template in discover_templates():
        if template.name == name:
            return template
    return None


def list_templates() -> List[Dict[str, Any]]:
    """Lists available templates with their metadata."""
    return [
        {"name": t.name, "description": t.metadata.get("description", "No description provided")}
        for t in discover_templates()
    ]
