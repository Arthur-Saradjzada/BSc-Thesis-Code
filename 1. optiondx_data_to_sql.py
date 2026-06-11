"""
optiondx_data_to_sql.py

Purpose:
1. Search all subfolders inside C:/Users/vcsa0/Desktop/optiondx_spx.
2. Read every OptionDX .txt file.
3. Convert the data to correct data types.
4. Save everything directly into MySQL table: spx_options_eod_clean.

Input folder:
    C:\\Users\\vcsa0\\Desktop\\optiondx_spx

Output table:
    spx_options_eod_clean

Run:
    optiondx_data_to_sql.py


ACTIONS BEFORE RUNNING:
1. Make sure CONNECTION_STRING is correct for your MySQL setup.
2. Make sure ROOT_FOLDER points to the correct folder containing the .txt files.
3. Make sure the MySQL database specified in CONNECTION_STRING exists.
"""

import os
import pandas as pd
import numpy as np

from sqlalchemy import create_engine, text
from sqlalchemy.types import Date, DateTime, BigInteger, String
from sqlalchemy.dialects.mysql import DOUBLE


# ---------------------------------------------------------------------
# 1. Settings
# ---------------------------------------------------------------------

CONNECTION_STRING = "mysql+pymysql://root:PASSWORD@localhost/DATABASE_NAME" # Change this to your actual connection string

ROOT_FOLDER = r"C:\Your\Path\Here\optiondx_spx" # Change this to your actual folder path containing the .txt files
TABLE_NAME = "spx_options_eod_clean"

CHUNKSIZE = 100_000


# ---------------------------------------------------------------------
# 2. Column names
# ---------------------------------------------------------------------

COLUMNS = [
    "QUOTE_UNIXTIME",
    "QUOTE_READTIME",
    "QUOTE_DATE",
    "QUOTE_TIME_HOURS",
    "UNDERLYING_LAST",
    "EXPIRE_DATE",
    "EXPIRE_UNIX",
    "DTE",
    "C_DELTA",
    "C_GAMMA",
    "C_VEGA",
    "C_THETA",
    "C_RHO",
    "C_IV",
    "C_VOLUME",
    "C_LAST",
    "C_SIZE",
    "C_BID",
    "C_ASK",
    "STRIKE",
    "P_BID",
    "P_ASK",
    "P_SIZE",
    "P_LAST",
    "P_DELTA",
    "P_GAMMA",
    "P_VEGA",
    "P_THETA",
    "P_RHO",
    "P_IV",
    "P_VOLUME",
    "STRIKE_DISTANCE",
    "STRIKE_DISTANCE_PCT",
]


DATE_COLUMNS = ["QUOTE_DATE", "EXPIRE_DATE"]
DATETIME_COLUMNS = ["QUOTE_READTIME"]

INTEGER_COLUMNS = [
    "QUOTE_UNIXTIME",
    "EXPIRE_UNIX",
    "C_VOLUME",
    "P_VOLUME",
]

FLOAT_COLUMNS = [
    "QUOTE_TIME_HOURS",
    "UNDERLYING_LAST",
    "DTE",
    "C_DELTA",
    "C_GAMMA",
    "C_VEGA",
    "C_THETA",
    "C_RHO",
    "C_IV",
    "C_LAST",
    "C_BID",
    "C_ASK",
    "STRIKE",
    "P_BID",
    "P_ASK",
    "P_LAST",
    "P_DELTA",
    "P_GAMMA",
    "P_VEGA",
    "P_THETA",
    "P_RHO",
    "P_IV",
    "STRIKE_DISTANCE",
    "STRIKE_DISTANCE_PCT",
]

STRING_COLUMNS = ["C_SIZE", "P_SIZE"]


