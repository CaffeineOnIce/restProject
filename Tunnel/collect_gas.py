import time
from datetime import datetime, timezone
from fetch_gas import handle_gas


def collect_gas(duration, interval):
    end_time = time.time() + duration
    samples = []
    count = 0

    while time.time() < end_time:
        result = handle_gas()
        timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S")

        if result["status"] == "completed":
            samples.append({"timestamp": timestamp, "value": result["gas"]})
            count += 1

        time.sleep(interval)

    return samples
