import requests
from datetime import datetime, timezone, timedelta
from config import ESP32_URL, supabase

IST = timezone(timedelta(hours=5, minutes=30))


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
            now = datetime.now(IST).strftime("%Y-%m-%dT%H:%M:%S")
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
            now = datetime.now(IST).strftime("%Y-%m-%dT%H:%M:%S")
            error_result = {
                "status": "error",
                "error_msg": "Invalid sensor data format",
                "completed_at": now,
            }
            supabase.table("temphum").insert(error_result).execute()
            return {"temp": None, "hum": None, "status": "error"}
    except Exception as e:
        now = datetime.now(IST).strftime("%Y-%m-%dT%H:%M:%S")
        error_result = {"status": "error", "error_msg": str(e), "completed_at": now}
        supabase.table("temphum").insert(error_result).execute()
        return {"temp": None, "hum": None, "status": "error"}
