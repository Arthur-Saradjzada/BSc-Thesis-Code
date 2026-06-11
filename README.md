# BSc-Thesis-Code

## 1. Import OptionDX SPX data into MySQL

File: `optiondx_data_to_sql.py`

This script imports SPX End-of-Day option chain data from OptionDX into a MySQL database.

The script searches all subfolders inside the main data folder, reads every `.txt` file, cleans the data types, and saves the result into a MySQL table.

### Data source

The raw data should be downloaded manually from:

https://www.optionsdx.com/

Use the following download settings:

- Underlying: SPX
- Data type: Option Chains
- Quote Frequency: End of Day
- Years: 2010 to 2023
- File format: `.txt`

### Folder structure

Place the downloaded files in folders by year, for example:

```text
optiondx_data/
├── 2010/
├── 2011/
├── 2012/
├── ...
└── 2023/
```

Each year folder should contain the monthly `.txt` files downloaded from OptionDX.

### Before running

Make sure the following steps are completed:

1. MySQL Server is installed and running.
2. MySQL Workbench is installed if you want to create and inspect the database using a graphical interface.
3. The MySQL database exists.
4. `CONNECTION_STRING` is updated for your MySQL username, password, host, and database name.
5. `ROOT_FOLDER` points to the folder containing the downloaded OptionDX `.txt` files.

Example connection string:

```python
CONNECTION_STRING = "mysql+pymysql://root:PASSWORD@localhost/spx_data"
```

Example root folder:

```python
ROOT_FOLDER = r"C:\Users\vcsa0\Desktop\optiondx_data"
```

Create the database in MySQL Workbench or MySQL command line:

```sql
CREATE DATABASE spx_data;
```

### Python packages

Install the required Python packages:

```bash
pip install pandas numpy sqlalchemy pymysql
```

### Run the script

Run the script from the project folder:

```bash
python optiondx_data_to_sql.py
```

### Output

The cleaned data is saved into the following MySQL table:

```text
spx_options_eod_clean
```

At the end, the script prints a final check showing:

- Total number of rows
- First quote date
- Last quote date
- Number of unique quote dates

### Note

The raw OptionDX `.txt` files are not included in this GitHub repository. The data must be downloaded separately from OptionDX.

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
