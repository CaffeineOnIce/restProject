import asyncio
from datetime import datetime
import pandas as pd
import httpx
import matplotlib.pyplot as plt
from nicegui import ui, app, background_tasks

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

BASE_URL = "https://restapi.shares.zrok.io"

ui.add_css(
    """
:root { --bg: #0F1419; --bg-secondary: #1E2329; --card: #161B22; --border: rgba(255,255,255,0.08); --text: #E6EDF3; --muted: #8B949E; --primary: #F3EFE0; }
body { background-color: var(--bg) !important; color: var(--text) !important; font-family: system-ui, sans-serif; font-size: 16px; }
.nicegui-content { background: linear-gradient(180deg, #0F1419 0%, #161B22 100%); min-height: 100vh; }
.q-field--outlined .q-field__control {
    background-color: var(--bg-secondary) !important;
    border-radius: 8px !important;
}
.q-drawer { background-color: var(--bg-secondary) !important; border-right: 1px solid var(--border) !important; }
.q-header { background-color: var(--bg) !important; border-bottom: 1px solid var(--border) !important; color: var(--text) !important; }
.q-card { background-color: var(--card) !important; border: 1px solid var(--border) !important; color: var(--text) !important; box-shadow: none !important; border-radius: 12px !important; }
.q-table { background-color: transparent !important; color: var(--text) !important; }
.q-table th, .q-table td { border-bottom: 1px solid var(--border) !important; }
.q-table th { color: var(--muted) !important; font-weight: 600 !important; font-size: 1rem !important; }
.q-separator { background-color: var(--border) !important; }
.metric-label { color: var(--muted); font-size: 0.95rem; text-transform: uppercase; letter-spacing: 0.5px; margin-top: 4px; }
.custom-button { background-color: var(--primary) !important; color: #0F1419 !important; font-weight: 600; border-radius: 8px !important; text-transform: none !important; font-size: 1.05rem !important; transition: all 0.2s ease; }
.custom-button:hover { background-color: #e5e1d1 !important; transform: translateY(-1px); }
""",
    shared=True,
)


# --- Helpers ---
async def check_health(timeout=5):
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{BASE_URL}/health", timeout=timeout)
            return True, resp.json().get("status") == "ok"
    except Exception:
        return False, "offline"


async def check_esp(timeout=5):
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{BASE_URL}/temphum", timeout=timeout)
            return True
    except Exception:
        return False


async def fetch_sensor(endpoint, field, timeout=20):
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{BASE_URL}{endpoint}", timeout=timeout)
        resp.raise_for_status()
        val = resp.json().get(field)
        if val is None:
            raise ValueError(resp.json().get("error_msg", "Sensor unavailable"))
        return float(val)


def init_storage():
    for k in [
        "temp_log",
        "hum_log",
        "gas_log",
        "temphum_data",
        "gas_data",
        "temphum_exp",
        "gas_exp",
    ]:
        app.storage.user.setdefault(k, [] if k.endswith("_log") else None)


# --- Unified Plot Helper ---
def render_plot(x, y, title, color, rotation=90, bottom_margin=None):
    plot = ui.matplotlib(figsize=(6, 4)).classes("w-full h-106")
    with plot.figure as fig:
        ax = fig.gca()
        ax.plot(x, y, marker="o", linestyle="-", color=color)
        ax.set_title(title, fontsize=12)
        if rotation:
            ax.tick_params(axis="x", rotation=rotation)
        if bottom_margin:
            fig.subplots_adjust(bottom=bottom_margin, left=0.12, right=0.95, top=0.90)


# --- UI Components ---
def render_status_header():
    with ui.row().classes("w-full justify-between items-center mb-8"):
        ui.label("Dashboard").classes("text-3xl font-bold m-0 text-[var(--text)]")
        with ui.row().classes(
            "items-center gap-3 px-4 py-2 bg-[var(--card)] border border-[var(--border)] rounded-lg"
        ):
            status_dot = ui.element("div").classes("w-3 h-3 rounded-full")
            status_text = ui.label("Checking...").classes(
                "text-[var(--text)] font-medium text-base"
            )

            async def update_status():
                rasp_ok, _ = await check_health()
                esp_ok = await check_esp()
                ok = rasp_ok and esp_ok
                color = "#2ea043" if ok else "#f85149"
                status_dot.style(
                    f"background-color: {color}; box-shadow: 0 0 8px {color}"
                )
                status_text.set_text("Online" if ok else "Offline")

            ui.timer(5, update_status)
            background_tasks.create(update_status())