SQL_DTYPE_MAP = {
    "QUOTE_UNIXTIME": BigInteger(),
    "QUOTE_READTIME": DateTime(),
    "QUOTE_DATE": Date(),
    "QUOTE_TIME_HOURS": DOUBLE(),
    "UNDERLYING_LAST": DOUBLE(),
    "EXPIRE_DATE": Date(),
    "EXPIRE_UNIX": BigInteger(),
    "DTE": DOUBLE(),

    "C_DELTA": DOUBLE(),
    "C_GAMMA": DOUBLE(),
    "C_VEGA": DOUBLE(),
    "C_THETA": DOUBLE(),
    "C_RHO": DOUBLE(),
    "C_IV": DOUBLE(),
    "C_VOLUME": BigInteger(),
    "C_LAST": DOUBLE(),
    "C_SIZE": String(50),
    "C_BID": DOUBLE(),
    "C_ASK": DOUBLE(),

    "STRIKE": DOUBLE(),

    "P_BID": DOUBLE(),
    "P_ASK": DOUBLE(),
    "P_SIZE": String(50),
    "P_LAST": DOUBLE(),
    "P_DELTA": DOUBLE(),
    "P_GAMMA": DOUBLE(),
    "P_VEGA": DOUBLE(),
    "P_THETA": DOUBLE(),
    "P_RHO": DOUBLE(),
    "P_IV": DOUBLE(),
    "P_VOLUME": BigInteger(),

    "STRIKE_DISTANCE": DOUBLE(),
    "STRIKE_DISTANCE_PCT": DOUBLE(),
}


engine = create_engine(CONNECTION_STRING)


# ---------------------------------------------------------------------
# 3. Cleaning helper functions
# ---------------------------------------------------------------------

def clean_string_series(s: pd.Series) -> pd.Series:
    return (
        s.astype(str)
         .str.strip()
         .replace(
             {
                 "": np.nan,
                 "nan": np.nan,
                 "NaN": np.nan,
                 "None": np.nan,
                 "NULL": np.nan,
                 "null": np.nan,
             }
         )
    )


def to_numeric_clean(s: pd.Series) -> pd.Series:
    s = clean_string_series(s)
    s = s.str.replace(",", "", regex=False)
    return pd.to_numeric(s, errors="coerce")


def to_integer_clean(s: pd.Series) -> pd.Series:
    numeric = to_numeric_clean(s)
    return numeric.round().astype("Int64")


def to_date_clean(s: pd.Series) -> pd.Series:
    s = clean_string_series(s)
    return pd.to_datetime(s, errors="coerce").dt.date


def to_datetime_clean(s: pd.Series) -> pd.Series:
    s = clean_string_series(s)
    return pd.to_datetime(s, errors="coerce")


