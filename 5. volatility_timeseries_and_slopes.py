"""
volatility_timeseries_and_slopes.py

Purpose:
Create descriptive time-series plots from the SPX implied-volatility
surface panel.

The script produces two figures:

1. Volatility time series
   - Panel A: average implied volatility across all 24 surface buckets.
   - VIX overlay from the SQL table vix_eod.
   - Panel B: implied-volatility time series for all 24 buckets.

2. Surface slope time series
   - Panel A: smile slope by maturity bucket:
         IV(DOTM put) - IV(DOTM call)
   - Panel B: term-structure slope by moneyness bucket:
         IV(180-360d) - IV(7-45d)

Important:
The VIX series is used only as a benchmark overlay. 

Before running:
    1. Check CONNECTION_STRING.
    2. Check SURFACE_FILE.
       This must point to the CSV file created by construct_volatility_surface.py. # will be adjusted to SQL SOON

    3. Check VIX_TABLE_NAME.
       The VIX table should be in the same database and should contain:
           QUOTE_DATE
           UNDERLYING_LAST

    4. Check START_DATE and END_DATE.

    5. Check SAVE_FIGURES.

Run:
    python volatility_timeseries_and_slopes.py
"""

import os
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from sqlalchemy import create_engine


# ---------------------------------------------------------------------
# 1. Settings
# ---------------------------------------------------------------------

CONNECTION_STRING = os.getenv(
    "MYSQL_CONNECTION_STRING",
    "mysql+pymysql://root:PASSWORD@localhost/spx_data",
)

SURFACE_FILE = Path(r"C:\Here\Your\Path\volatility_surface_panel.csv")

VIX_TABLE_NAME = "vix_eod"
VIX_VALUE_COLUMN = "UNDERLYING_LAST"

START_DATE = "2010-01-01"
END_DATE = "2022-01-01"  

SAVE_FIGURES = False

FIGURE2_PDF = "figure1_volatility_timeseries.pdf"
FIGURE2_PNG = "figure1_volatility_timeseries.png"

FIGURE3_PDF = "figure2_volatility_slopes.pdf"
FIGURE3_PNG = "figure2_volatility_slopes.png"


# ---------------------------------------------------------------------
# 2. Bucket ordering
# ---------------------------------------------------------------------

MONEYNESS_ORDER = [
    "DOTM call",
    "OTM call",
    "ATM call",
    "ATM put",
    "OTM put",
    "DOTM put",
]

MATURITY_ORDER = [
    "7-45d",
    "45-90d",
    "90-180d",
    "180-360d",
]

MATURITY_LABELS = {
    "7-45d": "7-45 days",
    "45-90d": "45-90 days",
    "90-180d": "90-180 days",
    "180-360d": "180-360 days",
}

MONEYNESS_LABELS = {
    "DOTM put": "DOTM Put",
    "OTM put": "OTM Put",
    "ATM put": "ATM Put",
    "ATM call": "ATM Call",
    "OTM call": "OTM Call",
    "DOTM call": "DOTM Call",
}

BUCKET_ORDER = [
    f"{mon} | {mat}"
    for mon in MONEYNESS_ORDER
    for mat in MATURITY_ORDER
]


# ---------------------------------------------------------------------
# 3. Load surface panel
# ---------------------------------------------------------------------

def load_surface_panel() -> pd.DataFrame:
    """
    Load the balanced volatility-surface panel from CSV.
    """

    if not SURFACE_FILE.exists():
        raise FileNotFoundError(
            f"Surface file not found: {SURFACE_FILE}\n"
            "Check SURFACE_FILE and make sure construct_volatility_surface.py has been run."
        )

    df = pd.read_csv(SURFACE_FILE)

    required_columns = {
        "QUOTE_DATE",
        "MON_LABEL",
        "MAT_LABEL",
        "IV",
    }

    missing_columns = required_columns.difference(df.columns)

    if missing_columns:
        raise ValueError(
            f"Surface file is missing required columns: {sorted(missing_columns)}"
        )

    df["QUOTE_DATE"] = pd.to_datetime(df["QUOTE_DATE"])
    df["IV"] = df["IV"].astype(float)

    df = df[
        (df["QUOTE_DATE"] >= pd.Timestamp(START_DATE))
        & (df["QUOTE_DATE"] < pd.Timestamp(END_DATE))
    ].copy()

    if df.empty:
        raise ValueError(
            "No observations remain after applying START_DATE and END_DATE."
        )

    return df


