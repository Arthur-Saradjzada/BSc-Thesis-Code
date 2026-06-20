import numpy as np
import pandas as pd
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.ticker import FixedLocator, NullFormatter
from sqlalchemy import create_engine

###############COLLECT DATA#################
CONNECTION_STRING = "mysql+pymysql://root:PASSWORD@localhost/spx_data"
TABLE_NAME        = "spx_options_eod_clean"
OUT_PLOT          = r"C:\your\path\Downloads\bidask_spread.png"

engine = create_engine(CONNECTION_STRING)

query = f"""
SELECT STRIKE, UNDERLYING_LAST AS S, C_BID, C_ASK, P_BID, P_ASK
FROM {TABLE_NAME}
WHERE C_BID IS NOT NULL AND C_ASK IS NOT NULL
  AND P_BID IS NOT NULL AND P_ASK IS NOT NULL
  AND UNDERLYING_LAST IS NOT NULL
  AND STRIKE IS NOT NULL;
"""
df = pd.read_sql(query, engine)
print(f"Rows (no filters): {len(df):,}")

###############BID-ASK SPREAD#################

df["MONEYNESS"] = df["STRIKE"] / df["S"]
df["C_SPREAD"]  = df["C_ASK"] - df["C_BID"]
df["P_SPREAD"]  = df["P_ASK"] - df["P_BID"]

call_status = []
for m in df["MONEYNESS"]:
    if m < 1.0:
        call_status.append("ITM")
    else:
        call_status.append("OTM")

put_status = []
for m in df["MONEYNESS"]:
    if m > 1.0:
        put_status.append("ITM")
    else:
        put_status.append("OTM")

calls = pd.DataFrame({
    "MONEYNESS": df["MONEYNESS"],
    "SPREAD":    df["C_SPREAD"],
    "STATUS":    call_status,
})
puts = pd.DataFrame({
    "MONEYNESS": df["MONEYNESS"],
    "SPREAD":    df["P_SPREAD"],
    "STATUS":    put_status,
})
legs = pd.concat([calls, puts], ignore_index=True)

legs = legs.dropna(subset=["SPREAD"])
legs = legs[legs["SPREAD"] >= 0]

bins = np.arange(0.0, 2.05, 0.05)
legs["BIN"] = pd.cut(legs["MONEYNESS"], bins)

itm_legs = legs[legs["STATUS"] == "ITM"]
otm_legs = legs[legs["STATUS"] == "OTM"]

itm_median = itm_legs.groupby("BIN")["SPREAD"].median()
otm_median = otm_legs.groupby("BIN")["SPREAD"].median()

med = pd.DataFrame({"ITM": itm_median, "OTM": otm_median})

xcent = [interval.mid for interval in med.index]

print("\nMedian absolute dollar spread by moneyness:")
print(med.round(3).to_string())

###############OUTPUT#################

mpl.rcParams.update({
    "font.family":     "serif",
    "font.serif":      ["Times New Roman", "DejaVu Serif"],
    "font.size":       11,
    "axes.labelsize":  11,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "legend.fontsize": 10,
    "axes.linewidth":  0.8,
    "axes.edgecolor":  "#333333",
    "figure.dpi":      150,
})

COL_ITM = "#9E2A2B"
COL_OTM = "#1F4E79"
COL_REF = "#888888"

itm = med["ITM"].copy()
otm = med["OTM"].copy()
itm[itm <= 0] = np.nan
otm[otm <= 0] = np.nan

fig, ax = plt.subplots(figsize=(7.0, 4.2))

ax.plot(xcent, itm, color=COL_ITM, lw=1.6, marker="o", ms=4,
        markerfacecolor="white", markeredgecolor=COL_ITM, markeredgewidth=1.1,
        label="In-the-money leg")
ax.plot(xcent, otm, color=COL_OTM, lw=1.6, marker="s", ms=4,
        markerfacecolor="white", markeredgecolor=COL_OTM, markeredgewidth=1.1,
        label="Out-of-the-money leg")

ax.set_yscale("log")
ax.set_ylim(0.1, 20)
ax.set_xlim(0.5, 1.5)

def dollar_label(value, position):
    return f"{value:g}"

ax.yaxis.set_major_locator(FixedLocator([0.1, 0.5, 1, 2, 5, 10, 20]))
ax.yaxis.set_major_formatter(plt.FuncFormatter(dollar_label))
ax.yaxis.set_minor_formatter(NullFormatter())  

ax.axvline(1.0, color=COL_REF, ls=(0, (4, 3)), lw=0.9, zorder=0)
ax.text(1.01, 0.12, "ATM", color=COL_REF, fontsize=9, va="bottom", ha="left")

ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
ax.spines["left"].set_color("#333333")
ax.spines["bottom"].set_color("#333333")
ax.yaxis.grid(True, which="major", color="#E6E6E6", lw=0.7, zorder=0)
ax.xaxis.grid(False)
ax.set_axisbelow(True)
ax.tick_params(direction="out", length=3, color="#333333")

ax.set_xlabel("Moneyness  K / S")
ax.set_ylabel("Median bid-ask spread (USD)")
ax.legend(loc="upper left", frameon=False, handlelength=1.8, borderaxespad=0.4)

fig.tight_layout()
fig.savefig(OUT_PLOT, dpi=300, bbox_inches="tight")
plt.show()
plt.close(fig)
print(f"\nPlot written to: {OUT_PLOT}")
