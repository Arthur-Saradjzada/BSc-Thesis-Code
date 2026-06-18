# BSc-Thesis-Code

## 1. Dataset

### Data source

The raw data should be downloaded manually from:

https://www.optionsdx.com/

Use the following download settings:

- Underlying: SPX
- Data type: Option Chains
- Quote Frequency: End of Day
- Years: 2010 to 2023
- File format: `.txt`


Each year folder should contain the monthly `.txt` files downloaded from OptionDX (do not forget to unzip the folders before running).

## 2. Create summary statistics table for SPX options

File: `summary_statistics_spx.py`

This script creates a LaTeX summary-statistics table for the cleaned SPX option data.

It uses the MySQL table created by the previous import script:

```text
spx_options_eod_clean
```

The script filters the option data, groups the observations by maturity and delta-based moneyness buckets, and calculates summary statistics.

### What the script does

The script:

1. Reads SPX option data from MySQL.
2. Converts the call and put columns into option-level rows.
3. Applies filtering rules for date, maturity, implied volatility, delta, and option price.
4. Groups options by maturity bucket and moneyness bucket.
5. Computes means and standard deviations.
6. Computes average trading-volume shares.
7. Saves the result as a LaTeX table.

### Before running

Make sure:

1. MySQL Server is installed and running.
2. The table `spx_options_eod_clean` already exists.
3. The database connection string is correct.
4. The filtering settings in the script are correct.

Main settings to check:

```python
TABLE_NAME = "spx_options_eod_clean"
START_DATE = "2010-01-01"
END_DATE = "2022-01-01"
MIN_DTE = 7
MAX_DTE = 360
MIN_IV = 0.05
MAX_IV = 0.70
MIN_PRICE = 0.05
```

### Python packages

Install the required Python packages:

```bash
pip install pandas sqlalchemy pymysql
```

### Database connection

The script uses this environment variable:

```text
MYSQL_CONNECTION_STRING
```

PowerShell example:

```powershell
$env:MYSQL_CONNECTION_STRING="mysql+pymysql://root:YOUR_PASSWORD@localhost/spx_data"
```

### Run the script

```bash
python summary_statistics_spx.py
```

### Output

The script creates this file:

```text
summary_statistics_spx.tex
```

This file contains a LaTeX table with summary statistics by maturity and moneyness bucket.

LaTeX requirements:

```latex
\usepackage{booktabs}
\usepackage{multirow}
```

## 3. Construct SPX volatility surface

File: `construct_volatility_surface.py`

This script constructs an implied volatility surface from the cleaned SPX option data.

It uses the MySQL table created by the import script:

```text
spx_options_eod_clean
```

The script filters SPX call and put options, assigns each option to a delta-based moneyness bucket and a maturity bucket, and selects one representative contract for each bucket on each trading day.

### What the script does

The script:

1. Reads filtered SPX option data from MySQL.
2. Keeps options based on date, maturity, implied volatility, delta, and price filters.
3. Creates 6 moneyness buckets and 4 maturity buckets.
4. Builds a balanced 24-bucket volatility surface for each trading day.
5. Saves the volatility surface panel as a CSV file.
6. Plots the implied volatility surface for one selected trading day.

### Before running

Make sure:

1. MySQL Server is installed and running.
2. The table `spx_options_eod_clean` already exists.
3. `CONNECTION_STRING` is correct.
4. `TABLE_NAME` is correct.
5. `START_DATE` and `END_DATE` are correct.
6. `PLOT_DAY` is set to the trading day you want to visualize.
7. `OUTPUT_CSV` is updated to the full path where the CSV file should be saved.

Main settings to check:

```python
CONNECTION_STRING = "mysql+pymysql://root:PASSWORD@localhost/spx_data"
TABLE_NAME = "spx_options_eod_clean"

START_DATE = "2010-01-01"
END_DATE = "2022-01-01"

PLOT_DAY = "2010-06-04"
OUTPUT_CSV = r"C:\Your\Path\volatility_surface_panel.csv"
```

