"""
descriptive_statistics_spx.py

Purpose:
Create a LaTeX descriptive-statistics table for filtered SPX option data.

The script:
1. Reads option data from a MySQL table.
2. Converts the wide call/put format into option-level rows inside SQL.
3. Applies the selected filtering rules.
4. Assigns maturity and delta-based moneyness buckets.
5. Computes descriptive statistics by bucket.
6. Prints and saves a LaTeX table.

Before running:
1. Make sure the MySQL table exists.
2. Install dependencies:
       pip install pandas sqlalchemy pymysql
3. Set your database connection string as an environment variable.

   PowerShell example:
       $env:MYSQL_CONNECTION_STRING="mysql+pymysql://root:YOUR_PASSWORD@localhost/spx_data"

   Or edit CONNECTION_STRING below manually.

4. Check these settings:
       TABLE_NAME
       START_DATE
       END_DATE
       MIN_DTE
       MAX_DTE
       MIN_IV
       MAX_IV
       MIN_PRICE
       OUTPUT_TEX_FILE

Run:
    python descriptive_statistics_spx.py

LaTeX requirements:
    \\usepackage{booktabs}
    \\usepackage{multirow}
"""

import os
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine


# ---------------------------------------------------------------------
# 1. Settings
# ---------------------------------------------------------------------

CONNECTION_STRING = os.getenv(
    "MYSQL_CONNECTION_STRING",
    "mysql+pymysql://root:PASSWORD@localhost/spx_data",
)

TABLE_NAME = "spx_options_eod_clean"

START_DATE = "2010-01-01"
END_DATE = "2022-01-01" 

MIN_DTE = 7
MAX_DTE = 360

MIN_IV = 0.05
MAX_IV = 0.70

MIN_PRICE = 0.05

OUTPUT_TEX_FILE = Path("descriptive_statistics_spx.tex")

engine = create_engine(CONNECTION_STRING)


# ---------------------------------------------------------------------
# 2. Labels and ordering
# ---------------------------------------------------------------------

MONEYNESS_ORDER = [
    "DOTM put",
    "OTM put",
    "ATM put",
    "ATM call",
    "OTM call",
    "DOTM call",
]

MATURITY_ORDER = [
    "7--45 days",
    "45--90 days",
    "90--180 days",
    "180--360 days",
]

VARIABLES = [
    ("IV", "iv_mean", "iv_sd"),
    ("DTM", "dtm_mean", "dtm_sd"),
    ("Moneyness", "moneyness_mean", "moneyness_sd"),
    (r"$\Delta$", "delta_mean", "delta_sd"),
]


# ---------------------------------------------------------------------
# 3. SQL query
# ---------------------------------------------------------------------

