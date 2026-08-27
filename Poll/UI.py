import asyncio
import json
from datetime import datetime
import httpx
import matplotlib.pyplot as plt
import pandas as pd
from nicegui import app, ui

plt.rcParams.update(
    {
        "figure.facecolor": "#161B22",
        "axes.facecolor": "#12161C",
        "text.color": "#E6EDF3",
        "axes.labelcolor": "#8B949E",
        "xtick.color": "#8B949E",
        "ytick.color": "#8B949E",
        "grid.color": "#30363D",
        "axes.spines.top": False,
        "axes.spines.right": False,
    }
)

BASE_URL = "https://restproject-inbd.onrender.com"

ui.add_css(
    """
:root { --bg: #0F1419; --bg-secondary: #1E2329; --card: #161B22; --border: rgba(255,255,255,0.08); --text: #E6EDF3; --muted: #8B949E; --primary: #F3EFE0; }
body { background-color: var(--bg) !important; color: var(--text) !important; font-family: system-ui, sans-serif; font-size: 16px; font-weight: bold !important; }
.nicegui-content { background: linear-gradient(180deg, #0F1419 0%, #161B22 100%); min-height: 100vh; }
.q-card { background-color: var(--card) !important; border: 1px solid var(--border) !important; color: var(--text) !important; box-shadow: none !important; border-radius: 12px !important; }
.metric-label { color: var(--muted); font-size: 1.2rem; text-transform: uppercase; letter-spacing: 0.5px; margin-top: 4px; font-weight:bold; }
.custom-button { background-color: var(--primary) !important; color: #0F1419 !important; font-weight: 600; border-radius: 8px !important; text-transform: none !important; font-size: 1.05rem !important; }
""",
    shared=True,
)


async def fetch_sensor(endpoint, timeout=30):
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{BASE_URL}{endpoint}", timeout=timeout)
        resp.raise_for_status()
        return resp.json()


def render_plot(x, y, title, color):
    plot = ui.matplotlib(figsize=(6, 4)).classes("w-full h-96")
    with plot.figure as fig:
        ax = fig.gca()
        ax.plot(x, y, marker="o", linestyle="-", color=color)
        ax.set_title(title, fontsize=12)
        ax.tick_params(axis="x", rotation=90)
        fig.subplots_adjust(bottom=0.20, left=0.12, right=0.95, top=0.90)
    plt.close(fig)


@ui.refreshable
def render_overview():
    with ui.row().classes("w-full justify-between items-center mb-8"):
        ui.label("Overview (Polling Architecture)").classes(
            "text-4xl font-bold m-0 text-[var(--text)]"
        )

    async def fetch_all():
        fetch_all_btn.disable()
        fetch_all_btn.text = "Fetching via Cloud..."
        try:
            for name, endpoint, field, unit, log_key in [
                ("Temperature", "/th", "temp", "°C", "temp_log"),
                ("Humidity", "/th", "hum", "%", "hum_log"),
                ("Gas", "/gas", "gas", "ppm", "gas_log"),
            ]:
                try:
                    data = await fetch_sensor(endpoint)
                    val = data.get(field)
                    app.storage.user[log_key].insert(
                        0,
                        {
                            "Time": datetime.now().strftime("%H:%M:%S"),
                            "Value": val,
                            "Status": "Completed",
                            "Error": "",
                        },
                    )
                except Exception as e:
                    app.storage.user[log_key].insert(
                        0,
                        {
                            "Time": datetime.now().strftime("%H:%M:%S"),
                            "Value": None,
                            "Status": "Failed",
                            "Error": str(e),
                        },
                    )
            ui.notify("Cloud fetch complete", type="positive")
        finally:
            fetch_all_btn.enable()
            fetch_all_btn.text = "Fetch All Sensors"
            render_overview.refresh()

    fetch_all_btn = ui.button("Fetch All Sensors", on_click=fetch_all).classes(
        "custom-button px-6 h-10"
    )
    with ui.row().classes("w-full gap-6 flex-wrap"):
        for name, log_key, unit, color in [
            ("Temperature", "temp_log", "°C", "#58A6FF"),
            ("Humidity", "hum_log", "%", "#3FB950"),
            ("Gas", "gas_log", "ppm", "#D29922"),
        ]:
            logs = app.storage.user.get(log_key, [])
            latest_val = (
                f"{logs[0]['Value']:.2f}"
                if logs and logs[0]["Status"] == "Completed"
                else "—"
            )
            with ui.card().classes("flex-1 min-w-[250px] p-6"):
                ui.label(name).classes(
                    "text-xl font-bold text-[var(--muted)] uppercase tracking-wide"
                )
                ui.label(f"{latest_val} {unit}").style(f"color: {color}").classes(
                    "text-5xl font-bold mt-2 leading-none"
                )


