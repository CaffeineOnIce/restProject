import time
from datetime import datetime, timezone, timedelta
from fetch_gas import handle_gas

# Define Indian Standard Time (UTC + 5:30)
IST = timezone(timedelta(hours=5, minutes=30))


def collect_gas(duration, interval):
    # Calculate exact number of samples needed
    num_samples = int(duration / interval)
    samples = []

    # Use a for loop to guarantee exact sample count
    for i in range(num_samples):
        result = handle_gas()
        # Use IST instead of UTC
        ts = datetime.now(IST).strftime("%H:%M:%S")

        if result["status"] == "completed":
            samples.append({"timestamp": ts, "gas": result["gas"]})

        # Sleep only if not the last iteration
        if i < num_samples - 1:
            time.sleep(interval)

    return samples
