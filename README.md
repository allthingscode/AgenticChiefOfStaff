<div align="center">
  <img src="nanobot_logo.png" width="200" alt="Nanobot Logo">
  <h1>🦅 Nanobot: Strategic Edition</h1>
  <p>A high-reliability agent system optimized for executive briefings and persistent memory.</p>

  ### [🚀 See What Makes This Edition Special →](./strategery/STRATEGIC_EDITION.md)
</div>

---

### 1. Requirements
- Python 3.10+
- [uv](https://github.com/astral-sh/uv) (for dependency management)
- Node.js (for some MCP servers)

### 2. Configuration
Create a `config.json` in `~/.nanobot/` and define your `strategic_edition` settings:
```json
{
  "strategic_edition": {
    "user_email": "your-email@example.com",
    "storage_root": "D:/Nanobot_Storage",
    "app_root": "C:/Path/To/Nanobot"
  }
}
```

### 3. Launching
Use the provided PowerShell script for the best experience on Windows:
```powershell
.\start_strategic_nanobot.ps1
```

## 🧪 Testing
Run the test suite to verify your environment:
```powershell
pytest tests/unit/test_strategic_main.py
```

## 📜 License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
