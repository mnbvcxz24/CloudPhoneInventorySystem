# RFInventorySystem

A small Windows desktop app for tracking Redfinger plans and single-use redemption codes. Data is stored locally in `rf_inventory.db` beside the application.

## Requirements
- Windows with Python 3.10 or newer
- Internet connection on first launch to install `openpyxl` for Excel export

## Run
1. Download or clone this repository.
2. Double-click `run.bat`.
3. Add product plans in **Product & Sales**.
4. Add each purchased code in **Code List**. The PHP cost is locked at the current IDR-to-PHP rate when the code is added.
5. Change the code status to **Reserved**, **Claimed**, or **Expired** as needed. A code marked **Claimed** records the date and counts as a sale.
6. Use **Export to Excel** to export Product & Sales, Code List, and Profit Summary.

Default exchange rate: `0.0035375 PHP per IDR`. Update it in the Code List tab. Updating the rate only affects newly added codes and the live product cost display; historical per-code PHP costs remain unchanged.

## Status behavior
- **Available**: counted in stock.
- **Reserved**: held, not counted as available stock or sales.
- **Claimed**: treated as sold and included in revenue, cost, and profit.
- **Expired**: excluded from available stock and sales.

Codes must be unique. Avoid deleting a code after it has been claimed unless you intend to remove it from historical totals.

## Notes
- This is a local desktop app; the database is not automatically synchronized between computers.
- Keep a backup of `rf_inventory.db` because it contains your inventory records.
