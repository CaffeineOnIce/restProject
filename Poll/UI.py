import asyncio
import json
from datetime import datetime
import httpx
import matplotlib.pyplot as plt
import pandas as pd
from nicegui import app, ui, background_tasks

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

BASE_URL = "https://restproject-inbd.onrender.com"

ui.add_css("""
:root { --bg: #0F1419; --bg-secondary: #1E2329; --card: #161B22; --border: rgba(255,255,255,0.08); --text: #E6EDF3; --muted: #8B949E; --primary: #F3EFE0; }
body { background-color: var(--bg) !important; color: var(--text) !important; font-family: system-ui, sans-serif; font-size: 16px; font-weight: bold !important; }
.nicegui-content { background: linear-gradient(180deg, #0F1419 0%, #161B22 100%); min-height: 100vh; }
.q-card { background-color: var(--card) !important; border: 1px solid var(--border) !important; color: var(--text) !important; box-shadow: none !important; border-radius: 12px !important; }
.metric-label { color: var(--muted); font-size: 1.2rem; text-transform: uppercase; letter-spacing: 0.5px; margin-top: 4px; font-weight:bold; }
.custom-button { background-color: var(--primary) !important; color: #0F1419 !important; font-weight: 600; border-radius: 8px !important; text-transform: none !important; font-size: 1.05rem !important; }
""", shared=True)

async def check_system_status(timeout=5):
    cloud_ok = False
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{BASE_URL}/health", timeout=timeout)
            cloud_ok = resp.status_code == 200
    except Exception: pass
    esp_ok = False
    if cloud_ok:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(f"{BASE_URL}/th", timeout=timeout + 5)
                esp_ok = resp.status_code == 200
        except Exception: pass
    if cloud_ok and esp_ok: return "#2ea043", "All Systems Online"
    if cloud_ok: return "#f59e0b", "ESP32/Bridge Offline"
    return "#f85149", "Cloud API Offline"

async def fetch_sensor(endpoint, field, timeout=30):
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{BASE_URL}{endpoint}", timeout=timeout)
        resp.raise_for_status()
        val = resp.json().get(field)
        if val is None: raise ValueError(resp.json().get("error_msg", "Sensor unavailable"))
        return float(val)

def init_storage():
    for k in ["temp_log", "hum_log", "gas_log", "temphum_data", "gas_data", "temphum_stats", "gas_stats"]:
        app.storage.user.setdefault(k, [] if k.endswith("_log") else None)

def render_plot(x, y, title, color, rotation=90, bottom_margin=None):
    plot = ui.matplotlib(figsize=(6, 4)).classes("w-full h-96")
    with plot.figure as fig:
        ax = fig.gca()
        ax.plot(x, y, marker="o", linestyle="-", color=color)
        ax.set_title(title, fontsize=12)
        if rotation: ax.tick_params(axis="x", rotation=rotation)
        if bottom_margin: fig.subplots_adjust(bottom=bottom_margin, left=0.12, right=0.95, top=0.90)
    plt.close(fig)

def render_last_collection(title, data_key, stats_key, metrics):
    with ui.card().classes("flex-1 min-w-[300px] p-6"):
        ui.label(title).classes("text-2xl font-bold text-[var(--text)] mb-4")
        data = app.storage.user.get(data_key)
        stats = app.storage.user.get(stats_key) or {}
        if data:
            with ui.row().classes("w-full justify-around"):
                for col, unit in metrics:
                    col_stats = stats.get(col, {})
                    if col_stats:
                        with ui.column().classes("items-center"):
                            ui.label(f"Avg: {col_stats.get('avg', 0):.1f} {unit}").classes("text-lg font-bold text-[var(--text)]")
                            ui.label(f"Min: {col_stats.get('min', 0):.1f} | Max: {col_stats.get('max', 0):.1f}").classes("text-sm text-[var(--muted)]")
        else:
            ui.label("No collections yet.").classes("text-[var(--muted)] italic")

