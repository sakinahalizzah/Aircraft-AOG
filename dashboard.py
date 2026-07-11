import streamlit as st
import pandas as pd

st.set_page_config(
    page_title="Aircraft Fleet Dashboard",
    layout="wide"
)

# Read latest CSV every run
df = pd.read_csv("aircraft_status_summary.csv")

st.title("✈️ Aircraft Fleet Dashboard")

# KPI
col1, col2, col3, col4 = st.columns(4)

col1.metric("Fleet Size", len(df))
col2.metric("🟢 Active", (df["status"] == "🟢 Active").sum())
col3.metric("🟡 Idle", (df["status"] == "🟡 Idle (T+3)").sum())
col4.metric("🔴 Grounded", (df["status"] == "🔴 Grounded (T+7)").sum())

st.divider()

# Filter
status = st.multiselect(
    "Status",
    df["status"].unique(),
    default=df["status"].unique()
)

filtered = df[df["status"].isin(status)]

st.dataframe(
    filtered,
    use_container_width=True
)