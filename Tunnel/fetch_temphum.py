import requests
from datetime import datetime, timezone
from config import ESP32_URL, supabase


def handle_temp_hum():
    """Fetch ONE temperature+humidity reading from ESP32 and save to Supabase."""
    try:
        resp = requests.get(f"{ESP32_URL}/temphum", timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if (
            "temperature" in data
            and "humidity" in data
            and isinstance(data["temperature"], (int, float))
            and isinstance(data["humidity"], (int, float))
        ):
            now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            result = {
                "status": "completed",
                "temp": round(data["temperature"], 2),
                "hum": round(data["humidity"], 2),
                "completed_at": now,
            }
            supabase.table("temphum").insert(result).execute()
            return {
                "temp": result["temp"],
                "hum": result["hum"],
                "status": result["status"],
            }
        else:
            now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            error_result = {
                "status": "error",
                "error_msg": "Invalid sensor data format",
                "completed_at": now,
            }
            supabase.table("temphum").insert(error_result).execute()
            return {"temp": None, "hum": None, "status": "error"}
    except Exception as e:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        error_result = {
            "status": "error",
            "error_msg": str(e),
            "completed_at": now,
        }
        supabase.table("temphum").insert(error_result).execute()
        return {"temp": None, "hum": None, "status": "error"}
