import threading
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


def run_background_task(task_id, func, duration, interval):
    """Runs the collection function in a background thread."""
    try:
        result = func(duration, interval)
        with tasks_lock:
            tasks[task_id] = {"status": "completed", "result": result}
    except Exception as e:
        with tasks_lock:
            tasks[task_id] = {"status": "error", "error": str(e)}


@app.route("/temphum", methods=["GET"])
def api_temphum():
    return jsonify(handle_temp_hum())


@app.route("/gas", methods=["GET"])
def api_gas():
    return jsonify(handle_gas())


@app.route("/health")
def health():
    return jsonify({"status": "ok", "timestamp": datetime.now().isoformat()})


@app.route("/ctemphum", methods=["POST"])
def api_collect_temphum():
    try:
        data = request.get_json()
        if not data or "duration" not in data or "interval" not in data:
            return jsonify({"error": "Missing duration or interval"}), 400

        duration = int(data["duration"])
        interval = int(data["interval"])

        if duration <= 0 or interval <= 0:
            return jsonify({"error": "Invalid duration/interval"}), 400

        task_id = str(uuid.uuid4())
        with tasks_lock:
            tasks[task_id] = {"status": "running", "result": None}

        thread = threading.Thread(
            target=run_background_task,
            args=(task_id, collect_temphum, duration, interval),
        )
        thread.daemon = True
        thread.start()

        return jsonify({"status": "started", "task_id": task_id}), 202

    except ValueError:
        return jsonify({"error": "Duration/interval must be integers"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/cgas", methods=["POST"])
def api_collect_gas():
    try:
        data = request.get_json()
        if not data or "duration" not in data or "interval" not in data:
            return jsonify({"error": "Missing duration or interval"}), 400

        duration = int(data["duration"])
        interval = int(data["interval"])

        if duration <= 0 or interval <= 0:
            return jsonify({"error": "Invalid duration/interval"}), 400

        task_id = str(uuid.uuid4())
        with tasks_lock:
            tasks[task_id] = {"status": "running", "result": None}

        thread = threading.Thread(
            target=run_background_task, args=(task_id, collect_gas, duration, interval)
        )
        thread.daemon = True
        thread.start()

        return jsonify({"status": "started", "task_id": task_id}), 202

    except ValueError:
        return jsonify({"error": "Duration/interval must be integers"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/task/<task_id>", methods=["GET"])
def get_task_status(task_id):
    with tasks_lock:
        task = tasks.get(task_id)
        if not task:
            return jsonify({"error": "Task not found"}), 404
        return jsonify(task)


if __name__ == "__main__":
    print("Server active. Waiting for requests on port 52471...")
    app.run(host="0.0.0.0", port=52471, debug=False, threaded=True)
