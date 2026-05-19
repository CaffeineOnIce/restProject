import streamlit as st
import requests
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Edge Sensors", layout="wide")
st.title("🌡️ Edge Sensor Dashboard")

BASE_URL = st.text_input("Zrok Endpoint", value="restapi.shares.zrok.io")

# Session State
if "temp_log" not in st.session_state:
    st.session_state.temp_log = []
if "gas_log" not in st.session_state:
    st.session_state.gas_log = []
MAX_LOG = 15

# Table Color
def style_status(val):
    if val == "Completed":
        return "background-color: rgba(40, 167, 69, 0.25); color: #28a745; font-weight: bold;"
    elif val == "Failed":
        return "background-color: rgba(220, 53, 69, 0.25); color: #dc3545; font-weight: bold;"
    return ""

# UI Section Components
def render_temp_hum_section(url):
    st.subheader("Temperature & Humidity")

    if st.button("📥 Fetch Data", key="btn_temp", width='stretch'):
        with st.spinner("Fetching from edge device..."):
            try:
                resp = requests.get(f"https://{url}/temphum", timeout=12)
                resp.raise_for_status()
                data = resp.json()

                if "temp" in data and "hum" in data and data["temp"] is not None:
                    entry = {
                        "Time": datetime.now().strftime("%H:%M:%S"),
                        "Temp (°C)": float(data["temp"]),
                        "Humidity (%)": float(data["hum"]),
                        "Status": "Completed",
                        "Error": "",
                    }
                else:
                    raise ValueError(
                        data.get("error_msg", "Insufficient sensor data gathered.")
                    )
            except Exception as e:
                entry = {
                    "Time": datetime.now().strftime("%H:%M:%S"),
                    "Temp (°C)": None,
                    "Humidity (%)": None,
                    "Status": "Failed",
                    "Error": str(e),
                }

            st.session_state.temp_log.insert(0, entry)

    if st.session_state.temp_log:
        latest = st.session_state.temp_log[0]
        if latest["Status"] == "Completed":
            m1, m2 = st.columns(2)
            m1.metric("Temperature", f"{latest['Temp (°C)']:.2f} °C")
            m2.metric("Humidity", f"{latest['Humidity (%)']:.2f} %")
        else:
            st.error(f"⚠️ Fetch Failed: {latest['Error']}")
    else:
        st.info("No data collected yet.")

    if st.session_state.temp_log:
        cols = ["Time", "Temp (°C)", "Humidity (%)", "Status"]
        if any(e["Error"] for e in st.session_state.temp_log):
            cols.append("Error")

        df = pd.DataFrame(st.session_state.temp_log)[cols].head(MAX_LOG)

        styled_df = df.style.map(style_status, subset=["Status"]).format(
            {"Temp (°C)": "{:.2f}", "Humidity (%)": "{:.2f}"}, na_rep="—"
        )
        st.dataframe(styled_df, width='stretch', hide_index=True)


def render_gas_section(url):
    st.subheader("Gas")

    if st.button("📥 Fetch Data", key="btn_gas", width='stretch'):
        with st.spinner("Measuring air quality..."):
            try:
                resp = requests.get(f"https://{url}/gas", timeout=12)
                resp.raise_for_status()
                data = resp.json()

                if "gas" in data and data["gas"] is not None:
                    entry = {
                        "Time": datetime.now().strftime("%H:%M:%S"),
                        "Gas (ppm)": float(data["gas"]),
                        "Status": "Completed",
                        "Error": "",
                    }
                else:
                    raise ValueError(
                        data.get("error_msg", "Insufficient sensor data gathered.")
                    )
            except Exception as e:
                entry = {
                    "Time": datetime.now().strftime("%H:%M:%S"),
                    "Gas (ppm)": None,
                    "Status": "Failed",
                    "Error": str(e),
                }

            st.session_state.gas_log.insert(0, entry)

    if st.session_state.gas_log:
        latest = st.session_state.gas_log[0]
        if latest["Status"] == "Completed":
            st.metric("Air Quality", f"{latest['Gas (ppm)']:.2f} ppm")
        else:
            st.error(f"⚠️ Fetch Failed: {latest['Error']}")
    else:
        st.info("No data collected yet.")

    if st.session_state.gas_log:
        cols = ["Time", "Gas (ppm)", "Status"]
        if any(e["Error"] for e in st.session_state.gas_log):
            cols.append("Error")

        df = pd.DataFrame(st.session_state.gas_log)[cols].head(MAX_LOG)

        styled_df = df.style.map(style_status, subset=["Status"]).format(
            {"Gas (ppm)": "{:.2f}"}, na_rep="—"
        )
        st.dataframe(styled_df, width='stretch', hide_index=True)

# Main Layout
col1, col2 = st.columns(2)

with col1:
    render_temp_hum_section(BASE_URL)

with col2:
    render_gas_section(BASE_URL)

st.markdown("---")

# Trend Charts
st.subheader("Trends")

valid_temp = [e for e in st.session_state.temp_log if e["Status"] == "Completed"]
valid_gas = [e for e in st.session_state.gas_log if e["Status"] == "Completed"]

if valid_temp or valid_gas:
    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        if valid_temp:
            df_temp_chart = pd.DataFrame(valid_temp)[::-1]
            df_temp_chart = df_temp_chart.set_index("Time")[
                ["Temp (°C)", "Humidity (%)"]
            ]
            st.line_chart(df_temp_chart)
        else:
            st.caption("Awaiting valid temperature readings to map timeline.")

    with chart_col2:
        if valid_gas:
            df_gas_chart = pd.DataFrame(valid_gas)[::-1]
            df_gas_chart = df_gas_chart.set_index("Time")[["Gas (ppm)"]]
            st.line_chart(df_gas_chart)
        else:
            st.caption("Awaiting valid gas readings to map timeline.")
else:
    st.info(
        "No timeline metrics plotted yet."
    )
