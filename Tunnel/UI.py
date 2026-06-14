from datetime import datetime

import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="Sensor Dashboard", layout="wide")

st.markdown(
    """
    <style>
    :root {
        --bg: #0F1419;
        --bg-secondary: #1E2329;
        --card: #161B22;
        --border: rgba(255,255,255,0.08);
        --text: #E6EDF3;
        --muted: #8B949E;
    }
    html, body, [class*="css"] {
        background: var(--bg) !important;
        color: var(--text) !important;
        font-size: 17px;
    }
    .stApp {
        background: linear-gradient(180deg, #0F1419 0%, #161B22 100%);
    }
    section[data-testid="stSidebar"] {
        background: var(--bg-secondary);
        border-right: 1px solid var(--border);
    }
    .block-container {
        padding-top: 1.2rem;
    }
    .card-title {
        font-size: 1.35rem;
        font-weight: 700;
    }
    .big-metric {
        font-size: 2.5rem;
        font-weight: 800;
        line-height: 1;
    }
    .metric-label {
        color: var(--muted);
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-top: 4px;
    }
    .stButton > button[kind="primary"] {
        background: #F3EFE0 !important;
        border-color: #F3EFE0 !important;
        color: #0F1419 !important;
        font-weight: 600;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

BASE_URL = st.sidebar.text_input("Base URL", "https://restapi.shares.zrok.io").rstrip(
    "/"
)


def check_health(timeout=5):
    try:
        resp = requests.get(f"{BASE_URL}/health", timeout=timeout)
        resp.raise_for_status()
        return True, resp.json().get("status") == "ok"
    except:
        return False, "offline"


def check_esp(timeout=5):
    try:
        resp = requests.get(f"{BASE_URL}/temphum", timeout=timeout)
        resp.raise_for_status()
        return True
    except:
        return False


rasp_ok, _ = check_health()
esp_ok = check_esp()

system_ok = rasp_ok and esp_ok
status_color = "#2ea043" if system_ok else "#f85149"
status_text = "Online" if system_ok else "Offline"

st.markdown(
    f"""
    <div style="display:flex;justify-content:space-between;align-items:center;">
        <h1 style="margin:0;font-size:2.5rem;">Dashboard</h1>
        <div style="display:flex;align-items:center;gap:8px;font-size:14px;color:var(--text);">
            <div style="width:12px;height:12px;border-radius:50%;background:{status_color};box-shadow:0 0 8px {status_color};"></div>
            <span>{status_text}</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

for k in [
    "temp_log",
    "hum_log",
    "gas_log",
    "temphum_data",
    "gas_data",
    "temphum_exp",
    "gas_exp",
]:
    st.session_state.setdefault(k, [] if k.endswith("_log") else None)


def fetch_sensor(endpoint, field, timeout=20):
    resp = requests.get(f"{BASE_URL}{endpoint}", timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    val = data.get(field)
    if val is None:
        raise ValueError(data.get("error_msg", "Sensor unavailable"))
    return float(val)


def render_fetch_card(name, endpoint, field, unit, log_key):
    st.markdown(f'<div class="card-title">{name}</div>', unsafe_allow_html=True)
    left, right = st.columns([1, 1])
    with left:
        if st.button(
            f"Fetch {name}", key=f"btn_{name}", width="stretch", type="primary"
        ):
            with st.spinner(f"Fetching {name}..."):
                try:
                    val = fetch_sensor(endpoint, field)
                    st.session_state[log_key].insert(
                        0,
                        {
                            "Time": datetime.now().strftime("%H:%M:%S"),
                            "Value": val,
                            "Status": "Completed",
                            "Error": "",
                        },
                    )
                except Exception as e:
                    st.session_state[log_key].insert(
                        0,
                        {
                            "Time": datetime.now().strftime("%H:%M:%S"),
                            "Value": None,
                            "Status": "Failed",
                            "Error": str(e),
                        },
                    )
            st.rerun()
    with right:
        logs = st.session_state[log_key]
        if logs and logs[0]["Status"] == "Completed":
            st.metric(
                name, f"{logs[0]['Value']:.2f} {unit}", label_visibility="collapsed"
            )
        else:
            st.metric(name, "—", label_visibility="collapsed")

    logs = st.session_state[log_key]
    if logs:
        if logs[0]["Status"] == "Failed":
            st.error(logs[0]["Error"])
        valid = [r for r in logs if r["Status"] == "Completed"]
        cols = ["Time", "Value", "Status"] + (
            ["Error"] if any(r["Error"] for r in logs) else []
        )
        st.dataframe(
            pd.DataFrame(logs[:15])[cols].style.format({"Value": "{:.2f}"}, na_rep="—"),
            width="stretch",
            hide_index=True,
        )
        if valid:
            st.line_chart(
                pd.DataFrame(valid)[::-1].set_index("Time")[["Value"]], width="stretch"
            )
    else:
        st.info("No readings collected yet.")
    st.markdown("</div>", unsafe_allow_html=True)


def render_collect_temphum():
    st.markdown('<div class="card-title">Data Collection</div>', unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 3, 1])
    with col1:
        duration = st.number_input(
            "Duration (seconds)", min_value=5, value=30, step=5, key="dur_th"
        )
        interval = st.number_input(
            "Interval (seconds)", min_value=1, value=5, step=1, key="int_th"
        )
        expected = max(1, duration // interval)
    with col2:
        m1, m2, m3 = st.columns(3)
        with m1:
            st.markdown(
                f'<div class="big-metric" align="center">{expected}</div><div class="metric-label" align="center">Expected Samples</div>',
                unsafe_allow_html=True,
            )
        with m2:
            st.markdown(
                f'<div class="big-metric" align="center">{interval}s</div><div class="metric-label" align="center">Frequency</div>',
                unsafe_allow_html=True,
            )
        with m3:
            st.markdown(
                f'<div class="big-metric" align="center">{duration}s</div><div class="metric-label" align="center">Runtime</div>',
                unsafe_allow_html=True,
            )
    with col3:
        if st.button("Start Collection", key="btn_th", width="stretch", type="primary"):
            with st.spinner("Starting collection..."):
                try:
                    resp = requests.post(
                        f"{BASE_URL}/ctemphum",
                        json={"duration": duration, "interval": interval},
                        timeout=duration + 10000,
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    st.session_state["temphum_data"] = data
                    st.session_state["temphum_exp"] = expected
                    st.success(f"Collection completed ({len(data)} samples)")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

    data = st.session_state.get("temphum_data")
    expected = st.session_state.get("temphum_exp")
    if data and expected:
        df = pd.DataFrame(data)
        actual = len(df)
        rate = (actual / expected * 100) if expected else 0
        st.divider()
        am1, am2, am3 = st.columns(3)
        with am1:
            st.markdown(
                f'<div class="big-metric">{actual}</div><div class="metric-label">Actual Samples</div>',
                unsafe_allow_html=True,
            )
        with am2:
            st.markdown(
                f'<div class="big-metric">{rate:.0f}%</div><div class="metric-label">Success Rate</div>',
                unsafe_allow_html=True,
            )
        with am3:
            avg_t = f"{df['temp'].mean():.1f}°C" if "temp" in df.columns else "—"
            avg_h = f"{df['hum'].mean():.1f}%" if "hum" in df.columns else "—"
            st.markdown(
                f'<div class="big-metric">{avg_t} / {avg_h}</div><div class="metric-label">Avg Temp / Hum</div>',
                unsafe_allow_html=True,
            )
        st.divider()
        met1, met2 = st.columns(2)
        with met1:
            if "temp" in df.columns:
                st.subheader("Temperature")
                st.dataframe(
                    df[["timestamp", "temp"]].style.format({"temp": "{:.2f}"}),
                    width="stretch",
                    hide_index=True,
                )
                st.line_chart(df.set_index("timestamp")["temp"], width="stretch")
        with met2:
            if "hum" in df.columns:
                st.subheader("Humidity")
                st.dataframe(
                    df[["timestamp", "hum"]].style.format({"hum": "{:.2f}"}),
                    width="stretch",
                    hide_index=True,
                )
                st.line_chart(df.set_index("timestamp")["hum"], width="stretch")
    st.markdown("</div>", unsafe_allow_html=True)


def render_collect_gas():
    st.markdown('<div class="card-title">Data Collection</div>', unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 3, 1])
    with col1:
        duration = st.number_input(
            "Duration (seconds)", min_value=5, value=60, step=5, key="dur_g"
        )
        interval = st.number_input(
            "Interval (seconds)", min_value=1, value=5, step=1, key="int_g"
        )
        expected = max(1, duration // interval)
    with col2:
        m1, m2, m3 = st.columns(3)
        with m1:
            st.markdown(
                f'<div class="big-metric" align="center">{expected}</div><div class="metric-label" align="center">Expected Samples</div>',
                unsafe_allow_html=True,
            )
        with m2:
            st.markdown(
                f'<div class="big-metric" align="center">{interval}s</div><div class="metric-label" align="center">Frequency</div>',
                unsafe_allow_html=True,
            )
        with m3:
            st.markdown(
                f'<div class="big-metric" align="center">{duration}s</div><div class="metric-label" align="center">Runtime</div>',
                unsafe_allow_html=True,
            )
    with col3:
        if st.button("Start Collection", key="btn_g", width="stretch", type="primary"):
            with st.spinner("Starting collection..."):
                try:
                    resp = requests.post(
                        f"{BASE_URL}/cgas",
                        json={"duration": duration, "interval": interval},
                        timeout=duration + 10000,
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    st.session_state["gas_data"] = data
                    st.session_state["gas_exp"] = expected
                    st.success(f"Collection completed ({len(data)} samples)")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

    data = st.session_state.get("gas_data")
    expected = st.session_state.get("gas_exp")
    if data and expected:
        df = pd.DataFrame(data)
        actual = len(df)
        rate = (actual / expected * 100) if expected else 0
        st.divider()
        am1, am2, am3 = st.columns(3)
        with am1:
            st.markdown(
                f'<div class="big-metric">{actual}</div><div class="metric-label">Actual Samples</div>',
                unsafe_allow_html=True,
            )
        with am2:
            st.markdown(
                f'<div class="big-metric">{rate:.0f}%</div><div class="metric-label">Success Rate</div>',
                unsafe_allow_html=True,
            )
        with am3:
            avg = f"{df['gas'].mean():.1f} ppm" if "gas" in df.columns else "—"
            st.markdown(
                f'<div class="big-metric">{avg}</div><div class="metric-label">Average Gas</div>',
                unsafe_allow_html=True,
            )
        st.divider()
        if "gas" in df.columns:
            st.dataframe(
                df[["timestamp", "gas"]].style.format({"gas": "{:.2f}"}),
                width="stretch",
                hide_index=True,
            )
            st.line_chart(df.set_index("timestamp")["gas"], width="stretch")
    st.markdown("</div>", unsafe_allow_html=True)


page = st.sidebar.radio(
    "Navigation",
    ["Overview", "Temperature", "Humidity", "Gas", "Temp/Hum Range", "Gas Range"],
)

if page == "Overview":
    render_fetch_card("Temperature", "/temphum", "temp", "°C", "temp_log")
    render_fetch_card("Humidity", "/temphum", "hum", "%", "hum_log")
    render_fetch_card("Gas", "/gas", "gas", "ppm", "gas_log")
elif page == "Temperature":
    render_fetch_card("Temperature", "/temphum", "temp", "°C", "temp_log")
elif page == "Humidity":
    render_fetch_card("Humidity", "/temphum", "hum", "%", "hum_log")
elif page == "Gas":
    render_fetch_card("Gas", "/gas", "gas", "ppm", "gas_log")
elif page == "Temp/Hum Range":
    render_collect_temphum()
elif page == "Gas Range":
    render_collect_gas()
