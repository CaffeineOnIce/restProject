#!/usr/bin/env python3
import os, time, json, logging
from config import supabase, ESP32_URL
from fetch_temphum import handle_temp_hum
from fetch_gas import handle_gas
from collect_temphum import collect_temphum
from collect_gas import collect_gas

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

POLL_INTERVAL = int(os.getenv("SCRIPT_POLL_INTERVAL", 2))


def process_single_job(table, endpoint_handler, field_map):
    # FIXED: Use "null" string for PostgREST NULL check
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

    result = endpoint_handler()
    if result["status"] == "completed":
        payload = {
            "status": "completed",
            "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        payload.update({k: result[v] for k, v in field_map.items()})
        supabase.table(table).update(payload).eq("id", job["id"]).execute()
    else:
        supabase.table(table).update(
            {
                "status": "error",
                "error_msg": result.get("error_msg", "Sensor failed"),
                "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
        ).eq("id", job["id"]).execute()


def process_collection_job(table, collector_func, field_map):
    # FIXED: Use "null" string for PostgREST NOT NULL check
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

    supabase.table(table).update({"status": "processing"}).eq("id", job["id"]).execute()
    result = collector_func(duration, interval)

    if result["samples"]:
        supabase.table(table).update(
            {
                "status": "completed",
                "result_data": json.dumps(result),
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
    th_map = {"temp": "temp", "hum": "hum"}
    gas_map = {"gas": "gas"}

    while True:
        process_single_job("temphum", handle_temp_hum, th_map)
        process_single_job("gasval", handle_gas, gas_map)
        process_collection_job("temphum", collect_temphum, th_map)
        process_collection_job("gasval", collect_gas, gas_map)
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main_loop()
