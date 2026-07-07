import csv
import os
import time
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests

from opensky_auth import TokenManager

FLEET_FILE = "fleet.csv"
HISTORY_DIR = "history"
SUMMARY_FILE = "aog_history.csv"

LOOKBACK_DAYS = 10
GROUNDED_THRESHOLD_DAYS = 7