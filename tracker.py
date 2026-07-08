"""
tracker.py
Daily AOG proxy tracker for the AirAsia Group fleet.

For each tail in fleet.csv, checks when it last flew using the OpenSky
flights API. Flags aircraft idle beyond thresholds, saves a daily
snapshot, and appends to a running trend file.

Setup:
    1. Create a free account at opensky-network.org
    2. In your account page, create an API client (gives you a
       client_id and client_secret)
    3. Set them as environment variables, or put them in a file
       named credentials.json like:
           {"client_id": "...", "client_secret": "..."}
    4. pip install -r requirements.txt
    5. python build_fleet.py   (once)
    6. python tracker.py       (daily)

Output:
    history/snapshot_YYYY-MM-DD.csv   full tail-level detail
    aog_history.csv                   one summary row per day (the trend)
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

# ---------------------------------------------------------------- config

LOOKBACK_DAYS = 30          # max window OpenSky allows per query
IDLE_THRESHOLD = 3          # days without flying = IDLE
AOG_THRESHOLD = 7           # days without flying = GROUNDED (AOG proxy)
SLEEP_BETWEEN_CALLS = 1.2   # seconds, stay polite with the free API

TOKEN_URL = (
    "https://auth.opensky-network.org/auth/realms/opensky-network"
    "/protocol/openid-connect/token"
)
FLIGHTS_URL = "https://opensky-network.org/api/flights/aircraft"

HERE = Path(__file__).parent
HISTORY_DIR = HERE / "history"
TREND_FILE = HERE / "aog_history.csv"
FLEET_FILE = HERE / "fleet.csv"


# ---------------------------------------------------------------- auth

def get_token() -> str | None:
    """Get an OAuth2 token. Returns None to fall back to anonymous access."""
    client_id = os.environ.get("OPENSKY_CLIENT_ID")
    client_secret = os.environ.get("OPENSKY_CLIENT_SECRET")

    cred_file = HERE / "credentials.json"
    if not client_id and cred_file.exists():
        creds = json.loads(cred_file.read_text())
        client_id = creds.get("client_id")
        client_secret = creds.get("client_secret")

    if not client_id:
        print("No credentials found, using anonymous access (heavily rate limited).")
        return None

    for attempt in range(1, 4):
        try:
            resp = requests.post(
                TOKEN_URL,
                data={
                    "grant_type": "client_credentials",
                    "client_id": client_id,
                    "client_secret": client_secret,
                },
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json()["access_token"]
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            print(f"  Auth attempt {attempt}/3 failed ({e.__class__.__name__}).")
            if attempt < 3:
                time.sleep(10 * attempt)  # 10s, then 20s
        except requests.exceptions.HTTPError as e:
            # Bad credentials, server error, etc. — not a network issue, don't retry.
            print(f"  Auth request failed: {e}")
            break

    print("  Could not obtain a token after retries. Falling back to anonymous access.")
    return None


# ---------------------------------------------------------------- core

def last_flight_time(icao24: str, headers: dict) -> int | None:
    """Return unix time of the aircraft's most recent flight in the
    lookback window, or None if it has not flown at all."""
    now = int(time.time())
    begin = now - LOOKBACK_DAYS * 86400

    resp = requests.get(
        FLIGHTS_URL,
        params={"icao24": icao24.lower(), "begin": begin, "end": now},
        headers=headers,
        timeout=30,
    )

    if resp.status_code == 404:
        return None  # no flights found in window
    if resp.status_code == 429:
        print("  Rate limited. Sleeping 60s...")
        time.sleep(60)
        return last_flight_time(icao24, headers)
    resp.raise_for_status()

    flights = resp.json()
    if not flights:
        return None
    return max(f["lastSeen"] for f in flights if f.get("lastSeen"))


def classify(idle_days: float | None) -> str:
    if idle_days is None:
        return "NO_FLIGHTS_30D+"
    if idle_days >= AOG_THRESHOLD:
        return "GROUNDED"
    if idle_days >= IDLE_THRESHOLD:
        return "IDLE"
    return "ACTIVE"


def main():
    if not FLEET_FILE.exists():
        print("fleet.csv not found. Run build_fleet.py first.")
        return 1

    fleet = pd.read_csv(FLEET_FILE, dtype=str).fillna("")
    print(f"Tracking {len(fleet)} aircraft...")

    token = get_token()
    headers = {"Authorization": f"Bearer {token}"} if token else {}

    now = time.time()
    rows = []

    for i, ac in fleet.iterrows():
        icao24 = ac["icao24"]
        try:
            last_seen = last_flight_time(icao24, headers)
        except Exception as e:
            print(f"  {ac['registration'] or icao24}: error {e}, skipping")
            last_seen = "ERROR"

        if last_seen == "ERROR":
            idle_days, status = None, "ERROR"
        elif last_seen is None:
            idle_days, status = None, classify(None)
        else:
            idle_days = round((now - last_seen) / 86400, 1)
            status = classify(idle_days)

        rows.append(
            {
                "registration": ac["registration"],
                "icao24": icao24,
                "operator": ac["operatoricao"] or ac["operator"],
                "model": ac["model"] or ac.get("typecode", ""),
                "idle_days": idle_days,
                "status": status,
            }
        )

        done = len(rows)
        if done % 25 == 0:
            print(f"  {done}/{len(fleet)} checked")
        time.sleep(SLEEP_BETWEEN_CALLS)

    snap = pd.DataFrame(rows)

    # ---- save daily snapshot
    HISTORY_DIR.mkdir(exist_ok=True)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    snap_path = HISTORY_DIR / f"snapshot_{today}.csv"
    snap.to_csv(snap_path, index=False)

    # ---- append to trend file
    tracked = snap[snap["status"] != "ERROR"]
    grounded = tracked["status"].isin(["GROUNDED", "NO_FLIGHTS_30D+"]).sum()
    summary = {
        "date": today,
        "fleet_tracked": len(tracked),
        "active": (tracked["status"] == "ACTIVE").sum(),
        "idle": (tracked["status"] == "IDLE").sum(),
        "grounded": grounded,
        "grounded_pct": round(100 * grounded / max(len(tracked), 1), 1),
    }
    trend = pd.DataFrame([summary])
    if TREND_FILE.exists():
        old = pd.read_csv(TREND_FILE)
        old = old[old["date"] != today]  # overwrite same-day reruns
        trend = pd.concat([old, trend], ignore_index=True)
    trend.to_csv(TREND_FILE, index=False)

    # ---- print the "so what"
    print("\n================ AOG PROXY SUMMARY ================")
    print(f"Date: {today}")
    print(f"Fleet tracked: {summary['fleet_tracked']}")
    print(f"Active: {summary['active']}")
    print(f"Idle (3-7 days): {summary['idle']}")
    print(f"Grounded (7+ days): {summary['grounded']}  "
          f"({summary['grounded_pct']}% of fleet)")

    grounded_list = tracked[
        tracked["status"].isin(["GROUNDED", "NO_FLIGHTS_30D+"])
    ].sort_values("idle_days", ascending=False, na_position="first")
    if len(grounded_list):
        print("\nGrounded aircraft:")
        print(
            grounded_list[["registration", "operator", "model", "idle_days"]]
            .to_string(index=False)
        )
    print(f"\nSnapshot saved: {snap_path}")
    print(f"Trend file:     {TREND_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
