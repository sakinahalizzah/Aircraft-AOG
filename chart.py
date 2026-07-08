"""
chart.py
Plots the grounded percentage trend from aog_history.csv.

Usage:
    python chart.py
"""

import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_csv("aog_history.csv", parse_dates=["date"])
df = df.sort_values("date")

fig, ax = plt.subplots(figsize=(10, 5))
ax.plot(df["date"], df["grounded_pct"], marker="o", linewidth=2)
ax.set_title("AirAsia Group: grounded fleet % (AOG proxy, 7+ days idle)")
ax.set_ylabel("% of tracked fleet")
ax.set_xlabel("Date")
ax.grid(alpha=0.3)
fig.autofmt_xdate()
fig.tight_layout()
fig.savefig("aog_trend.png", dpi=150)
print("Saved aog_trend.png")
plt.show()
