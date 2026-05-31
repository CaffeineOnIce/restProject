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
</style>
""",
    unsafe_allow_html=True,
)

st.title("🌡️ Sensor Dashboard")
st.caption("Sensor monitoring and historical trends")

BASE_URL = st.sidebar.text_input("Base URL", "https://restapi.shares.zrok.io").rstrip(
    "/"
)
SENSORS = {
    "Temperature": {
        "endpoint": "/temphum",
        "field": "temp",
        "label": "Temperature",
        "unit": "°C",
        "timeout": 20,
    },
    "Humidity": {
        "endpoint": "/temphum",
        "field": "hum",
        "label": "Humidity",
        "unit": "%",
        "timeout": 20,
    },
    "Gas": {
        "endpoint": "/gas",
        "field": "gas",
        "label": "Air Quality",
        "unit": "ppm",
        "timeout": 20,
    },
}

MAX_LOG = 15
for sensor in SENSORS:
    st.session_state.setdefault(f"{sensor}_log", [])


def status_style(value):
    if value == "Completed":
        return "background-color:rgba(46,204,113,.16); color:#66d18f; font-weight:700;"
    if value == "Failed":
        return "background-color:rgba(231,76,60,.16); color:#ff7b72; font-weight:700;"
    return ""


def fetch_sensor(cfg):
    response = requests.get(
        f"{BASE_URL}{cfg['endpoint']}",
        timeout=cfg["timeout"],
    )
    response.raise_for_status()
    data = response.json()
    value = data.get(cfg["field"])
    if value is None:
        raise ValueError(data.get("error_msg", "Sensor value unavailable"))
    return float(value)


def render_sensor(name):
    cfg = SENSORS[name]
    log_key = f"{name}_log"
    logs = st.session_state[log_key]

    st.markdown('<div class="card">', unsafe_allow_html=True)
    left, right = st.columns([2, 1])
    with left:
        st.markdown(
            f"""
            <div class="card-title">{name}</div>
            <div class="card-subtitle">
            Live readings, history and trends
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button(
            f"📥 Fetch {name}",
            key=f"btn_{name}",
            width="stretch",
        ):
            with st.spinner(f"Fetching {name.lower()} data..."):
                try:
                    logs.insert(
                        0,
                        {
                            "Time": datetime.now().strftime("%H:%M:%S"),
                            "Value": fetch_sensor(cfg),
                            "Status": "Completed",
                            "Error": "",
                        },
                    )
                except Exception as e:
                    logs.insert(
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
        if logs and logs[0]["Status"] == "Completed":
            st.metric(
                cfg["label"],
                f"{logs[0]['Value']:.2f} {cfg['unit']}",
            )
        else:
            st.metric(
                cfg["label"],
                "—",
            )

    if logs:
        latest = logs[0]
        if latest["Status"] == "Failed":
            st.error(latest["Error"])

        valid = [row for row in logs if row["Status"] == "Completed"]
        if valid:
            chart_df = pd.DataFrame(valid)[::-1].set_index("Time")[["Value"]]
            st.line_chart(
                chart_df,
                width="stretch",
            )

        columns = ["Time", "Value", "Status"]
        if any(row["Error"] for row in logs):
            columns.append("Error")

        df = pd.DataFrame(logs[:MAX_LOG])[columns]
        st.dataframe(
            df.style.map(status_style, subset=["Status"]).format(
                {"Value": "{:.2f}"},
                na_rep="—",
            ),
            width="stretch",
            hide_index=True,
        )
    else:
        st.info("No readings collected yet.")

    st.markdown("</div>", unsafe_allow_html=True)


def render_collection_module():
    st.markdown(
        '<div class="card">',
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <div class="card-title">
        Data Collection
        </div>
        <div class="card-subtitle">
        Schedule repeated sensor acquisition
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        sensor = st.selectbox(
            "Sensor",
            ["Temperature", "Humidity", "Gas"],
        )
    with col2:
        duration = st.number_input(
            "Duration (seconds)",
            min_value=5,
            value=60,
            step=5,
        )
    with col3:
        interval = st.number_input(
            "Interval (seconds)",
            min_value=1,
            value=5,
            step=1,
        )

    expected_samples = max(1, duration // interval)

    st.divider()
    m1, m2, m3 = st.columns(3)
    with m1:
        st.metric("Expected Samples", expected_samples)
    with m2:
        st.metric("Frequency", f"{interval}s")
    with m3:
        st.metric("Runtime", f"{duration}s")

    st.divider()
    routes = {
        "Temperature": "/collect/temp",
        "Humidity": "/collect/hum",
        "Gas": "/collect/gas",
    }

    if st.button(
        "▶ Start Collection",
        width="stretch",
    ):
        with st.spinner("Starting collection..."):
            try:
                response = requests.post(
                    f"{BASE_URL}{routes[sensor]}",
                    json={"duration": duration, "interval": interval},
                    timeout=duration + 300,
                )
                response.raise_for_status()
                result = response.json()
                st.success(f"Collection completed ({len(result)} samples)")
                if result:
                    df = pd.DataFrame(result)
                    st.dataframe(
                        df,
                        width="stretch",
                        hide_index=True,
                    )
            except Exception as e:
                st.error(str(e))

    st.markdown("</div>", unsafe_allow_html=True)


selection = st.sidebar.radio(
    "Navigation",
    ["Overview", *SENSORS.keys(), "Data Collection"],
)

st.sidebar.markdown("---")
st.sidebar.caption(f"{len(SENSORS)} active sensor modules")

if selection == "Overview":
    col1, col2 = st.columns(2)
    with col1:
        render_sensor("Temperature")
    with col2:
        render_sensor("Humidity")
    render_sensor("Gas")
elif selection == "Data Collection":
    render_collection_module()
else:
    render_sensor(selection)
