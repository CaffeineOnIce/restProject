import requests
from datetime import datetime, timezone
from config import ESP32_URL, supabase


def handle_gas():
    """Fetch ONE gas reading from ESP32 and save to Supabase."""
    try:
        resp = requests.get(f"{ESP32_URL}/gas", timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if "gas" in data and isinstance(data["gas"], (int, float)):
            now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            result = {
                "status": "completed",
                "gas": round(data["gas"], 2),
                "completed_at": now,
            }
            supabase.table("gasval").insert(result).execute()
            return {
                "gas": result["gas"],
                "status": result["status"],
            }
        else:
            now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            error_result = {
                "status": "error",
                "error_msg": "Invalid sensor data format",
                "completed_at": now,
            }
            supabase.table("gasval").insert(error_result).execute()
            return {"gas": None, "status": "error"}
    except Exception as e:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        error_result = {
            "status": "error",
            "error_msg": str(e),
            "completed_at": now,
        }
        supabase.table("gasval").insert(error_result).execute()
        return {"gas": None, "status": "error"}
