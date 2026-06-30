import numpy as np
import pandas as pd
import matplotlib as mpl
import matplotlib.pyplot as plt
from sqlalchemy import create_engine

SURFACE_FILE = r"C:\Users\vcsa0\Downloads\surface_points.xlsx"

CONNECTION_STRING = "mysql+pymysql://root:PASSWORD!@localhost/spx_data"
VIX_TABLE = "vix_eod"

START_DATE = "2010-01-01"
END_DATE = "2024-01-01"

mon_order = ["DOTM call", "OTM call", "ATM call", "ATM put", "OTM put", "DOTM put"]
mat_order = ["7-45d", "45-90d", "90-180d", "180-360d"]

df = pd.read_excel(SURFACE_FILE)
df["QUOTE_DATE"] = pd.to_datetime(df["QUOTE_DATE"])
df["IV"] = df["IV"].astype(float)
df = df[(df["QUOTE_DATE"] >= START_DATE) & (df["QUOTE_DATE"] < END_DATE)]

print(f"Surface rows: {len(df):,}   days: {df['QUOTE_DATE'].nunique():,}")

vix = None
try:
    engine = create_engine(CONNECTION_STRING)
    vix_query = f"""
        SELECT QUOTE_DATE, UNDERLYING_LAST AS VIX
        FROM {VIX_TABLE}
        WHERE QUOTE_DATE >= '{START_DATE}' AND QUOTE_DATE < '{END_DATE}'
          AND UNDERLYING_LAST IS NOT NULL AND UNDERLYING_LAST > 0
        ORDER BY QUOTE_DATE;
    """
    vix = pd.read_sql(vix_query, engine)
    vix["QUOTE_DATE"] = pd.to_datetime(vix["QUOTE_DATE"])
    vix["VIX"] = vix["VIX"].astype(float)

    vix = vix.groupby("QUOTE_DATE", as_index=False)["VIX"].mean()

    print(f"VIX median before scaling: {vix['VIX'].median():.2f}")
    if vix["VIX"].median() > 2:     
        vix["VIX"] = vix["VIX"] / 100.0
    vix = vix.set_index("QUOTE_DATE")
except Exception as error:
    print(f"VIX overlay skipped: {error}")

df["BUCKET"] = df["MON_LABEL"] + " | " + df["MAT_LABEL"]
iv_wide = df.pivot_table(index="QUOTE_DATE", columns="BUCKET", values="IV").sort_index()

avg_iv = iv_wide.mean(axis=1)

mpl.rcParams.update({
    "font.family":      "serif",
    "font.serif":       ["Times New Roman", "DejaVu Serif"],
    "font.size":        14,
    "axes.labelsize":   15,
    "axes.titlesize":   15,
    "xtick.labelsize":  12,
    "ytick.labelsize":  12,
    "legend.fontsize":  11,
    "axes.linewidth":   0.9,
    "axes.edgecolor":   "#4D4D4D",
    "figure.dpi":       150,
    "pdf.fonttype":     42,
})

COL_MAIN = "#1F4E79"   
COL_VIX  = "#9E2A2B"  
COL_REF  = "#9A9A9A"   

def style_axis(ax):
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#4D4D4D")
    ax.spines["bottom"].set_color("#4D4D4D")
    ax.yaxis.grid(True, which="major", color="#E8E8E8", lw=0.8, zorder=0)
    ax.xaxis.grid(False)
    ax.set_axisbelow(True)
    ax.tick_params(direction="out", length=4, width=0.9, color="#4D4D4D")

fig, (axA, axB) = plt.subplots(2, 1, figsize=(12, 9))
fig.suptitle("Volatility Time Series", fontsize=12, fontweight="bold")

axA.plot(avg_iv.index, avg_iv.values, linewidth=1.3, color=COL_MAIN,
         label="Average implied volatility")
if vix is not None:
    vix_aligned = vix.reindex(avg_iv.index)
    axA.plot(vix_aligned.index, vix_aligned["VIX"].values, linewidth=1.0,
             color=COL_VIX, label="VIX")
axA.set_title("(A) Average implied volatility", fontsize=10)
axA.set_ylabel("Implied volatility")
axA.legend(loc="upper left", frameon=False)
style_axis(axA)

for bucket in iv_wide.columns:
    axB.plot(iv_wide.index, iv_wide[bucket], linewidth=0.6, color=COL_MAIN, alpha=0.5)
axB.set_title("(B) Implied volatility across buckets", fontsize=10)
axB.set_ylabel("Implied volatility")
axB.set_xlabel("Date")
style_axis(axB)

plt.tight_layout()
fig.savefig("figure2_volatility_timeseries.pdf", bbox_inches="tight")
fig.savefig("figure2_volatility_timeseries.png", dpi=300, bbox_inches="tight")
plt.show()

surface = df.pivot_table(index="QUOTE_DATE", columns=["MON_LABEL", "MAT_LABEL"], values="IV").sort_index()

smile_slopes = pd.DataFrame(index=surface.index)
for mat in mat_order:
    smile_slopes[mat] = surface[("DOTM put", mat)] - surface[("DOTM call", mat)]

term_slopes = pd.DataFrame(index=surface.index)
for mon in mon_order:
    term_slopes[mon] = surface[(mon, "180-360d")] - surface[(mon, "7-45d")]

fig, (axA, axB) = plt.subplots(2, 1, figsize=(12, 9))
fig.suptitle("Slope of the Volatility Smile and Term Structure", fontsize=12, fontweight="bold")

for mat in mat_order:
    axA.plot(smile_slopes.index, smile_slopes[mat], linewidth=1.0, label=mat)
axA.set_title("(A) Slope of volatility smile", fontsize=10)
axA.set_ylabel("Smile slope")
axA.legend(loc="upper left", frameon=False, ncol=2)
style_axis(axA)

for mon in mon_order:
    axB.plot(term_slopes.index, term_slopes[mon], linewidth=1.0, label=mon)
axB.axhline(0.0, linewidth=0.9, linestyle=(0, (4, 3)), color=COL_REF, zorder=0)
axB.set_title("(B) Slope of volatility term structure", fontsize=10)
axB.set_ylabel("Term-structure slope")
axB.set_xlabel("Date")
axB.legend(loc="lower right", frameon=False, ncol=2)
style_axis(axB)

plt.tight_layout()
fig.savefig("figure3_volatility_slopes.pdf", bbox_inches="tight")
fig.savefig("figure3_volatility_slopes.png", dpi=300, bbox_inches="tight")
plt.show()

print("Done.")
