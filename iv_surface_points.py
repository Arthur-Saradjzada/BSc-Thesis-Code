import numpy as np
import pandas as pd
from sqlalchemy import create_engine

CONNECTION_STRING = "mysql+pymysql://root:PASSWORD!@localhost/spx_data"
TABLE_NAME = "spx_options_eod_clean"

START_DATE = "2010-01-01"
END_DATE   = "2024-01-01"  

MIN_DTE = 7
MAX_DTE = 360
MIN_IV = 0.05
MAX_IV = 0.70
MIN_PRICE = 0.05

DELTA_WEIGHT = 10.0       

OUTPUT_XLSX = r"C:\Users\vcsa0\Downloads\surface_points.xlsx"
DROPPED_CSV = r"C:\Users\vcsa0\Downloads\dropped_days.csv"

engine = create_engine(CONNECTION_STRING)

query = f"""
SELECT
    QUOTE_DATE, DTE, STRIKE, UNDERLYING_LAST AS S,
    C_DELTA AS DELTA, C_IV AS IV,
    (C_BID + C_ASK) / 2.0 AS PRICE, 'C' AS OPTION_TYPE
FROM {TABLE_NAME}
WHERE C_DELTA IS NOT NULL AND C_IV IS NOT NULL
  AND C_BID IS NOT NULL AND C_ASK IS NOT NULL
  AND STRIKE IS NOT NULL AND UNDERLYING_LAST IS NOT NULL
  AND QUOTE_DATE >= '{START_DATE}' AND QUOTE_DATE < '{END_DATE}'
  AND DTE >= {MIN_DTE} AND DTE <= {MAX_DTE}
  AND C_IV >= {MIN_IV} AND C_IV <= {MAX_IV}
  AND C_DELTA > 0 AND C_DELTA < 0.5
  AND (C_BID + C_ASK) / 2.0 >= {MIN_PRICE}

UNION ALL

SELECT
    QUOTE_DATE, DTE, STRIKE, UNDERLYING_LAST AS S,
    P_DELTA AS DELTA, P_IV AS IV,
    (P_BID + P_ASK) / 2.0 AS PRICE, 'P' AS OPTION_TYPE
FROM {TABLE_NAME}
WHERE P_DELTA IS NOT NULL AND P_IV IS NOT NULL
  AND P_BID IS NOT NULL AND P_ASK IS NOT NULL
  AND STRIKE IS NOT NULL AND UNDERLYING_LAST IS NOT NULL
  AND QUOTE_DATE >= '{START_DATE}' AND QUOTE_DATE < '{END_DATE}'
  AND DTE >= {MIN_DTE} AND DTE <= {MAX_DTE}
  AND P_IV >= {MIN_IV} AND P_IV <= {MAX_IV}
  AND P_DELTA > -0.5 AND P_DELTA < 0
  AND (P_BID + P_ASK) / 2.0 >= {MIN_PRICE};
"""

print("Loading filtered data...")
df = pd.read_sql(query, engine)

df["QUOTE_DATE"] = pd.to_datetime(df["QUOTE_DATE"])
df["DELTA"] = df["DELTA"].astype(float)
df["DTE"] = df["DTE"].astype(float)
df["IV"] = df["IV"].astype(float)
df["STRIKE"] = df["STRIKE"].astype(float)
df["S"] = df["S"].astype(float)
df["KS"] = df["STRIKE"] / df["S"]

print(f"Rows loaded: {len(df):,}")

def moneyness_bucket(delta, option_type):
    if option_type == "P":
        if -0.125 <= delta < 0:
            return "DOTM put"
        elif -0.375 <= delta < -0.125:
            return "OTM put"
        elif -0.5 < delta < -0.375:
            return "ATM put"
        else:
            return None
    else:  # call
        if 0.375 <= delta < 0.5:
            return "ATM call"
        elif 0.125 <= delta < 0.375:
            return "OTM call"
        elif 0 < delta < 0.125:
            return "DOTM call"
        else:
            return None


def maturity_bucket(dte):
    if 7 <= dte < 45:
        return "7-45d"
    elif 45 <= dte < 90:
        return "45-90d"
    elif 90 <= dte < 180:
        return "90-180d"
    elif 180 <= dte <= 360:
        return "180-360d"
    else:
        return None


