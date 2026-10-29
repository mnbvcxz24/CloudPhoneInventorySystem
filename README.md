# RFInventorySystem

A small Windows desktop app for tracking Redfinger plans and single-use redemption codes. Data is stored locally in `rf_inventory.db` beside the application. When configured, the app also syncs its current inventory to a Google Sheet through a Google Apps Script Web App.

## Requirements
- Windows with Python 3.10 or newer
- Python standard library only

## Run
1. Download or clone this repository.
2. Double-click `run.bat`.
3. Add product plans in **Product & Sales**.
4. To change a plan, select it in the table and click **Edit selected**. Update the fields, then click **Save changes**.
5. Add each purchased code in **Code List**. The PHP cost is locked at the current IDR-to-PHP rate when the code is added.
6. Change a code status to **Reserved**, **Claimed**, or **Expired** as needed. A code marked **Claimed** records the date and counts as a sale.

Default exchange rate: `0.0035375 PHP per IDR`. Update it in the Code List tab. Updating the rate only affects newly added codes and the live product cost display; historical per-code PHP costs remain unchanged.

## Google Sheets setup
1. Open the Google Sheet you want to use.
2. In that sheet, choose **Extensions > Apps Script**.
3. Copy the contents of `google_apps_script.gs` into the Apps Script editor and save.
4. Replace `CHANGE_THIS_TO_A_LONG_RANDOM_SECRET` in the script with a long, private secret. Keep it private.
5. In Apps Script, choose **Deploy > New deployment > Web app**. Set **Execute as** to **Me** and the access setting to **Anyone** so the desktop app can call the endpoint. The script checks the shared secret before writing any data.
6. Deploy and copy the Web App URL (usually starts with `https://script.google.com/macros/s/`).
7. In RFInventorySystem, click **Google Sheets setup**, paste the Web App URL, and enter the same secret.
8. Click **Sync now** for the first sync. After setup, product changes, code additions/deletions, status changes, and exchange-rate changes trigger automatic sync attempts.

The script creates or updates these tabs: **Product & Sales**, **Code List**, and **Profit Summary**. Each sync replaces the contents of those managed tabs with the app's current snapshot. Do not put unrelated data in those three tabs. Other tabs in the spreadsheet are left alone.

If your Google Workspace administrator blocks public Web App deployments, the endpoint may not be usable with this setup.

## Status behavior
- **Available**: counted in stock.
- **Reserved**: held, not counted as available stock or sales.
- **Claimed**: treated as sold and included in revenue, cost, and profit.
- **Expired**: excluded from available stock and sales.

Codes must be unique. Avoid deleting a code after it has been claimed unless you intend to remove it from historical totals.

## Notes
- Google Sheets is a synchronized view of the desktop app's data. This setup is one-way: changes made directly in Google Sheets are overwritten by the next sync and are not imported into the app.
- Keep a backup of `rf_inventory.db` because it contains your local inventory records.