def render_fetch_card(name, endpoint, field, unit, log_key):
    with ui.card().classes("w-full p-6"):
        ui.label(name).classes("text-xl font-bold mb-6 text-[var(--text)]")
        with ui.row().classes("w-full items-start gap-8"):
            with ui.column().classes("flex-1"):
                btn = ui.button(f"Fetch {name}").classes(
                    "custom-button w-full h-12 text-lg"
                )

                async def on_fetch():
                    btn.disable()
                    btn.text = f"Fetching {name}..."
                    try:
                        val = await fetch_sensor(endpoint, field)
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
                    finally:
                        btn.enable()
                        btn.text = f"Fetch {name}"
                        refresh_display()

                btn.on_click(on_fetch)
            with ui.column().classes("flex-1 items-end"):
                metric_label = ui.label("—").classes(
                    "text-3xl font-bold text-[var(--text)] leading-none"
                )
                ui.label(unit).classes("metric-label mt-2")

        container = ui.column().classes("w-full mt-8")

        def refresh_display():
            container.clear()
            logs = app.storage.user[log_key]
            if not logs:
                with container:
                    ui.label("No readings collected yet.").classes(
                        "text-[var(--muted)] text-base italic"
                    )
                metric_label.set_text("—")
                return

            metric_label.set_text(
                f"{logs[0]['Value']:.2f}" if logs[0]["Status"] == "Completed" else "Err"
            )
            if logs[0]["Status"] == "Failed" and logs[0]["Error"]:
                ui.notify(logs[0]["Error"], type="negative")

            with container:
                if logs[0]["Status"] == "Failed":
                    ui.label(logs[0]["Error"]).classes(
                        "text-red-400 text-base mb-4 bg-red-900/20 p-3 rounded border border-red-900/50 w-full"
                    )

                valid_logs = [r for r in logs if r["Status"] == "Completed"]
                cols = ["Time", "Value", "Status"] + (
                    ["Error"] if any(r["Error"] for r in logs) else []
                )

                with ui.row().classes("w-full gap-6 items-start"):
                    with ui.column().classes("flex-1"):
                        ui.table.from_pandas(pd.DataFrame(logs[:20])[cols]).props(
                            "dark flat"
                        ).classes("w-full text-base")
                    with ui.column().classes("flex-1"):
                        if valid_logs:
                            chart_df = pd.DataFrame(valid_logs)[::-1].set_index("Time")[
                                ["Value"]
                            ]
                            render_plot(
                                chart_df.index,
                                chart_df["Value"],
                                name,
                                "#F3EFE0",
                                rotation=90,
                                bottom_margin=0.20,
                            )

        refresh_display()


