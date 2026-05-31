import time
from datetime import datetime, timezone
from fetch_temphum import handle_temp_hum


def collect_hum(duration, interval):
    end_time = time.time() + duration
    samples = []
    count = 0

    while time.time() < end_time:
        result = handle_temp_hum()
        timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S")

        if result["status"] == "completed":
            samples.append({"timestamp": timestamp, "value": result["hum"]})
            count += 1

        time.sleep(interval)

    return samples
