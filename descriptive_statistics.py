import numpy as np
import pandas as pd
from sqlalchemy import create_engine

CONNECTION_STRING = "mysql+pymysql://root:PASSWORD!@localhost/spx_data"
TABLE_NAME        = "spx_options_eod_clean"

START_DATE = "2010-01-01"
END_DATE   = "2024-01-01" 

engine = create_engine(CONNECTION_STRING)

query = f"""
SELECT
    QUOTE_DATE, DTE, STRIKE, UNDERLYING_LAST AS S,
    C_DELTA, C_IV, C_BID, C_ASK, C_VOLUME,
    P_DELTA, P_IV, P_BID, P_ASK, P_VOLUME
FROM {TABLE_NAME}
WHERE QUOTE_DATE >= '{START_DATE}' AND QUOTE_DATE < '{END_DATE}';
"""
wide = pd.read_sql(query, engine)
print(f"STEP 1 - raw rows (call+put pairs): {len(wide):,}")
print(f"STEP 1 - raw trading days:          {wide['QUOTE_DATE'].nunique():,}")

calls = pd.DataFrame({
    "QUOTE_DATE": wide["QUOTE_DATE"],
    "DTE":        wide["DTE"],
    "STRIKE":     wide["STRIKE"],
    "S":          wide["S"],
    "DELTA":      wide["C_DELTA"],
    "IV":         wide["C_IV"],
    "PRICE":      (wide["C_BID"] + wide["C_ASK"]) / 2.0,   
    "VOLUME":     wide["C_VOLUME"],
    "TYPE":       "C",
})
puts = pd.DataFrame({
    "QUOTE_DATE": wide["QUOTE_DATE"],
    "DTE":        wide["DTE"],
    "STRIKE":     wide["STRIKE"],
    "S":          wide["S"],
    "DELTA":      wide["P_DELTA"],
    "IV":         wide["P_IV"],
    "PRICE":      (wide["P_BID"] + wide["P_ASK"]) / 2.0,   
    "VOLUME":     wide["P_VOLUME"],
    "TYPE":       "P",
})
opt = pd.concat([calls, puts], ignore_index=True)
print(f"STEP 2 - option-level rows (calls + puts): {len(opt):,}")

opt["MONEYNESS"] = opt["STRIKE"] / opt["S"]

before = len(opt)
opt = opt.dropna(subset=["IV", "DELTA", "PRICE", "S", "STRIKE"])
print(f"STEP 4.0 - after dropping missing IV/Delta/price/strike/spot: {len(opt):,}  "
      f"(removed {before - len(opt):,})")

before = len(opt)
is_otm_call = (opt["TYPE"] == "C") & (opt["DELTA"] > 0) & (opt["DELTA"] < 0.5)
is_otm_put  = (opt["TYPE"] == "P") & (opt["DELTA"] < 0) & (opt["DELTA"] > -0.5)
opt = opt[is_otm_call | is_otm_put]
print(f"STEP 4.1 - after OTM filter |Delta| < 0.5: {len(opt):,}  "
      f"(removed {before - len(opt):,})")

before = len(opt)
opt = opt[(opt["DTE"] >= 7) & (opt["DTE"] <= 360)]
print(f"STEP 4.2 - after maturity 7-360 days: {len(opt):,}  "
      f"(removed {before - len(opt):,})")

before = len(opt)
opt = opt[opt["IV"] <= 0.70]
print(f"STEP 4.3 - after IV ceiling 0.70: {len(opt):,}  "
      f"(removed {before - len(opt):,})")

before = len(opt)
opt = opt[opt["IV"] >= 0.05]
print(f"STEP 4.4 - after IV floor 0.05: {len(opt):,}  "
      f"(removed {before - len(opt):,})")

before = len(opt)
opt = opt[opt["PRICE"] >= 0.05]
print(f"STEP 4.5 - after price floor $0.05: {len(opt):,}  "
      f"(removed {before - len(opt):,})")

n_days_raw   = wide["QUOTE_DATE"].nunique()
n_days_final = opt["QUOTE_DATE"].nunique()

print(f"\nFinal filtered observations: {len(opt):,}")
print(f"Trading days (raw):          {n_days_raw:,}")
print(f"Trading days (filtered):     {n_days_final:,}")
print(f"Days lost entirely:          {n_days_raw - n_days_final:,}")
print(f"Average obs per day:         {len(opt) / n_days_final:,.1f}")

def maturity_bucket(dte):
    if 7 <= dte < 45:
        return "7--45 days"
    elif 45 <= dte < 90:
        return "45--90 days"
    elif 90 <= dte < 180:
        return "90--180 days"
    elif 180 <= dte <= 360:
        return "180--360 days"
    else:
        return None  

maturity_labels = []
for dte in opt["DTE"]:
    maturity_labels.append(maturity_bucket(dte))
opt["MATURITY_BUCKET"] = maturity_labels

def moneyness_bucket(delta, opt_type):
    if opt_type == "P":
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

moneyness_labels = []
for delta, opt_type in zip(opt["DELTA"], opt["TYPE"]):
    moneyness_labels.append(moneyness_bucket(delta, opt_type))
opt["MONEYNESS_BUCKET"] = moneyness_labels

