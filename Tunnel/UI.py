import asyncio
from datetime import datetime
import pandas as pd
import httpx
import matplotlib.pyplot as plt
from nicegui import ui, app, background_tasks

plt.rcParams.update({"figure.facecolor": "#161B22", "axes.facecolor": "#12161C", "text.color": "#E6EDF3", "axes.labelcolor": "#8B949E", "xtick.color": "#8B949E", "ytick.color": "#8B949E", "grid.color": "#30363D", "axes.spines.top": False, "axes.spines.right": False})

BASE_URL = "https://restapi.shares.zrok.io"

ui.add_css("""
:root { 
    --bg: #0F1419; 
    --bg-secondary: #1E2329; 
    --card: #161B22; 
    --border: rgba(255,255,255,0.08); 
    --text: #E6EDF3; 
    --muted: #8B949E; 
    --primary: #F3EFE0; 
}

body { 
    background-color: var(--bg) !important; 
    color: var(--text) !important; 
    font-family: system-ui, sans-serif; 
    font-size: 17px !important; 
    font-weight: bold !important; 
}

.nicegui-content { 
    background: linear-gradient(180deg, #0F1419 0%, #161B22 100%); 
    min-height: 100vh; 
}

.q-field--outlined .q-field__control { 
    background-color: var(--bg-secondary) !important; 
    border-radius: 8px !important; 
    height: 64px !important 
}

.q-drawer { 
    background-color: var(--bg-secondary) !important; 
    border-right: 1px solid var(--border) !important; 
}

.q-header { 
    background-color: var(--bg) !important; 
    border-bottom: 1px solid var(--border) !important; 
    color: var(--text) !important; 
}

.q-card { 
    background-color: var(--card) !important; 
    border: 1px solid var(--border) !important; 
    color: var(--text) !important; 
    box-shadow: none !important; 
    border-radius: 12px !important; 
}

.q-field__label, .q-field__native { 
    font-size: 20px !important; 
}

.q-table { 
    background-color: transparent !important; 
    color: var(--text) !important; 
}

.q-table th { 
    color: var(--muted) !important; 
    font-weight: 600 !important; 
    font-size: 1.2rem !important; 
    padding: 16px 16px !important;
}

.q-table td { 
    font-size: 1.2rem !important; 
    padding: 16px 16px !important;
    border-bottom: 1px solid var(--border) !important; 
}

.q-separator { 
    background-color: var(--border) !important; 
}

.metric-label { 
    color: var(--muted); 
    font-size: 1.25rem; 
    text-transform: uppercase; 
    letter-spacing: 0.5px; 
    margin-top: 4px; 
    font-weight:bold; 
}

.custom-button { 
    background-color: var(--primary) !important; 
    color: #0F1419 !important; 
    font-weight: 600; 
    border-radius: 8px !important; 
    text-transform: none !important; 
    font-size: 1.1rem !important; 
    transition: all 0.2s ease; 
}

.custom-button:hover { 
    background-color: #e5e1d1 !important; 
    transform: translateY(-1px); 
}
""", shared=True)

async def check_endpoint(endpoint, timeout=5):
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{BASE_URL}{endpoint}", timeout=timeout)
            return resp.json().get("status") == "ok" if endpoint == "/health" else True
    except Exception:
        return False

async def fetch_sensor(endpoint, field, timeout=20):
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{BASE_URL}{endpoint}", timeout=timeout)
        resp.raise_for_status()
        val = resp.json().get(field)
        if val is None: raise ValueError(resp.json().get("error_msg", "Sensor unavailable"))
        return float(val)

def init_storage():
    for k in ["temp_log", "hum_log", "gas_log", "temphum_data", "gas_data", "temphum_exp", "gas_exp"]:
        app.storage.user.setdefault(k, [] if k.endswith("_log") else None)

