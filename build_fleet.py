"""
build_fleet.py
Builds the AirAsia Group fleet list from the OpenSky aircraft database.

Run this once, then re-run monthly to catch fleet changes (deliveries,
re-registrations, exits).

Usage:
    python build_fleet.py

Output:
    fleet.csv  (icao24, registration, operator, operatoricao, model, typecode)
"""

import io
import sys

import pandas as pd
import requests

DATABASE_URL = "https://opensky-network.org/datasets/metadata/aircraftDatabase.csv"

# AA Group operators: IATA code (what's on the flight number) mapped to
# ICAO code (the prefix OpenSky actually sees in ADS-B callsigns).
# AXM/XAX/AIQ/AWQ are solid. Verify APG (Philippines) and KTC (Cambodia)
# against ch-aviation before trusting those subsets — see README.
# TAX (Thai AirAsia X / XJ) is not in the user-confirmed list but is kept
# in, flagged unverified, since it's part of the group's long-haul unit.
GROUP_OPERATORS = {
    "AXM": {"iata": "AK", "name": "AirAsia Malaysia", "verified": True},
    "XAX": {"iata": "D7", "name": "AirAsia X", "verified": True},
    "AIQ": {"iata": "FD", "name": "Thai AirAsia", "verified": True},
    "AWQ": {"iata": "QZ", "name": "Indonesia AirAsia", "verified": True},
    "APG": {"iata": "Z2", "name": "AirAsia Philippines", "verified": False},
    "KTC": {"iata": "KT", "name": "AirAsia Cambodia", "verified": False},
    "TAX": {"iata": "XJ", "name": "Thai AirAsia X", "verified": False},
}
GROUP_ICAO_CODES = set(GROUP_OPERATORS.keys())

# Fallback: catch anything with AirAsia in the operator name that the
# ICAO code list above might miss.
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

    # Drop rows without a usable hex transponder code.
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
