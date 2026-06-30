import numpy as np
import pandas as pd
import matplotlib as mpl
import matplotlib.pyplot as plt

INPUT_XLSX = r"C:\Users\vcsa0\Downloads\surface_points.xlsx"
PLOT_DAY = "2010-06-04"       

OUT_PDF = rf"C:\Users\vcsa0\Downloads\iv_surface_{PLOT_DAY}.pdf"
OUT_PNG = rf"C:\Users\vcsa0\Downloads\iv_surface_{PLOT_DAY}.png"

mon_order = ["DOTM call", "OTM call", "ATM call", "ATM put", "OTM put", "DOTM put"]
mat_order = ["7-45d", "45-90d", "90-180d", "180-360d"]

df = pd.read_excel(INPUT_XLSX)
df["QUOTE_DATE"] = pd.to_datetime(df["QUOTE_DATE"])

day = df[df["QUOTE_DATE"] == pd.Timestamp(PLOT_DAY)]

if len(day) == 0:
    print(f"{PLOT_DAY} is not in the file (it may have been dropped).")
    raise SystemExit

print(f"{PLOT_DAY}: found {len(day)} points (should be 24)")

grid = np.full((len(mon_order), len(mat_order)), np.nan)

for _, row in day.iterrows():
    i = mon_order.index(row["MON_LABEL"])   
    j = mat_order.index(row["MAT_LABEL"])   
    grid[i, j] = row["IV"]

x = np.arange(1, len(mat_order) + 1)
y = np.arange(1, len(mon_order) + 1)
X, Y = np.meshgrid(x, y)
Z = grid

mpl.rcParams.update({
    "font.family":   "serif",
    "font.serif":    ["Times New Roman", "DejaVu Serif"],
    "pdf.fonttype":  42,            
})

fig = plt.figure(figsize=(12, 8.5))
ax = fig.add_subplot(111, projection="3d")

ax.plot_surface(X, Y, Z, color="red", alpha=0.85,
                edgecolor="black", linewidth=0.3, antialiased=True)

ax.set_xticks(x)
ax.set_xticklabels(["7-45\ndays", "45-90\ndays", "90-180\ndays", "180-360\ndays"],
                   fontsize=12)
ax.set_yticks(y)
ax.set_yticklabels(["DOTM\nCall", "OTM\nCall", "ATM\nCall",
                    "ATM\nPut", "OTM\nPut", "DOTM\nPut"], fontsize=12)
ax.tick_params(axis="z", labelsize=12)   # CHANGED: larger z tick labels

ax.set_xlabel("Maturity Group", labelpad=16, fontsize=14)
ax.set_ylabel("Moneyness Group", labelpad=16, fontsize=14)
ax.set_zlabel("Implied Volatility", labelpad=12, fontsize=14)

ax.view_init(elev=20, azim=225)

plt.tight_layout()
fig.savefig(OUT_PDF, bbox_inches="tight")
fig.savefig(OUT_PNG, dpi=300, bbox_inches="tight")
plt.show()
plt.close(fig)
print(f"\nPDF written to: {OUT_PDF}")
print(f"PNG written to: {OUT_PNG}")
