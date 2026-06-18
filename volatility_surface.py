"""
volatility_surface.py

Purpose:
Construct a balanced 24-bucket implied volatility surface from filtered SPX option data.

The script:
1. Loads call and put options from the typed SQL table.
2. Applies the option filters.
3. Assigns each contract to a delta-based moneyness bucket and a DTE-based maturity bucket.
4. For each trading day and each of the 24 target buckets, selects one representative contract.
5. Saves the balanced surface panel as a CSV file.
6. Shows the implied volatility surface for one selected trading day.



Input:
    spx_options_eod_clean

Before running:
    1. Check CONNECTION_STRING.
    2. Check TABLE_NAME.
    3. Check START_DATE and END_DATE.
    4. Check PLOT_DAY.
    5. Check OUTPUT_CSV. This must be the full path where the CSV file should be saved. This file will be used in the following programs

Example OUTPUT_CSV:
    OUTPUT_CSV = r"C:\\Users\\vcsa0\\Downloads\\volatility_surface_panel.csv"

Run:
    python construct_volatility_surface.py
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sqlalchemy import create_engine


# ---------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------

CONNECTION_STRING = "mysql+pymysql://root:PASSWORD@localhost/spx_data"
TABLE_NAME = "spx_options_eod_clean"

START_DATE = "2010-01-01"
END_DATE = "2022-01-01"

MIN_DTE = 7
MAX_DTE = 360
MIN_IV = 0.05
MAX_IV = 0.70
MIN_PRICE = 0.05

PLOT_DAY = "2010-06-04"

# Full path where the balanced volatility-surface panel will be saved.
OUTPUT_CSV = r"C:PATH HERE volatility_surface_panel.csv" # <-- UPDATE THIS TO YOUR DESIRED PATH

engine = create_engine(CONNECTION_STRING)


# ---------------------------------------------------------------------
# Query: pull filtered OTM call and put data
# ---------------------------------------------------------------------

query = f"""
SELECT
    QUOTE_DATE,
    DTE,
    C_DELTA AS DELTA,
    C_IV AS IV,
    (C_BID + C_ASK) / 2.0 AS PRICE,
    'C' AS OPTION_TYPE
FROM {TABLE_NAME}
WHERE C_DELTA IS NOT NULL
  AND C_IV IS NOT NULL
  AND C_BID IS NOT NULL
  AND C_ASK IS NOT NULL
  AND QUOTE_DATE >= '{START_DATE}'
  AND QUOTE_DATE < '{END_DATE}'
  AND DTE >= {MIN_DTE}
  AND DTE <= {MAX_DTE}
  AND C_IV >= {MIN_IV}
  AND C_IV <= {MAX_IV}
  AND C_DELTA > 0
  AND C_DELTA < 0.5
  AND (C_BID + C_ASK) / 2.0 >= {MIN_PRICE}

UNION ALL

SELECT
    QUOTE_DATE,
    DTE,
    P_DELTA AS DELTA,
    P_IV AS IV,
    (P_BID + P_ASK) / 2.0 AS PRICE,
    'P' AS OPTION_TYPE
FROM {TABLE_NAME}
WHERE P_DELTA IS NOT NULL
  AND P_IV IS NOT NULL
  AND P_BID IS NOT NULL
  AND P_ASK IS NOT NULL
  AND QUOTE_DATE >= '{START_DATE}'
  AND QUOTE_DATE < '{END_DATE}'
  AND DTE >= {MIN_DTE}
  AND DTE <= {MAX_DTE}
  AND P_IV >= {MIN_IV}
  AND P_IV <= {MAX_IV}
  AND P_DELTA > -0.5
  AND P_DELTA < 0
  AND (P_BID + P_ASK) / 2.0 >= {MIN_PRICE};