def render_plot(x, y, title, color, xlabel="Time", ylabel="Value", rotation=90, bottom_margin=None):
    plot = ui.matplotlib(figsize=(6, 4)).classes("w-full h-96")
    with plot.figure as fig:
        ax = fig.gca()
        ax.plot(x, y, marker="o", linestyle="-", color=color)
        ax.set_title(title, fontsize=16, fontweight='bold')
        ax.set_xlabel(xlabel, fontsize=14, fontweight='bold')
        ax.set_ylabel(ylabel, fontsize=14, fontweight='bold')
        
        # Increase font sizes of the tick labels (grid values)
        ax.tick_params(axis="x", rotation=rotation, labelsize=12)
        ax.tick_params(axis="y", labelsize=12)
        
        if bottom_margin:
            fig.subplots_adjust(bottom=bottom_margin, left=0.15, right=0.95, top=0.90)
        else:
            fig.subplots_adjust(bottom=0.15, left=0.15, right=0.95, top=0.90)

def render_last_collection(title, data_key, metrics):
    with ui.card().classes("flex-1 min-w-[300px] p-6"):
        ui.label(title).classes("text-xl font-bold text-[var(--text)] mb-4")
        data = app.storage.user.get(data_key)
        if data:
            df = pd.DataFrame(data)
            with ui.row().classes("w-full justify-around"):
                for col, unit in metrics:
                    if col in df.columns:
                        with ui.column().classes("items-center"):
                            ui.label(f"Avg: {df[col].mean():.1f}{unit}").classes("text-lg font-bold text-[var(--text)]")
                            ui.label(f"Min: {df[col].min():.1f} | Max: {df[col].max():.1f}").classes("text-sm text-[var(--muted)]")
        else:
            ui.label("No collections yet.").classes("text-[var(--muted)] italic text-base")

@ui.refreshable
def render_overview():
    with ui.row().classes("w-full justify-end mb-6"):
        async def fetch_all():
            fetch_all_btn.disable()
            fetch_all_btn.text = "Fetching All..."
            try:
                for name, endpoint, field, unit, log_key in [("Temperature", "/temphum", "temp", "°C", "temp_log"), ("Humidity", "/temphum", "hum", "%", "hum_log"), ("Carbon Dioxide", "/gas", "gas", "ppm", "gas_log")]:
                    try:
                        val = await fetch_sensor(endpoint, field)
                        app.storage.user[log_key].insert(0, {"Time": datetime.now().strftime("%H:%M:%S"), "Value": val, "Status": "Completed", "Error": ""})
                    except Exception as e:
                        app.storage.user[log_key].insert(0, {"Time": datetime.now().strftime("%H:%M:%S"), "Value": None, "Status": "Failed", "Error": str(e)})
                ui.notify("All sensors fetched", type="positive")
            finally:
                render_overview.refresh()
        fetch_all_btn = ui.button("Fetch All Sensors", on_click=fetch_all).classes("custom-button px-6 h-10")

    with ui.row().classes("w-full gap-6 flex-wrap"):
        for name, log_key, unit, color in [("Temperature", "temp_log", "°C", "#58A6FF"), ("Humidity", "hum_log", "%", "#3FB950"), ("Carbon Dioxide", "gas_log", "ppm", "#D29922")]:
            logs = app.storage.user.get(log_key, [])
            latest_val = f"{logs[0]['Value']:.2f}" if logs and logs[0]["Status"] == "Completed" else "—"
            latest_time = logs[0]["Time"] if logs else "Never"
            with ui.card().classes("flex-1 min-w-[250px] p-6"):
                ui.label(name).classes("text-lg font-bold text-[var(--muted)] uppercase tracking-wide")
                ui.label(f"{latest_val} {unit}").style(f"color: {color}").classes("text-5xl font-bold mt-2 leading-none")
                ui.label(f"Last fetched: {latest_time}").classes("text-xl text-[var(--muted)] mt-3")

    with ui.row().classes("w-full gap-6 flex-wrap mt-6"):
        for name, log_key, unit, color in [("Temp Trend", "temp_log", "°C", "#58A6FF"), ("Hum Trend", "hum_log", "%", "#3FB950"), ("CO2 Trend", "gas_log", "ppm", "#D29922")]:
            logs = app.storage.user.get(log_key, [])
            valid_logs = [r for r in logs if r["Status"] == "Completed"][:15]
            with ui.card().classes("flex-1 min-w-[300px] p-4"):
                ui.label(name).classes("text-xl font-bold text-[var(--text)] mb-2")
                if valid_logs:
                    chart_df = pd.DataFrame(valid_logs).set_index("Time")[["Value"]]
                    plot = ui.matplotlib(figsize=(4, 2)).classes("w-full h-45")
                    with plot.figure as fig:
                        ax = fig.gca()
                        ax.plot(chart_df.index, chart_df["Value"], marker="o", color=color, linewidth=2, markersize=4)
                        ax.set_xticks([])
                        ax.set_xlabel("Time", fontsize=11, fontweight='bold')
                        ax.set_ylabel(f"Value ({unit})", fontsize=11, fontweight='bold')
                        ax.tick_params(axis="y", labelsize=10)
                        fig.subplots_adjust(left=0.2, right=0.95, top=0.9, bottom=0.15)
                else:
                    ui.label("No data yet").classes("text-xl font-bold text-[var(--muted)] italic h-32 flex items-center justify-center")

    with ui.row().classes("w-full gap-6 flex-wrap mt-6"):
        render_last_collection("Last Temp/Hum Collection", "temphum_data", [("temp", "°C"), ("hum", "%")])
        render_last_collection("Last CO2 Collection", "gas_data", [("gas", " ppm")])

