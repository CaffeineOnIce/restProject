#!/usr/bin/env python3
import os, time, uuid
from flask import Flask, jsonify, request
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
supabase = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))

POLL_INTERVAL = 1
TIMEOUT = 25

# --- Single Fetch ---
@app.route("/th", methods=["POST"])
def get_temp_hum():
    res = supabase.table("temphum").insert({"status": "pending"}).execute()
    job_id = res.data[0]["id"]
    for _ in range(TIMEOUT):
        time.sleep(POLL_INTERVAL)
        result = supabase.table("temphum").select("*").eq("id", job_id).execute().data[0]
        if result["status"] == "completed":
            return jsonify({"temp": result["temp"], "hum": result["hum"]}), 200
        if result["status"] == "error":
            return jsonify({"error": result["error_msg"]}), 500
    supabase.table("temphum").update({"status": "error", "error_msg": "Bridge Timeout"}).eq("id", job_id).execute()
    return jsonify({"error": "ESP32 did not respond in time"}), 504

@app.route("/gas", methods=["POST"])
def get_gas():
    res = supabase.table("gasval").insert({"status": "pending"}).execute()
    job_id = res.data[0]["id"]
    for _ in range(TIMEOUT):
        time.sleep(POLL_INTERVAL)
        result = supabase.table("gasval").select("*").eq("id", job_id).execute().data[0]
        if result["status"] == "completed":
            return jsonify({"gas": result["gas"]}), 200
        if result["status"] == "error":
            return jsonify({"error": result["error_msg"]}), 500
    supabase.table("gasval").update({"status": "error", "error_msg": "Bridge Timeout"}).eq("id", job_id).execute()
    return jsonify({"error": "ESP32 did not respond in time"}), 504

# --- Range Collection ---
@app.route("/cth", methods=["POST"])
def collect_th():
    data = request.get_json()
    res = supabase.table("temphum").insert({
        "status": "pending", 
        "duration": data.get("duration", 30), 
        "interval": data.get("interval", 5)
    }).execute()
    return jsonify({"status": "started", "task_id": res.data[0]["id"]}), 202

@app.route("/cgas", methods=["POST"])
def collect_gas():
    data = request.get_json()
    res = supabase.table("gasval").insert({
        "status": "pending", 
        "duration": data.get("duration", 30), 
        "interval": data.get("interval", 5)
    }).execute()
    return jsonify({"status": "started", "task_id": res.data[0]["id"]}), 202

@app.route("/task/<task_id>", methods=["GET"])
def get_task(task_id):
    for table in ["temphum", "gasval"]:
        res = supabase.table(table).select("*").eq("id", task_id).execute().data
        if res:
            job = res[0]
            if job["status"] == "completed":
                return jsonify({"status": "completed", "result": job.get("result_data", {})}), 200
            if job["status"] == "error":
                return jsonify({"status": "error", "error": job.get("error_msg", "Failed")}), 500
            return jsonify({"status": "running"}), 202
    return jsonify({"error": "Task not found"}), 404

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "online"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))