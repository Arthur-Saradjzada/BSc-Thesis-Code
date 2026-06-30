import numpy as np
import pandas as pd
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.ticker import FixedLocator, NullFormatter
from sqlalchemy import create_engine

###############COLLECT DATA#################
CONNECTION_STRING = "mysql+pymysql://root:PANArthur123!@localhost/spx_data"
TABLE_NAME        = "spx_options_eod_clean"
OUT_PDF = r"C:\Users\vcsa0\Downloads\bidask_spread.pdf"
OUT_PNG = r"C:\Users\vcsa0\Downloads\bidask_spread.png"

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
    "font.family":      "serif",
    "font.serif":       ["Times New Roman", "DejaVu Serif"],
    "font.size":        15,        
    "axes.labelsize":   16,          
    "axes.titlesize":   16,
    "xtick.labelsize":  13,         
    "ytick.labelsize":  13,
    "legend.fontsize":  13,
    "axes.linewidth":   0.9,
    "axes.edgecolor":   "#4D4D4D",
    "figure.dpi":       150,
    "pdf.fonttype":     42,         
})

COL_ITM = "#9E2A2B"   
COL_OTM = "#1F4E79"   
COL_REF = "#888888" 

itm = med["ITM"].copy()
otm = med["OTM"].copy()
itm[itm <= 0] = np.nan
otm[otm <= 0] = np.nan

fig, ax = plt.subplots(figsize=(9.0, 5.4))

ax.plot(xcent, itm, color=COL_ITM, lw=2.0, marker="o", ms=5,
        markerfacecolor="white", markeredgecolor=COL_ITM, markeredgewidth=1.3,
        label="In-the-money leg")
ax.plot(xcent, otm, color=COL_OTM, lw=2.0, marker="s", ms=5,
        markerfacecolor="white", markeredgecolor=COL_OTM, markeredgewidth=1.3,
        label="Out-of-the-money leg")

ax.set_yscale("log")
ax.set_ylim(0.1, 40)
ax.set_xlim(0.1, 2.2)

def dollar_label(value, position):
    return f"{value:g}"

ax.yaxis.set_major_locator(FixedLocator([0.1, 0.5, 1, 2, 5, 10, 20, 30, 40]))
ax.yaxis.set_major_formatter(plt.FuncFormatter(dollar_label))
ax.yaxis.set_minor_formatter(NullFormatter())

ax.axvline(1.0, color=COL_REF, ls=(0, (4, 3)), lw=1.0, zorder=0)
ax.text(1.02, 0.115, "ATM", color=COL_REF, fontsize=12, va="bottom", ha="left")

ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
ax.spines["left"].set_color("#4D4D4D")
ax.spines["bottom"].set_color("#4D4D4D")
ax.yaxis.grid(True, which="major", color="#E8E8E8", lw=0.8, zorder=0)
ax.xaxis.grid(False)
ax.set_axisbelow(True)
ax.tick_params(direction="out", length=4, width=0.9, color="#4D4D4D")

ax.set_xlabel(r"Moneyness  $K/S$")
ax.set_ylabel("Median bid-ask spread (USD)")
ax.legend(loc="upper left", frameon=False, handlelength=1.9, borderaxespad=0.5)

fig.tight_layout()
fig.savefig(OUT_PDF, bbox_inches="tight")
fig.savefig(OUT_PNG, dpi=300, bbox_inches="tight")
plt.show()
plt.close(fig)
print(f"\nPDF written to: {OUT_PDF}")
print(f"PNG written to: {OUT_PNG}")