def render_fetch_card(name, endpoint, field, unit, log_key):
    with ui.card().classes("w-full p-6"):
        ui.label(name).classes("text-2xl font-bold mb-6 text-[var(--text)]")
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
                metric_label = ui.label("—").classes("text-4xl font-bold text-[var(--text)] leading-none")
        
        container = ui.column().classes("w-full mt-8")
        def refresh_display():
            container.clear()
            logs = app.storage.user[log_key]
            if not logs:
                with container: ui.label("No readings collected yet.").classes("text-[var(--muted)] text-xl italic")
                metric_label.set_text(f"— {unit}")
                return
            
            latest = logs[0]
            
            metric_label.set_text(f"{latest['Value']:.2f} {unit}" if latest["Status"] == "Completed" else f"Err {unit}")
            
            if latest["Status"] == "Failed" and latest["Error"]:
                short_error = latest["Error"][:50] + "..." if len(latest["Error"]) > 50 else latest["Error"]
                ui.notify(short_error, type="negative")
                
                with container:
                    ui.label(short_error).classes("text-red-400 text-xl mb-4 bg-red-900/20 p-3 rounded border border-red-900/50 w-full")

            valid_logs = [r for r in logs if r["Status"] == "Completed"][:15]
            cols = ["Time", "Value", "Status"] + (["Error"] if any(r["Error"] for r in logs) else [])
            
            with container:
                with ui.row().classes("w-full gap-6 items-start"):
                    with ui.column().classes("flex-1"):
                        df_logs = pd.DataFrame(logs[:15])
                        if "Error" in df_logs.columns:
                            df_logs["Error"] = df_logs["Error"].apply(lambda x: str(x)[:40] + "..." if len(str(x)) > 40 else x)
                        
                        ui.table.from_pandas(df_logs[cols]).props("dark flat").classes("w-full text-lg")
                    
                    with ui.column().classes("flex-1"):
                        if valid_logs:
                            chart_df = pd.DataFrame(valid_logs)[::-1].set_index("Time")[["Value"]]
                            render_plot(chart_df.index, chart_df["Value"], name, "#F3EFE0", xlabel="Time", ylabel=f"{name} ({unit})", rotation=90, bottom_margin=0.20)
        refresh_display()