### Python packages

Install the required Python packages:

```bash
pip install numpy pandas matplotlib sqlalchemy pymysql
```

### Run the script

```bash
python construct_volatility_surface.py
```

### Output

The script creates a CSV file:

```text
volatility_surface_panel.csv
```

This CSV file is used as input for later programs. #WILL PROBABLY BE ADJUSTED TO SQL 

The script also shows a 3D plot of the implied volatility surface for the selected `PLOT_DAY`.

## 4. Import VIX data into MySQL

File: `vix_data_to_sql.py`

This script imports VIX End-of-Day option chain data from OptionDX into a MySQL database.

The script searches all subfolders inside the VIX data folder, reads every `.txt` file, cleans the data types, and saves the result into a MySQL table.

### Input

The raw VIX `.txt` files should be stored in a local folder, for example:

```text
VIX_data/
├── 2010/
├── 2011/
├── ...
└── 2023/
```

### Before running

Make sure:

1. MySQL Server is installed and running.
2. The MySQL database exists, for example `spx_data`.
3. `CONNECTION_STRING` is correct.
4. `ROOT_FOLDER` points to the folder containing the VIX `.txt` files.

Main settings to check:

```python
CONNECTION_STRING = "mysql+pymysql://root:PASSWORD@localhost/spx_data"
ROOT_FOLDER = r"C:\Here\Your\Path\VIX_data"
TABLE_NAME = "vix_eod"
```

### Python packages

Install the required Python packages:

```bash
pip install pandas numpy sqlalchemy pymysql
```

### Run the script

```bash
python vix_data_to_sql.py
```

### Output

The script creates and fills the following MySQL table:

```text
vix_eod
```

At the end, the script prints a final check showing:

- Total number of rows
- First quote date
- Last quote date
- Number of unique quote dates
- SQL column types

## 5. Plot SPX volatility time series and slopes

File: `volatility_timeseries_and_slopes.py`

This script creates descriptive time-series plots from the balanced SPX implied-volatility surface panel.

It uses the CSV file created by:

```text
construct_volatility_surface.py
```

It also uses the VIX table created by:

```text
vix_data_to_sql.py
```

### What the script does

The script creates two figures:

1. Volatility time series
   - Average implied volatility across all 24 surface buckets
   - VIX overlay from the MySQL table `vix_eod`
   - Implied-volatility time series for all 24 buckets

2. Surface slope time series
   - Smile slope by maturity bucket: `IV(DOTM put) - IV(DOTM call)`
   - Term-structure slope by moneyness bucket: `IV(180-360d) - IV(7-45d)`

### Before running

Make sure:

1. The file `volatility_surface_panel.csv` already exists.
2. The MySQL table `vix_eod` already exists.
3. `CONNECTION_STRING` is correct.
4. `SURFACE_FILE` points to the CSV file created by `construct_volatility_surface.py`.
5. `START_DATE` and `END_DATE` are correct.
6. `SAVE_FIGURES` is set to `True` if you want to save the figures.

Main settings to check:

```python
CONNECTION_STRING = "mysql+pymysql://root:PASSWORD@localhost/spx_data"
SURFACE_FILE = Path(r"C:\Here\Your\Path\volatility_surface_panel.csv")

VIX_TABLE_NAME = "vix_eod"
START_DATE = "2010-01-01"
END_DATE = "2022-01-01"

SAVE_FIGURES = False
```

### Python packages

Install the required Python packages:

```bash
pip install numpy pandas matplotlib sqlalchemy pymysql
```

### Run the script

```bash
python volatility_timeseries_and_slopes.py
```

### Output

The script displays:

```text
Volatility time-series plot
Volatility smile slope plot
Volatility term-structure slope plot
```

If `SAVE_FIGURES = True`, the script saves:

```text
figure2_volatility_timeseries.pdf
figure2_volatility_timeseries.png
figure3_volatility_slopes.pdf
figure3_volatility_slopes.png
```

Note: the VIX series is used only as a benchmark overlay.