def build_descriptive_query() -> str:
    """
    Build SQL query that:
    - reshapes calls and puts into option-level rows;
    - filters the option observations;
    - assigns buckets;
    - computes descriptive statistics;
    - computes average daily trading-volume shares.
    """

    return f"""
    WITH option_level AS (
        SELECT
            QUOTE_DATE,
            DTE,
            C_DELTA AS DELTA,
            C_IV AS IV,
            UNDERLYING_LAST AS UNDERLYING,
            STRIKE,
            (C_BID + C_ASK) / 2.0 AS PRICE,
            COALESCE(C_VOLUME, 0) AS VOLUME,
            'C' AS OPTION_TYPE
        FROM {TABLE_NAME}
        WHERE C_DELTA IS NOT NULL
          AND C_IV IS NOT NULL
          AND C_BID IS NOT NULL
          AND C_ASK IS NOT NULL
          AND UNDERLYING_LAST IS NOT NULL
          AND STRIKE IS NOT NULL

        UNION ALL

        SELECT
            QUOTE_DATE,
            DTE,
            P_DELTA AS DELTA,
            P_IV AS IV,
            UNDERLYING_LAST AS UNDERLYING,
            STRIKE,
            (P_BID + P_ASK) / 2.0 AS PRICE,
            COALESCE(P_VOLUME, 0) AS VOLUME,
            'P' AS OPTION_TYPE
        FROM {TABLE_NAME}
        WHERE P_DELTA IS NOT NULL
          AND P_IV IS NOT NULL
          AND P_BID IS NOT NULL
          AND P_ASK IS NOT NULL
          AND UNDERLYING_LAST IS NOT NULL
          AND STRIKE IS NOT NULL
    ),

    filtered_options AS (
        SELECT
            QUOTE_DATE,
            DTE,
            DELTA,
            IV,
            STRIKE / UNDERLYING AS MONEYNESS,
            VOLUME,

            CASE
                WHEN DTE >= 7 AND DTE < 45 THEN '7--45 days'
                WHEN DTE >= 45 AND DTE < 90 THEN '45--90 days'
                WHEN DTE >= 90 AND DTE < 180 THEN '90--180 days'
                WHEN DTE >= 180 AND DTE <= 360 THEN '180--360 days'
            END AS MATURITY_BUCKET,

            CASE
                WHEN OPTION_TYPE = 'P' AND DELTA > -0.125 AND DELTA < 0
                    THEN 'DOTM put'
                WHEN OPTION_TYPE = 'P' AND DELTA > -0.375 AND DELTA <= -0.125
                    THEN 'OTM put'
                WHEN OPTION_TYPE = 'P' AND DELTA > -0.5 AND DELTA <= -0.375
                    THEN 'ATM put'
                WHEN OPTION_TYPE = 'C' AND DELTA >= 0.375 AND DELTA < 0.5
                    THEN 'ATM call'
                WHEN OPTION_TYPE = 'C' AND DELTA >= 0.125 AND DELTA < 0.375
                    THEN 'OTM call'
                WHEN OPTION_TYPE = 'C' AND DELTA > 0 AND DELTA < 0.125
                    THEN 'DOTM call'
            END AS MONEYNESS_BUCKET

        FROM option_level
        WHERE QUOTE_DATE >= '{START_DATE}'
          AND QUOTE_DATE < '{END_DATE}'

          AND DTE >= {MIN_DTE}
          AND DTE <= {MAX_DTE}

          AND IV >= {MIN_IV}
          AND IV <= {MAX_IV}

          AND (
                (OPTION_TYPE = 'C' AND DELTA > 0 AND DELTA < 0.5)
                OR
                (OPTION_TYPE = 'P' AND DELTA > -0.5 AND DELTA < 0)
              )

          AND PRICE >= {MIN_PRICE}
          AND UNDERLYING > 0
          AND STRIKE > 0
    ),

    bucket_stats AS (
        SELECT
            MONEYNESS_BUCKET,
            MATURITY_BUCKET,

            COUNT(*) AS n_obs,

            AVG(IV) AS iv_mean,
            STDDEV_SAMP(IV) AS iv_sd,

            AVG(DTE) AS dtm_mean,
            STDDEV_SAMP(DTE) AS dtm_sd,

            AVG(MONEYNESS) AS moneyness_mean,
            STDDEV_SAMP(MONEYNESS) AS moneyness_sd,

            AVG(DELTA) AS delta_mean,
            STDDEV_SAMP(DELTA) AS delta_sd

        FROM filtered_options
        WHERE MATURITY_BUCKET IS NOT NULL
          AND MONEYNESS_BUCKET IS NOT NULL
        GROUP BY MONEYNESS_BUCKET, MATURITY_BUCKET
    ),

    daily_bucket_volume AS (
        SELECT
            QUOTE_DATE,
            MONEYNESS_BUCKET,
            MATURITY_BUCKET,
            SUM(VOLUME) AS bucket_volume
        FROM filtered_options
        WHERE MATURITY_BUCKET IS NOT NULL
          AND MONEYNESS_BUCKET IS NOT NULL
        GROUP BY QUOTE_DATE, MONEYNESS_BUCKET, MATURITY_BUCKET
    ),

    daily_total_volume AS (
        SELECT
            QUOTE_DATE,
            SUM(VOLUME) AS total_volume
        FROM filtered_options
        WHERE MATURITY_BUCKET IS NOT NULL
          AND MONEYNESS_BUCKET IS NOT NULL
        GROUP BY QUOTE_DATE
    ),

    volume_stats AS (
        SELECT
            b.MONEYNESS_BUCKET,
            b.MATURITY_BUCKET,
            AVG(
                CASE
                    WHEN t.total_volume > 0
                    THEN 100.0 * b.bucket_volume / t.total_volume
                    ELSE NULL
                END
            ) AS trading_vol_pct
        FROM daily_bucket_volume b
        INNER JOIN daily_total_volume t
            ON b.QUOTE_DATE = t.QUOTE_DATE
        GROUP BY b.MONEYNESS_BUCKET, b.MATURITY_BUCKET
    )

    SELECT
        s.MONEYNESS_BUCKET,
        s.MATURITY_BUCKET,
        s.n_obs,

        s.iv_mean,
        s.iv_sd,

        s.dtm_mean,
        s.dtm_sd,

        s.moneyness_mean,
        s.moneyness_sd,

        s.delta_mean,
        s.delta_sd,

        v.trading_vol_pct

    FROM bucket_stats s
    LEFT JOIN volume_stats v
        ON s.MONEYNESS_BUCKET = v.MONEYNESS_BUCKET
       AND s.MATURITY_BUCKET = v.MATURITY_BUCKET;
    """


# ---------------------------------------------------------------------
# 4. Load descriptive statistics
# ---------------------------------------------------------------------

def load_descriptive_statistics() -> pd.DataFrame:
    """
    Run the SQL query and return the result as a pandas DataFrame.
    """

    query = build_descriptive_query()
    df = pd.read_sql(query, engine)

    df["MONEYNESS_BUCKET"] = pd.Categorical(
        df["MONEYNESS_BUCKET"],
        categories=MONEYNESS_ORDER,
        ordered=True,
    )

    df["MATURITY_BUCKET"] = pd.Categorical(
        df["MATURITY_BUCKET"],
        categories=MATURITY_ORDER,
        ordered=True,
    )

    df = df.sort_values(["MONEYNESS_BUCKET", "MATURITY_BUCKET"])

    return df