def clean_chunk(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = COLUMNS

    for col in DATE_COLUMNS:
        df[col] = to_date_clean(df[col])

    for col in DATETIME_COLUMNS:
        df[col] = to_datetime_clean(df[col])

    for col in INTEGER_COLUMNS:
        df[col] = to_integer_clean(df[col])

    for col in FLOAT_COLUMNS:
        df[col] = to_numeric_clean(df[col])

    for col in STRING_COLUMNS:
        df[col] = clean_string_series(df[col])

    return df


# ---------------------------------------------------------------------
# 4. File discovery
# ---------------------------------------------------------------------

def find_txt_files_by_folder(root_folder: str) -> dict[str, list[str]]:
    """
    Return a dictionary:
        folder_path -> list of txt files inside that folder

    This allows clean progress printing per folder/year.
    """
    files_by_folder = {}

    for folder, _, files in os.walk(root_folder):
        txt_files = [
            os.path.join(folder, file)
            for file in files
            if file.lower().endswith(".txt")
        ]

        if txt_files:
            txt_files.sort()
            files_by_folder[folder] = txt_files

    return dict(sorted(files_by_folder.items()))


# ---------------------------------------------------------------------
# 5. SQL helpers
# ---------------------------------------------------------------------

def drop_output_table():
    with engine.begin() as conn:
        conn.execute(text(f"DROP TABLE IF EXISTS {TABLE_NAME};"))


def add_indexes():
    index_statements = [
        f"CREATE INDEX idx_quote_date ON {TABLE_NAME} (QUOTE_DATE);",
        f"CREATE INDEX idx_expire_date ON {TABLE_NAME} (EXPIRE_DATE);",
        f"CREATE INDEX idx_quote_expire_strike ON {TABLE_NAME} (QUOTE_DATE, EXPIRE_DATE, STRIKE);",
        f"CREATE INDEX idx_dte ON {TABLE_NAME} (DTE);",
        f"CREATE INDEX idx_strike ON {TABLE_NAME} (STRIKE);",
    ]

    with engine.begin() as conn:
        for stmt in index_statements:
            try:
                conn.execute(text(stmt))
            except Exception as e:
                print(f"Could not create index: {stmt}")
                print(f"Reason: {e}")


# ---------------------------------------------------------------------
# 6. Import one file
# ---------------------------------------------------------------------

def import_one_file(file_path: str, first_write: bool) -> tuple[bool, int]:
    file_rows = 0

    reader = pd.read_csv(
        file_path,
        sep=",",
        header=0,
        names=COLUMNS,
        dtype=str,
        chunksize=CHUNKSIZE,
        encoding="utf-8",
        encoding_errors="ignore",
        skipinitialspace=True,
        low_memory=False,
    )

    for chunk in reader:
        if len(chunk.columns) != len(COLUMNS):
            raise ValueError(
                f"Column mismatch in {file_path}: "
                f"{len(chunk.columns)} columns found, expected {len(COLUMNS)}"
            )

        cleaned = clean_chunk(chunk)

        if_exists_mode = "replace" if first_write else "append"

        cleaned.to_sql(
            TABLE_NAME,
            con=engine,
            if_exists=if_exists_mode,
            index=False,
            dtype=SQL_DTYPE_MAP,
            chunksize=10_000,
            method="multi",
        )

        first_write = False
        file_rows += len(cleaned)

    return first_write, file_rows


# ---------------------------------------------------------------------
# 7. Final check
# ---------------------------------------------------------------------

def final_check():
    row_count = pd.read_sql(
        f"SELECT COUNT(*) AS n_rows FROM {TABLE_NAME};",
        engine,
    )

    date_check = pd.read_sql(
        f"""
        SELECT
            MIN(QUOTE_DATE) AS first_date,
            MAX(QUOTE_DATE) AS last_date,
            COUNT(DISTINCT QUOTE_DATE) AS n_quote_dates
        FROM {TABLE_NAME};
        """,
        engine,
    )

    print("\nFinal table check")
    print("-----------------")
    print(row_count.to_string(index=False))
    print(date_check.to_string(index=False))


# ---------------------------------------------------------------------
# 8. Main
# ---------------------------------------------------------------------

def main():
    files_by_folder = find_txt_files_by_folder(ROOT_FOLDER)

    total_files = sum(len(files) for files in files_by_folder.values())

    print(f"Found {total_files} txt files in {len(files_by_folder)} folders.")
    print(f"Output table: {TABLE_NAME}")

    if total_files == 0:
        print("No txt files found. Check ROOT_FOLDER.")
        return

    drop_output_table()

    first_write = True
    total_inserted = 0

    for folder, files in files_by_folder.items():
        folder_inserted = 0

        print(f"\nFolder started: {folder}")
        print(f"Files in folder: {len(files)}")

        for file_path in files:
            try:
                first_write, file_rows = import_one_file(file_path, first_write)
                folder_inserted += file_rows
                total_inserted += file_rows

                print(
                    f"File finished: {os.path.basename(file_path)} | "
                    f"rows inserted: {file_rows:,} | "
                    f"total inserted so far: {total_inserted:,}"
                )

            except Exception as e:
                print(f"ERROR in file: {file_path}")
                print(e)

        print(
            f"Folder finished: {folder} | "
            f"folder rows inserted: {folder_inserted:,} | "
            f"total inserted so far: {total_inserted:,}"
        )

    add_indexes()
    final_check()

    print("\nImport complete.")


if __name__ == "__main__":
    main()
