import time
from datetime import datetime, timezone, timedelta
from fetch_gas import handle_gas

IST = timezone(timedelta(hours=5, minutes=30))

def collect_gas(duration, interval):
    num_samples = int(duration / interval)
    samples = []

    for i in range(num_samples):
        result = handle_gas()
        ts = datetime.now(IST).strftime("%H:%M:%S")

        if result["status"] == "completed":
            samples.append({"timestamp": ts, "gas": result["gas"]})

        if i < num_samples - 1:
            time.sleep(interval)

    stats = {}
    if samples:
        values = [s["gas"] for s in samples]
        stats["gas"] = {
            "min": min(values),
            "max": max(values),
            "avg": sum(values) / len(values),
        }

    return {"samples": samples, "stats": stats}
