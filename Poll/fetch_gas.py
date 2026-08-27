
import requests
from datetime import datetime, timezone, timedelta
from config import ESP32_URL, supabase

IST = timezone(timedelta(hours=5, minutes=30))

def handle_gas():
    """Fetch ONE gas reading from ESP32 and save to Supabase."""
    try:
        resp = requests.get(f"{ESP32_URL}/gas", timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if "gas" in data:
            now = datetime.now(IST).strftime("%Y-%m-%dT%H:%M:%S")
            result = {
                "status": "completed",
                "gas": round(data["gas"], 2),
                "completed_at": now,
            }
            supabase.table("gasval").insert(result).execute()
            return {"gas": result["gas"], "status": "completed"}
        else:
            return {"gas": None, "status": "error", "error_msg": "Invalid data"}
    except Exception as e:
        return {"gas": None, "status": "error", "error_msg": str(e)}
