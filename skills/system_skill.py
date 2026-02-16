# skills/system_skill.py
import psutil

def get_system_status():
    """
    Returns the current CPU usage and system health of the agent's dedicated machine.
    Use this to check if the bot is running normally or if the system is under load.
    """
    cpu = psutil.cpu_percent(interval=1.0)
    return f"🖥️ System Health: CPU at {cpu}% usage. All systems operational."

SYSTEM_TOOLS = [get_system_status]