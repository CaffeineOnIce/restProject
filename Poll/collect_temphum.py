import time
from datetime import datetime, timezone, timedelta
from fetch_temphum import handle_temp_hum

IST = timezone(timedelta(hours=5, minutes=30))

def collect_temphum(duration, interval):
    """Collect multiple temp/hum samples and return aggregated stats."""
    num_samples = max(1, int(duration / interval))
    samples = []
    
    for i in range(num_samples):
        result = handle_temp_hum()
        ts = datetime.now(IST).strftime("%H:%M:%S")
        if result["status"] == "completed":
            samples.append({"timestamp": ts, "temp": result["temp"], "hum": result["hum"]})
        if i < num_samples - 1:
            time.sleep(interval)
    
    stats = {}
    if samples:
        for col in ["temp", "hum"]:
            values = [s[col] for s in samples if s[col] is not None]
            if values:
                stats[col] = {"min": min(values), "max": max(values), "avg": sum(values) / len(values)}
    
    return {"samples": samples, "stats": stats}
