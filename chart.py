# AirAsia Group AOG Proxy Tracker

Purpose: a daily indicator of how much of the AirAsia Group fleet is not flying. Grounded fleet is a leading indicator of traffic risk at KLIA, especially T2.

## How it works

1. `build_fleet.py` pulls the OpenSky aircraft database and filters it to AirAsia Group operators. Output: `fleet.csv`.
2. `tracker.py` checks every tail daily against the OpenSky flights API and asks one question: when did this aircraft last fly?
3. Aircraft idle 7+ days are flagged GROUNDED. The daily grounded percentage is appended to `aog_history.csv`. That file is your trend.
4. `chart.py` plots the trend.

## Setup (once)

1. Create a free account at opensky-network.org
2. In your account page, create an API client. Copy the client_id and client_secret into a file named `credentials.json` in this folder:

```json
{"client_id": "CLIENT_ID", "client_secret": "CLIENT_SECRET"}
```

3. Install dependencies:

```
pip install -r requirements.txt
```

4. Build the fleet list:

```
python build_fleet.py
```

Sanity check the count against ch-aviation or Planespotters. Edit `fleet.csv` by hand if needed. Re-run monthly to catch deliveries and exits.

## Daily run

```
python tracker.py
```

Takes roughly 5 to 8 minutes for 200+ tails because the script is polite to the free API.

## Automating it

**Windows Task Scheduler:** create a basic task, daily at a fixed time, action = start a program, program = your python.exe path, argument = full path to tracker.py, start in = this folder.

**Better: GitHub Actions (runs even when your laptop is off).** Push this folder to a private GitHub repo, add `OPENSKY_CLIENT_ID` and `OPENSKY_CLIENT_SECRET` as repo secrets, and add `.github/workflows/daily.yml` (included in this project). The workflow runs daily and commits the updated CSVs back to the repo.

## Reading the numbers

- A steady-state grounded percentage exists for every airline. Scheduled maintenance alone means the number is never zero. What matters is the trend and the level versus baseline.
- Run it for 2 to 3 weeks before drawing conclusions. That gives you a baseline.
- Cross-check quarterly against Capital A results, which disclose aircraft in operation versus total fleet. That calibrates your proxy.
- The proxy cannot distinguish AOG from heavy checks or storage. For fleet-health trend purposes, the distinction matters less than the direction.

## Known limitations

- OpenSky coverage in parts of Southeast Asia is weaker than commercial feeds. A tail flying only in low-coverage areas can look idle when it is not. Watch for false positives on Indonesia and Philippines AOCs.
- The OpenSky aircraft database lags new deliveries and re-registrations. The monthly fleet rebuild plus a manual check handles this.
- Verify the operator ICAO codes for Philippines AirAsia and AirAsia Cambodia in `build_fleet.py` before trusting those subsets. The Malaysian and Thai codes (AXM, XAX, AIQ, TAX) and Indonesia (AWQ) are solid.
