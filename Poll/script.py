#!/usr/bin/env python3
import os, time, requests, json, logging
from supabase import create_client
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

load_dotenv(".env")
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
ESP32_URL = os.getenv("ESP32_URL", "http://esp32.local")
POLL_INTERVAL = int(os.getenv("SCRIPT_POLL_INTERVAL", 2))


def fetch_single(endpoint):
    for attempt in range(3):
        try:
            resp = requests.get(f"{ESP32_URL}{endpoint}", timeout=5)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning(f"Attempt {attempt+1} failed: {e}")
            time.sleep(1)
    return None


def process_single_job(table, endpoint, field_map):
    pending = (
        supabase.table(table)
        .select("*")
        .eq("status", "pending")
        .filter("duration", "is", "null")
        .order("created_at")
        .limit(1)
        .execute()
        .data
    )
    if not pending:
        return
    job = pending[0]
    supabase.table(table).update({"status": "processing"}).eq("id", job["id"]).execute()
    data = fetch_single(endpoint)
    if isinstance(data, dict) and "error" not in data:
        payload = {
            "status": "completed",
            "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        payload.update({k: data[v] for k, v in field_map.items()})
        supabase.table(table).update(payload).eq("id", job["id"]).execute()
    else:
        supabase.table(table).update(
            {
                "status": "error",
                "error_msg": "Sensor timeout",
                "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
        ).eq("id", job["id"]).execute()


def process_collection_job(table, endpoint, field_map):
    pending = (
        supabase.table(table)
        .select("*")
        .eq("status", "pending")
        .filter("duration", "not.is", "null")
        .order("created_at")
        .limit(1)
        .execute()
        .data
    )
    if not pending:
        return
    job = pending[0]
    duration = job.get("duration", 30)
    interval = max(1, job.get("interval", 5))
    num_samples = int(duration / interval)
    supabase.table(table).update({"status": "processing"}).eq("id", job["id"]).execute()
    samples = []
    for i in range(num_samples):
        data = fetch_single(endpoint)
        if isinstance(data, dict) and "error" not in data:
            sample = {"timestamp": time.strftime("%H:%M:%S")}
            sample.update({k: data[v] for k, v in field_map.items()})
            samples.append(sample)
        if i < num_samples - 1:
            time.sleep(interval)
    if samples:
        stats = {}
        for col in field_map.keys():
            values = [s[col] for s in samples]
            stats[col] = {
                "min": min(values),
                "max": max(values),
                "avg": sum(values) / len(values),
            }
        supabase.table(table).update(
            {
                "status": "completed",
                "result_data": json.dumps({"samples": samples, "stats": stats}),
                "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
        ).eq("id", job["id"]).execute()
    else:
        supabase.table(table).update(
            {
                "status": "error",
                "error_msg": "All samples failed",
                "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
        ).eq("id", job["id"]).execute()


def main_loop():
    logger.info("Cloud bridge active. Polling Supabase...")
    th_map = {"temp": "temperature", "hum": "humidity"}
    gas_map = {"gas": "gas"}
    while True:
        process_single_job("temphum", "/temphum", th_map)
        process_single_job("gasval", "/gas", gas_map)
        process_collection_job("temphum", "/temphum", th_map)
        process_collection_job("gasval", "/gas", gas_map)
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main_loop()
