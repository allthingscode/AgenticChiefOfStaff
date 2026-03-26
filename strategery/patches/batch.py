"""
Strategic Batch Loader: Modular Folder-Based Cron Jobs.
Strategic Batch Patch: Implements modular cron task loading and silent delivery.
Scans the configured workspace cron directory for Markdown files and converts them to CronJobs.
"""

import re
from datetime import datetime
from pathlib import Path
from typing import List

import yaml
from loguru import logger

# Import nanobot cron types for conversion
try:
    from nanobot.cron.types import CronJob, CronJobState, CronPayload, CronSchedule
except ImportError:
    # Fallback for static analysis
    CronJob = CronSchedule = CronPayload = CronJobState = None

def parse_modular_job_file(file_path: Path) -> CronJob | None:
    """Parses a single Markdown file into a CronJob."""
    try:
        content = file_path.read_text(encoding="utf-8-sig")

        # Simple front-matter extraction (--- metadata ---)
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)
        if not match:
            logger.warning(f"Batch: File {file_path.name} missing front-matter metadata. Skipping.")
            return None

        metadata_str = match.group(1)
        task_body = match.group(2).strip()

        metadata = yaml.safe_load(metadata_str)
        if not metadata or not isinstance(metadata, dict):
            return None

        # Required fields
        job_id = str(metadata.get("id", file_path.stem))
        name = metadata.get("name", job_id)
        schedule_str = metadata.get("schedule", "every(24h)")
        specialist = metadata.get("specialist", "researcher")

        # Parse schedule: cron(expr) or every(duration) or at(ms)
        schedule = None
        if schedule_str.startswith("cron("):
            expr = schedule_str[5:-1]
            schedule = CronSchedule(kind="cron", expr=expr)
        elif schedule_str.startswith("every("):
            duration = schedule_str[6:-1]
            # Convert simple durations (1h, 1d) to ms
            ms = 0
            if duration.endswith("h"): ms = int(duration[:-1]) * 3600000
            elif duration.endswith("d"): ms = int(duration[:-1]) * 86400000
            elif duration.endswith("m"): ms = int(duration[:-1]) * 60000
            else: ms = int(duration) # raw ms
            schedule = CronSchedule(kind="every", every_ms=ms)
        elif schedule_str.startswith("at("):
            at_ms = int(schedule_str[3:-1])
            schedule = CronSchedule(kind="at", at_ms=at_ms)

        if not schedule:
            logger.error(f"Batch: Invalid schedule format in {file_path.name}: {schedule_str}")
            return None

        # Construct payload with Specialist trigger
        # This message will be handled by the Main Agent and delegated via spawn
        message_body = f"Spawn a {specialist} specialist to perform the following batch task:\n\n{task_body}"

        # MANDATE: If deliver is 'silent', we prefix the message to allow cron_logic to suppress routing
        deliver_pref = metadata.get("deliver", False)
        if deliver_pref == "silent":
            message = f"[SILENT]\n{message_body}"
            deliver = False # Standard delivery off, silent logic on
        else:
            message = message_body
            deliver = bool(deliver_pref)

        payload = CronPayload(
            kind="agent_turn",
            message=message,
            deliver=deliver,
            channel=metadata.get("channel"),
            to=metadata.get("to")
        )
        # MANDATE (BUG-072): Prevent immediate redundant triggering on fresh boot.
        # If we use file ctime, and ctime + 24h is in the past, it triggers instantly.
        # We use current time as created_at for modular jobs to ensure the timer starts NOW.
        now_ms = int(datetime.now().timestamp() * 1000)

        return CronJob(
            id=f"batch_{job_id}", # Prefix to avoid collisions with jobs.json
            name=f"[Batch] {name}",
            enabled=metadata.get("enabled", True),
            schedule=schedule,
            payload=payload,
            state=CronJobState(),
            created_at_ms=now_ms,
            updated_at_ms=int(file_path.stat().st_mtime * 1000)
        )

    except Exception as e:
        logger.error(f"Batch: Error parsing {file_path.name}: {e}")
        return None

def strategic_load_modular_jobs(storage_root: Path) -> List[CronJob]:
    """Scans the cron items directory and returns a list of CronJobs."""
    items_dir = storage_root / "workspace" / "cron" / "items"
    if not items_dir.exists():
        try:
            items_dir.mkdir(parents=True, exist_ok=True)
            # Create a README to explain the system
            readme = items_dir / "README.md"
            readme.write_text("# Modular Batch Jobs\n\nAdd Markdown files here with YAML front-matter to schedule nightly tasks.")
        except: pass
        return []

    jobs = []
    for file in items_dir.glob("*.md"):
        if file.name.lower() == "readme.md": continue
        if job := parse_modular_job_file(file):
            jobs.append(job)

    if jobs:
        logger.info(f"Batch: Loaded {len(jobs)} modular jobs from {items_dir}")

    return jobs

def strategic_resolve_job_channel(storage_root: Path) -> tuple[str, str]:
    """
    Attempts to find a routable channel and chat_id for background jobs.
    Logic:
    1. Scan sessions for the most recently updated non-internal channel.
    2. Fallback to 'cli', 'direct'.
    """
    from nanobot.session.manager import SessionManager
    try:
        session_manager = SessionManager(storage_root / "workspace")
        # Get list of sessions sorted by mtime (newest first)
        sessions = session_manager.list_sessions()

        for item in sessions:
            key = item.get("key") or ""
            if ":" not in key: continue

            channel, chat_id = key.split(":", 1)
            # Skip internal channels
            if channel in {"cli", "system", "cron", "heartbeat"}:
                continue

            # If we found a real channel session, use it
            if channel and chat_id:
                return channel, chat_id
    except Exception as e:
        logger.warning(f"Batch: Error resolving job channel: {e}")

    return "cli", "direct"