def render_collect_card(sensor_type):
    is_th = sensor_type == "temphum"
    title = "Data Collection (Temp/Hum)" if is_th else "Data Collection (Gas)"
    endpoint = "/ctemphum" if is_th else "/cgas"
    data_key, exp_key = (
        ("temphum_data", "temphum_exp") if is_th else ("gas_data", "gas_exp")
    )

    metrics = (
        [
            {"col": "temp", "title": "Temperature", "color": "#58A6FF", "unit": "°C"},
            {"col": "hum", "title": "Humidity", "color": "#3FB950", "unit": "%"},
        ]
        if is_th
        else [
            {"col": "gas", "title": "Gas Readings", "color": "#D29922", "unit": " ppm"}
        ]
    )

    with ui.card().classes("w-full p-6"):
        ui.label(title).classes("text-xl font-bold mb-6 text-[var(--text)]")
        with ui.row().classes("w-full items-center gap-8"):
            with ui.column().classes("gap-4"):
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

            def calc_expected():
                return max(1, int((duration.value or 30) // (interval.value or 5)))

            with ui.row().classes("flex-1 justify-around items-center"):
                with ui.column().classes("items-center"):
                    expected_lbl = ui.label(str(calc_expected())).classes(
                        "text-2xl font-bold text-[var(--text)]"
                    )
                    ui.label("Expected Samples").classes("metric-label")
                with ui.column().classes("items-center"):
                    freq_lbl = ui.label(f"{int(interval.value)}s").classes(
                        "text-2xl font-bold text-[var(--text)]"
                    )
                    ui.label("Frequency").classes("metric-label")
                with ui.column().classes("items-center"):
                    runtime_lbl = ui.label(f"{int(duration.value)}s").classes(
                        "text-2xl font-bold text-[var(--text)]"
                    )
                    ui.label("Runtime").classes("metric-label")

            with ui.column().classes("items-center"):
                btn = ui.button("Start Collection").classes(
                    "custom-button w-48 h-12 text-lg"
                )

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
                        resp = await client.post(
                            f"{BASE_URL}{endpoint}",
                            json={
                                "duration": duration.value,
                                "interval": interval.value,
                            },
                            timeout=10,
                        )
                        resp.raise_for_status()
                        start_data = resp.json()
                        if start_data.get("status") != "started":
                            raise Exception(start_data.get("error", "Failed"))
                        task_id = start_data["task_id"]
                        btn.text = "Collecting..."
                        while True:
                            await asyncio.sleep(2)
                            status_resp = await client.get(
                                f"{BASE_URL}/task/{task_id}", timeout=10
                            )
                            status_resp.raise_for_status()
                            task_status = status_resp.json()
                            if task_status["status"] == "completed":
                                app.storage.user[data_key] = task_status["result"]
                                app.storage.user[exp_key] = calc_expected()
                                ui.notify(
                                    f"Collection completed ({len(task_status['result'])} samples)",
                                    type="positive",
                                )
                                break
                            elif task_status["status"] == "error":
                                raise Exception(
                                    task_status.get("error", "Background task failed")
                                )
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
            if not data:
                return

            df = pd.DataFrame(data)
            actual, rate = len(df), (len(df) / expected * 100) if expected else 0

            with results_container:
                ui.separator().classes("bg-[var(--border)] mb-6")
                with ui.row().classes("w-full justify-center gap-16 mb-6"):
                    for val, lbl in [
                        (str(actual), "Actual Samples"),
                        (f"{rate:.0f}%", "Success Rate"),
                    ]:
                        with ui.column().classes("items-center"):
                            ui.label(val).classes(
                                "text-2xl font-bold text-[var(--text)]"
                            )
                            ui.label(lbl).classes("metric-label")
                ui.separator().classes("bg-[var(--border)] my-6")

                for m in metrics:
                    if m["col"] in df.columns:
                        with ui.card().classes("w-full p-4 mb-6"):
                            ui.label(m["title"]).classes(
                                "text-xl font-bold mb-4 text-[var(--text)]"
                            )
                            with ui.row().classes(
                                "w-full justify-around mb-4 p-3 bg-[var(--bg-secondary)] rounded-lg"
                            ):
                                for stat, val in [
                                    ("Min", df[m["col"]].min()),
                                    ("Max", df[m["col"]].max()),
                                    ("Avg", df[m["col"]].mean()),
                                ]:
                                    with ui.column().classes("items-center"):
                                        ui.label(f"{val:.2f}{m['unit']}").classes(
                                            "text-xl font-bold text-[var(--text)]"
                                        )
                                        ui.label(stat).classes("metric-label")
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


# --- Main Layout ---
@ui.page("/")
def index():
    init_storage()
    with ui.header().classes("h-20 items-center px-6"):
        ui.label("Sensor Dashboard").classes("text-2xl font-bold text-[var(--text)]")
        ui.space()

        def update_base_url(e):
            global BASE_URL
            BASE_URL = e.value.rstrip("/")

        ui.input(value=BASE_URL, label="API Base URL").classes("w-80 text-base").props(
            "dark outlined bg-color=#1E2329"
        ).on_value_change(update_base_url)

    main_container = ui.column().classes("w-full p-8 gap-8 max-w-7xl mx-auto")
    with main_container:
        render_status_header()
        content = ui.column().classes("w-full gap-8")

    with ui.left_drawer(value=True).classes("p-4").props("width=250 elevated"):
        ui.label("Navigation").classes("text-lg font-bold mb-6 text-[var(--text)] px-2")

        cards_config = {
            "temp": ("Temperature", "/temphum", "temp", "°C", "temp_log"),
            "hum": ("Humidity", "/temphum", "hum", "%", "hum_log"),
            "gas": ("Gas", "/gas", "gas", "ppm", "gas_log"),
        }

        nav_buttons = {}

        def render_content(page_key):
            # 1. Highlight the selected tab with a subtle dark grey
            for key, btn in nav_buttons.items():
                if key == page_key:
                    # Selected state: Slight dark grey background, normal text, medium weight
                    btn.classes(remove="bg-transparent text-[var(--muted)]")
                    btn.classes(add="bg-[#252A31] text-[var(--text)] font-medium")
                else:
                    # Unselected state: Transparent, muted text
                    btn.classes(remove="bg-[#252A31] font-medium")
                    btn.classes(add="bg-transparent text-[var(--muted)]")

            # 2. Render the page content
            content.clear()
            with content:
                if page_key == "overview":
                    with ui.row().classes("w-full gap-6 flex-wrap"):
                        for key in ["temp", "hum", "gas"]:
                            render_fetch_card(*cards_config[key])
                elif page_key in cards_config:
                    render_fetch_card(*cards_config[page_key])
                elif page_key == "th_range":
                    render_collect_card("temphum")
                elif page_key == "gas_range":
                    render_collect_card("gas")

        menu_items = [
            ("Overview", "overview"),
            ("Temperature", "temp"),
            ("Humidity", "hum"),
            ("Gas", "gas"),
            ("Temp/Hum Range", "th_range"),
            ("Gas Range", "gas_range"),
        ]

        for label, key in menu_items:
            btn = ui.button(label, on_click=lambda k=key: render_content(k))
            # Set initial unselected classes (muted text, transparent bg)
            btn.classes(
                "w-full justify-start bg-transparent text-[var(--muted)] mb-2 h-10 text-left text-base"
            )
            nav_buttons[key] = btn

    # Initial render
    render_content("overview")


ui.run(title="Sensor Dashboard", dark=True, storage_secret="my-secret-key", port=8081)
