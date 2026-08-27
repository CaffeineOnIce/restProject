#!/usr/bin/env python3
import os, time, json, logging
from supabase import create_client
from dotenv import load_dotenv
from fetch_temphum import handle_temp_hum
from fetch_gas import handle_gas
from collect_temphum import collect_temphum
from collect_gas import collect_gas

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

load_dotenv(".env")
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
POLL_INTERVAL = int(os.getenv("SCRIPT_POLL_INTERVAL", 2))

def process_single_job(table, handler, field_map):
    """Process a single-fetch job (duration IS NULL)."""
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
    
    result = handler()
    if result.get("status") == "completed":
        payload = {"status": "completed", "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ")}
        payload.update({k: result[v] for k, v in field_map.items()})
        supabase.table(table).update(payload).eq("id", job["id"]).execute()
    else:
        supabase.table(table).update({
            "status": "error",
            "error_msg": result.get("error_msg", "Handler failed"),
            "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ")
        }).eq("id", job["id"]).execute()

def process_collection_job(table, collector, field_map):
    """Process a range-collection job (duration NOT NULL)."""
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
    
    result = collector(duration, interval)
    if result.get("samples"):
        supabase.table(table).update({
            "status": "completed",
            "result_data": json.dumps(result),
            "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ")
        }).eq("id", job["id"]).execute()
    else:
        supabase.table(table).update({
            "status": "error",
            "error_msg": "No valid samples collected",
            "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ")
        }).eq("id", job["id"]).execute()

def main_loop():
    logger.info("🌉 Bridge active. Polling Supabase...")
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
