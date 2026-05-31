import time
from datetime import datetime, timezone
from fetch_gas import handle_gas


def collect_gas(duration, interval):
    end_time = time.time() + duration
    samples = []
    while time.time() < end_time:
        result = handle_gas()
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        if result["status"] == "completed":
            samples.append({"timestamp": ts, "gas": result["gas"]})
        time.sleep(interval)
    return samples