# ---------------------------------------------------------------------
# 5. Formatting helpers
# ---------------------------------------------------------------------

def fmt(value: float, decimals: int = 2) -> str:
    """
    Format numeric values for LaTeX.
    """

    if pd.isna(value):
        return ""
    return f"{float(value):.{decimals}f}"


def get_cell(df: pd.DataFrame, mon: str, mat: str, column: str) -> str:
    """
    Get one formatted table value.
    """

    row = df[
        (df["MONEYNESS_BUCKET"] == mon)
        & (df["MATURITY_BUCKET"] == mat)
    ]

    if row.empty:
        return ""

    return fmt(row.iloc[0][column], 2)


# ---------------------------------------------------------------------
# 6. Build LaTeX table
# ---------------------------------------------------------------------

def build_latex_table(df: pd.DataFrame) -> str:
    """
    Create the LaTeX table as a string.
    """

    lines = []

    lines.append(r"\begin{table}[htbp]")
    lines.append(r"\centering")
    lines.append(r"\caption{Descriptive statistics}")
    lines.append(r"\label{tab:descriptive_statistics}")
    lines.append(r"\small")
    lines.append(r"\begin{tabular}{llrrrrrrrr}")
    lines.append(r"\toprule")
    lines.append(
        r"& & \multicolumn{2}{c}{7--45 days} "
        r"& \multicolumn{2}{c}{45--90 days} "
        r"& \multicolumn{2}{c}{90--180 days} "
        r"& \multicolumn{2}{c}{180--360 days} \\"
    )
    lines.append(
        r"\cmidrule(lr){3-4}"
        r"\cmidrule(lr){5-6}"
        r"\cmidrule(lr){7-8}"
        r"\cmidrule(lr){9-10}"
    )
    lines.append(r"& & Mean & SD & Mean & SD & Mean & SD & Mean & SD \\")
    lines.append(r"\midrule")

    for mon in MONEYNESS_ORDER:
        first_row = True

        for label, mean_col, sd_col in VARIABLES:
            cells = []

            for mat in MATURITY_ORDER:
                cells.append(get_cell(df, mon, mat, mean_col))
                cells.append(get_cell(df, mon, mat, sd_col))

            if first_row:
                line = rf"\multirow{{5}}{{*}}{{{mon}}} & {label} & " + " & ".join(cells) + r" \\"
                first_row = False
            else:
                line = rf"& {label} & " + " & ".join(cells) + r" \\"

            lines.append(line)

        volume_cells = []
        for mat in MATURITY_ORDER:
            volume_cells.append(get_cell(df, mon, mat, "trading_vol_pct"))
            volume_cells.append("")

        lines.append(r"& Trading Vol (\%) & " + " & ".join(volume_cells) + r" \\")

        if mon != MONEYNESS_ORDER[-1]:
            lines.append(r"\addlinespace")

    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(r"\begin{minipage}{0.98\textwidth}")
    lines.append(r"\smallskip")
    lines.append(
        r"\footnotesize "
        r"\textit{Note}: The table reports descriptive statistics for filtered option observations. "
        r"Implied volatility (IV), days to maturity (DTM), moneyness $(K/S)$, and option "
        r"delta $(\Delta)$ are reported with means and standard deviations. "
        r"Trading Vol (\%) is the average daily percentage share of total filtered option "
        r"volume in each maturity--moneyness bucket. "
        r"The maturity buckets are 7--45, 45--90, 90--180, and 180--360 days. "
        r"The moneyness buckets are defined using option delta."
    )
    lines.append(r"\end{minipage}")
    lines.append(r"\end{table}")

    return "\n".join(lines)


# ---------------------------------------------------------------------
# 7. Diagnostics
# ---------------------------------------------------------------------

def print_diagnostics(df: pd.DataFrame) -> None:
    """
    Print a compact diagnostic summary.
    """

    total_obs = int(df["n_obs"].sum())
    available_cells = len(df)

    print("\nDescriptive-statistics dataset")
    print("------------------------------")
    print(f"Available maturity-moneyness cells: {available_cells}")
    print(f"Total filtered observations:        {total_obs:,}")

    print("\nObservations by bucket")
    print("----------------------")
    compact = df[
        ["MONEYNESS_BUCKET", "MATURITY_BUCKET", "n_obs"]
    ].copy()

    print(compact.to_string(index=False))


# ---------------------------------------------------------------------
# 8. Main
# ---------------------------------------------------------------------

def main() -> None:
    if "YOUR_PASSWORD" in CONNECTION_STRING:
        raise ValueError(
            "Please set MYSQL_CONNECTION_STRING or replace YOUR_PASSWORD in CONNECTION_STRING."
        )

    print("Computing descriptive statistics...")

    stats = load_descriptive_statistics()

    print_diagnostics(stats)

    latex_table = build_latex_table(stats)

    OUTPUT_TEX_FILE.write_text(latex_table, encoding="utf-8")

    print("\nLaTeX table")
    print("-----------")
    print(latex_table)

    print(f"\nSaved LaTeX table to: {OUTPUT_TEX_FILE.resolve()}")


if __name__ == "__main__":
    main()
