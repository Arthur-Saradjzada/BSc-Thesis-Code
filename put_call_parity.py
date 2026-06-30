import numpy as np
import pandas as pd
import matplotlib as mpl
import matplotlib.pyplot as plt
from sqlalchemy import create_engine

CONNECTION_STRING = "mysql+pymysql://root:PASSWORD@localhost/spx_data"
TABLE_NAME        = "spx_options_eod_clean"

OUT_PDF = r"C:\Users\vcsa0\Downloads\parity_residual.pdf"
OUT_PNG = r"C:\Users\vcsa0\Downloads\parity_residual.png"

MIN_STRIKES = 6
bins = np.arange(0.2, 2.05, 0.05)

engine = create_engine(CONNECTION_STRING)

query = f"""
SELECT QUOTE_DATE, EXPIRE_DATE, DTE, STRIKE,
       UNDERLYING_LAST AS S,
       C_BID, C_ASK, C_IV,
       P_BID, P_ASK, P_IV
FROM {TABLE_NAME}
WHERE C_BID IS NOT NULL AND C_ASK IS NOT NULL
  AND P_BID IS NOT NULL AND P_ASK IS NOT NULL
  AND UNDERLYING_LAST IS NOT NULL
  AND STRIKE IS NOT NULL;
"""
df = pd.read_sql(query, engine)
print(f"Rows pulled (raw): {len(df):,}")

df["C_MID"]     = (df["C_BID"] + df["C_ASK"]) / 2.0
df["P_MID"]     = (df["P_BID"] + df["P_ASK"]) / 2.0
df["CMP"]       = df["C_MID"] - df["P_MID"]
df["MONEYNESS"] = df["STRIKE"] / df["S"]

def parity_bands(data):
    all_m = []
    all_r = []
    for (qd, ed), cell in data.groupby(["QUOTE_DATE", "EXPIRE_DATE"], sort=False):
        cell = cell[cell["CMP"].notna()]
        if len(cell) < MIN_STRIKES:
            continue
        K = cell["STRIKE"].values
        y = cell["CMP"].values
        Kbar = K.mean()
        ybar = y.mean()
        b = np.sum((K - Kbar) * (y - ybar)) / np.sum((K - Kbar)**2)
        a = ybar - b * Kbar
        resid = y - (a + b * K)
        all_m.extend(cell["MONEYNESS"].values)
        all_r.extend(resid)

    pts = pd.DataFrame({"MONEYNESS": all_m, "RESID": all_r})
    pts["BIN"] = pd.cut(pts["MONEYNESS"], bins)
    med = pts.groupby("BIN")["RESID"].median()
    p10 = pts.groupby("BIN")["RESID"].quantile(0.10)
    p90 = pts.groupby("BIN")["RESID"].quantile(0.90)
    return med, p10, p90

print("Fitting raw sample...")
med_raw, p10_raw, p90_raw = parity_bands(df)

xcent = [interval.mid for interval in med_raw.index]

###############  OUTPUT  #################
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

COL_BAND = "#9DBAD4"   
COL_MED  = "#0F3D63"   
COL_REF  = "#9A9A9A"   

fig, ax = plt.subplots(figsize=(9.0, 5.6))

ax.fill_between(xcent, p10_raw.values, p90_raw.values,
                color=COL_BAND, alpha=0.55,
                label="10th--90th percentile")

ax.plot(xcent, med_raw.values, color=COL_MED, lw=2.0, marker="o", ms=4.5,
        markerfacecolor="white", markeredgecolor=COL_MED, markeredgewidth=1.3,
        label="Median residual")

ax.axhline(0.0, color="#4D4D4D", lw=1.0)
ax.axvline(1.0, color=COL_REF, ls=(0, (4, 3)), lw=1.0, zorder=0)

ax.set_yscale("symlog", linthresh=0.1)
ax.set_ylim(-2.5, 2.5)
ax.set_yticks([-2, -1, -0.5, -0.1, 0, 0.1, 0.5, 1, 2])
ax.set_yticklabels(["-2", "-1", "-0.5", "-0.1", "0", "0.1", "0.5", "1", "2"])

ax.set_xlim(0.1, 2.2)

ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
ax.spines["left"].set_color("#4D4D4D")
ax.spines["bottom"].set_color("#4D4D4D")
ax.yaxis.grid(True, which="major", color="#E8E8E8", lw=0.8, zorder=0)
ax.xaxis.grid(False)
ax.set_axisbelow(True)
ax.tick_params(direction="out", length=4, width=0.9, color="#4D4D4D")

ax.set_xlabel(r"Moneyness  $K/S$")
ax.set_ylabel("Put-call parity residual (USD)")
ax.legend(loc="upper left", frameon=False, handlelength=1.9, borderaxespad=0.5)

fig.tight_layout()
fig.savefig(OUT_PDF, bbox_inches="tight")
fig.savefig(OUT_PNG, dpi=300, bbox_inches="tight")
plt.show()
plt.close(fig)
print(f"\nPDF written to: {OUT_PDF}")
print(f"PNG written to: {OUT_PNG}")
