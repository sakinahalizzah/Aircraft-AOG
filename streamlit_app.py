"""
streamlit_app.py
AirAsia Group AOG Tracker — Streamlit dashboard.

Reads everything from GitHub (no file upload widgets):
    - aog_history.csv              -> trend chart
    - history/snapshot_*.csv (latest) -> per-tail status, summary cards, breakdowns
    - fleet.csv                    -> registration/operator/model reference
    - klia_snapshot_*.csv (latest, optional) -> KLIA live traffic panel

Configure the repo location and (for private repos) a token in
.streamlit/secrets.toml — see secrets.toml.example in this folder.
Nothing about the repo is hardcoded here.

Deploy privately:
    Deploy on Streamlit Community Cloud as usual, then go to
    App settings -> Sharing -> set to Private and add viewer emails.
    That access control happens on the platform side, not in this file.
"""

import re
from datetime import datetime, timezone
from io import StringIO

import pandas as pd
import requests
import streamlit as st
import altair as alt

# ---------------------------------------------------------------- config

st.set_page_config(
    page_title="AirAsia Group AOG Tracker",
    page_icon="\u2708\ufe0f",
    layout="wide",
)

ICAO_TO_IATA = {"AXM": "AK", "XAX": "D7", "AIQ": "FD", "TAX": "XJ",
                "AWQ": "QZ", "EZD": "Z2", "KTC": "KT"}

REFRESH_SECONDS = 300  # cache TTL; also used to label "data as of"

GITHUB_OWNER = st.secrets.get("GITHUB_OWNER", "sakinahalizzah")
GITHUB_REPO = st.secrets.get("GITHUB_REPO", "Aircraft-AOG")
GITHUB_BRANCH = st.secrets.get("GITHUB_BRANCH", "main")
GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN", "")  # only needed for a private repo


# ---------------------------------------------------------------- github fetch

def _headers(raw: bool = True) -> dict:
    h = {"Accept": "application/vnd.github.raw" if raw else "application/vnd.github+json"}
    if GITHUB_TOKEN:
        h["Authorization"] = f"token {GITHUB_TOKEN}"
    return h


@st.cache_data(ttl=REFRESH_SECONDS, show_spinner=False)
def gh_fetch_text(path: str) -> str:
    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/{path}"
    resp = requests.get(url, headers=_headers(raw=True), params={"ref": GITHUB_BRANCH}, timeout=20)
    resp.raise_for_status()
    return resp.text


@st.cache_data(ttl=REFRESH_SECONDS, show_spinner=False)
def gh_list_dir(path: str) -> list:
    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/{path}"
    resp = requests.get(url, headers=_headers(raw=False), params={"ref": GITHUB_BRANCH}, timeout=20)
    resp.raise_for_status()
    return resp.json()


@st.cache_data(ttl=REFRESH_SECONDS, show_spinner=False)
def load_data():
    problems = []

    # ---- trend
    trend = pd.DataFrame()
    try:
        text = gh_fetch_text("aog_history.csv")
        trend = pd.read_csv(StringIO(text), parse_dates=["date"])
    except Exception as e:
        problems.append(f"aog_history.csv: {e}")

    # ---- latest snapshot (per-tail status; fleet.csv alone has no status column)
    snapshot = pd.DataFrame()
    try:
        listing = gh_list_dir("history")
        snaps = sorted(
            (f["name"] for f in listing if re.match(r"^snapshot_.*\.csv$", f["name"])),
        )
        if snaps:
            text = gh_fetch_text(f"history/{snaps[-1]}")
            snapshot = pd.read_csv(StringIO(text), dtype={"icao24": str})
        else:
            problems.append("history/: no snapshot_*.csv found yet")
    except Exception as e:
        problems.append(f"history/: {e}")

    # ---- fleet.csv (reference only — registration/operator/model)
    fleet = pd.DataFrame()
    try:
        text = gh_fetch_text("fleet.csv")
        fleet = pd.read_csv(StringIO(text), dtype=str)
    except Exception as e:
        problems.append(f"fleet.csv: {e}")


# ---------------------------------------------------------------- light theme

