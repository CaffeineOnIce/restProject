import streamlit as st
import requests
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Sensor Dashboard", layout="wide")

st.markdown(
    """
    <style>
    :root{
        --bg:#111318;
        --border:rgba(255,255,255,.08);
        --text:#e8edf2;
        --muted:#a7b0bc;
    }
    html,body,[class*="css"]{
        background:var(--bg)!important;
        color:var(--text)!important;
        font-size:17px;
    }
    .stApp{
        background:linear-gradient(180deg,#111318 0%,#0f1217 100%);
    }
    section[data-testid="stSidebar"]{
        background:#0f1217;
        border-right:1px solid var(--border);
    }
    .block-container{
        padding-top:1.2rem;
    }
    .card{
        background:rgba(23,27,34,.88);
        border:1px solid var(--border);
        border-radius:18px;
        padding:18px;
        margin-bottom:16px;
    }
    .card-title{
        font-size:1.35rem;
        font-weight:700;
    }
    .card-subtitle{
        color:var(--muted);
        font-size:.95rem;
        margin-top:2px;
    }
    .big-metric{
        font-size:2.5rem;
        font-weight:800;
        line-height:1;
    }
    .metric-label{
        color:var(--muted);
        font-size:0.85rem;
        text-transform:uppercase;
        letter-spacing:0.5px;
        margin-top:4px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🌡️ Sensor Dashboard")
st.caption("Sensor monitoring and historical trends")

BASE_URL = st.sidebar.text_input("Base URL", "https://restapi.shares.zrok.io").rstrip(
    "/"
)

# Persistent state for all logs and collections
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
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown(
        f'<div class="card-title">{name}</div><div class="card-subtitle">Live readings, history and trends</div>',
        unsafe_allow_html=True,
    )

    left, right = st.columns([2, 1])
    with left:
        if st.button(f"📥 Fetch {name}", key=f"btn_{name}", use_container_width=True):
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
            st.metric(name, f"{logs[0]['Value']:.2f} {unit}")
        else:
            st.metric(name, "—")

    logs = st.session_state[log_key]
    if logs:
        if logs[0]["Status"] == "Failed":
            st.error(logs[0]["Error"])
        valid = [r for r in logs if r["Status"] == "Completed"]
        if valid:
            st.line_chart(
                pd.DataFrame(valid)[::-1].set_index("Time")[["Value"]],
                use_container_width=True,
            )
        cols = ["Time", "Value", "Status"] + (
            ["Error"] if any(r["Error"] for r in logs) else []
        )
        st.dataframe(
            pd.DataFrame(logs[:15])[cols].style.format({"Value": "{:.2f}"}, na_rep="—"),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No readings collected yet.")
    st.markdown("</div>", unsafe_allow_html=True)


def render_collect_temphum():
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown(
        '<div class="card-title">Data Collection</div><div class="card-subtitle">Schedule repeated sensor acquisition</div>',
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        duration = st.number_input(
            "Duration (seconds)", min_value=5, value=60, step=5, key="dur_th"
        )
    with col2:
        interval = st.number_input(
            "Interval (seconds)", min_value=1, value=5, step=1, key="int_th"
        )
    with col3:
        st.metric("Sensor", "Temp + Hum")

    expected = max(1, duration // interval)
    st.divider()

    m1, m2, m3 = st.columns(3)
    with m1:
        st.markdown(
            f'<div class="big-metric">{expected}</div><div class="metric-label">Expected Samples</div>',
            unsafe_allow_html=True,
        )
    with m2:
        st.markdown(
            f'<div class="big-metric">{interval}s</div><div class="metric-label">Frequency</div>',
            unsafe_allow_html=True,
        )
    with m3:
        st.markdown(
            f'<div class="big-metric">{duration}s</div><div class="metric-label">Runtime</div>',
            unsafe_allow_html=True,
        )

    st.divider()

    if st.button("▶ Start Collection", key="btn_th", use_container_width=True):
        with st.spinner("Starting collection..."):
            try:
                resp = requests.post(
                    f"{BASE_URL}/ctemphum",
                    json={"duration": duration, "interval": interval},
                    timeout=duration + 300,
                )
                resp.raise_for_status()
                data = resp.json()
                st.session_state["temphum_data"] = data
                st.session_state["temphum_exp"] = expected
                st.success(f"Collection completed ({len(data)} samples)")
                st.rerun()
            except Exception as e:
                st.error(str(e))

    data = st.session_state["temphum_data"]
    expected = st.session_state["temphum_exp"]
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
        if "temp" in df.columns:
            st.subheader("Temperature")
            st.line_chart(df.set_index("timestamp")["temp"], use_container_width=True)
            st.dataframe(
                df[["timestamp", "temp"]].style.format({"temp": "{:.2f}"}),
                use_container_width=True,
                hide_index=True,
            )
        if "hum" in df.columns:
            st.subheader("Humidity")
            st.line_chart(df.set_index("timestamp")["hum"], use_container_width=True)
            st.dataframe(
                df[["timestamp", "hum"]].style.format({"hum": "{:.2f}"}),
                use_container_width=True,
                hide_index=True,
            )

    st.markdown("</div>", unsafe_allow_html=True)


def render_collect_gas():
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown(
        '<div class="card-title">Data Collection</div><div class="card-subtitle">Schedule repeated sensor acquisition</div>',
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        duration = st.number_input(
            "Duration (seconds)", min_value=5, value=60, step=5, key="dur_g"
        )
    with col2:
        interval = st.number_input(
            "Interval (seconds)", min_value=1, value=5, step=1, key="int_g"
        )
    with col3:
        st.metric("Sensor", "Gas")

    expected = max(1, duration // interval)
    st.divider()

    m1, m2, m3 = st.columns(3)
    with m1:
        st.markdown(
            f'<div class="big-metric">{expected}</div><div class="metric-label">Expected Samples</div>',
            unsafe_allow_html=True,
        )
    with m2:
        st.markdown(
            f'<div class="big-metric">{interval}s</div><div class="metric-label">Frequency</div>',
            unsafe_allow_html=True,
        )
    with m3:
        st.markdown(
            f'<div class="big-metric">{duration}s</div><div class="metric-label">Runtime</div>',
            unsafe_allow_html=True,
        )

    st.divider()

    if st.button("▶ Start Collection", key="btn_g", use_container_width=True):
        with st.spinner("Starting collection..."):
            try:
                resp = requests.post(
                    f"{BASE_URL}/cgas",
                    json={"duration": duration, "interval": interval},
                    timeout=duration + 300,
                )
                resp.raise_for_status()
                data = resp.json()
                st.session_state["gas_data"] = data
                st.session_state["gas_exp"] = expected
                st.success(f"Collection completed ({len(data)} samples)")
                st.rerun()
            except Exception as e:
                st.error(str(e))

    data = st.session_state["gas_data"]
    expected = st.session_state["gas_exp"]
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
            st.line_chart(df.set_index("timestamp")["gas"], use_container_width=True)
            st.dataframe(
                df.style.format({"gas": "{:.2f}"}),
                use_container_width=True,
                hide_index=True,
            )

    st.markdown("</div>", unsafe_allow_html=True)


# Navigation
page = st.sidebar.radio(
    "Navigation",
    ["Overview", "Temperature", "Humidity", "Gas", "Collect Temp+Hum", "Collect Gas"],
)
st.sidebar.markdown("---")
st.sidebar.caption("All data persists across tabs")

if page == "Overview":
    c1, c2 = st.columns(2)
    with c1:
        render_fetch_card("Temperature", "/temphum", "temp", "°C", "temp_log")
    with c2:
        render_fetch_card("Humidity", "/temphum", "hum", "%", "hum_log")
    render_fetch_card("Gas", "/gas", "gas", "ppm", "gas_log")
elif page == "Temperature":
    render_fetch_card("Temperature", "/temphum", "temp", "°C", "temp_log")
elif page == "Humidity":
    render_fetch_card("Humidity", "/temphum", "hum", "%", "hum_log")
elif page == "Gas":
    render_fetch_card("Gas", "/gas", "gas", "ppm", "gas_log")
elif page == "Collect Temp+Hum":
    render_collect_temphum()
elif page == "Collect Gas":
    render_collect_gas()