# ---------------------------------------------------------------------
# 4. Load VIX from SQL
# ---------------------------------------------------------------------

def load_vix() -> tuple[pd.DataFrame | None, bool]:
    """
    Load the daily VIX index level from the vix_eod table.

    The VIX data are not option-filtered. We only keep valid daily index
    values:
        UNDERLYING_LAST is not null
        UNDERLYING_LAST > 0

    If VIX is stored as 20.5, it is converted to 0.205 so it is on the same
    decimal scale as implied volatility.
    """

    try:
        engine = create_engine(CONNECTION_STRING)

        vix_query = f"""
        SELECT
            QUOTE_DATE,
            AVG({VIX_VALUE_COLUMN}) AS VIX
        FROM {VIX_TABLE_NAME}
        WHERE QUOTE_DATE >= '{START_DATE}'
          AND QUOTE_DATE < '{END_DATE}'
          AND {VIX_VALUE_COLUMN} IS NOT NULL
          AND {VIX_VALUE_COLUMN} > 0
        GROUP BY QUOTE_DATE
        ORDER BY QUOTE_DATE;
        """

        vix_df = pd.read_sql(vix_query, engine)

        if vix_df.empty:
            print("VIX table was found, but no valid VIX observations were returned.")
            return None, False

        vix_df["QUOTE_DATE"] = pd.to_datetime(vix_df["QUOTE_DATE"])
        vix_df["VIX"] = vix_df["VIX"].astype(float)

        # Convert percentage units to decimal units if needed.
        # Example: 20.5 -> 0.205
        if vix_df["VIX"].median() > 2:
            vix_df["VIX"] = vix_df["VIX"] / 100.0

        vix_df = vix_df.set_index("QUOTE_DATE").sort_index()

        return vix_df, True

    except Exception as error:
        print(f"VIX overlay skipped: {error}")
        return None, False


# ---------------------------------------------------------------------
# 5. Build wide IV panel
# ---------------------------------------------------------------------

