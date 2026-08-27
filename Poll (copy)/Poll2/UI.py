import asyncio
import json
from datetime import datetime
import httpx
import matplotlib.pyplot as plt
import pandas as pd
from nicegui import ui, app

plt.rcParams.update({
    "figure.facecolor": "#161B22",
    "axes.facecolor": "#12161C",
    "text.color": "#E6EDF3",
    "axes.labelcolor": "#8B949E",
    "xtick.color": "#8B949E",
    "ytick.color": "#8B949E",
    "grid.color": "#30363D",
    "axes.spines.top": False,
    "axes.spines.right": False,
})

# 👉 Change this to your Raspberry Pi's IP or hostname
PI_URL = "http://192.168.1.100:5000"

ui.add_css("""
:root { --bg: #0F1419; --card: #161B22; --border: rgba(255,255,255,0.08); --text: #E6EDF3; --muted: #8B949E; --primary: #F3EFE0; }
body { background-color: var(--bg) !important; color: var(--text) !important; font-family: system-ui, sans-serif; }
.q-card { background-color: var(--card) !important; border: 1px solid var(--border) !important; border-radius: 12px !important; }
.metric { font-size: 2.5rem; font-weight: bold; }
.custom-btn { background-color: var(--primary) !important; color: #0F1419 !important; border-radius: 8px !important; }
""", shared=True)

async def api_call(endpoint, method="POST", json_data=None, timeout=30):
    async with httpx.AsyncClient() as client:
        if method == "POST":
            resp = await client.post(f"{PI_URL}{endpoint}", json=json_data, timeout=timeout)
        else:
            resp = await client.get(f"{PI_URL}{endpoint}", timeout=timeout)
        resp.raise_for_status()
        return resp.json()

def render_plot(x, y, title, color):
    plot = ui.matplotlib(figsize=(5, 3)).classes("w-full")
    with plot.figure as fig:
        ax = fig.gca()
        ax.plot(x, y, marker="o", color=color)
        ax.set_title(title, fontsize=10)
        ax.tick_params(axis="x", rotation=45, labelsize=8)
        fig.tight_layout()
    plt.close(fig)

@ui.page("/")
def index():
    ui.label("🌡️ Sensor Dashboard").classes("text-2xl font-bold mb-4")
    
    # Status indicator
    status_dot = ui.element("div").classes("w-3 h-3 rounded-full bg-gray-500 inline-block mr-2")
    status_text = ui.label("Checking...").classes("text-sm")
    
    async def check_pi():
        try:
            resp = await httpx.AsyncClient().get(f"{PI_URL}/health", timeout=5)
            online = resp.status_code == 200
        except:
            online = False
        color = "#2ea043" if online else "#f85149"
        status_dot.style(f"background-color:{color};box-shadow:0 0 8px {color}")
        status_text.set_text("Online" if online else "Offline")
    
    ui.timer(5, check_pi)
    asyncio.create_task(check_pi())
    
    # Single fetch cards
    with ui.row().classes("gap-4"):
        with ui.card().classes("p-4 w-64"):
            ui.label("Temperature").classes("text-muted")
            temp_val = ui.label("—").classes("metric text-[#58A6FF]")
            ui.button("Fetch", on_click=lambda: fetch_single("/th", "temp", temp_val, "°C")).classes("custom-btn mt-2")
        
        with ui.card().classes("p-4 w-64"):
            ui.label("Humidity").classes("text-muted")
            hum_val = ui.label("—").classes("metric text-[#3FB950]")
            ui.button("Fetch", on_click=lambda: fetch_single("/th", "hum", hum_val, "%")).classes("custom-btn mt-2")
        
        with ui.card().classes("p-4 w-64"):
            ui.label("Gas").classes("text-muted")
            gas_val = ui.label("—").classes("metric text-[#D29922]")
            ui.button("Fetch", on_click=lambda: fetch_single("/gas", "gas", gas_val, "ppm")).classes("custom-btn mt-2")
    
    # Range collection
    with ui.card().classes("p-4 mt-4"):
        ui.label("📊 Range Collection").classes("text-lg font-bold mb-2")
        with ui.row().classes("items-end gap-4"):
            duration = ui.number(label="Duration (s)", value=30, min=5).classes("w-32")
            interval = ui.number(label="Interval (s)", value=5, min=1).classes("w-32")
            sensor = ui.select(["Temp/Hum", "Gas"], value="Temp/Hum").classes("w-32")
            ui.button("Start", on_click=lambda: start_collection(duration.value, interval.value, sensor.value)).classes("custom-btn")
    
    # Results area
    results = ui.column().classes("mt-4")
    
    def fetch_single(endpoint, field, label_ui, unit):
        async def _fetch():
            try:
                data = await api_call(endpoint)
                val = data.get(field)
                label_ui.set_text(f"{val:.1f} {unit}" if val is not None else "—")
            except Exception as e:
                label_ui.set_text(f"Error: {str(e)[:20]}")
        asyncio.create_task(_fetch())
    
    async def start_collection(duration, interval, sensor_type):
        endpoint = "/cth" if sensor_type == "Temp/Hum" else "/cgas"
        try:
            task = await api_call(endpoint, json_data={"duration": duration, "interval": interval})
            task_id = task["task_id"]
            ui.notify("Collecting...", type="info")
            
            while True:
                await asyncio.sleep(2)
                status = await api_call(f"/task/{task_id}", method="GET")
                if status["status"] == "completed":
                    result = json.loads(status["result"]) if isinstance(status["result"], str) else status["result"]
                    show_results(result, sensor_type)
                    ui.notify("Done!", type="positive")
                    break
                elif status["status"] == "error":
                    ui.notify(f"Failed: {status.get('error')}", type="negative")
                    break
        except Exception as e:
            ui.notify(str(e), type="negative")
    
    def show_results(data, sensor_type):
        results.clear()
        with results:
            df = pd.DataFrame(data["samples"])
            stats = data["stats"]
            
            if sensor_type == "Temp/Hum":
                for col, color, unit in [("temp", "#58A6FF", "°C"), ("hum", "#3FB950", "%")]:
                    with ui.card().classes("p-3 mb-2"):
                        ui.label(f"{col.upper()} Stats").classes("font-bold")
                        s = stats.get(col, {})
                        ui.label(f"Min: {s.get('min', 0):.1f}{unit} | Max: {s.get('max', 0):.1f}{unit} | Avg: {s.get('avg', 0):.1f}{unit}")
                        if col in df.columns:
                            render_plot(df["timestamp"], df[col], col, color)
            else:
                with ui.card().classes("p-3"):
                    ui.label("GAS Stats").classes("font-bold")
                    s = stats.get("gas", {})
                    ui.label(f"Min: {s.get('min', 0):.1f}ppm | Max: {s.get('max', 0):.1f}ppm | Avg: {s.get('avg', 0):.1f}ppm")
                    if "gas" in df.columns:
                        render_plot(df["timestamp"], df["gas"], "gas", "#D29922")

ui.run(title="Sensor UI", dark=True, port=8081)
