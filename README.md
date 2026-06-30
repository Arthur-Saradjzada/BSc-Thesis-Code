**Usage**

Run the code in the following order:

1. `put_call_parity.py` — cannot be run standalone; requires data from OptionDX.
2. `bid_ask_spread.py` — cannot be run standalone; requires data from OptionDX.
3. `descriptive_statistics.py` — cannot be run standalone; requires data from OptionDX.
4. `iv_surface_points.py` — cannot be run standalone; requires data from OptionDX. This produces the output `surface_points.xlsx`.
5. `iv_surface.py` — can be run standalone; make sure you set the path to `surface_points.xlsx`.
6. `vol_timeseries.py` — cannot be run standalone; requires data from OptionDX.
7. `plain_gas_validation.py` — can be run standalone.
8. `adjusted_gas_validation.py` — can be run standalone.
9. `plain_normal_vs_plain_t.py` — can be run standalone; make sure you set the path to `surface_points.xlsx`.
10. `plain_normal_vs_adjusted_normal.py` — can be run standalone; make sure you set the path to `surface_points.xlsx`.
11. `plain_normal_vs_adjusted_t.py` — can be run standalone; make sure you set the path to `surface_points.xlsx`.
