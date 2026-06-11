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
