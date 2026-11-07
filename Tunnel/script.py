import threading
import time
import uuid
from flask import Flask, jsonify, request
from datetime import datetime
from fetch_temphum import handle_temp_hum
from fetch_gas import handle_gas
from collect_temphum import collect_temphum
from collect_gas import collect_gas

app = Flask(__name__)
tasks = {}
tasks_lock = threading.Lock()


def now_ms():
    """Wall-clock time in epoch milliseconds (UTC), used for per-hop timing."""
    return time.time() * 1000


def run_background_task(task_id, func, duration, interval):
    """Runs the collection function in a background thread."""
    try:
        result = func(duration, interval)
        with tasks_lock:
            tasks[task_id] = {"status": "completed", "result": result}
    except Exception as e:
        with tasks_lock:
            tasks[task_id] = {"status": "error", "error": str(e)}


def start_collection(func):
    """Shared handler for /cth and /cgas (same request/response format as the Poll API)."""
    try:
        data = request.get_json(silent=True) or {}
        duration = int(data.get("duration", 30))
        interval = int(data.get("interval", 5))
        if duration <= 0 or interval <= 0:
            return jsonify({"error": "Invalid duration/interval"}), 400

        task_id = str(uuid.uuid4())
        with tasks_lock:
            tasks[task_id] = {"status": "running", "result": None}

        thread = threading.Thread(
            target=run_background_task, args=(task_id, func, duration, interval)
        )
        thread.daemon = True
        thread.start()
        return jsonify({"status": "started", "task_id": task_id}), 202

    except ValueError:
        return jsonify({"error": "Duration/interval must be integers"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Same routes, methods and response format as the Poll (Render) API.
@app.route("/th", methods=["POST"])
def get_temp_hum():
    t_pi_rx = now_ms()
    result = handle_temp_hum()
    timing = result.get("timing", {})
    timing["t_pi_rx"] = t_pi_rx
    if result["status"] == "completed":
        timing["t_pi_tx"] = now_ms()
        return jsonify({"temp": result["temp"], "hum": result["hum"], "timing": timing}), 200
    timing["t_pi_tx"] = now_ms()
    return jsonify({"error": result.get("error_msg", "Sensor failed"), "timing": timing}), 500


@app.route("/gas", methods=["POST"])
def get_gas():
    t_pi_rx = now_ms()
    result = handle_gas()
    timing = result.get("timing", {})
    timing["t_pi_rx"] = t_pi_rx
    if result["status"] == "completed":
        timing["t_pi_tx"] = now_ms()
        return jsonify({"gas": result["gas"], "timing": timing}), 200
    timing["t_pi_tx"] = now_ms()
    return jsonify({"error": result.get("error_msg", "Sensor failed"), "timing": timing}), 500


@app.route("/cth", methods=["POST"])
def collect_th():
    return start_collection(collect_temphum)


@app.route("/cgas", methods=["POST"])
def collect_gas_route():
    return start_collection(collect_gas)


@app.route("/task/<task_id>", methods=["GET"])
def get_task(task_id):
    with tasks_lock:
        task = tasks.get(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404
    if task["status"] == "completed":
        return jsonify({"status": "completed", "result": task["result"]}), 200
    if task["status"] == "error":
        return jsonify({"status": "error", "error": task.get("error", "Failed")}), 500
    return jsonify({"status": "running"}), 202


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "timestamp": datetime.now().isoformat()})


if __name__ == "__main__":
    print("Server active. Waiting for requests on port 52471...")
    app.run(host="0.0.0.0", port=52471, debug=False, threaded=True)