def build_wide_iv_panel(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert the long surface panel into a wide matrix:
        rows    = dates
        columns = maturity-moneyness buckets
        values  = implied volatility
    """

    df = df.copy()
    df["BUCKET"] = df["MON_LABEL"] + " | " + df["MAT_LABEL"]

    iv_wide = (
        df.pivot_table(
            index="QUOTE_DATE",
            columns="BUCKET",
            values="IV",
            aggfunc="mean",
        )
        .sort_index()
        .reindex(columns=BUCKET_ORDER)
    )

    return iv_wide


# ---------------------------------------------------------------------
# 6. Date-axis formatting helper
# ---------------------------------------------------------------------

def format_date_axis(ax) -> None:
    """
    Format x-axis as yearly date labels.
    """

    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.xaxis.set_minor_locator(mdates.MonthLocator(bymonth=[4, 7, 10]))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=0, fontsize=8)
    ax.set_xlabel("Date", fontsize=9)


# ---------------------------------------------------------------------
# 7. Plot volatility time series
# ---------------------------------------------------------------------

def plot_volatility_timeseries(
    iv_wide: pd.DataFrame,
    vix_df: pd.DataFrame | None,
    has_vix: bool,
) -> None:
    """
    Plot average implied volatility and the 24 individual bucket series.
    """

    avg_iv = iv_wide.mean(axis=1)

    fig, axes = plt.subplots(
        2,
        1,
        figsize=(11, 8),
        sharex=False,
    )

    fig.suptitle(
        "Volatility Time Series",
        fontsize=12,
        fontweight="bold",
        y=1.01,
    )

    # Panel A: average IV and VIX
    ax = axes[0]

    ax.plot(
        avg_iv.index,
        avg_iv.values,
        linewidth=0.9,
        label="Average implied volatility",
    )

    if has_vix and vix_df is not None:
        vix_aligned = vix_df.reindex(avg_iv.index)

        ax.plot(
            vix_aligned.index,
            vix_aligned["VIX"].values,
            linewidth=0.7,
            label="VIX",
        )

    ax.set_title("(A) Average implied volatility", fontsize=10, pad=6)
    ax.set_ylabel("Implied volatility", fontsize=9)

    upper_lim = max(0.85, float(np.nanmax(avg_iv.values)) * 1.10)
    ax.set_ylim(0.05, upper_lim)

    ax.legend(fontsize=8, loc="upper left", frameon=True)
    format_date_axis(ax)

    # Panel B: all 24 bucket series
    ax = axes[1]

    for bucket in BUCKET_ORDER:
        if bucket in iv_wide.columns:
            ax.plot(
                iv_wide.index,
                iv_wide[bucket],
                linewidth=0.4,
                alpha=0.75,
            )

    ax.plot(
        avg_iv.index,
        avg_iv.values,
        linewidth=1.2,
        alpha=0.9,
        label="Average",
    )

    ax.set_title("(B) Implied volatility across buckets", fontsize=10, pad=6)
    ax.set_ylabel("Implied volatility", fontsize=9)

    upper_lim = max(0.75, float(np.nanmax(iv_wide.values)) * 1.05)
    ax.set_ylim(0.05, upper_lim)

    format_date_axis(ax)

    plt.tight_layout()

    if SAVE_FIGURES:
        plt.savefig(FIGURE2_PDF, dpi=300, bbox_inches="tight")
        plt.savefig(FIGURE2_PNG, dpi=300, bbox_inches="tight")
        print(f"Saved: {FIGURE2_PDF}")
        print(f"Saved: {FIGURE2_PNG}")

    plt.show()


# ---------------------------------------------------------------------
# 8. Compute slope series
# ---------------------------------------------------------------------

def build_surface_pivot(df: pd.DataFrame) -> pd.DataFrame:
    """
    Create a pivot table with columns:
        (MON_LABEL, MAT_LABEL)
    """

    surface = (
        df.pivot_table(
            index="QUOTE_DATE",
            columns=["MON_LABEL", "MAT_LABEL"],
            values="IV",
            aggfunc="mean",
        )
        .sort_index()
    )

    return surface


def compute_smile_slopes(surface: pd.DataFrame) -> pd.DataFrame:
    """
    Smile slope by maturity:
        IV(DOTM put, maturity) - IV(DOTM call, maturity)
    """

    smile_slopes = pd.DataFrame(index=surface.index)

    for mat in MATURITY_ORDER:
        smile_slopes[mat] = (
            surface[("DOTM put", mat)]
            - surface[("DOTM call", mat)]
        )

    return smile_slopes


def compute_term_structure_slopes(surface: pd.DataFrame) -> pd.DataFrame:
    """
    Term-structure slope by moneyness:
        IV(moneyness, 180-360d) - IV(moneyness, 7-45d)
    """

    term_slopes = pd.DataFrame(index=surface.index)

    for mon in MONEYNESS_ORDER:
        term_slopes[mon] = (
            surface[(mon, "180-360d")]
            - surface[(mon, "7-45d")]
        )

    return term_slopes


# ---------------------------------------------------------------------
# 9. Plot slope figures
# ---------------------------------------------------------------------

def plot_slope_timeseries(
    smile_slopes: pd.DataFrame,
    term_slopes: pd.DataFrame,
) -> None:
    """
    Plot smile and term-structure slope time series.
    """

    fig, axes = plt.subplots(
        2,
        1,
        figsize=(11, 8),
        sharex=False,
    )

    fig.suptitle(
        "Slope of the Volatility Smile and Term Structure",
        fontsize=12,
        fontweight="bold",
        y=1.01,
    )

    # Panel A: smile slopes
    ax = axes[0]

    for mat in MATURITY_ORDER:
        ax.plot(
            smile_slopes.index,
            smile_slopes[mat],
            linewidth=0.7,
            label=MATURITY_LABELS[mat],
        )

    ax.set_title("(A) Slope of volatility smile", fontsize=10, pad=6)
    ax.set_ylabel("Smile slope", fontsize=9)
    ax.legend(fontsize=7, loc="upper left", frameon=True)

    smile_min = float(np.nanmin(smile_slopes.values))
    smile_max = float(np.nanmax(smile_slopes.values))
    ax.set_ylim(min(0.00, smile_min - 0.02), max(0.40, smile_max + 0.02))

    format_date_axis(ax)

    # Panel B: term-structure slopes
    ax = axes[1]

    for mon in MONEYNESS_ORDER:
        ax.plot(
            term_slopes.index,
            term_slopes[mon],
            linewidth=0.7,
            label=MONEYNESS_LABELS[mon],
        )

    ax.axhline(
        0.0,
        linewidth=0.6,
        linestyle="--",
        alpha=0.6,
    )

    ax.set_title("(B) Slope of volatility term structure", fontsize=10, pad=6)
    ax.set_ylabel("Term-structure slope", fontsize=9)
    ax.legend(fontsize=7, loc="lower right", frameon=True)

    term_min = float(np.nanmin(term_slopes.values))
    term_max = float(np.nanmax(term_slopes.values))
    ax.set_ylim(min(-0.25, term_min - 0.02), max(0.15, term_max + 0.02))

    format_date_axis(ax)

    plt.tight_layout()

    if SAVE_FIGURES:
        plt.savefig(FIGURE3_PDF, dpi=300, bbox_inches="tight")
        plt.savefig(FIGURE3_PNG, dpi=300, bbox_inches="tight")
        print(f"Saved: {FIGURE3_PDF}")
        print(f"Saved: {FIGURE3_PNG}")

    plt.show()


# ---------------------------------------------------------------------
# 10. Diagnostics
# ---------------------------------------------------------------------

def print_diagnostics(
    df: pd.DataFrame,
    iv_wide: pd.DataFrame,
    vix_df: pd.DataFrame | None,
    has_vix: bool,
) -> None:
    """
    Print compact checks.
    """

    print("\nSurface panel")
    print("-------------")
    print(f"Rows loaded:             {len(df):,}")
    print(f"Trading days:            {df['QUOTE_DATE'].nunique():,}")
    print(f"Sample start:            {df['QUOTE_DATE'].min().date()}")
    print(f"Sample end:              {df['QUOTE_DATE'].max().date()}")
    print(f"Wide panel shape:        {iv_wide.shape[0]:,} x {iv_wide.shape[1]:,}")
    print(f"Missing wide values:     {iv_wide.isna().sum().sum():,}")

    if has_vix and vix_df is not None:
        print("\nVIX overlay")
        print("-----------")
        print(f"VIX observations:        {len(vix_df):,}")
        print(f"VIX sample start:        {vix_df.index.min().date()}")
        print(f"VIX sample end:          {vix_df.index.max().date()}")

        common_dates = iv_wide.index.intersection(vix_df.index)
        print(f"Common IV/VIX dates:     {len(common_dates):,}")

        if len(common_dates) > 5:
            avg_iv = iv_wide.mean(axis=1)
            corr = avg_iv.loc[common_dates].corr(vix_df.loc[common_dates, "VIX"])
            print(f"Corr(avg IV, VIX):       {corr:.4f}")
    else:
        print("\nVIX overlay")
        print("-----------")
        print("VIX not available or not loaded.")


# ---------------------------------------------------------------------
# 11. Main
# ---------------------------------------------------------------------

def main() -> None:
    print("Loading volatility surface panel...")

    df = load_surface_panel()

    print("Loading VIX from SQL...")
    vix_df, has_vix = load_vix()

    print("Building wide IV panel...")
    iv_wide = build_wide_iv_panel(df)

    print_diagnostics(df, iv_wide, vix_df, has_vix)

    print("\nPlotting volatility time series...")
    plot_volatility_timeseries(iv_wide, vix_df, has_vix)

    print("\nComputing slope series...")
    surface = build_surface_pivot(df)
    smile_slopes = compute_smile_slopes(surface)
    term_slopes = compute_term_structure_slopes(surface)

    print("Plotting slope time series...")
    plot_slope_timeseries(smile_slopes, term_slopes)

    print("\nDone.")


if __name__ == "__main__":
    main()