st.markdown("""
<style>
  .stApp { background: #F7F8FA; }
  .metric-card {
      background: #FFFFFF; border: 1px solid #E4E7EB; border-radius: 8px;
      padding: 14px 16px; text-align: left;
  }
  .metric-card .num { font-family: 'IBM Plex Mono', monospace; font-size: 26px; font-weight: 700; }
  .metric-card .lbl { font-size: 12px; color: #6B7280; text-transform: uppercase; letter-spacing: .04em; margin-top: 4px;}
  .active-num   { color: #1B8A5A; }
  .idle-num     { color: #B7791F; }
  .grounded-num { color: #C0392B; }
  .stored-num   { color: #6B7280; }
  .caveat-box {
      background: #FFF8ED; border: 1px solid #F0DCAF; border-radius: 8px;
      padding: 14px 16px; font-size: 13px; color: #6B5A2A; line-height: 1.55;
  }
  .badge { padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 700; }
  .badge-ACTIVE   { background:#E6F4EC; color:#1B8A5A; }
  .badge-IDLE     { background:#FBF0DC; color:#B7791F; }
  .badge-GROUNDED { background:#FBE7E5; color:#C0392B; }
  .badge-ERROR    { background:#EEF0F2; color:#6B7280; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------- header

if not GITHUB_OWNER or not GITHUB_REPO:
    st.error(
        "GITHUB_OWNER / GITHUB_REPO are not set. Add them to `.streamlit/secrets.toml` "
        "(see secrets.toml.example) before deploying."
    )
    st.stop()

top_l, top_r = st.columns([3, 1])
with top_l:
    st.title("AirAsia Group AOG Tracker")
    st.caption("Grounded-fleet proxy · Aircraft on ground monitor · source: OpenSky Network")
with top_r:
    if st.button("Refresh now", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

trend, snapshot, fleet, klia, problems = load_data()

if problems:
    with st.expander("Data source warnings", expanded=False):
        for p in problems:
            st.write("- " + p)

st.caption(f"Data cached for {REFRESH_SECONDS // 60} min · refreshed {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}")

# ---------------------------------------------------------------- summary

tracked = snapshot[snapshot.get("status", pd.Series(dtype=str)) != "ERROR"] if not snapshot.empty else pd.DataFrame()
active_n = int((tracked["status"] == "ACTIVE").sum()) if not tracked.empty else 0
idle_n = int((tracked["status"] == "IDLE").sum()) if not tracked.empty else 0
grounded_n = int(tracked["status"].isin(["GROUNDED", "NO_FLIGHTS_30D+"]).sum()) if not tracked.empty else 0
fleet_n = len(tracked)
avail_pct = round(100 * active_n / fleet_n, 1) if fleet_n else 0.0

cards = st.columns(6)
card_defs = [
    ("Fleet size", fleet_n, ""),
    ("Active", active_n, "active-num"),
    ("Idle T+3", idle_n, "idle-num"),
    ("Grounded T+7", grounded_n, "grounded-num"),
    ("Stored", "\u2014", "stored-num"),
    ("Availability", f"{avail_pct}%", ""),
]
for col, (label, val, cls) in zip(cards, card_defs):
    col.markdown(
        f'<div class="metric-card"><div class="num {cls}">{val}</div>'
        f'<div class="lbl">{label}</div></div>',
        unsafe_allow_html=True,
    )

st.caption(
    "Active = flew in last 3 days · Idle T+3 = 3\u20136.9 days idle · "
    "Grounded T+7 = 7+ days idle or no flights in 30 days (the AOG proxy) · "
    "Stored is not auto-classified — flight data can't tell storage apart from AOG."
)

# ---------------------------------------------------------------- trend chart

st.subheader("AOG trend \u00b7 grounded % of tracked fleet")
if not trend.empty:
    trend = trend.sort_values("date")
    trend["idle_pct"] = (100 * trend["idle"] / trend["fleet_tracked"]).round(1)
    base = alt.Chart(trend).encode(x=alt.X("date:T", title=None))
    area = base.mark_area(color="#C0392B", opacity=0.12).encode(y=alt.Y("grounded_pct:Q", title="% of fleet"))
    line_g = base.mark_line(color="#C0392B", strokeWidth=2).encode(y="grounded_pct:Q")
    line_i = base.mark_line(color="#B7791F", strokeWidth=1.5, strokeDash=[4, 3]).encode(y="idle_pct:Q")
    st.altair_chart((area + line_g + line_i).properties(height=280), use_container_width=True)
else:
    st.info("No aog_history.csv data yet.")

# ---------------------------------------------------------------- breakdowns

col_a, col_b = st.columns([1.3, 1])

with col_a:
    st.subheader("By airline (IATA)")
    if not tracked.empty:
        by_op = (
            tracked.assign(iata=tracked["operator"].map(ICAO_TO_IATA).fillna(tracked["operator"]))
            .groupby(["iata", "status"]).size().reset_index(name="count")
        )
        chart = alt.Chart(by_op).mark_bar().encode(
            y=alt.Y("iata:N", title=None, sort="-x"),
            x=alt.X("count:Q", title="Aircraft", stack="zero"),
            color=alt.Color(
                "status:N",
                scale=alt.Scale(
                    domain=["ACTIVE", "IDLE", "GROUNDED", "NO_FLIGHTS_30D+"],
                    range=["#1B8A5A", "#B7791F", "#C0392B", "#C0392B"],
                ),
                legend=alt.Legend(title=None, orient="bottom"),
            ),
        ).properties(height=260)
        st.altair_chart(chart, use_container_width=True)
    else:
        st.info("No snapshot data yet.")

with col_b:
    st.subheader("By aircraft type")
    if not tracked.empty and "model" in tracked.columns:
        by_type = tracked.groupby(["model", "status"]).size().reset_index(name="count")
        chart = alt.Chart(by_type).mark_bar().encode(
            x=alt.X("model:N", title=None),
            y=alt.Y("count:Q", title="Aircraft", stack="zero"),
            color=alt.Color(
                "status:N",
                scale=alt.Scale(
                    domain=["ACTIVE", "IDLE", "GROUNDED", "NO_FLIGHTS_30D+"],
                    range=["#1B8A5A", "#B7791F", "#C0392B", "#C0392B"],
                ),
                legend=None,
            ),
        ).properties(height=260)
        st.altair_chart(chart, use_container_width=True)
    else:
        st.info("No snapshot data yet.")

# ---------------------------------------------------------------- detail table

st.subheader("Aircraft detail")
if not snapshot.empty:
    filt_col, search_col = st.columns([1, 2])
    with filt_col:
        status_filter = st.selectbox(
            "Status", ["All", "ACTIVE", "IDLE", "GROUNDED", "NO_FLIGHTS_30D+", "ERROR"]
        )
    with search_col:
        search = st.text_input("Search registration / icao24 / operator / model", "")

    view = snapshot.copy()
    if status_filter != "All":
        view = view[view["status"] == status_filter]
    if search:
        mask = view.apply(lambda r: search.lower() in " ".join(map(str, r.values)).lower(), axis=1)
        view = view[mask]
    if "operator" in view.columns:
        view["iata"] = view["operator"].map(ICAO_TO_IATA).fillna(view["operator"])

    st.dataframe(
        view.sort_values("idle_days", ascending=False, na_position="first"),
        use_container_width=True,
        height=420,
    )
else:
    st.info("No snapshot data yet.")

# ---------------------------------------------------------------- definitions

st.subheader("Definitions")
st.markdown(
    '<div class="caveat-box">'
    '<b>Grounded T+7</b> tracks <i>unexplained fleet inactivity</i>, not verified AOG. '
    'Industry usage of "AOG" is specifically unscheduled and mechanical, with no duration threshold — '
    "an aircraft is AOG from the fault until return to service, whether that's four hours or four weeks. "
    "This proxy can't distinguish true AOG from scheduled heavy maintenance or storage, since all three "
    'look identical as "not flying" in flight-history data. Read the trend and the level against baseline, '
    "not this percentage as a literal AOG count. Cross-check quarterly against Capital A Group's disclosed "
    "aircraft-in-operation figures to calibrate."
    "</div>",
    unsafe_allow_html=True,
)
