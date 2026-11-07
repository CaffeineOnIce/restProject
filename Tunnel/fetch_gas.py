import time
import requests
from datetime import datetime, timezone, timedelta
from config import ESP32_URL, supabase

# Define Indian Standard Time (UTC + 5:30)
IST = timezone(timedelta(hours=5, minutes=30))


def now_ms():
    """Wall-clock time in epoch milliseconds (UTC), used for per-hop timing."""
    return time.time() * 1000


def handle_gas():
    timing = {"t_esp_start": now_ms()}
    try:
        resp = requests.get(f"{ESP32_URL}/gas", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        timing["t_esp_end"] = now_ms()

        if "gas" in data and isinstance(data["gas"], (int, float)):
            now = datetime.now(IST).isoformat(timespec="seconds")
            result = {
                "status": "completed",
                "gas": round(data["gas"], 2),
                "completed_at": now,
            }
            supabase.table("gasval").insert(result).execute()
            timing["t_db_done"] = now_ms()
            return {
                "gas": result["gas"],
                "status": result["status"],
                "timing": timing,
            }
        else:
            now = datetime.now(IST).isoformat(timespec="seconds")
            error_result = {
                "status": "error",
                "error_msg": "Invalid sensor data format",
                "completed_at": now,
            }
            supabase.table("gasval").insert(error_result).execute()
            timing["t_db_done"] = now_ms()
            return {"gas": None, "status": "error", "timing": timing}
    except Exception as e:
        timing.setdefault("t_esp_end", now_ms())
        now = datetime.now(IST).isoformat(timespec="seconds")
        error_result = {
            "status": "error",
            "error_msg": str(e),
            "completed_at": now,
        }
        supabase.table("gasval").insert(error_result).execute()
        timing["t_db_done"] = now_ms()
        return {"gas": None, "status": "error", "timing": timing}
