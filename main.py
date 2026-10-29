import json
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import date, datetime
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


APP_NAME = "RFInventorySystem"
DB_PATH = Path(__file__).with_name("rf_inventory.db")
DEFAULT_RATE = 0.0035375
STATUSES = ("Available", "Reserved", "Claimed", "Expired")


class InventoryApp:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_NAME)
        self.root.geometry("1120x700")
        self.root.minsize(900, 580)
        self.db = sqlite3.connect(DB_PATH)
        self.db.row_factory = sqlite3.Row
        self.init_db()
        self.style()
        self.build_ui()
        self.refresh_all()

    def init_db(self):
        self.db.executescript("""
        PRAGMA foreign_keys = ON;
        CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        INSERT OR IGNORE INTO settings(key,value) VALUES ('idr_to_php','0.0035375');
        INSERT OR IGNORE INTO settings(key,value) VALUES ('sheets_web_app_url','');
        INSERT OR IGNORE INTO settings(key,value) VALUES ('sheets_sync_token','');
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            days INTEGER NOT NULL DEFAULT 0,
            cost_idr REAL NOT NULL DEFAULT 0,
            selling_price REAL NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL UNIQUE,
            product_id INTEGER NOT NULL REFERENCES products(id),
            cost_idr REAL NOT NULL,
            cost_php REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'Available',
            date_claimed TEXT
        );
        """)
        self.db.commit()

    def rate(self):
        row = self.db.execute("SELECT value FROM settings WHERE key='idr_to_php'").fetchone()
        return float(row["value"]) if row else DEFAULT_RATE

    def style(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Treeview", rowheight=27, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))
        style.configure("TButton", padding=(9, 6))
        style.configure("Title.TLabel", font=("Segoe UI", 18, "bold"))
        style.configure("Metric.TLabel", font=("Segoe UI", 13, "bold"))

    def build_ui(self):
        header = ttk.Frame(self.root, padding=(16, 12))
        header.pack(fill="x")
        ttk.Label(header, text="RFInventorySystem", style="Title.TLabel").pack(side="left")
        ttk.Label(header, text="Redfinger code inventory • single-use tracking").pack(side="left", padx=18, pady=(7, 0))
        self.sync_status = tk.StringVar(value="Google Sheets: not configured")
        ttk.Label(header, textvariable=self.sync_status).pack(side="right", padx=8)
        ttk.Button(header, text="Sync now", command=lambda: self.sync_to_sheets(show_result=True)).pack(side="right", padx=4)
        ttk.Button(header, text="Google Sheets setup", command=self.configure_sheets).pack(side="right", padx=4)

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=14, pady=(0, 12))
        self.products_tab = ttk.Frame(self.notebook, padding=12)
        self.codes_tab = ttk.Frame(self.notebook, padding=12)
        self.summary_tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(self.products_tab, text="Product & Sales")
        self.notebook.add(self.codes_tab, text="Code List")
        self.notebook.add(self.summary_tab, text="Profit Summary")
        self.build_products_tab()
        self.build_codes_tab()
        self.build_summary_tab()
        self.update_sync_status()

    def build_products_tab(self):
        form = ttk.LabelFrame(self.products_tab, text="Product plan details", padding=10)
        form.pack(fill="x", pady=(0, 10))
        self.p_name = tk.StringVar()
        self.p_type = tk.StringVar(value="Standard")
        self.p_days = tk.StringVar(value="30")
        self.p_cost = tk.StringVar(value="0")
        self.p_price = tk.StringVar(value="0")
        fields = [("Name", self.p_name, 18), ("Type", self.p_type, 14), ("Days", self.p_days, 8),
                  ("Cost / code (IDR)", self.p_cost, 16), ("Selling price / code (PHP)", self.p_price, 18)]
        self.p_name_entry = None
        for i, (label, var, width) in enumerate(fields):
            ttk.Label(form, text=label).grid(row=0, column=i, sticky="w", padx=4)
            entry = ttk.Entry(form, textvariable=var, width=width)
            entry.grid(row=1, column=i, padx=4, pady=4)
            if i == 0:
                self.p_name_entry = entry
        self.product_save_btn = ttk.Button(form, text="Add plan", command=self.save_product)
        self.product_save_btn.grid(row=1, column=len(fields), padx=8)
        ttk.Button(form, text="Edit selected", command=self.edit_selected_product).grid(row=1, column=len(fields) + 1, padx=4)
        self.editing_product_id = None
        cols = ("name", "type", "days", "stock", "cost_idr", "cost_php", "price", "sold_qty", "sold_amount")
        self.products_tree = ttk.Treeview(self.products_tab, columns=cols, show="headings")
        labels = ("Name", "Type", "Days", "Available stock", "Cost IDR", "Cost PHP", "Selling price", "Sold qty", "Sold amount")
        widths = (180, 100, 60, 110, 100, 100, 115, 75, 120)
        for col, label, width in zip(cols, labels, widths):
            self.products_tree.heading(col, text=label)
            self.products_tree.column(col, width=width, anchor="w" if col in ("name", "type") else "e")
        self.products_tree.pack(fill="both", expand=True)
        ttk.Label(self.products_tab, text="Available stock excludes Reserved, Claimed, and Expired codes.").pack(anchor="w", pady=(8, 0))

    def build_codes_tab(self):
        form = ttk.LabelFrame(self.codes_tab, text="Add single-use code", padding=10)
        form.pack(fill="x", pady=(0, 10))
        self.c_code = tk.StringVar()
        self.c_product = tk.StringVar()
        self.c_cost = tk.StringVar()
        self.c_status = tk.StringVar(value="Available")
        self.rate_var = tk.StringVar(value=str(self.rate()))
        ttk.Label(form, text="Code").grid(row=0, column=0, sticky="w", padx=4)
        ttk.Entry(form, textvariable=self.c_code, width=30).grid(row=1, column=0, padx=4, pady=4)
        ttk.Label(form, text="Product plan").grid(row=0, column=1, sticky="w", padx=4)
        self.product_combo = ttk.Combobox(form, textvariable=self.c_product, state="readonly", width=26)
        self.product_combo.grid(row=1, column=1, padx=4, pady=4)
        ttk.Label(form, text="Cost override (IDR, optional)").grid(row=0, column=2, sticky="w", padx=4)
        ttk.Entry(form, textvariable=self.c_cost, width=22).grid(row=1, column=2, padx=4, pady=4)
        ttk.Button(form, text="Add code", command=self.add_code).grid(row=1, column=3, padx=8)
        ttk.Label(form, text="IDR → PHP rate").grid(row=0, column=4, sticky="w", padx=4)
        ttk.Entry(form, textvariable=self.rate_var, width=13).grid(row=1, column=4, padx=4)
        ttk.Button(form, text="Save rate", command=self.save_rate).grid(row=1, column=5, padx=4)

        actions = ttk.Frame(self.codes_tab)
        actions.pack(fill="x", pady=(0, 8))
        ttk.Label(actions, text="Select a code, then change its status:").pack(side="left")
        self.status_combo = ttk.Combobox(actions, values=STATUSES, state="readonly", width=14)
        self.status_combo.set("Available")
        self.status_combo.pack(side="left", padx=8)
        ttk.Button(actions, text="Update status", command=self.update_status).pack(side="left")
        ttk.Button(actions, text="Delete selected", command=self.delete_code).pack(side="left", padx=8)

        cols = ("no", "code", "name", "type", "days", "cost_idr", "cost_php", "status", "date_claimed")
        self.codes_tree = ttk.Treeview(self.codes_tab, columns=cols, show="headings")
        labels = ("No", "Code", "Name", "Type", "Days", "Cost IDR", "Locked cost PHP", "Availability", "Date claimed")
        widths = (50, 260, 160, 100, 60, 100, 115, 110, 110)
        for col, label, width in zip(cols, labels, widths):
            self.codes_tree.heading(col, text=label)
            self.codes_tree.column(col, width=width, anchor="w" if col in ("code", "name", "type", "status", "date_claimed") else "e")
        self.codes_tree.pack(fill="both", expand=True)
        ttk.Label(self.codes_tab, text="Changing a code to Claimed records today's date and counts it as sold. Locked PHP costs never change when the rate changes.").pack(anchor="w", pady=(8, 0))

    def build_summary_tab(self):
        self.metric_revenue = tk.StringVar()
        self.metric_cost = tk.StringVar()
        self.metric_profit = tk.StringVar()
        row = ttk.Frame(self.summary_tab)
        row.pack(fill="x", pady=10)
        for title, var in (("Revenue", self.metric_revenue), ("Cost of claimed codes", self.metric_cost), ("Profit", self.metric_profit)):
            card = ttk.LabelFrame(row, text=title, padding=18)
            card.pack(side="left", fill="x", expand=True, padx=6)
            ttk.Label(card, textvariable=var, style="Metric.TLabel").pack(anchor="w")
        ttk.Label(self.summary_tab, text="Only codes marked Claimed count as sales. Reserved codes are not included in revenue or profit.").pack(anchor="w", padx=6, pady=8)
        ttk.Button(self.summary_tab, text="Refresh totals", command=self.refresh_all).pack(anchor="w", padx=6, pady=8)

    def save_product(self):
        try:
            name = self.p_name.get().strip()
            typ = self.p_type.get().strip() or "Standard"
            days = int(self.p_days.get())
            cost = float(self.p_cost.get())
            price = float(self.p_price.get())
            if not name or days < 0 or cost < 0 or price < 0:
                raise ValueError
            if self.editing_product_id is None:
                self.db.execute(
                    "INSERT INTO products(name,type,days,cost_idr,selling_price) VALUES(?,?,?,?,?)",
                    (name, typ, days, cost, price),
                )
            else:
                self.db.execute(
                    "UPDATE products SET name=?,type=?,days=?,cost_idr=?,selling_price=? WHERE id=?",
                    (name, typ, days, cost, price, self.editing_product_id),
                )
            self.db.commit()
            self.cancel_product_edit()
            self.refresh_all()
            self.sync_to_sheets()
        except (ValueError, sqlite3.IntegrityError):
            messagebox.showerror(
                "Invalid product",
                "Enter a name, whole number of days, and valid non-negative costs/prices.",
            )

    def edit_selected_product(self):
        selected = self.products_tree.selection()
        if not selected:
            messagebox.showwarning("Select a product", "Choose a product plan from the list first.")
            return
        product_id = int(selected[0])
        product = self.db.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
        if not product:
            return
        self.editing_product_id = product_id
        self.p_name.set(product["name"])
        self.p_type.set(product["type"])
        self.p_days.set(str(product["days"]))
        self.p_cost.set(str(product["cost_idr"]))
        self.p_price.set(str(product["selling_price"]))
        self.product_save_btn.configure(text="Save changes")
        self.p_name_entry.focus_set()

    def cancel_product_edit(self):
        self.editing_product_id = None
        self.p_name.set("")
        self.p_type.set("Standard")
        self.p_days.set("30")
        self.p_cost.set("0")
        self.p_price.set("0")
        self.product_save_btn.configure(text="Add plan")

    def add_code(self):
        try:
            code = self.c_code.get().strip()
            product = self.selected_product_id()
            if not code or product is None:
                raise ValueError
            p = self.db.execute("SELECT cost_idr FROM products WHERE id=?", (product,)).fetchone()
            cost = float(self.c_cost.get()) if self.c_cost.get().strip() else float(p["cost_idr"])
            if cost < 0:
                raise ValueError
            locked_php = cost * self.rate()
            self.db.execute("INSERT INTO codes(code,product_id,cost_idr,cost_php,status) VALUES(?,?,?,?, 'Available')",
                            (code, product, cost, locked_php))
            self.db.commit()
            self.c_code.set("")
            self.c_cost.set("")
            self.refresh_all()
            self.sync_to_sheets()
        except ValueError:
            messagebox.showerror("Invalid code", "Enter a unique code, choose a product, and use a valid non-negative cost.")
        except sqlite3.IntegrityError:
            messagebox.showerror("Duplicate code", "That code already exists. Each code must be unique.")

    def selected_product_id(self):
        value = self.c_product.get()
        if not value:
            return None
        try:
            return int(value.split(" | ", 1)[0])
        except ValueError:
            return None

    def save_rate(self):
        try:
            value = float(self.rate_var.get())
            if value <= 0:
                raise ValueError
            self.db.execute("INSERT INTO settings(key,value) VALUES('idr_to_php',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (str(value),))
            self.db.commit()
            self.refresh_all()
            self.sync_to_sheets()
            messagebox.showinfo("Exchange rate saved", "New codes will use the updated rate. Existing code costs stay locked.")
        except ValueError:
            messagebox.showerror("Invalid rate", "Enter a positive number.")

    def update_status(self):
        selected = self.codes_tree.selection()
        if not selected:
            messagebox.showwarning("Select a code", "Choose a code first.")
            return
        code_id = int(selected[0])
        status = self.status_combo.get()
        row = self.db.execute("SELECT status,date_claimed FROM codes WHERE id=?", (code_id,)).fetchone()
        if status == "Claimed" and row["status"] != "Claimed":
            claimed = date.today().isoformat()
        elif status == "Claimed":
            claimed = row["date_claimed"] or date.today().isoformat()
        else:
            claimed = None
        self.db.execute("UPDATE codes SET status=?,date_claimed=? WHERE id=?", (status, claimed, code_id))
        self.db.commit()
        self.refresh_all()
        self.sync_to_sheets()

    def delete_code(self):
        selected = self.codes_tree.selection()
        if not selected:
            messagebox.showwarning("Select a code", "Choose a code first.")
            return
        if not messagebox.askyesno("Delete code", "Delete the selected code permanently?"):
            return
        self.db.execute("DELETE FROM codes WHERE id=?", (int(selected[0]),))
        self.db.commit()
        self.refresh_all()
        self.sync_to_sheets()

    def refresh_all(self):
        self.refresh_products()
        self.refresh_codes()
        self.refresh_product_combo()
        claimed = self.db.execute("""
            SELECT COALESCE(SUM(p.selling_price),0) AS revenue,
                   COALESCE(SUM(c.cost_php),0) AS cost
            FROM codes c JOIN products p ON p.id=c.product_id WHERE c.status='Claimed'
        """).fetchone()
        revenue, cost = float(claimed["revenue"]), float(claimed["cost"])
        self.metric_revenue.set(f"₱{revenue:,.2f}")
        self.metric_cost.set(f"₱{cost:,.2f}")
        self.metric_profit.set(f"₱{revenue-cost:,.2f}")

    def refresh_products(self):
        for item in self.products_tree.get_children():
            self.products_tree.delete(item)
        rows = self.db.execute("""
        SELECT p.*,
          (SELECT COUNT(*) FROM codes c WHERE c.product_id=p.id AND c.status='Available') stock,
          (SELECT COUNT(*) FROM codes c WHERE c.product_id=p.id AND c.status='Claimed') sold
        FROM products p ORDER BY p.id
        """).fetchall()
        for p in rows:
            self.products_tree.insert("", "end", iid=str(p["id"]), values=(
                p["name"], p["type"], p["days"], p["stock"], f'{p["cost_idr"]:,.2f}',
                f'₱{p["cost_idr"]*self.rate():,.2f}', f'₱{p["selling_price"]:,.2f}',
                p["sold"], f'₱{p["sold"]*p["selling_price"]:,.2f}'))

    def refresh_product_combo(self):
        rows = self.db.execute("SELECT id,name,type,days FROM products ORDER BY name").fetchall()
        self.product_combo["values"] = [f'{p["id"]} | {p["name"]} | {p["type"]} | {p["days"]} days' for p in rows]
        if self.c_product.get() not in self.product_combo["values"]:
            self.c_product.set(self.product_combo["values"][0] if self.product_combo["values"] else "")

    def refresh_codes(self):
        for item in self.codes_tree.get_children():
            self.codes_tree.delete(item)
        rows = self.db.execute("""
        SELECT c.*,p.name,p.type,p.days FROM codes c JOIN products p ON p.id=c.product_id ORDER BY c.id
        """).fetchall()
        for i, c in enumerate(rows, 1):
            self.codes_tree.insert("", "end", iid=str(c["id"]), values=(
                i, c["code"], c["name"], c["type"], c["days"], f'{c["cost_idr"]:,.2f}',
                f'₱{c["cost_php"]:,.2f}', c["status"], c["date_claimed"] or ""))

    def setting(self, key, default=""):
        row = self.db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

    def set_setting(self, key, value):
        self.db.execute(
            "INSERT INTO settings(key,value) VALUES(?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        self.db.commit()

    def update_sync_status(self, message=None):
        if message:
            self.sync_status.set(message)
            return
        if self.setting("sheets_web_app_url").strip() and self.setting("sheets_sync_token").strip():
            self.sync_status.set("Google Sheets: ready")
        else:
            self.sync_status.set("Google Sheets: not configured")

    def configure_sheets(self):
        url = simpledialog.askstring(
            "Google Sheets setup",
            "Paste the deployed Google Apps Script Web App URL:",
            initialvalue=self.setting("sheets_web_app_url"),
            parent=self.root,
        )
        if url is None:
            return
        token = simpledialog.askstring(
            "Google Sheets setup",
            "Enter the shared secret you set in google_apps_script.gs:",
            initialvalue=self.setting("sheets_sync_token"),
            show="*",
            parent=self.root,
        )
        if token is None:
            return
        url = url.strip()
        token = token.strip()
        if url and not url.startswith("https://script.google.com/"):
            messagebox.showerror("Invalid URL", "Use the deployed Google Apps Script URL that starts with https://script.google.com/")
            return
        self.set_setting("sheets_web_app_url", url)
        self.set_setting("sheets_sync_token", token)
        self.update_sync_status()
        if url and token:
            self.sync_to_sheets(show_result=True)

    def build_sync_payload(self):
        products = self.db.execute("""
            SELECT p.*,
              (SELECT COUNT(*) FROM codes c WHERE c.product_id=p.id AND c.status='Available') AS stock,
              (SELECT COUNT(*) FROM codes c WHERE c.product_id=p.id AND c.status='Claimed') AS sold,
              (SELECT COALESCE(SUM(p2.selling_price),0) FROM codes c2
                 JOIN products p2 ON p2.id=c2.product_id
                 WHERE c2.product_id=p.id AND c2.status='Claimed') AS sold_amount
            FROM products p ORDER BY p.id
        """).fetchall()
        codes = self.db.execute("""
            SELECT c.*,p.name AS product_name,p.type AS product_type,p.days AS product_days,
                   p.selling_price AS selling_price
            FROM codes c JOIN products p ON p.id=c.product_id ORDER BY c.id
        """).fetchall()
        revenue = sum(float(c["selling_price"]) for c in codes if c["status"] == "Claimed")
        cost = sum(float(c["cost_php"]) for c in codes if c["status"] == "Claimed")
        return {
            "token": self.setting("sheets_sync_token"),
            "generatedAt": datetime.now().isoformat(timespec="seconds"),
            "exchangeRate": self.rate(),
            "products": [{
                "id": p["id"], "name": p["name"], "type": p["type"], "days": p["days"],
                "availableStock": p["stock"], "costIDR": p["cost_idr"],
                "costPHP": p["cost_idr"] * self.rate(), "sellingPricePHP": p["selling_price"],
                "soldQuantity": p["sold"], "soldAmountPHP": p["sold_amount"],
            } for p in products],
            "codes": [{
                "id": c["id"], "code": c["code"], "productName": c["product_name"],
                "productType": c["product_type"], "days": c["product_days"],
                "status": c["status"], "dateClaimed": c["date_claimed"] or "",
                "costIDR": c["cost_idr"], "lockedCostPHP": c["cost_php"],
                "sellingPricePHP": c["selling_price"],
            } for c in codes],
            "summary": {
                "revenuePHP": revenue, "costPHP": cost, "profitPHP": revenue - cost,
            },
        }

    def sync_to_sheets(self, show_result=False):
        url = self.setting("sheets_web_app_url").strip()
        token = self.setting("sheets_sync_token").strip()
        if not url or not token:
            self.update_sync_status()
            if show_result:
                messagebox.showinfo(
                    "Google Sheets not configured",
                    "First paste the deployed Apps Script Web App URL and shared secret in Google Sheets setup.",
                )
            return
        try:
            payload = json.dumps(self.build_sync_payload()).encode("utf-8")
            request = Request(
                url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(request, timeout=20) as response:
                result_text = response.read().decode("utf-8", errors="replace")
            result = json.loads(result_text)
            if not result.get("ok"):
                raise RuntimeError(result.get("error", "The Apps Script endpoint rejected the sync."))
            self.update_sync_status("Google Sheets: synced")
            if show_result:
                messagebox.showinfo("Sync complete", "Inventory was synced to Google Sheets.")
        except (URLError, HTTPError, TimeoutError, OSError, ValueError, RuntimeError) as exc:
            self.update_sync_status("Google Sheets: sync failed")
            if show_result:
                messagebox.showerror("Google Sheets sync failed", str(exc))

    def close(self):
        self.db.close()
        self.root.destroy()


def main():
    root = tk.Tk()
    app = InventoryApp(root)
    root.protocol("WM_DELETE_WINDOW", app.close)
    root.mainloop()


if __name__ == "__main__":
    main()
