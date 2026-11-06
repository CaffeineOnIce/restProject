#!/usr/bin/env python3
import os, time, json, logging
from datetime import datetime, timezone
from config import supabase, ESP32_URL
from fetch_temphum import handle_temp_hum
from fetch_gas import handle_gas
from collect_temphum import collect_temphum
from collect_gas import collect_gas

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

POLL_INTERVAL = float(os.getenv("SCRIPT_POLL_INTERVAL", 2))


def now_ms():
    """Wall-clock time in epoch milliseconds (UTC), used for per-hop timing."""
    return time.time() * 1000


def utc_now():
    """ISO-8601 UTC timestamp with offset, for timestamptz columns."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


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
    t_pi_seen = now_ms()
    job = pending[0]
    supabase.table(table).update({"status": "processing"}).eq("id", job["id"]).execute()

    result = endpoint_handler()
    timing = result.get("timing", {})
    timing_cols = {
        "t_pi_seen": t_pi_seen,
        "t_esp_start": timing.get("t_esp_start"),
        "t_esp_end": timing.get("t_esp_end"),
        "t_db_done": timing.get("t_db_done"),
    }
    if result["status"] == "completed":
        payload = {
            "status": "completed",
            "completed_at": utc_now(),
        }
        payload.update({k: result[v] for k, v in field_map.items()})
        payload.update(timing_cols)
        payload["t_pi_done"] = now_ms()
        supabase.table(table).update(payload).eq("id", job["id"]).execute()
    else:
        payload = {
            "status": "error",
            "error_msg": result.get("error_msg", "Sensor failed"),
            "completed_at": utc_now(),
        }
        payload.update(timing_cols)
        payload["t_pi_done"] = now_ms()
        supabase.table(table).update(payload).eq("id", job["id"]).execute()


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
                "completed_at": utc_now(),
            }
        ).eq("id", job["id"]).execute()
    else:
        supabase.table(table).update(
            {
                "status": "error",
                "error_msg": "All samples failed",
                "completed_at": utc_now(),
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