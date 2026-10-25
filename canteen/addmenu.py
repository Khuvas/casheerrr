"""Add / edit / delete menu items."""
import sqlite3
import tkinter as tk
from tkinter import messagebox, ttk

from common import make_tree, parse_int, rp, selected_id


class MenuService:
    def __init__(self, db):
        self.db = db

    def items(self):
        return self.db.execute("SELECT * FROM menu ORDER BY name COLLATE NOCASE").fetchall()

    def item(self, item_id):
        return self.db.execute("SELECT * FROM menu WHERE id=?", (item_id,)).fetchone()

    def add_item(self, name, price, stock=0):
        name = name.strip()
        if not name:
            raise ValueError("Item name is required.")
        if price < 0 or stock < 0:
            raise ValueError("Price and stock cannot be negative.")
        try:
            with self.db:
                self.db.execute("INSERT INTO menu(name, price, stock) VALUES(?,?,?)",
                                (name, price, stock))
        except sqlite3.IntegrityError:
            raise ValueError(f'"{name}" already exists.')

    def update_item(self, item_id, name, price):
        name = name.strip()
        if not name or price < 0:
            raise ValueError("Enter a name and a non-negative price.")
        try:
            with self.db:
                self.db.execute("UPDATE menu SET name=?, price=? WHERE id=?",
                                (name, price, item_id))
        except sqlite3.IntegrityError:
            raise ValueError(f'"{name}" already exists.')

    def delete_item(self, item_id):
        with self.db:
            self.db.execute("DELETE FROM menu WHERE id=?", (item_id,))


class MenuTab(ttk.Frame):
    def __init__(self, parent, service):
        super().__init__(parent, padding=8)
        self.svc = service
        self.v_name, self.v_price, self.v_stock = tk.StringVar(), tk.StringVar(), tk.StringVar()

        box = ttk.LabelFrame(self, text="Add menu item", padding=8)
        box.pack(fill="x")
        for label, var, w in [("Name", self.v_name, 24), ("Price", self.v_price, 10),
                              ("Starting stock", self.v_stock, 8)]:
            ttk.Label(box, text=label).pack(side="left", padx=(0, 4))
            ttk.Entry(box, textvariable=var, width=w).pack(side="left", padx=(0, 12))
        ttk.Button(box, text="Add", command=self.add).pack(side="left")

        f, self.tree = make_tree(self, [("name", "Item"), ("price", "Price")],
                                 {"name": 300, "price": 120}, height=14)
        f.pack(fill="both", expand=True, pady=8)
        bar = ttk.Frame(self)
        bar.pack(fill="x")
        ttk.Button(bar, text="Edit selected", command=self.edit).pack(side="left")
        ttk.Button(bar, text="Delete selected", command=self.delete).pack(side="left", padx=6)
        self.refresh()

    def _err(self, e):
        messagebox.showerror("Error", str(e), parent=self.winfo_toplevel())

    def add(self):
        try:
            price = parse_int(self.v_price.get(), "Price")
            stock = parse_int(self.v_stock.get(), "Stock", allow_empty=True) or 0
            self.svc.add_item(self.v_name.get(), price, stock)
        except ValueError as e:
            self._err(e)
            return
        for v in (self.v_name, self.v_price, self.v_stock):
            v.set("")
        self.refresh()

    def edit(self):
        item_id = selected_id(self.tree)
        if item_id is None:
            return
        row = self.svc.item(item_id)
        win = tk.Toplevel(self)
        win.title("Edit item")
        win.transient(self.winfo_toplevel())
        win.grab_set()
        body = ttk.Frame(win, padding=10)
        body.pack(fill="both", expand=True)
        name, price = tk.StringVar(value=row["name"]), tk.StringVar(value=str(row["price"]))
        for i, (label, var) in enumerate([("Name", name), ("Price", price)]):
            ttk.Label(body, text=label).grid(row=i, column=0, padx=8, pady=6, sticky="w")
            ttk.Entry(body, textvariable=var, width=26).grid(row=i, column=1, padx=8, pady=6)

        def save():
            try:
                self.svc.update_item(item_id, name.get(), parse_int(price.get(), "Price"))
            except ValueError as e:
                messagebox.showerror("Error", str(e), parent=win)
                return
            win.destroy()
            self.refresh()

        ttk.Button(body, text="Save", command=save).grid(row=2, column=0, columnspan=2, pady=8)

    def delete(self):
        item_id = selected_id(self.tree)
        if item_id is None:
            return
        row = self.svc.item(item_id)
        if messagebox.askyesno(
                "Delete", f"Delete {row['name']}?\nPast sales stay in the income record.",
                parent=self.winfo_toplevel()):
            self.svc.delete_item(item_id)
            self.refresh()

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        for r in self.svc.items():
            self.tree.insert("", "end", iid=str(r["id"]), values=(r["name"], rp(r["price"])))