"""

print("Loading filtered data...")
df = pd.read_sql(query, engine)

df["QUOTE_DATE"] = pd.to_datetime(df["QUOTE_DATE"])
df["DELTA"] = df["DELTA"].astype(float)
df["DTE"] = df["DTE"].astype(float)
df["IV"] = df["IV"].astype(float)

print(f"Rows loaded: {len(df):,}")


# ---------------------------------------------------------------------
# Bucket definitions
# ---------------------------------------------------------------------

mon_order = [
    "DOTM call",
    "OTM call",
    "ATM call",
    "ATM put",
    "OTM put",
    "DOTM put",
]

mat_order = [
    "7-45d",
    "45-90d",
    "90-180d",
    "180-360d",
]

mon_specs = {
    "DOTM put": {"low": -0.125, "high": 0.000, "mid": -0.0625},
    "OTM put": {"low": -0.375, "high": -0.125, "mid": -0.2500},
    "ATM put": {"low": -0.500, "high": -0.375, "mid": -0.4375},
    "ATM call": {"low": 0.375, "high": 0.500, "mid": 0.4375},
    "OTM call": {"low": 0.125, "high": 0.375, "mid": 0.2500},
    "DOTM call": {"low": 0.000, "high": 0.125, "mid": 0.0625},
}

mat_specs = {
    "7-45d": {"low": 7.0, "high": 45.0, "mid": 26.0},
    "45-90d": {"low": 45.0, "high": 90.0, "mid": 67.5},
    "90-180d": {"low": 90.0, "high": 180.0, "mid": 135.0},
    "180-360d": {"low": 180.0, "high": 360.0, "mid": 270.0},
}

bucket_specs = []

for mon_label in mon_order:
    for mat_label in mat_order:
        bucket_specs.append(
            {
                "MON_LABEL": mon_label,
                "MAT_LABEL": mat_label,
                "DELTA_MID": mon_specs[mon_label]["mid"],
                "DTE_MID": mat_specs[mat_label]["mid"],
            }
        )

bucket_df = pd.DataFrame(bucket_specs)


# ---------------------------------------------------------------------
# Assign each contract to a moneyness bucket
# ---------------------------------------------------------------------

df["MON_LABEL"] = np.nan

df.loc[(df["DELTA"] > -0.500) & (df["DELTA"] <= -0.375), "MON_LABEL"] = "ATM put"
df.loc[(df["DELTA"] > -0.375) & (df["DELTA"] <= -0.125), "MON_LABEL"] = "OTM put"
df.loc[(df["DELTA"] > -0.125) & (df["DELTA"] < 0.000), "MON_LABEL"] = "DOTM put"

df.loc[(df["DELTA"] >= 0.375) & (df["DELTA"] < 0.500), "MON_LABEL"] = "ATM call"
df.loc[(df["DELTA"] >= 0.125) & (df["DELTA"] < 0.375), "MON_LABEL"] = "OTM call"
df.loc[(df["DELTA"] > 0.000) & (df["DELTA"] < 0.125), "MON_LABEL"] = "DOTM call"


# ---------------------------------------------------------------------
# Assign each contract to a maturity bucket
# ---------------------------------------------------------------------

df["MAT_LABEL"] = np.nan

df.loc[(df["DTE"] >= 7.0) & (df["DTE"] < 45.0), "MAT_LABEL"] = "7-45d"
df.loc[(df["DTE"] >= 45.0) & (df["DTE"] < 90.0), "MAT_LABEL"] = "45-90d"
df.loc[(df["DTE"] >= 90.0) & (df["DTE"] < 180.0), "MAT_LABEL"] = "90-180d"
df.loc[(df["DTE"] >= 180.0) & (df["DTE"] <= 360.0), "MAT_LABEL"] = "180-360d"

df = df.dropna(subset=["MON_LABEL", "MAT_LABEL"]).copy()

print(f"Rows after bucket assignment: {len(df):,}")


# ---------------------------------------------------------------------
# Construct balanced 24-bucket surface
# ---------------------------------------------------------------------

def select_surface_for_day(day_data: pd.DataFrame) -> pd.DataFrame:
    selected_rows = []
    quote_date = day_data["QUOTE_DATE"].iloc[0]

    for _, bucket in bucket_df.iterrows():
        target_mon = bucket["MON_LABEL"]
        target_mat = bucket["MAT_LABEL"]
        delta_mid = bucket["DELTA_MID"]
        dte_mid = bucket["DTE_MID"]

        in_bucket = day_data[
            (day_data["MON_LABEL"] == target_mon)
            & (day_data["MAT_LABEL"] == target_mat)
        ].copy()

        if len(in_bucket) > 0:
            candidates = in_bucket
            fallback_used = False
        else:
            candidates = day_data.copy()
            fallback_used = True

        candidates = candidates.copy()
        candidates["DIST"] = (
            10.0 * (candidates["DELTA"] - delta_mid) ** 2
            + (candidates["DTE"] - dte_mid) ** 2
        )

        best = (
            candidates
            .sort_values(["DIST", "PRICE"], ascending=[True, False])
            .iloc[0]
            .copy()
        )

        best["TARGET_MON_LABEL"] = target_mon
        best["TARGET_MAT_LABEL"] = target_mat
        best["FALLBACK_USED"] = fallback_used
        best["QUOTE_DATE"] = quote_date

        selected_rows.append(best)

    return pd.DataFrame(selected_rows)


print("\nConstructing balanced 24-bucket surface...")

df_surface = (
    df.groupby("QUOTE_DATE", group_keys=False)
    .apply(select_surface_for_day)
    .reset_index(drop=True)
)

df_surface = df_surface.rename(
    columns={
        "MON_LABEL": "CONTRACT_MON_LABEL",
        "MAT_LABEL": "CONTRACT_MAT_LABEL",
        "TARGET_MON_LABEL": "MON_LABEL",
        "TARGET_MAT_LABEL": "MAT_LABEL",
    }
)

n_days = df_surface["QUOTE_DATE"].nunique()
n_obs = len(df_surface)
bucket_counts = df_surface.groupby("QUOTE_DATE").size()

print(f"\nSurface observations : {n_obs:,}")
print(f"Trading days         : {n_days:,}")
print(f"Avg buckets per day  : {n_obs / n_days:.1f}  (target: 24.0)")
print(f"Min buckets per day  : {bucket_counts.min()}")
print(f"Max buckets per day  : {bucket_counts.max()}")
print(f"Share exactly 24     : {(bucket_counts == 24).mean():.2%}")
print(f"Fallback selections  : {df_surface['FALLBACK_USED'].sum():,}")


# ---------------------------------------------------------------------
# Save balanced panel
# ---------------------------------------------------------------------

df_surface_out = df_surface[
    [
        "QUOTE_DATE",
        "MON_LABEL",
        "MAT_LABEL",
        "DELTA",
        "DTE",
        "IV",
        "PRICE",
        "OPTION_TYPE",
        "DIST",
        "FALLBACK_USED",
        "CONTRACT_MON_LABEL",
        "CONTRACT_MAT_LABEL",
    ]
].sort_values(["QUOTE_DATE", "MON_LABEL", "MAT_LABEL"])

df_surface_out.to_csv(OUTPUT_CSV, index=False)

print(f"\nSaved panel: {OUTPUT_CSV} ({len(df_surface_out):,} rows)")


# ---------------------------------------------------------------------
# Plot volatility surface for one selected day
# ---------------------------------------------------------------------

mon_idx = {m: i + 1 for i, m in enumerate(mon_order)}
mat_idx = {m: i + 1 for i, m in enumerate(mat_order)}


def plot_surface(date_str: str, ax, title: str) -> None:
    date = pd.Timestamp(date_str)
    day_data = df_surface[df_surface["QUOTE_DATE"] == date].copy()

    if len(day_data) == 0:
        available = np.sort(df_surface["QUOTE_DATE"].unique())
        nearest = available[np.argmin(np.abs(available - np.datetime64(date)))]
        day_data = df_surface[df_surface["QUOTE_DATE"] == nearest].copy()
        print(f"{date_str} not found, using {pd.Timestamp(nearest).date()}")

    day_data["MON_IDX"] = day_data["MON_LABEL"].map(mon_idx)
    day_data["MAT_IDX"] = day_data["MAT_LABEL"].map(mat_idx)
    day_data = day_data.dropna(subset=["MON_IDX", "MAT_IDX"])

    pivot = day_data.pivot_table(
        index="MON_IDX",
        columns="MAT_IDX",
        values="IV",
        aggfunc="mean",
    )

    pivot = pivot.reindex(index=[1, 2, 3, 4, 5, 6], columns=[1, 2, 3, 4])

    X, Y = np.meshgrid(
        pivot.columns.values.astype(float),
        pivot.index.values.astype(float),
    )
    Z = pivot.values.astype(float)

    ax.plot_surface(
        X,
        Y,
        Z,
        color="red",
        alpha=0.85,
        edgecolor="black",
        linewidth=0.3,
        antialiased=True,
    )

    ax.set_xticks([1, 2, 3, 4])
    ax.set_xticklabels(
        ["7-45\ndays", "45-90\ndays", "90-180\ndays", "180-360\ndays"],
        fontsize=7,
    )

    ax.set_yticks([1, 2, 3, 4, 5, 6])
    ax.set_yticklabels(
        ["DOTM\nCall", "OTM\nCall", "ATM\nCall", "ATM\nPut", "OTM\nPut", "DOTM\nPut"],
        fontsize=7,
    )

    ax.set_xlabel("Maturity Group", labelpad=8, fontsize=8)
    ax.set_ylabel("Moneyness Group", labelpad=8, fontsize=8)
    ax.set_zlabel("Implied Volatility", labelpad=8, fontsize=8)

    ax.set_zlim(0.05, 0.80)
    ax.set_title(title, fontsize=11, pad=12)

    ax.view_init(elev=20, azim=225)


print(f"\nPlotting surface for {PLOT_DAY}...")

fig = plt.figure(figsize=(10, 7))
ax = fig.add_subplot(111, projection="3d")

plot_surface(PLOT_DAY, ax, f"Volatility Surface on {PLOT_DAY}")

plt.tight_layout()
plt.show()