@ui.refreshable
def render_overview():
    with ui.row().classes("w-full justify-between items-center mb-8"):
        ui.label("Overview (Polling Architecture)").classes("text-4xl font-bold m-0 text-[var(--text)]")
        async def fetch_all():
            fetch_all_btn.disable()
            fetch_all_btn.text = "Fetching via Cloud..."
            try:
                for name, endpoint, field, unit, log_key in [("Temperature", "/th", "temp", "°C", "temp_log"), ("Humidity", "/th", "hum", "%", "hum_log"), ("Gas", "/gas", "gas", "ppm", "gas_log")]:
                    try:
                        val = await fetch_sensor(endpoint, field)
                        app.storage.user[log_key].insert(0, {"Time": datetime.now().strftime("%H:%M:%S"), "Value": val, "Status": "Completed", "Error": ""})
                    except Exception as e:
                        app.storage.user[log_key].insert(0, {"Time": datetime.now().strftime("%H:%M:%S"), "Value": None, "Status": "Failed", "Error": str(e)})
                ui.notify("Cloud fetch complete", type="positive")
            finally:
                fetch_all_btn.enable()
                fetch_all_btn.text = "Fetch All Sensors"
                render_overview.refresh()
        fetch_all_btn = ui.button("Fetch All Sensors", on_click=fetch_all).classes("custom-button px-6 h-10")
    with ui.row().classes("w-full gap-6 flex-wrap"):
        for name, log_key, unit, color in [("Temperature", "temp_log", "°C", "#58A6FF"), ("Humidity", "hum_log", "%", "#3FB950"), ("Gas", "gas_log", "ppm", "#D29922")]:
            logs = app.storage.user.get(log_key, [])
            latest_val = f"{logs[0]['Value']:.2f}" if logs and logs[0]["Status"] == "Completed" else "—"
            latest_time = logs[0]["Time"] if logs else "Never"
            with ui.card().classes("flex-1 min-w-[250px] p-6"):
                ui.label(name).classes("text-xl font-bold text-[var(--muted)] uppercase tracking-wide")
                ui.label(f"{latest_val} {unit}").style(f"color: {color}").classes("text-5xl font-bold mt-2 leading-none")
                ui.label(f"Last fetched: {latest_time}").classes("text-sm text-[var(--muted)] mt-3")
    with ui.row().classes("w-full gap-6 flex-wrap mt-6"):
        for name, log_key, color in [("Temp Trend", "temp_log", "#58A6FF"), ("Hum Trend", "hum_log", "#3FB950"), ("Gas Trend", "gas_log", "#D29922")]:
            logs = app.storage.user.get(log_key, [])
            valid_logs = [r for r in logs if r["Status"] == "Completed"][:10][::-1]
            with ui.card().classes("flex-1 min-w-[300px] p-4"):
                ui.label(name).classes("text-lg font-bold text-[var(--text)] mb-2")
                if valid_logs:
                    chart_df = pd.DataFrame(valid_logs).set_index("Time")[["Value"]]
                    plot = ui.matplotlib(figsize=(4, 2)).classes("w-full h-45")
                    with plot.figure as fig:
                        ax = fig.gca()
                        ax.plot(chart_df.index, chart_df["Value"], marker="o", color=color, linewidth=2, markersize=4)
                        ax.set_xticks([])
                        ax.tick_params(axis="y", labelsize=8)
                        fig.subplots_adjust(left=0.1, right=0.95, top=0.9, bottom=0.1)
                else:
                    ui.label("No data yet").classes("text-[var(--muted)] italic h-32 flex items-center justify-center")
    with ui.row().classes("w-full gap-6 flex-wrap mt-6"):
        render_last_collection("Last Temp/Hum Collection", "temphum_data", "temphum_stats", [("temp", "°C"), ("hum", "%")])
        render_last_collection("Last Gas Collection", "gas_data", "gas_stats", [("gas", "ppm")])

def render_fetch_card(name, endpoint, field, unit, log_key):
    with ui.card().classes("w-full p-6"):
        ui.label(name).classes("text-3xl font-bold mb-6 text-[var(--text)]")
        with ui.row().classes("w-full items-start gap-8"):
            with ui.column().classes("flex-1"):
                btn = ui.button(f"Fetch {name}").classes("custom-button w-full h-12 text-lg")
                async def on_fetch():
                    btn.disable()
                    btn.text = f"Fetching {name}..."
                    try:
                        val = await fetch_sensor(endpoint, field)
                        app.storage.user[log_key].insert(0, {"Time": datetime.now().strftime("%H:%M:%S"), "Value": val, "Status": "Completed", "Error": ""})
                    except Exception as e:
                        app.storage.user[log_key].insert(0, {"Time": datetime.now().strftime("%H:%M:%S"), "Value": None, "Status": "Failed", "Error": str(e)})
                    finally:
                        btn.enable()
                        btn.text = f"Fetch {name}"
                        refresh_display()
                btn.on_click(on_fetch)
            with ui.column().classes("flex-1 items-end"):
                metric_label = ui.label("—").classes("text-3xl font-bold text-[var(--text)] leading-none")
        container = ui.column().classes("w-full mt-8")
        def refresh_display():
            container.clear()
            logs = app.storage.user[log_key]
            if not logs:
                with container: ui.label("No readings collected yet.").classes("text-[var(--muted)] text-base italic")
                metric_label.set_text("—")
                return
            latest = logs[0]
            metric_label.set_text(f"{latest['Value']:.2f} {unit}" if latest["Status"] == "Completed" else "—")
            if latest["Status"] == "Failed" and latest["Error"]:
                short_error = latest["Error"][:50] + "..." if len(latest["Error"]) > 50 else latest["Error"]
                ui.notify(short_error, type="negative")
                with container: ui.label(short_error).classes("text-red-400 text-base mb-4 bg-red-900/20 p-3 rounded border border-red-900/50 w-full")
            valid_logs = [r for r in logs if r["Status"] == "Completed"]
            cols = ["Time", "Value", "Status"] + (["Error"] if any(r["Error"] for r in logs) else [])
            with container:
                with ui.row().classes("w-full gap-6 items-start"):
                    with ui.column().classes("flex-1"):
                        df_logs = pd.DataFrame(logs[:20])
                        if "Error" in df_logs.columns: df_logs["Error"] = df_logs["Error"].apply(lambda x: str(x)[:40] + "..." if len(str(x)) > 40 else x)
                        ui.table.from_pandas(df_logs[cols]).props("dark flat").classes("w-full text-base")
                    with ui.column().classes("flex-1"):
                        if valid_logs:
                            chart_df = pd.DataFrame(valid_logs)[::-1].set_index("Time")[["Value"]]
                            render_plot(chart_df.index, chart_df["Value"], name, "#F3EFE0", rotation=90, bottom_margin=0.20)
        refresh_display()

