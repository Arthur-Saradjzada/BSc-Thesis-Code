# BSc-Thesis-Code

## 1. Import OptionDX SPX data into MySQL

File: `optiondx_data_to_sql.py`

This script imports SPX End-of-Day option chain data from OptionDX into a MySQL database.

The data should be downloaded manually from:

https://www.optionsdx.com/

Download settings:

- Underlying: SPX
- Data type: Option Chains
- Quote Frequency: End of Day
- Years: 2010 to 2023
- File format: `.txt`

Place the downloaded files in folders by year, for example:

```text
optiondx_data/
├── 2010/
├── 2011/
├── ...
└── 2023/
