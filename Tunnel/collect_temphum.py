import time
from datetime import datetime, timezone
from fetch_temphum import handle_temp_hum


def collect_temphum(duration, interval):
    end_time = time.time() + duration
    samples = []
    while time.time() < end_time:
        result = handle_temp_hum()
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        if result["status"] == "completed":
            samples.append(
                {"timestamp": ts, "temp": result["temp"], "hum": result["hum"]}
            )
        time.sleep(interval)
    return samples