def render_collect_card(sensor_type):
    is_th = sensor_type == "temphum"
    title = f"Data Collection ({'Temp/Hum' if is_th else 'CO2'})"
    endpoint = "/ctemphum" if is_th else "/cgas"
    data_key, exp_key = ("temphum_data", "temphum_exp") if is_th else ("gas_data", "gas_exp")
    metrics = [{"col": "temp", "title": "Temperature", "color": "#58A6FF", "unit": "°C"}, {"col": "hum", "title": "Humidity", "color": "#3FB950", "unit": "%"}] if is_th else [{"col": "gas", "title": "CO2 Readings", "color": "#D29922", "unit": " ppm"}]

    with ui.card().classes("w-full p-6"):
        ui.label(title).classes("text-2xl font-bold mb-6 text-[var(--text)]")
        with ui.row().classes("w-full items-center gap-8"):
            with ui.column().classes("gap-4"):
                duration = ui.number(label="Duration (s)", value=30, min=5, step=1).classes("w-48 text-base").props("dark outlined")
                interval = ui.number(label="Interval (s)", value=5, min=1, step=1).classes("w-48 text-base").props("dark outlined")
            
            def calc_expected(): return max(1, int((duration.value or 30) // (interval.value or 5)))
            
            with ui.row().classes("flex-1 justify-around items-center"):
                with ui.column().classes("items-center"):
                    expected_lbl = ui.label(str(calc_expected())).classes("text-5xl font-bold text-[var(--text)]")
                    ui.label("Expected Samples").classes("metric-label")
                with ui.column().classes("items-center"):
                    freq_lbl = ui.label(f"{int(interval.value)}s").classes("text-5xl font-bold text-[var(--text)]")
                    ui.label("Frequency").classes("metric-label")
                with ui.column().classes("items-center"):
                    runtime_lbl = ui.label(f"{int(duration.value)}s").classes("text-5xl font-bold text-[var(--text)]")
                    ui.label("Runtime").classes("metric-label")
            
            with ui.column().classes("items-center"):
                btn = ui.button("Start Collection").classes("custom-button w-48 h-12 text-lg")
            
            def update_stats():
                expected_lbl.set_text(str(calc_expected()))
                freq_lbl.set_text(f"{int(interval.value)}s")
                runtime_lbl.set_text(f"{int(duration.value)}s")
            
            duration.on_value_change(lambda _: update_stats())
            interval.on_value_change(lambda _: update_stats())
            
            async def start_collection():
                btn.disable()
                btn.text = "Starting..."
                try:
                    async with httpx.AsyncClient() as client:
                        resp = await client.post(f"{BASE_URL}{endpoint}", json={"duration": duration.value, "interval": interval.value}, timeout=10)
                        resp.raise_for_status()
                        start_data = resp.json()
                        if start_data.get("status") != "started": raise Exception(start_data.get("error", "Failed"))
                        task_id = start_data["task_id"]
                        btn.text = "Collecting..."
                        while True:
                            await asyncio.sleep(2)
                            status_resp = await client.get(f"{BASE_URL}/task/{task_id}", timeout=10)
                            status_resp.raise_for_status()
                            task_status = status_resp.json()
                            if task_status["status"] == "completed":
                                app.storage.user[data_key] = task_status["result"]
                                app.storage.user[exp_key] = calc_expected()
                                ui.notify(f"Collection completed ({len(task_status['result'])} samples)", type="positive")
                                break
                            elif task_status["status"] == "error": raise Exception(task_status.get("error", "Background task failed"))
                except Exception as e:
                    ui.notify(str(e), type="negative")
                finally:
                    btn.enable()
                    btn.text = "Start Collection"
                    refresh_results()
            btn.on_click(start_collection)

        results_container = ui.column().classes("w-full mt-8")
        def refresh_results():
            results_container.clear()
            data = app.storage.user.get(data_key)
            expected = app.storage.user.get(exp_key, 1)
            if not data: return
            df = pd.DataFrame(data)
            actual, rate = len(df), (len(df) / expected * 100) if expected else 0
            with results_container:
                ui.separator().classes("bg-[var(--border)] mb-6")
                with ui.row().classes("w-full justify-center gap-16 mb-6"):
                    for val, lbl in [(str(actual), "Actual Samples"), (f"{rate:.0f}%", "Success Rate")]:
                        with ui.column().classes("items-center"):
                            ui.label(val).classes("text-2xl font-bold text-[var(--text)]")
                            ui.label(lbl).classes("metric-label")
                ui.separator().classes("bg-[var(--border)] my-6")
                for m in metrics:
                    if m["col"] in df.columns:
                        with ui.card().classes("w-full p-4 mb-6"):
                            ui.label(m["title"]).classes("text-2xl font-bold mb-4 text-[var(--text)]")
                            with ui.row().classes("w-full justify-around mb-4 p-3 bg-[var(--bg-secondary)] rounded-lg"):
                                for stat, val in [("Min", df[m["col"]].min()), ("Max", df[m["col"]].max()), ("Avg", df[m["col"]].mean())]:
                                    with ui.column().classes("items-center"):
                                        ui.label(f"{val:.2f}{m['unit']}").classes("text-xl font-bold text-[var(--text)]")
                                        ui.label(stat).classes("metric-label")
                            with ui.row().classes("w-full gap-6 items-start"):
                                with ui.column().classes("flex-1"):
                                    ui.table.from_pandas(df[["timestamp", m["col"]]]).props("dark flat").classes("w-full text-lg")
                                with ui.column().classes("flex-1"):
                                    render_plot(df["timestamp"], df[m["col"]], m["title"], m["color"], xlabel="Timestamp", ylabel=f"{m['title']} ({m['unit'].strip()})")
        refresh_results()

@ui.page("/")
def index():
    init_storage()
    with ui.header().classes("h-25 items-center px-6"):
        ui.label("Sensor Dashboard").classes("text-2xl font-bold text-[var(--text)]")
        
        with ui.row().classes("items-center gap-3 px-4 py-2 ml-4 bg-[var(--card)] border border-[var(--border)] rounded-lg"):
            status_dot = ui.element("div").classes("w-3 h-3 rounded-full")
            status_text = ui.label("Checking...").classes("text-[var(--text)] font-medium text-lg")
            async def update_status():
                ok = await check_endpoint("/health") and await check_endpoint("/temphum")
                color = "#2ea043" if ok else "#f85149"
                status_dot.style(f"background-color: {color}; box-shadow: 0 0 8px {color}")
                status_text.set_text("Online" if ok else "Offline")
            ui.timer(5, update_status)
            background_tasks.create(update_status())

        ui.space()
        def update_base_url(e):
            global BASE_URL
            BASE_URL = e.value.rstrip("/")
        ui.input(value=BASE_URL, label="URL").classes("w-80 text-base").props("dark outlined bg-color=#1E2329").on_value_change(update_base_url)

    main_container = ui.column().classes("w-full p-8 gap-8 max-w-7xl mx-auto")
    with main_container:
        content = ui.column().classes("w-full gap-8")

    with ui.left_drawer(value=True).classes("p-4").props("width=250 elevated"):
        ui.label("Navigation").classes("text-xl font-bold mb-6 text-[var(--text)] px-2")
        cards_config = {"temp": ("Temperature", "/temphum", "temp", "°C", "temp_log"), "hum": ("Humidity", "/temphum", "hum", "%", "hum_log"), "gas": ("Carbon Dioxide", "/gas", "gas", "ppm", "gas_log")}
        nav_buttons = {}
        
        def render_content(page_key):
            for key, btn in nav_buttons.items():
                if key == page_key:
                    btn.classes(remove="bg-transparent text-[var(--muted)]").classes(add="bg-[#252A31] text-[var(--text)] font-medium")
                else:
                    btn.classes(remove="bg-[#252A31] font-medium").classes(add="bg-transparent text-[var(--muted)]")
            content.clear()
            with content:
                if page_key == "overview": render_overview()
                elif page_key in cards_config: render_fetch_card(*cards_config[page_key])
                else: render_collect_card("temphum" if page_key == "th_range" else "gas")

        menu_items = [("Overview", "overview"), ("Temperature", "temp"), ("Humidity", "hum"), ("CO2", "gas"), ("Temp/Hum Range", "th_range"), ("CO2 Range", "gas_range")]
        for label, key in menu_items:
            btn = ui.button(label, on_click=lambda k=key: render_content(k))
            btn.classes("w-full justify-start bg-transparent text-[var(--muted)] mb-2 h-10 text-left text-base")
            nav_buttons[key] = btn
    render_content("overview")

ui.run(title="Sensor Dashboard", dark=True, storage_secret="my-secret-key", port=8081)