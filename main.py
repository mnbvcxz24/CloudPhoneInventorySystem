import json
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import date, datetime
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


APP_NAME = "CloudPhoneInventorySystem"
DB_PATH = Path(__file__).with_name("rf_inventory.db")
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
        self.migrate_database()

    def migrate_database(self):
        product_columns = {row["name"] for row in self.db.execute("PRAGMA table_info(products)")}
        code_columns = {row["name"] for row in self.db.execute("PRAGMA table_info(codes)")}
        if "cost_php" not in product_columns:
            self.db.execute("ALTER TABLE products ADD COLUMN cost_php REAL NOT NULL DEFAULT 0")
            old_rate = self.db.execute("SELECT value FROM settings WHERE key='idr_to_php'").fetchone()
            rate = float(old_rate["value"]) if old_rate else 0.0035375
            self.db.execute("UPDATE products SET cost_php=cost_idr*?", (rate,))
        if "selling_price_php" not in code_columns:
            self.db.execute("ALTER TABLE codes ADD COLUMN selling_price_php REAL NOT NULL DEFAULT 0")
            self.db.execute("UPDATE codes SET selling_price_php=(SELECT selling_price FROM products WHERE products.id=codes.product_id)")
        self.db.execute("DELETE FROM settings WHERE key='idr_to_php'")
        self.db.commit()

    def style(self):
        self.colors = {
            "background": "#F4F7FB",
            "surface": "#FFFFFF",
            "sidebar": "#111C36",
            "sidebar_hover": "#1D2A49",
            "primary": "#4263EB",
            "primary_active": "#3451CC",
            "accent": "#0F9F8F",
            "text": "#18243A",
            "muted": "#718096",
            "border": "#E1E8F0",
            "table_alt": "#F7F9FC",
            "selected": "#DCE7FF",
            "selected_text": "#233F99",
        }
        self.root.configure(bg=self.colors["background"])
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(".", font=("Segoe UI", 10), foreground=self.colors["text"])
        style.configure("TLabel", font=("Segoe UI", 10))
        style.configure("TFrame", background=self.colors["background"])
        style.configure("TLabel", background=self.colors["background"], foreground=self.colors["text"])
        style.configure("Title.TLabel", background=self.colors["background"],
                        foreground=self.colors["text"], font=("Segoe UI", 20, "bold"))
        style.configure("Subtitle.TLabel", background=self.colors["background"],
                        foreground=self.colors["muted"], font=("Segoe UI", 10))
        style.configure("Metric.TLabel", background=self.colors["surface"],
                        foreground=self.colors["primary"], font=("Segoe UI", 18, "bold"))
        style.configure("TLabelframe", background=self.colors["surface"],
                        bordercolor=self.colors["border"], relief="solid", borderwidth=1)
        style.configure("TLabelframe.Label", background=self.colors["surface"],
                        foreground=self.colors["primary"], font=("Segoe UI", 10, "bold"))
        style.configure("TButton", padding=(12, 8), background=self.colors["primary"],
                        foreground="#FFFFFF", borderwidth=0, focusthickness=0, relief="flat")
        style.map("TButton",
                  background=[("pressed", self.colors["primary_active"]),
                              ("active", self.colors["primary_active"])],
                  foreground=[("disabled", "#94A3B8"), ("!disabled", "#FFFFFF")])
        style.configure("TEntry", padding=6, fieldbackground="#FFFFFF",
                        bordercolor=self.colors["border"], lightcolor=self.colors["border"],
                        darkcolor=self.colors["border"])
        style.configure("TCombobox", padding=6, fieldbackground="#FFFFFF",
                        background="#FFFFFF", bordercolor=self.colors["border"], arrowsize=13)
        style.map("TCombobox", fieldbackground=[("readonly", "#FFFFFF")],
                  foreground=[("readonly", self.colors["text"])])
        style.configure("TNotebook", background=self.colors["background"], borderwidth=0,
                        tabmargins=(2, 5, 2, 0))
        style.configure("TNotebook.Tab", padding=(13, 8), background="#E5ECF5",
                        foreground=self.colors["muted"], font=("Segoe UI", 10, "bold"), relief="flat")
        style.map("TNotebook.Tab", padding=[("selected", (18, 11)), ("!selected", (13, 8))])
        style.map("TNotebook.Tab",
                  background=[("selected", self.colors["primary"]), ("active", "#DCE7F5")],
                  foreground=[("selected", "#FFFFFF"), ("active", self.colors["text"])])
        style.configure("Treeview", rowheight=32, font=("Segoe UI", 10),
                        background=self.colors["surface"], fieldbackground=self.colors["surface"],
                        foreground=self.colors["text"], bordercolor=self.colors["border"],
                        borderwidth=0)
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"),
                        background="#E8EEF7", foreground="#334155", padding=(4, 8),
                        relief="flat")
        style.map("Treeview",
                  background=[("selected", self.colors["selected"])],
                  foreground=[("selected", self.colors["selected_text"])])
        style.map("Treeview.Heading", background=[("active", "#DCE7F5")])

    def build_ui(self):
        self.root.configure(bg=self.colors["background"])

        shell = tk.Frame(self.root, bg=self.colors["background"])
        shell.pack(fill="both", expand=True)

        sidebar = tk.Frame(shell, bg=self.colors["sidebar"], width=220)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        brand = tk.Frame(sidebar, bg=self.colors["sidebar"])
        brand.pack(fill="x", padx=20, pady=(25, 28))
        mark = tk.Label(brand, text="RF", bg=self.colors["primary"], fg="#FFFFFF",
                        font=("Segoe UI", 15, "bold"), width=3, height=1, pady=7)
        mark.pack(anchor="w", pady=(0, 12))
        tk.Label(brand, text="CloudPhoneInventory", bg=self.colors["sidebar"], fg="#FFFFFF",
                 font=("Segoe UI", 15, "bold")).pack(anchor="w")
        tk.Label(brand, text="INVENTORY WORKSPACE", bg=self.colors["sidebar"], fg="#9EACCA",
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(4, 0))

        tk.Label(sidebar, text="WORKSPACE", bg=self.colors["sidebar"], fg="#8391AF",
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=22, pady=(0, 10))

        self.nav_buttons = {}
        nav_items = [
            ("products", "▦", "Product & Sales"),
            ("codes", "▤", "Code List"),
            ("summary", "◫", "Profit Summary"),
        ]
        for key, symbol, label in nav_items:
            button = tk.Button(
                sidebar, text=f"  {symbol}     {label}", anchor="w",
                command=lambda page=key: self.show_page(page),
                bg=self.colors["sidebar"], fg="#C5CEE0", activebackground=self.colors["sidebar_hover"],
                activeforeground="#FFFFFF", relief="flat", bd=0, cursor="hand2",
                font=("Segoe UI", 10, "bold"), padx=14, pady=13,
                highlightthickness=0,
            )
            button.pack(fill="x", padx=10, pady=3)
            self.nav_buttons[key] = button

        sidebar_footer = tk.Frame(sidebar, bg=self.colors["sidebar"])
        sidebar_footer.pack(side="bottom", fill="x", padx=20, pady=20)
        tk.Frame(sidebar_footer, bg="#34415F", height=1).pack(fill="x", pady=(0, 12))
        tk.Label(sidebar_footer, text="CLOUD PHONE INVENTORY", bg=self.colors["sidebar"],
                 fg="#9EACCA", font=("Segoe UI", 8, "bold")).pack(anchor="w")
        tk.Label(sidebar_footer, text="Local inventory • Google Sheets sync", bg=self.colors["sidebar"],
                 fg="#9EACCA", font=("Segoe UI", 8), wraplength=175, justify="left").pack(anchor="w", pady=(5, 0))

        workspace = tk.Frame(shell, bg=self.colors["background"])
        workspace.pack(side="left", fill="both", expand=True)

        header = tk.Frame(workspace, bg=self.colors["surface"], height=82,
                          highlightbackground=self.colors["border"], highlightthickness=1)
        header.pack(fill="x")
        header.pack_propagate(False)

        title_area = tk.Frame(header, bg=self.colors["surface"])
        title_area.pack(side="left", fill="y", padx=25, pady=15)
        self.page_title = tk.StringVar(value="Product & Sales")
        self.page_subtitle = tk.StringVar(value="Manage cloud-phone plans, PHP costs, and selling prices.")
        tk.Label(title_area, textvariable=self.page_title, bg=self.colors["surface"], fg=self.colors["text"],
                 font=("Segoe UI", 17, "bold")).pack(anchor="w")
        tk.Label(title_area, textvariable=self.page_subtitle, bg=self.colors["surface"], fg=self.colors["muted"],
                 font=("Segoe UI", 9)).pack(anchor="w", pady=(3, 0))

        header_actions = tk.Frame(header, bg=self.colors["surface"])
        header_actions.pack(side="right", padx=20, pady=18)
        self.sync_status = tk.StringVar(value="Google Sheets: not configured")
        tk.Label(header_actions, textvariable=self.sync_status, bg=self.colors["surface"],
                 fg=self.colors["muted"], font=("Segoe UI", 9)).pack(side="left", padx=(0, 12))
        ttk.Button(header_actions, text="Google Sheets setup", command=self.configure_sheets).pack(side="left", padx=4)
        ttk.Button(header_actions, text="Sync now", command=lambda: self.sync_to_sheets(show_result=True)).pack(side="left", padx=4)

        self.page_host = tk.Frame(workspace, bg=self.colors["background"])
        self.page_host.pack(fill="both", expand=True, padx=20, pady=18)

        self.products_tab = ttk.Frame(self.page_host, padding=14)
        self.codes_tab = ttk.Frame(self.page_host, padding=14)
        self.summary_tab = ttk.Frame(self.page_host, padding=14)

        self.build_products_tab()
        self.build_codes_tab()
        self.build_summary_tab()
        self.show_page("products")
        self.update_sync_status()

    def show_page(self, page):
        pages = {
            "products": (self.products_tab, "Product & Sales", "Manage plans, pricing, and sales performance."),
            "codes": (self.codes_tab, "Code List", "Track individual codes, PHP costs, prices, and availability."),
            "summary": (self.summary_tab, "Profit Summary", "Review revenue, claimed-code costs, and net profit."),
        }
        for frame, _, _ in pages.values():
            frame.pack_forget()
        frame, title, subtitle = pages[page]
        frame.pack(fill="both", expand=True)
        self.page_title.set(title)
        self.page_subtitle.set(subtitle)
        for key, button in self.nav_buttons.items():
            active = key == page
            button.configure(
                bg=self.colors["primary"] if active else self.colors["sidebar"],
                fg="#FFFFFF" if active else "#C5CEE0",
                activebackground=self.colors["primary"] if active else self.colors["sidebar_hover"],
            )

    def build_products_tab(self):
        form = ttk.LabelFrame(self.products_tab, text="Product plan details", padding=10)
        form.pack(fill="x", pady=(0, 10))
        self.p_name = tk.StringVar()
        self.p_type = tk.StringVar(value="Standard")
        self.p_days = tk.StringVar(value="30")
        self.p_cost = tk.StringVar(value="0")
        self.p_price = tk.StringVar(value="0")
        fields = [("Name", self.p_name, 18), ("Type", self.p_type, 14), ("Days", self.p_days, 8),
                  ("Default cost / code (PHP)", self.p_cost, 18), ("Selling price / code (PHP)", self.p_price, 18)]
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
        cols = ("name", "type", "days", "stock", "cost_php", "price", "sold_qty", "sold_amount", "sold_cost", "sold_profit")
        self.products_tree = ttk.Treeview(self.products_tab, columns=cols, show="headings")
        self.products_tree.tag_configure("odd", background=self.colors["surface"])
        self.products_tree.tag_configure("even", background=self.colors["table_alt"])
        labels = ("Name", "Type", "Days", "Available stock", "Default cost PHP", "Selling price PHP", "Sold qty", "Sold amount PHP", "Sold cost PHP", "Profit PHP")
        widths = (155, 90, 55, 105, 125, 125, 72, 125, 125, 115)
        for col, label, width in zip(cols, labels, widths):
            self.products_tree.heading(col, text=label, anchor="center")
            self.products_tree.column(col, width=width, anchor="center")
        self.products_tree.pack(fill="both", expand=True)
        product_scroll = ttk.Scrollbar(self.products_tab, orient="horizontal", command=self.products_tree.xview)
        product_scroll.pack(fill="x")
        self.products_tree.configure(xscrollcommand=product_scroll.set)
        ttk.Label(self.products_tab, text="Sold cost and profit use each claimed code's own recorded cost. Default cost is only used for newly added codes without an override.").pack(anchor="w", pady=(8, 0))

    def build_codes_tab(self):
        form = ttk.LabelFrame(self.codes_tab, text="Add single-use code", padding=10)
        form.pack(fill="x", pady=(0, 10))
        self.c_code = tk.StringVar()
        self.c_product = tk.StringVar()
        self.c_cost = tk.StringVar()
        self.c_status = tk.StringVar(value="Available")
        ttk.Label(form, text="Code").grid(row=0, column=0, sticky="w", padx=4)
        ttk.Entry(form, textvariable=self.c_code, width=30).grid(row=1, column=0, padx=4, pady=4)
        ttk.Label(form, text="Product plan").grid(row=0, column=1, sticky="w", padx=4)
        self.product_combo = ttk.Combobox(form, textvariable=self.c_product, state="readonly", width=26)
        self.product_combo.grid(row=1, column=1, padx=4, pady=4)
        ttk.Label(form, text="Cost override (PHP, optional)").grid(row=0, column=2, sticky="w", padx=4)
        ttk.Entry(form, textvariable=self.c_cost, width=22).grid(row=1, column=2, padx=4, pady=4)
        ttk.Button(form, text="Add code", command=self.add_code).grid(row=1, column=3, padx=8)

        actions = ttk.Frame(self.codes_tab)
        actions.pack(fill="x", pady=(0, 8))
        ttk.Label(actions, text="Select a code, then change its status:").pack(side="left")
        self.status_combo = ttk.Combobox(actions, values=STATUSES, state="readonly", width=14)
        self.status_combo.set("Available")
        self.status_combo.pack(side="left", padx=8)
        ttk.Button(actions, text="Update status", command=self.update_status).pack(side="left")
        ttk.Button(actions, text="Edit cost & price", command=self.edit_selected_code_prices).pack(side="left", padx=8)
        ttk.Button(actions, text="Delete selected", command=self.delete_code).pack(side="left", padx=8)

        cols = ("no", "code", "name", "type", "days", "cost_php", "price_php", "status", "date_claimed")
        self.codes_tree = ttk.Treeview(self.codes_tab, columns=cols, show="headings")
        self.codes_tree.tag_configure("odd", background=self.colors["surface"])
        self.codes_tree.tag_configure("even", background=self.colors["table_alt"])
        labels = ("No", "Code", "Name", "Type", "Days", "Cost PHP", "Price PHP", "Availability", "Date claimed")
        widths = (48, 250, 150, 90, 55, 120, 120, 105, 110)
        for col, label, width in zip(cols, labels, widths):
            self.codes_tree.heading(col, text=label, anchor="center")
            self.codes_tree.column(col, width=width, anchor="center")
        self.codes_tree.pack(fill="both", expand=True)
        codes_scroll = ttk.Scrollbar(self.codes_tab, orient="horizontal", command=self.codes_tree.xview)
        codes_scroll.pack(fill="x")
        self.codes_tree.configure(xscrollcommand=codes_scroll.set)
        ttk.Label(self.codes_tab, text="Select a code and click Edit cost & price to update its individual PHP cost and selling price. Changes recalculate revenue and profit, including claimed codes.").pack(anchor="w", pady=(8, 0))

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
                    "INSERT INTO products(name,type,days,cost_php,selling_price) VALUES(?,?,?,?,?)",
                    (name, typ, days, cost, price),
                )
            else:
                self.db.execute(
                    "UPDATE products SET name=?,type=?,days=?,cost_php=?,selling_price=? WHERE id=?",
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
        self.p_cost.set(str(product["cost_php"]))
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
            p = self.db.execute("SELECT cost_php,selling_price FROM products WHERE id=?", (product,)).fetchone()
            cost = float(self.c_cost.get()) if self.c_cost.get().strip() else float(p["cost_php"])
            if cost < 0:
                raise ValueError
            self.db.execute("INSERT INTO codes(code,product_id,cost_php,selling_price_php,status) VALUES(?,?,?,?, 'Available')",
                            (code, product, cost, float(p["selling_price"])))
            self.db.commit()
            self.c_code.set("")
            self.c_cost.set("")
            self.refresh_all()
            self.sync_to_sheets()
        except ValueError:
            messagebox.showerror("Invalid code", "Enter a unique code, choose a product, and use a valid non-negative PHP cost.")
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

    def edit_selected_code_prices(self):
        selected = self.codes_tree.selection()
        if not selected:
            messagebox.showwarning("Select a code", "Choose a code first.")
            return
        code_id = int(selected[0])
        row = self.db.execute("SELECT code,cost_php,selling_price_php FROM codes WHERE id=?", (code_id,)).fetchone()
        if not row:
            return
        cost = simpledialog.askfloat("Edit code cost", f"Cost PHP for code:\n{row['code']}", initialvalue=float(row["cost_php"]), minvalue=0, parent=self.root)
        if cost is None:
            return
        price = simpledialog.askfloat("Edit code price", f"Selling price PHP for code:\n{row['code']}", initialvalue=float(row["selling_price_php"]), minvalue=0, parent=self.root)
        if price is None:
            return
        self.db.execute("UPDATE codes SET cost_php=?,selling_price_php=? WHERE id=?", (cost, price, code_id))
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
        claimed = self.db.execute("SELECT COALESCE(SUM(selling_price_php),0) AS revenue, COALESCE(SUM(cost_php),0) AS cost FROM codes WHERE status='Claimed'").fetchone()
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
              (SELECT COUNT(*) FROM codes c WHERE c.product_id=p.id AND c.status='Claimed') sold,
              (SELECT COALESCE(SUM(c.selling_price_php),0) FROM codes c WHERE c.product_id=p.id AND c.status='Claimed') sold_amount,
              (SELECT COALESCE(SUM(c.cost_php),0) FROM codes c WHERE c.product_id=p.id AND c.status='Claimed') sold_cost
            FROM products p ORDER BY p.id
        """).fetchall()
        for index, p in enumerate(rows):
            self.products_tree.insert("", "end", iid=str(p["id"]), tags=("even" if index % 2 else "odd",), values=(
                p["name"], p["type"], p["days"], p["stock"], f'₱{p["cost_php"]:,.2f}',
                f'₱{p["selling_price"]:,.2f}', p["sold"], f'₱{p["sold_amount"]:,.2f}',
                f'₱{p["sold_cost"]:,.2f}', f'₱{p["sold_amount"]-p["sold_cost"]:,.2f}'))

    def refresh_codes(self):
        for item in self.codes_tree.get_children():
            self.codes_tree.delete(item)
        rows = self.db.execute("""
            SELECT c.*,p.name,p.type,p.days FROM codes c
            JOIN products p ON p.id=c.product_id ORDER BY c.id
        """).fetchall()
        for index, item in enumerate(rows, 1):
            self.codes_tree.insert("", "end", iid=str(item["id"]), tags=("even" if index % 2 == 0 else "odd",), values=(
                index, item["code"], item["name"], item["type"], item["days"],
                f'₱{item["cost_php"]:,.2f}', f'₱{item["selling_price_php"]:,.2f}',
                item["status"], item["date_claimed"] or ""))


    def refresh_product_combo(self):
        rows = self.db.execute("SELECT id,name,type,days FROM products ORDER BY name").fetchall()
        self.product_combo["values"] = [f'{p["id"]} | {p["name"]} | {p["type"]} | {p["days"]} days' for p in rows]
        if self.c_product.get() not in self.product_combo["values"]:
            self.c_product.set(self.product_combo["values"][0] if self.product_combo["values"] else "")

    def refresh_codes(self):
        for item in self.codes_tree.get_children():
            self.codes_tree.delete(item)
        rows = self.db.execute("""
        SELECT c.*,p.name,p.type,p.days,p.selling_price FROM codes c JOIN products p ON p.id=c.product_id ORDER BY c.id
        """).fetchall()
        for index, c in enumerate(rows, 1):
            self.codes_tree.insert("", "end", iid=str(c["id"]), tags=("even" if index % 2 == 0 else "odd",), values=(
                index, c["code"], c["name"], c["type"], c["days"], f'{c["cost_idr"]:,.2f}',
                f'₱{c["cost_php"]:,.2f}', f'₱{c["selling_price"]:,.2f}',
                c["status"], c["date_claimed"] or ""))

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
              (SELECT COALESCE(SUM(c.selling_price_php),0) FROM codes c WHERE c.product_id=p.id AND c.status='Claimed') AS sold_amount,
              (SELECT COALESCE(SUM(c.cost_php),0) FROM codes c WHERE c.product_id=p.id AND c.status='Claimed') AS sold_cost
            FROM products p ORDER BY p.id
        """).fetchall()
        codes = self.db.execute("SELECT c.*,p.name AS product_name,p.type AS product_type,p.days AS product_days FROM codes c JOIN products p ON p.id=c.product_id ORDER BY c.id").fetchall()
        revenue = sum(float(x["selling_price_php"]) for x in codes if x["status"] == "Claimed")
        cost = sum(float(x["cost_php"]) for x in codes if x["status"] == "Claimed")
        return {
            "token": self.setting("sheets_sync_token"),
            "generatedAt": datetime.now().isoformat(timespec="seconds"),
            "products": [{
                "id": p["id"], "name": p["name"], "type": p["type"], "days": p["days"],
                "availableStock": p["stock"], "costPHP": p["cost_php"], "sellingPricePHP": p["selling_price"],
                "soldQuantity": p["sold"], "soldAmountPHP": p["sold_amount"], "soldCostPHP": p["sold_cost"],
                "soldProfitPHP": p["sold_amount"] - p["sold_cost"],
            } for p in products],
            "codes": [{
                "id": x["id"], "code": x["code"], "productName": x["product_name"],
                "productType": x["product_type"], "days": x["product_days"],
                "status": x["status"], "dateClaimed": x["date_claimed"] or "",
                "costPHP": x["cost_php"], "sellingPricePHP": x["selling_price_php"],
            } for x in codes],
            "summary": {"revenuePHP": revenue, "costPHP": cost, "profitPHP": revenue-cost},
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
