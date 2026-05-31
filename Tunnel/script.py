from flask import Flask, jsonify, request
from datetime import datetime
from fetch_temphum import handle_temp_hum
from fetch_gas import handle_gas
from collect_temp import collect_temp
from collect_hum import collect_hum
from collect_gas import collect_gas

app = Flask(__name__)


@app.route("/temphum", methods=["GET"])
def api_temphum():
    return jsonify(handle_temp_hum())


@app.route("/gas", methods=["GET"])
def api_gas():
    return jsonify(handle_gas())


@app.route("/collect/temp", methods=["POST"])
def api_collect_temp():
    try:
        data = request.get_json()
        if not data or "duration" not in data or "interval" not in data:
            return jsonify({"error": "Missing duration or interval"}), 400
        duration = int(data["duration"])
        interval = int(data["interval"])
        if duration <= 0 or interval <= 0 or interval > duration:
            return jsonify({"error": "Invalid duration/interval"}), 400

        result = collect_temp(duration, interval)
        return jsonify(result)
    except ValueError:
        return jsonify({"error": "Duration/interval must be integers"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/collect/hum", methods=["POST"])
def api_collect_hum():
    try:
        data = request.get_json()
        if not data or "duration" not in data or "interval" not in data:
            return jsonify({"error": "Missing duration or interval"}), 400
        duration = int(data["duration"])
        interval = int(data["interval"])
        if duration <= 0 or interval <= 0 or interval > duration:
            return jsonify({"error": "Invalid duration/interval"}), 400

        result = collect_hum(duration, interval)
        return jsonify(result)
    except ValueError:
        return jsonify({"error": "Duration/interval must be integers"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/collect/gas", methods=["POST"])
def api_collect_gas():
    try:
        data = request.get_json()
        if not data or "duration" not in data or "interval" not in data:
            return jsonify({"error": "Missing duration or interval"}), 400
        duration = int(data["duration"])
        interval = int(data["interval"])
        if duration <= 0 or interval <= 0 or interval > duration:
            return jsonify({"error": "Invalid duration/interval"}), 400

        result = collect_gas(duration, interval)
        return jsonify(result)
    except ValueError:
        return jsonify({"error": "Duration/interval must be integers"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/health")
def health():
    return jsonify({"status": "ok", "timestamp": datetime.now().isoformat()})


if __name__ == "__main__":
    print("Server active. Waiting for requests on port 52471...")
    app.run(host="0.0.0.0", port=52471, debug=False)
