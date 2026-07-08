"""
build_fleet.py
Builds the AirAsia Group fleet list from the OpenSky aircraft database.

Run this once, then re-run monthly to catch fleet changes.

Usage:
    python build_fleet.py

Output:
    fleet.csv  (icao24, registration, operator, model)
"""

import io
import sys
import pandas as pd
import requests

DATABASE_URL = "https://opensky-network.org/datasets/metadata/aircraftDatabase.csv"

# Operator ICAO codes for the AirAsia Group AOCs.
# Verify Philippines and Cambodia codes on ch-aviation before relying on them.
GROUP_ICAO_CODES = {
    "AXM": {"iata": "AK", "name": "AirAsia Malaysia"},
    "XAX": {"iata": "D7", "name": "AirAsia X"},
    "AIQ": {"iata": "FD", "name": "Thai AirAsia"},
    "AWQ": {"iata": "QZ", "name": "Indonesia AirAsia"},
    "APG": {"iata": "Z2", "name": "AirAsia Philippines"},
    "KTC": {"iata": "KT", "name": "AirAsia Cambodia"},
    "TAX": {"iata": "XJ", "name": "Thai AirAsia X"},
}

# Fallback: catch anything with AirAsia in the operator name
NAME_KEYWORD = "airasia"


def main():
    print("Downloading OpenSky aircraft database (large file, ~100MB)...")
    resp = requests.get(DATABASE_URL, timeout=300)
    resp.raise_for_status()

    df = pd.read_csv(
        io.StringIO(resp.text),
        dtype=str,
        usecols=[
            "icao24",
            "registration",
            "operator",
            "operatoricao",
            "model",
            "typecode",
        ],
    )

    df = df.fillna("")

    mask_code = df["operatoricao"].str.upper().isin(GROUP_ICAO_CODES)
    mask_name = df["operator"].str.lower().str.contains(NAME_KEYWORD)
    fleet = df[mask_code | mask_name].copy()

    # Drop rows without a usable hex code
    fleet = fleet[fleet["icao24"].str.len() == 6]
    fleet = fleet.drop_duplicates(subset="icao24")
    fleet = fleet.sort_values(["operatoricao", "registration"])

    fleet.to_csv("fleet.csv", index=False)

    print(f"\nDone. {len(fleet)} aircraft written to fleet.csv")
    print("\nBreakdown by operator code:")
    print(fleet["operatoricao"].value_counts().to_string())
    print(
        "\nSanity check this against ch-aviation or Planespotters fleet counts."
        "\nThe OpenSky database can lag on new deliveries and re-registrations."
    )


if __name__ == "__main__":
    sys.exit(main())
