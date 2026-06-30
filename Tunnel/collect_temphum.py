import time
from datetime import datetime, timezone, timedelta
from fetch_temphum import handle_temp_hum

# Define Indian Standard Time (UTC + 5:30)
IST = timezone(timedelta(hours=5, minutes=30))


def collect_temphum(duration, interval):
    # Calculate exact number of samples needed
    num_samples = int(duration / interval)
    samples = []

    # Use a for loop to guarantee exact sample count
    for i in range(num_samples):
        result = handle_temp_hum()
        # Use IST instead of UTC
        ts = datetime.now(IST).strftime("%H:%M:%S")

        if result["status"] == "completed":
            samples.append(
                {"timestamp": ts, "temp": result["temp"], "hum": result["hum"]}
            )

        # Sleep only if not the last iteration
        if i < num_samples - 1:
            time.sleep(interval)

    return samples
