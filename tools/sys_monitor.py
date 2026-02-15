import psutil

def get_system_metrics() -> str:
    """
    Retrieves live system telemetry from the local Windows machine, including battery status 
    and the top 15 most memory-intensive processes. 
    
    Call this tool WHENEVER the user asks about system performance, lag, optimization, 
    or what applications they should close.
    """
    battery = psutil.sensors_battery()
    batt_pct = battery.percent if battery else "N/A"
    plugged = "Plugged In" if battery and battery.power_plugged else "On Battery"

    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'memory_percent']):
        try:
            processes.append(proc.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
            
    top_mem = sorted(processes, key=lambda p: p['memory_percent'] or 0, reverse=True)[:15]
    mem_list = "\n".join([f"- {p['name']} (PID {p['pid']}): {(p['memory_percent'] or 0):.1f}% RAM" for p in top_mem])
    
    # We return the raw string. Gemini will read this and format it for the user.
    return f"Battery: {batt_pct}% ({plugged})\nTop 15 RAM Processes:\n{mem_list}"