mon_labels = []
for delta, option_type in zip(df["DELTA"], df["OPTION_TYPE"]):
    mon_labels.append(moneyness_bucket(delta, option_type))
df["MON_LABEL"] = mon_labels

mat_labels = []
for dte in df["DTE"]:
    mat_labels.append(maturity_bucket(dte))
df["MAT_LABEL"] = mat_labels

df = df.dropna(subset=["MON_LABEL", "MAT_LABEL"]).copy()
print(f"Rows after bucket labelling: {len(df):,}")

mon_order = ["DOTM put", "OTM put", "ATM put", "ATM call", "OTM call", "DOTM call"]
mat_order = ["7-45d", "45-90d", "90-180d", "180-360d"]

mon_target_delta = {
    "DOTM put": -0.0625, "OTM put": -0.25, "ATM put": -0.4375,
    "ATM call": 0.4375, "OTM call": 0.25, "DOTM call": 0.0625,
}
mat_target_dte = {
    "7-45d": 26.0, "45-90d": 67.5, "90-180d": 135.0, "180-360d": 270.0,
}

kept_rows = []          
incomplete_days = []  

print("\nCollecting 24 points per day...")

for day, day_data in df.groupby("QUOTE_DATE", sort=True):

    day_rows = []
    empty_buckets = []

    for mon in mon_order:
        for mat in mat_order:

            in_bucket = day_data[(day_data["MON_LABEL"] == mon) &
                                 (day_data["MAT_LABEL"] == mat)]

            if len(in_bucket) == 0:
                empty_buckets.append(f"{mon} / {mat}")
                continue

            target_delta = mon_target_delta[mon]
            target_dte = mat_target_dte[mat]
            dist = (DELTA_WEIGHT * (in_bucket["DELTA"] - target_delta) ** 2
                    + (in_bucket["DTE"] - target_dte) ** 2)

            best = in_bucket.loc[dist.idxmin()]

            day_rows.append({
                "QUOTE_DATE": day,
                "MON_LABEL": mon,
                "MAT_LABEL": mat,
                "DELTA": best["DELTA"],
                "DTE": best["DTE"],
                "KS": best["KS"],
                "IV": best["IV"],
                "LOG_IV": np.log(best["IV"]),
                "PRICE": best["PRICE"],
                "OPTION_TYPE": best["OPTION_TYPE"],
            })

    if len(empty_buckets) == 0:
        kept_rows.extend(day_rows)
    else:
        incomplete_days.append((day, empty_buckets))

print("\n" + "=" * 70)
print("DAYS WITHOUT 24 POINTS  (dropped, no substitution)")
print("=" * 70)
print(f"Days dropped: {len(incomplete_days)}")
for day, empty in incomplete_days:
    print(f"   {pd.Timestamp(day).date()}  missing {len(empty)} bucket(s): "
          f"{', '.join(empty)}")

dropped_rows = []
for day, empty in incomplete_days:
    for bucket in empty:
        dropped_rows.append({"QUOTE_DATE": pd.Timestamp(day).date(),
                             "EMPTY_BUCKET": bucket})
pd.DataFrame(dropped_rows).to_csv(DROPPED_CSV, index=False)
print(f"\nSaved dropped-day detail: {DROPPED_CSV}")

surface = pd.DataFrame(kept_rows)

surface["MON_LABEL"] = pd.Categorical(surface["MON_LABEL"],
                                      categories=mon_order, ordered=True)
surface["MAT_LABEL"] = pd.Categorical(surface["MAT_LABEL"],
                                      categories=mat_order, ordered=True)
surface = surface.sort_values(["QUOTE_DATE", "MON_LABEL", "MAT_LABEL"]).reset_index(drop=True)

surface.to_excel(OUTPUT_XLSX, index=False)

n_days = surface["QUOTE_DATE"].nunique()
print("\n" + "=" * 70)
print("SURFACE POINTS SAVED")
print("=" * 70)
print(f"Kept days (24 points each): {n_days:,}")
print(f"Total surface points      : {len(surface):,}  (should be {n_days * 24:,})")
print(f"Saved Excel file          : {OUTPUT_XLSX}")
