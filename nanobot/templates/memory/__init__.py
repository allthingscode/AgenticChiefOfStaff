"""
This module provides the core memory management for nanobot.

It defines the `Memory` class, which is responsible for storing, retrieving,
and managing various types of data used by the nanobot. This includes:
- Conversation history
- User preferences
- System configurations
- Knowledge base entries
"""

import json
import os
from datetime import datetime

class Memory:
    """
    Manages the storage and retrieval of nanobot's memory.

    Memory can include conversation history, user preferences, system configurations,
    and a knowledge base. It supports persistence to a file system.
    """

    def __init__(self, memory_file="nanobot_memory.json"):
        """
        Initializes the Memory manager.

        Args:
            memory_file (str): The path to the JSON file used for persistent storage.
        """
        self.memory_file = memory_file
        self.data = self._load_memory()

    def _load_memory(self):
        """
        Loads memory from the specified JSON file.

        If the file does not exist or is empty, initializes with a default structure.

        Returns:
            dict: The loaded memory data.
        """
        if os.path.exists(self.memory_file) and os.path.getsize(self.memory_file) > 0:
            try:
                with open(self.memory_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                print(f"Warning: Memory file '{self.memory_file}' is corrupted. Initializing new memory.")
                return self._default_memory_structure()
        return self._default_memory_structure()

    def _save_memory(self):
        """
        Saves the current memory data to the JSON file.
        """
        with open(self.memory_file, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=4)

    def _default_memory_structure(self):
        """
        Returns the default structure for new memory.
        """
        return {
            "conversation_history": [],
            "user_preferences": {},
            "system_config": {},
            "knowledge_base": {},
            "last_updated": datetime.now().isoformat()
        }

    def add_to_history(self, role, message):
        """
        Adds a message to the conversation history.

        Args:
            role (str): The role of the speaker (e.g., "user", "nanobot", "system").
            message (str): The content of the message.
        """
        timestamp = datetime.now().isoformat()
        self.data["conversation_history"].append({"timestamp": timestamp, "role": role, "message": message})
        self.data["last_updated"] = timestamp
        self._save_memory()

    def get_history(self, limit=None):
        """
        Retrieves the conversation history.

        Args:
            limit (int, optional): The maximum number of recent messages to retrieve.
                                   If None, all history is returned.

        Returns:
            list: A list of historical messages.
        """
        if limit is None:
            return self.data["conversation_history"]
        return self.data["conversation_history"][-limit:]

    def clear_history(self):
        """
        Clears the entire conversation history.
        """
        self.data["conversation_history"] = []
        self.data["last_updated"] = datetime.now().isoformat()
        self._save_memory()

    def set_user_preference(self, key, value):
        """
        Sets a user preference.

        Args:
            key (str): The key for the preference.
            value: The value of the preference.
        """
        self.data["user_preferences"][key] = value
        self.data["last_updated"] = datetime.now().isoformat()
        self._save_memory()

    def get_user_preference(self, key, default=None):
        """
        Retrieves a user preference.

        Args:
            key (str): The key for the preference.
            default: The default value to return if the key is not found.

        Returns:
            The value of the preference, or the default value if not found.
        """
        return self.data["user_preferences"].get(key, default)

    def set_system_config(self, key, value):
        """
        Sets a system configuration.

        Args:
            key (str): The key for the configuration.
            value: The value of the configuration.
        """
        self.data["system_config"][key] = value
        self.data["last_updated"] = datetime.now().isoformat()
        self._save_memory()

    def get_system_config(self, key, default=None):
        """
        Retrieves a system configuration.

        Args:
            key (str): The key for the configuration.
            default: The default value to return if the key is not found.

        Returns:
            The value of the configuration, or the default value if not found.
        """
        return self.data["system_config"].get(key, default)

    def add_knowledge_entry(self, key, value):
        """
        Adds or updates an entry in the knowledge base.

        Args:
            key (str): The key for the knowledge entry.
            value: The content of the knowledge entry.
        """
        self.data["knowledge_base"][key] = value
        self.data["last_updated"] = datetime.now().isoformat()
        self._save_memory()

    def get_knowledge_entry(self, key, default=None):
        """
        Retrieves an entry from the knowledge base.

        Args:
            key (str): The key for the knowledge entry.
            default: The default value to return if the key is not found.

        Returns:
            The content of the knowledge entry, or the default value if not found.
        """
        return self.data["knowledge_base"].get(key, default)

    def delete_knowledge_entry(self, key):
        """
        Deletes an entry from the knowledge base.

        Args:
            key (str): The key of the entry to delete.

        Returns:
            bool: True if the entry was deleted, False otherwise.
        """
        if key in self.data["knowledge_base"]:
            del self.data["knowledge_base"][key]
            self.data["last_updated"] = datetime.now().isoformat()
            self._save_memory()
            return True
        return False

    def get_all_memory(self):
        """
        Returns all stored memory data.

        Returns:
            dict: A copy of the entire memory data.
        """
        return self.data.copy()

    def reset_memory(self):
        """
        Resets all memory to its default state.
        """
        self.data = self._default_memory_structure()
        self._save_memory()
