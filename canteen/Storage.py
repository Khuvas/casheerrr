"""Storage (stock) management: restock, remove, set exact quantity."""
import tkinter as tk
from tkinter import messagebox, ttk

from common import LOW_STOCK, make_tree, parse_int, selected_id


class StorageService:
    def __init__(self, db):
        self.db = db

    def adjust_stock(self, item_id, delta):
        row = self.db.execute("SELECT name, stock FROM menu WHERE id=?", (item_id,)).fetchone()
        if row is None:
            raise ValueError("Item not found.")
        if row["stock"] + delta < 0:
            raise ValueError(f"Cannot remove {-delta}; only {row['stock']} in stock.")
        with self.db:
            self.db.execute("UPDATE menu SET stock = stock + ? WHERE id=?", (delta, item_id))

    def set_stock(self, item_id, qty):
        if qty < 0:
            raise ValueError("Stock cannot be negative.")
        with self.db:
            self.db.execute("UPDATE menu SET stock=? WHERE id=?", (qty, item_id))

    @staticmethod
    def status(stock):
        """Returns (label, tag) for a stock level."""
        if stock == 0:
            return "Out of stock", "out"
        if stock <= LOW_STOCK:
            return "Low", "low"
        return "OK", ""


class StorageTab(ttk.Frame):
    def __init__(self, parent, storage, menu):
        super().__init__(parent, padding=8)
        self.svc, self.menu = storage, menu
        self.qty = tk.StringVar()

        f, self.tree = make_tree(
            self, [("name", "Item"), ("stock", "In stock"), ("status", "Status")],
            {"name": 300, "stock": 100, "status": 120}, height=16)
        f.pack(fill="both", expand=True)
        self.tree.tag_configure("low", foreground="#b45309")
        self.tree.tag_configure("out", foreground="#c8102e")

        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=8)
        ttk.Label(bar, text="Quantity").pack(side="left")
        ttk.Entry(bar, textvariable=self.qty, width=8).pack(side="left", padx=6)
        ttk.Button(bar, text="Restock (+)", command=lambda: self.change(1)).pack(side="left")
        ttk.Button(bar, text="Remove (−)", command=lambda: self.change(-1)).pack(side="left", padx=6)
        ttk.Button(bar, text="Set exact", command=lambda: self.change(0)).pack(side="left")
        self.refresh()

    def change(self, sign):
        top = self.winfo_toplevel()
        item_id = selected_id(self.tree)
        if item_id is None:
            messagebox.showinfo("Storage", "Select an item first.", parent=top)
            return
        try:
            qty = parse_int(self.qty.get(), "Quantity")
            if sign == 0:
                self.svc.set_stock(item_id, qty)
            else:
                if qty == 0:
                    raise ValueError("Quantity must be at least 1.")
                self.svc.adjust_stock(item_id, sign * qty)
        except ValueError as e:
            messagebox.showerror("Error", str(e), parent=top)
            return
        self.qty.set("")
        self.refresh()
        if self.tree.exists(str(item_id)):
            self.tree.selection_set(str(item_id))

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        for r in self.menu.items():
            label, tag = self.svc.status(r["stock"])
            self.tree.insert("", "end", iid=str(r["id"]),
                             values=(r["name"], r["stock"], label), tags=(tag,))