before = len(opt)
opt = opt.dropna(subset=["MATURITY_BUCKET", "MONEYNESS_BUCKET"])
print(f"\nSTEP 6 - after bucket assignment: {len(opt):,}  "
      f"(unbucketed removed: {before - len(opt):,})")

print("\nObservations per bucket:")
print(opt.groupby(["MONEYNESS_BUCKET", "MATURITY_BUCKET"]).size().to_string())

MONEYNESS_ORDER = ["DOTM put", "OTM put", "ATM put",
                   "ATM call", "OTM call", "DOTM call"]
MATURITY_ORDER  = ["7--45 days", "45--90 days", "90--180 days", "180--360 days"]

grouped = opt.groupby(["MONEYNESS_BUCKET", "MATURITY_BUCKET"])

stats = pd.DataFrame({
    "iv_mean":        grouped["IV"].mean(),
    "iv_sd":          grouped["IV"].std(),
    "dtm_mean":       grouped["DTE"].mean(),
    "dtm_sd":         grouped["DTE"].std(),
    "moneyness_mean": grouped["MONEYNESS"].mean(),
    "moneyness_sd":   grouped["MONEYNESS"].std(),
    "delta_mean":     grouped["DELTA"].mean(),
    "delta_sd":       grouped["DELTA"].std(),
}).reset_index()


daily_bucket = (opt.groupby(["QUOTE_DATE", "MONEYNESS_BUCKET", "MATURITY_BUCKET"])
                   ["VOLUME"].sum().reset_index())
daily_bucket = daily_bucket.rename(columns={"VOLUME": "bucket_vol"})

daily_total = (opt.groupby("QUOTE_DATE")["VOLUME"].sum().reset_index())
daily_total = daily_total.rename(columns={"VOLUME": "total_vol"})

daily_bucket = daily_bucket.merge(daily_total, on="QUOTE_DATE")
daily_bucket["share_pct"] = 100.0 * daily_bucket["bucket_vol"] / daily_bucket["total_vol"]

vol_share = (daily_bucket.groupby(["MONEYNESS_BUCKET", "MATURITY_BUCKET"])
                         ["share_pct"].mean().reset_index())
vol_share = vol_share.rename(columns={"share_pct": "trading_vol_pct"})

stats = stats.merge(vol_share, on=["MONEYNESS_BUCKET", "MATURITY_BUCKET"])

stats["MONEYNESS_BUCKET"] = pd.Categorical(stats["MONEYNESS_BUCKET"],
                                           categories=MONEYNESS_ORDER, ordered=True)
stats["MATURITY_BUCKET"]  = pd.Categorical(stats["MATURITY_BUCKET"],
                                           categories=MATURITY_ORDER, ordered=True)
stats = stats.sort_values(["MONEYNESS_BUCKET", "MATURITY_BUCKET"])

print("\nPer-bucket statistics:")
print(stats.round(3).to_string(index=False))

VARIABLES = [
    ("IV",          "iv_mean",        "iv_sd"),
    ("DTM",         "dtm_mean",       "dtm_sd"),
    ("Moneyness",   "moneyness_mean", "moneyness_sd"),
    (r"$\Delta$",   "delta_mean",     "delta_sd"),
]

def cell(mon, mat, column):
    row = stats[(stats["MONEYNESS_BUCKET"] == mon) &
                (stats["MATURITY_BUCKET"] == mat)]
    if row.empty:
        return ""
    return f"{row.iloc[0][column]:.2f}"

lines = []
lines.append(r"\begin{table}[htbp]")
lines.append(r"\centering")
lines.append(r"\caption{Summary statistics}")
lines.append(r"\label{tab:summary_statistics}")
lines.append(r"\small")
lines.append(r"\begin{tabular}{llrrrrrrrr}")
lines.append(r"\toprule")
lines.append(r"& & \multicolumn{2}{c}{7--45 days} & \multicolumn{2}{c}{45--90 days} "
             r"& \multicolumn{2}{c}{90--180 days} & \multicolumn{2}{c}{180--360 days} \\")
lines.append(r"\cmidrule(lr){3-4}\cmidrule(lr){5-6}\cmidrule(lr){7-8}\cmidrule(lr){9-10}")
lines.append(r"& & Mean & SD & Mean & SD & Mean & SD & Mean & SD \\")
lines.append(r"\midrule")

for mon in MONEYNESS_ORDER:
    first = True
    for label, mean_col, sd_col in VARIABLES:
        cells = []
        for mat in MATURITY_ORDER:
            cells.append(cell(mon, mat, mean_col))
            cells.append(cell(mon, mat, sd_col))
        if first:
            lines.append(rf"\multirow{{5}}{{*}}{{{mon}}} & {label} & " + " & ".join(cells) + r" \\")
            first = False
        else:
            lines.append(rf"& {label} & " + " & ".join(cells) + r" \\")

    vol_cells = []
    for mat in MATURITY_ORDER:
        vol_cells.append(cell(mon, mat, "trading_vol_pct"))
        vol_cells.append("")
    lines.append(r"& Trading Vol (\%) & " + " & ".join(vol_cells) + r" \\")

    if mon != MONEYNESS_ORDER[-1]:
        lines.append(r"\addlinespace")

lines.append(r"\bottomrule")
lines.append(r"\end{tabular}")
lines.append(r"\end{table}")

latex_table = "\n".join(lines)
