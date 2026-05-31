import streamlit as st
import requests
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Sensor Dashboard", layout="wide")

st.markdown(
    """
    <style>
    :root{--bg:#111318;--border:rgba(255,255,255,.08);--text:#e8edf2;--muted:#a7b0bc;}
    html,body,[class*="css"]{background:var(--bg)!important;color:var(--text)!important;font-size:17px;}
    .stApp{background:linear-gradient(180deg,#111318 0%,#0f1217 100%);}
    section[data-testid="stSidebar"]{background:#0f1217;border-right:1px solid var(--border);}
    .block-container{padding-top:1.2rem;}
    .card{background:rgba(23,27,34,.88);border:1px solid var(--border);border-radius:18px;padding:18px;margin-bottom:16px;}
    .card-title{font-size:1.35rem;font-weight:700;}
    .card-subtitle{color:var(--muted);font-size:.95rem;margin-top:2px;}
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🌡️ Sensor Dashboard")

BASE_URL = st.sidebar.text_input("Base URL", "https://restapi.shares.zrok.io").rstrip(
    "/"
)

SENSORS = {
    "Temperature": {
        "endpoint": "/temphum",
        "field": "temp",
        "unit": "°C",
        "collect": "/ctemp",
    },
    "Humidity": {
        "endpoint": "/temphum",
        "field": "hum",
        "unit": "%",
        "collect": "/chum",
    },
    "Gas": {"endpoint": "/gas", "field": "gas", "unit": "ppm", "collect": "/cgas"},
}

st.session_state.setdefault("log", [])


def fetch_sensor(endpoint, field, timeout=20):
    resp = requests.get(f"{BASE_URL}{endpoint}", timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    value = data.get(field)
    if value is None:
        raise ValueError(data.get("error_msg", "Sensor unavailable"))
    return float(value)


def render_fetch(name, cfg):
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown(
        f'<div class="card-title">📥 Fetch {name}</div>', unsafe_allow_html=True
    )

    col1, col2 = st.columns([3, 1])
    with col1:
        if st.button(f"Fetch {name}", key=f"btn_{name}", use_container_width=True):
            try:
                val = fetch_sensor(cfg["endpoint"], cfg["field"])
                st.session_state["log"].insert(
                    0,
                    {
                        "Time": datetime.now().strftime("%H:%M:%S"),
                        "Value": val,
                        "Status": "OK",
                    },
                )
            except Exception as e:
                st.session_state["log"].insert(
                    0,
                    {
                        "Time": datetime.now().strftime("%H:%M:%S"),
                        "Value": None,
                        "Status": "Error",
                        "Msg": str(e),
                    },
                )
            st.rerun()

    with col2:
        if st.session_state["log"] and st.session_state["log"][0]["Status"] == "OK":
            st.metric(name, f"{st.session_state['log'][0]['Value']:.2f} {cfg['unit']}")
        else:
            st.metric(name, "—")

    if st.session_state["log"]:
        if st.session_state["log"][0]["Status"] == "Error":
            st.error(st.session_state["log"][0].get("Msg", ""))

        valid = [r for r in st.session_state["log"] if r["Status"] == "OK"]
        if valid:
            st.line_chart(
                pd.DataFrame(valid[::-1]).set_index("Time")[["Value"]],
                use_container_width=True,
            )

        st.dataframe(
            pd.DataFrame(st.session_state["log"][:10]),
            use_container_width=True,
            hide_index=True,
        )

    st.markdown("</div>", unsafe_allow_html=True)


def render_collect(name, cfg):
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown(
        f'<div class="card-title">📊 Collect {name}</div>', unsafe_allow_html=True
    )

    col1, col2 = st.columns(2)
    with col1:
        duration = st.number_input(
            "Duration (s)", min_value=5, value=30, step=5, key=f"dur_{name}"
        )
    with col2:
        interval = st.number_input(
            "Interval (s)", min_value=1, value=5, step=1, key=f"int_{name}"
        )

    if st.button(f"▶ Start", key=f"collect_{name}", use_container_width=True):
        with st.spinner(f"Collecting {name.lower()}..."):
            try:
                resp = requests.post(
                    f"{BASE_URL}{cfg['collect']}",
                    json={"duration": duration, "interval": interval},
                    timeout=duration + 300,
                )
                resp.raise_for_status()
                data = resp.json()

                st.success(f"✅ {len(data)} samples")
                if data:
                    df = pd.DataFrame(data)
                    st.metric(
                        "Average",
                        f"{df['value'].mean():.2f}" if "value" in df.columns else "N/A",
                    )
                    st.dataframe(
                        df.style.format({"value": "{:.2f}"}),
                        use_container_width=True,
                        hide_index=True,
                    )
                    if "timestamp" in df.columns:
                        st.line_chart(
                            df.set_index("timestamp")["value"], use_container_width=True
                        )
            except Exception as e:
                st.error(f"❌ {str(e)}")

    st.markdown("</div>", unsafe_allow_html=True)


page = st.sidebar.radio(
    "Navigation",
    [
        "Fetch Temp",
        "Fetch Humidity",
        "Fetch Gas",
        "Collect Temp",
        "Collect Humidity",
        "Collect Gas",
    ],
)

if page == "Fetch Temp":
    render_fetch("Temperature", SENSORS["Temperature"])
elif page == "Fetch Humidity":
    render_fetch("Humidity", SENSORS["Humidity"])
elif page == "Fetch Gas":
    render_fetch("Gas", SENSORS["Gas"])
elif page == "Collect Temp":
    render_collect("Temperature", SENSORS["Temperature"])
elif page == "Collect Humidity":
    render_collect("Humidity", SENSORS["Humidity"])
elif page == "Collect Gas":
    render_collect("Gas", SENSORS["Gas"])
