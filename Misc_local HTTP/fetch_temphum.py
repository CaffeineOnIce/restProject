import csv
import os
import requests
from datetime import datetime, timezone, timedelta
from config import ESP32_URL

# Define Indian Standard Time (UTC + 5:30)
IST = timezone(timedelta(hours=5, minutes=30))
CSV_FILE = "temphum.csv"


def save_to_csv(data):
    file_exists = os.path.isfile(CSV_FILE)
    with open(CSV_FILE, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["completed_at", "status", "temp", "hum", "error_msg"]
        )
        if not file_exists:
            writer.writeheader()
        writer.writerow(data)


def handle_temp_hum():
    """Fetch ONE temperature+humidity reading from ESP32 and save to CSV."""
    try:
        resp = requests.get(f"{ESP32_URL}/temphum", timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if (
            "temp" in data
            and "hum" in data
            and isinstance(data["temp"], (int, float))
            and isinstance(data["hum"], (int, float))
        ):
            now = datetime.now(IST).strftime("%Y-%m-%dT%H:%M:%S")
            result = {
                "completed_at": now,
                "status": "completed",
                "temp": round(data["temp"], 2),
                "hum": round(data["hum"], 2),
                "error_msg": "",
            }
            save_to_csv(result)
            return {
                "temp": result["temp"],
                "hum": result["hum"],
                "status": result["status"],
            }
        else:
            now = datetime.now(IST).strftime("%Y-%m-%dT%H:%M:%S")
            error_result = {
                "completed_at": now,
                "status": "error",
                "temp": None,
                "hum": None,
                "error_msg": "Invalid sensor data format",
            }
            save_to_csv(error_result)
            return {"temp": None, "hum": None, "status": "error"}
    except Exception as e:
        now = datetime.now(IST).strftime("%Y-%m-%dT%H:%M:%S")
        error_result = {
            "completed_at": now,
            "status": "error",
            "temp": None,
            "hum": None,
            "error_msg": str(e),
        }
        save_to_csv(error_result)
        return {"temp": None, "hum": None, "status": "error"}