def render_collect_card(sensor_type):
    is_th = sensor_type == "temphum"
    title = f"Data Collection ({'Temp/Hum' if is_th else 'Gas'})"
    endpoint = "/cth" if is_th else "/cgas"
    data_key, stats_key = ("temphum_data", "temphum_stats") if is_th else ("gas_data", "gas_stats")
    metrics = ([{"col": "temp", "title": "Temperature", "color": "#58A6FF", "unit": "°C"}, {"col": "hum", "title": "Humidity", "color": "#3FB950", "unit": "%"}] if is_th else [{"col": "gas", "title": "Gas Readings", "color": "#D29922", "unit": "ppm"}])
    with ui.card().classes("w-full p-6"):
        ui.label(title).classes("text-2xl font-bold mb-6 text-[var(--text)]")
        with ui.row().classes("w-full items-center gap-8"):
            with ui.column().classes("gap-4"):
                duration = ui.number(label="Duration (s)", value=30, min=5, step=1).classes("w-48 text-base").props("dark outlined")
                interval = ui.number(label="Interval (s)", value=5, min=1, step=1).classes("w-48 text-base").props("dark outlined")
            def calc_expected():
                d = duration.value if duration.value is not None else 30
                i = interval.value if interval.value is not None else 5
                return max(1, int(d // i))
            with ui.row().classes("flex-1 justify-around items-center"):
                with ui.column().classes("items-center"):
                    expected_lbl = ui.label(str(calc_expected())).classes("text-6xl font-bold text-[var(--text)]")
                    ui.label("Expected Samples").classes("metric-label")
                with ui.column().classes("items-center"):
                    freq_lbl = ui.label(f"{int(interval.value)}s" if interval.value is not None else "—").classes("text-6xl font-bold text-[var(--text)]")
                    ui.label("Frequency").classes("metric-label")
                with ui.column().classes("items-center"):
                    runtime_lbl = ui.label(f"{int(duration.value)}s" if duration.value is not None else "—").classes("text-6xl font-bold text-[var(--text)]")
                    ui.label("Runtime").classes("metric-label")
            with ui.column().classes("items-center"):
                btn = ui.button("Start Cloud Collection").classes("custom-button w-48 h-12 text-lg")
            def update_stats():
                expected_lbl.set_text(str(calc_expected()))
                freq_lbl.set_text(f"{int(interval.value)}s" if interval.value is not None else "—")
                runtime_lbl.set_text(f"{int(duration.value)}s" if duration.value is not None else "—")
            duration.on_value_change(lambda _: update_stats())
            interval.on_value_change(lambda _: update_stats())
            async def start_collection():
                btn.disable()
                btn.text = "Dispatching to Edge..."
                try:
                    async with httpx.AsyncClient() as client:
                        resp = await client.post(f"{BASE_URL}{endpoint}", json={"duration": duration.value, "interval": interval.value}, timeout=10)
                        resp.raise_for_status()
                        task_id = resp.json()["task_id"]
                        btn.text = "Edge Collecting..."
                        while True:
                            await asyncio.sleep(2)
                            status_resp = await client.get(f"{BASE_URL}/task/{task_id}", timeout=10)
                            task_status = status_resp.json()
                            if task_status["status"] == "completed":
                                result_data = json.loads(task_status["result"]) if isinstance(task_status["result"], str) else task_status["result"]
                                app.storage.user[data_key] = result_data["samples"]
                                app.storage.user[stats_key] = result_data["stats"]
                                ui.notify(f"Collection completed ({len(result_data['samples'])} samples)", type="positive")
                                break
                            elif task_status["status"] == "error":
                                raise Exception(task_status.get("error", "Edge task failed"))
                except Exception as e:
                    ui.notify(str(e), type="negative")
                finally:
                    btn.enable()
                    btn.text = "Start Cloud Collection"
                    refresh_results()
            btn.on_click(start_collection)
        results_container = ui.column().classes("w-full mt-8")
        def refresh_results():
            results_container.clear()
            data = app.storage.user.get(data_key)
            if not data: return
            df = pd.DataFrame(data)
            with results_container:
                for m in metrics:
                    if m["col"] in df.columns:
                        with ui.card().classes("w-full p-4 mb-6"):
                            ui.label(m["title"]).classes("text-2xl font-bold mb-4 text-[var(--text)]")
                            edge_stats = app.storage.user.get(stats_key, {}) or {}
                            col_stats = edge_stats.get(m["col"], {})
                            with ui.row().classes("w-full justify-around mb-4 p-3 bg-[var(--bg-secondary)] rounded-lg"):
                                for stat_name, label in [("min", "Min"), ("max", "Max"), ("avg", "Avg")]:
                                    val = col_stats.get(stat_name, 0)
                                    with ui.column().classes("items-center"):
                                        ui.label(f"{val:.2f} {m['unit']}").classes("text-xl font-bold text-[var(--text)]")
                                        ui.label(label).classes("metric-label")
                            with ui.row().classes("w-full gap-6 items-start"):
                                with ui.column().classes("flex-1"):
                                    ui.table.from_pandas(df[["timestamp", m["col"]]]).props("dark flat").classes("w-full text-base")
                                with ui.column().classes("flex-1"):
                                    render_plot(df["timestamp"], df[m["col"]], m["title"], m["color"])
        refresh_results()

@ui.page("/")
def index():
    init_storage()
    with ui.header().classes("h-25 items-center px-6"):
        ui.label("Polling Architecture Dashboard").classes("text-3xl font-bold text-[var(--text)]")
        with ui.row().classes("items-center gap-2 ml-4 px-3 py-1 bg-[var(--card)] border border-[var(--border)] rounded-lg"):
            status_dot = ui.element("div").classes("w-3 h-3 rounded-full bg-gray-500")
            status_text = ui.label("Checking...").classes("text-[var(--text)] font-medium text-sm")
            async def update_status():
                color, text = await check_system_status()
                status_dot.style(f"background-color: {color}; box-shadow: 0 0 8px {color}")
                status_text.set_text(text)
            ui.timer(5, update_status)
            background_tasks.create(update_status())
        ui.space()
        def update_base_url(e):
            global BASE_URL
            BASE_URL = e.value.rstrip("/")
        ui.input(value=BASE_URL, label="Cloud API URL").classes("w-80 text-base").props("dark outlined bg-color=#1E2329").on_value_change(update_base_url)
    main_container = ui.column().classes("w-full p-8 gap-8 max-w-7xl mx-auto")
    with main_container:
        content = ui.column().classes("w-full gap-8")
    with ui.left_drawer(value=True).classes("p-4").props("width=250 elevated"):
        ui.label("Navigation").classes("text-xl font-bold mb-6 text-[var(--text)] px-2")
        cards_config = {"temp": ("Temperature", "/th", "temp", "°C", "temp_log"), "hum": ("Humidity", "/th", "hum", "%", "hum_log"), "gas": ("Gas", "/gas", "gas", "ppm", "gas_log")}
        nav_buttons = {}
        def render_content(page_key):
            for key, btn in nav_buttons.items():
                if key == page_key: btn.classes(remove="bg-transparent text-[var(--muted)]").classes(add="bg-[#252A31] text-[var(--text)] font-medium")
                else: btn.classes(remove="bg-[#252A31] font-medium").classes(add="bg-transparent text-[var(--muted)]")
            content.clear()
            with content:
                if page_key == "overview": render_overview()
                elif page_key in cards_config: render_fetch_card(*cards_config[page_key])
                else: render_collect_card("temphum" if page_key == "th_range" else "gas")
        menu_items = [("Overview", "overview"), ("Temperature", "temp"), ("Humidity", "hum"), ("Gas", "gas"), ("Temp/Hum Range", "th_range"), ("Gas Range", "gas_range")]
        for label, key in menu_items:
            btn = ui.button(label, on_click=lambda k=key: render_content(k))
            btn.classes("w-full justify-start bg-transparent text-[var(--muted)] mb-2 h-10 text-left text-base")
            nav_buttons[key] = btn
    render_content("overview")

ui.run(title="Polling Dashboard", dark=True, storage_secret="polling-secret", port=8081)