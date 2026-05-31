import time
from datetime import datetime, timezone
from fetch_temphum import handle_temp_hum


def collect_temp(duration, interval):
    end_time = time.time() + duration
    samples = []
    while time.time() < end_time:
        result = handle_temp_hum()
        if result["status"] == "completed":
            samples.append(
                {
                    "timestamp": datetime.now(timezone.utc).strftime("%H:%M:%S"),
                    "value": result["temp"],
                }
            )
        remaining = end_time - time.time()
        if remaining > interval:
            time.sleep(interval)
    return samples