def render_collect_card(sensor_type):
    is_th = sensor_type == "temphum"
    title = f"Data Collection ({'Temp/Hum' if is_th else 'Gas'})"
    endpoint = "/cth" if is_th else "/cgas"
    data_key, stats_key = (
        ("temphum_data", "temphum_stats") if is_th else ("gas_data", "gas_stats")
    )
    metrics = (
        [
            {"col": "temp", "title": "Temperature", "color": "#58A6FF", "unit": "°C"},
            {"col": "hum", "title": "Humidity", "color": "#3FB950", "unit": "%"},
        ]
        if is_th
        else [
            {"col": "gas", "title": "Gas Readings", "color": "#D29922", "unit": "ppm"}
        ]
    )

    with ui.card().classes("w-full p-6"):
        ui.label(title).classes("text-2xl font-bold mb-6 text-[var(--text)]")
        with ui.row().classes("w-full items-center gap-8"):
            duration = (
                ui.number(label="Duration (s)", value=30, min=5, step=1)
                .classes("w-48 text-base")
                .props("dark outlined")
            )
            interval = (
                ui.number(label="Interval (s)", value=5, min=1, step=1)
                .classes("w-48 text-base")
                .props("dark outlined")
            )
            btn = ui.button("Start Cloud Collection").classes(
                "custom-button w-48 h-12 text-lg"
            )

            async def start_collection():
                btn.disable()
                btn.text = "Dispatching to Edge..."
                try:
                    async with httpx.AsyncClient() as client:
                        resp = await client.post(
                            f"{BASE_URL}{endpoint}",
                            json={
                                "duration": duration.value,
                                "interval": interval.value,
                            },
                            timeout=10,
                        )
                        resp.raise_for_status()
                        task_id = resp.json()["task_id"]
                        btn.text = "Edge Collecting..."
                        while True:
                            await asyncio.sleep(2)
                            status_resp = await client.get(
                                f"{BASE_URL}/task/{task_id}", timeout=10
                            )
                            task_status = status_resp.json()
                            if task_status["status"] == "completed":
                                result_data = (
                                    json.loads(task_status["result"])
                                    if isinstance(task_status["result"], str)
                                    else task_status["result"]
                                )
                                app.storage.user[data_key] = result_data["samples"]
                                app.storage.user[stats_key] = result_data["stats"]
                                ui.notify("Collection completed", type="positive")
                                break
                            elif task_status["status"] == "error":
                                raise Exception(
                                    task_status.get("error", "Edge task failed")
                                )
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
            if not data:
                return
            df = pd.DataFrame(data)
            with results_container:
                for m in metrics:
                    if m["col"] in df.columns:
                        with ui.card().classes("w-full p-4 mb-6"):
                            ui.label(m["title"]).classes(
                                "text-2xl font-bold mb-4 text-[var(--text)]"
                            )
                            edge_stats = app.storage.user.get(stats_key, {}) or {}
                            col_stats = edge_stats.get(m["col"], {})
                            with ui.row().classes(
                                "w-full justify-around mb-4 p-3 bg-[var(--bg-secondary)] rounded-lg"
                            ):
                                for stat_name, label in [
                                    ("min", "Min"),
                                    ("max", "Max"),
                                    ("avg", "Avg"),
                                ]:
                                    val = col_stats.get(stat_name, 0)
                                    with ui.column().classes("items-center"):
                                        ui.label(f"{val:.2f} {m['unit']}").classes(
                                            "text-xl font-bold text-[var(--text)]"
                                        )
                                        ui.label(label).classes("metric-label")
                            with ui.row().classes("w-full gap-6 items-start"):
                                with ui.column().classes("flex-1"):
                                    ui.table.from_pandas(
                                        df[["timestamp", m["col"]]]
                                    ).props("dark flat").classes("w-full text-base")
                                with ui.column().classes("flex-1"):
                                    render_plot(
                                        df["timestamp"],
                                        df[m["col"]],
                                        m["title"],
                                        m["color"],
                                    )

        refresh_results()


@ui.page("/")
def index():
    for k in [
        "temp_log",
        "hum_log",
        "gas_log",
        "temphum_data",
        "gas_data",
        "temphum_stats",
        "gas_stats",
    ]:
        app.storage.user.setdefault(k, [] if k.endswith("_log") else None)

    with ui.header().classes("h-25 items-center px-6"):
        ui.label("Polling Architecture Dashboard").classes(
            "text-3xl font-bold text-[var(--text)]"
        )
        ui.space()
        ui.input(value=BASE_URL, label="Cloud API URL").classes("w-80 text-base").props(
            "dark outlined bg-color=#1E2329"
        )

    main_container = ui.column().classes("w-full p-8 gap-8 max-w-7xl mx-auto")
    with main_container:
        content = ui.column().classes("w-full gap-8")

    with ui.left_drawer(value=True).classes("p-4").props("width=250 elevated"):
        ui.label("Navigation").classes("text-xl font-bold mb-6 text-[var(--text)] px-2")

        def render_content(page_key):
            content.clear()
            with content:
                if page_key == "overview":
                    render_overview()
                elif page_key == "th_range":
                    render_collect_card("temphum")
                elif page_key == "gas_range":
                    render_collect_card("gas")

        menu_items = [
            ("Overview", "overview"),
            ("Temp/Hum Range", "th_range"),
            ("Gas Range", "gas_range"),
        ]
        for label, key in menu_items:
            ui.button(label, on_click=lambda k=key: render_content(k)).classes(
                "w-full justify-start bg-transparent text-[var(--muted)] mb-2 h-10 text-left text-base"
            )
    render_content("overview")


ui.run(title="Polling Dashboard", dark=True, storage_secret="polling-secret", port=8081)
