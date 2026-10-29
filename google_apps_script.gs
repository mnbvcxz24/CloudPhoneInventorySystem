/**
 * RFInventorySystem -> Google Sheets sync endpoint.
 *
 * Attach this script to the existing Google Sheet:
 * Extensions > Apps Script.
 * Set SYNC_TOKEN to a long random secret, then deploy as a Web App.
 */
const SYNC_TOKEN = "CHANGE_THIS_TO_A_LONG_RANDOM_SECRET";

function doPost(e) {
  try {
    const payload = JSON.parse((e && e.postData && e.postData.contents) || "{}");
    if (!SYNC_TOKEN || SYNC_TOKEN === "CHANGE_THIS_TO_A_LONG_RANDOM_SECRET") {
      return jsonResponse({ ok: false, error: "Set SYNC_TOKEN in the Apps Script before syncing." });
    }
    if (payload.token !== SYNC_TOKEN) {
      return jsonResponse({ ok: false, error: "Unauthorized: shared secret does not match." });
    }

    const ss = SpreadsheetApp.getActiveSpreadsheet();
    if (!ss) {
      return jsonResponse({ ok: false, error: "No active spreadsheet. Attach this script to your target Google Sheet." });
    }

    const products = Array.isArray(payload.products) ? payload.products : [];
    const codes = Array.isArray(payload.codes) ? payload.codes : [];
    const summary = payload.summary || {};
    const syncedAt = payload.generatedAt || new Date().toISOString();

    replaceSheet(ss, "Product & Sales",
      ["Product ID", "Name", "Type", "Days", "Available Stock", "Cost / Code (IDR)", "Cost / Code (PHP)", "Selling Price (PHP)", "Sold Qty", "Sold Amount (PHP)"],
      products.map(p => [p.id, p.name, p.type, p.days, p.availableStock, p.costIDR, p.costPHP, p.sellingPricePHP, p.soldQuantity, p.soldAmountPHP]),
      syncedAt);

    replaceSheet(ss, "Code List",
      ["Code ID", "Code", "Product", "Type", "Days", "Status", "Date Claimed", "Cost (IDR)", "Locked Cost (PHP)", "Selling Price (PHP)"],
      codes.map(c => [c.id, c.code, c.productName, c.productType, c.days, c.status, c.dateClaimed, c.costIDR, c.lockedCostPHP, c.sellingPricePHP]),
      syncedAt);

    replaceSheet(ss, "Profit Summary",
      ["Metric", "Amount (PHP)"],
      [
        ["Revenue", Number(summary.revenuePHP || 0)],
        ["Cost of claimed codes", Number(summary.costPHP || 0)],
        ["Profit", Number(summary.profitPHP || 0)],
        ["IDR to PHP rate", Number(payload.exchangeRate || 0)],
        ["Last synced", syncedAt]
      ],
      syncedAt);

    return jsonResponse({ ok: true, syncedAt: syncedAt, products: products.length, codes: codes.length });
  } catch (err) {
    return jsonResponse({ ok: false, error: String(err && err.message ? err.message : err) });
  }
}

function replaceSheet(ss, name, headers, rows, syncedAt) {
  let sheet = ss.getSheetByName(name);
  if (!sheet) sheet = ss.insertSheet(name);
  sheet.clearContents();
  const values = [headers].concat(rows);
  sheet.getRange(1, 1, values.length, headers.length).setValues(values);
  sheet.setFrozenRows(1);
  sheet.getRange(1, 1, 1, headers.length)
    .setFontWeight("bold")
    .setBackground("#183153")
    .setFontColor("#ffffff");
  const existingFilter = sheet.getFilter();
  if (existingFilter) existingFilter.remove();
  sheet.getRange(1, 1, values.length, headers.length).createFilter();
  sheet.autoResizeColumns(1, headers.length);
  sheet.getRange(1, headers.length + 2).setValue("Last synced");
  sheet.getRange(2, headers.length + 2).setValue(syncedAt);
}

function jsonResponse(value) {
  return ContentService
    .createTextOutput(JSON.stringify(value))
    .setMimeType(ContentService.MimeType.JSON);
}
