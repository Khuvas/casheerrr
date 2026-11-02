"""Make an order at the counter: pick items, calculate the total, take payment.

Also provides CartPicker, the menu + cart widget that the pre-order tab reuses.
"""
import tkinter as tk
from tkinter import messagebox, ttk

from common import make_tree, parse_int, rp, selected_id
from receipt import show_preview


class OrderService:
    def __init__(self, db, menu, income):
        self.db, self.menu, self.income = db, menu, income

    def cart_total(self, cart):
        total = 0
        for item_id, qty in cart.items():
            row = self.menu.item(item_id)
            if row:
                total += row["price"] * qty
        return total

    def reserve_stock(self, cart):
        """Check that everything in `cart` is in stock, then deduct it.

        Returns (lines, total); lines = [(item_id, name, price, qty)].
        Does not commit: call inside a `with db:` block.
        """
        if not cart:
            raise ValueError("The order is empty.")
        lines, total = [], 0
        for item_id, qty in cart.items():
            row = self.menu.item(item_id)
            if row is None:
                raise ValueError("An item in this order no longer exists.")
            if row["stock"] < qty:
                raise ValueError(f"Not enough stock for {row['name']} (left: {row['stock']}).")
            lines.append((item_id, row["name"], row["price"], qty))
            total += row["price"] * qty
        for item_id, _, _, qty in lines:
            self.db.execute("UPDATE menu SET stock = stock - ? WHERE id=?", (qty, item_id))
        return lines, total

    def checkout(self, cart, paid, cashier):
        """Complete a counter sale. paid=None means exact payment. Returns (total, change, sale_id)."""
        with self.db:
            lines, total = self.reserve_stock(cart)
            if paid is None:
                paid = total
            if paid < total:
                raise ValueError(f"Cash received is short by {rp(total - paid)}.")
            sale_id = self.income.record_sale([(n, p, q) for _, n, p, q in lines],
                                              total, paid, cashier, "counter")
        return total, paid - total, sale_id


class CartPicker(ttk.Frame):
    """Menu list on the left, current order on the right.

    Hosts can pack extra widgets (payment, customer details) into `self.right`.
    """

    def __init__(self, parent, menu, on_change=None, cart_height=8):
        super().__init__(parent)
        self.menu, self.on_change = menu, on_change
        self.cart = {}
        self.total_var = tk.StringVar(value=rp(0))
        self.columnconfigure(0, weight=3)
        self.columnconfigure(1, weight=2)
        self.rowconfigure(0, weight=1)

        left = ttk.LabelFrame(self, text="Menu (double-click to add)", padding=6)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        f, self.menu_tree = make_tree(
            left, [("name", "Item"), ("price", "Price"), ("stock", "Stock")],
            {"name": 220, "price": 100, "stock": 70})
        f.pack(fill="both", expand=True)
        self.menu_tree.bind("<Double-1>", lambda e: self.add())
        ttk.Button(left, text="Add to order", command=self.add).pack(fill="x", pady=(6, 0))

        self.right = right = ttk.LabelFrame(self, text="Current order", padding=6)
        right.grid(row=0, column=1, sticky="nsew")
        f, self.cart_tree = make_tree(
            right, [("name", "Item"), ("qty", "Qty"), ("sub", "Subtotal")],
            {"name": 150, "qty": 45, "sub": 100}, height=cart_height)
        f.pack(fill="both", expand=True)
        bar = ttk.Frame(right)
        bar.pack(fill="x", pady=4)
        ttk.Button(bar, text="+", width=4, command=lambda: self.change(1)).pack(side="left")
        ttk.Button(bar, text="−", width=4, command=lambda: self.change(-1)).pack(side="left", padx=4)
        ttk.Button(bar, text="Remove", command=lambda: self.change(None)).pack(side="left")
        row = ttk.Frame(right)
        row.pack(fill="x", pady=4)
        ttk.Label(row, text="Total").pack(side="left")
        ttk.Label(row, textvariable=self.total_var,
                  font=("TkDefaultFont", 18, "bold")).pack(side="right")

    def total(self):
        total = 0
        for item_id, qty in self.cart.items():
            row = self.menu.item(item_id)
            if row:
                total += row["price"] * qty
        return total

    def add(self):
        item_id = selected_id(self.menu_tree)
        if item_id is None:
            return
        row = self.menu.item(item_id)
        if self.cart.get(item_id, 0) >= row["stock"]:
            messagebox.showwarning("Out of stock", f"No more {row['name']} in stock.",
                                   parent=self.winfo_toplevel())
            return
        self.cart[item_id] = self.cart.get(item_id, 0) + 1
        self.refresh()

    def change(self, delta):
        item_id = selected_id(self.cart_tree)
        if item_id is None:
            return
        if delta is None:
            self.cart.pop(item_id, None)
        else:
            qty = self.cart[item_id] + delta
            row = self.menu.item(item_id)
            if qty <= 0:
                del self.cart[item_id]
            elif row and qty <= row["stock"]:
                self.cart[item_id] = qty
        self.refresh()
        if item_id in self.cart:
            self.cart_tree.selection_set(str(item_id))

    def clear(self):
        self.cart.clear()
        self.refresh()

    def refresh(self):
        keep = self.menu_tree.selection()
        self.menu_tree.delete(*self.menu_tree.get_children())
        for r in self.menu.items():
            self.menu_tree.insert("", "end", iid=str(r["id"]),
                                  values=(r["name"], rp(r["price"]), r["stock"]))
        if keep and self.menu_tree.exists(keep[0]):
            self.menu_tree.selection_set(keep[0])

        self.cart_tree.delete(*self.cart_tree.get_children())
        for item_id, qty in list(self.cart.items()):
            row = self.menu.item(item_id)
            if row is None or row["stock"] == 0:
                del self.cart[item_id]
                continue
            qty = self.cart[item_id] = min(qty, row["stock"])
            self.cart_tree.insert("", "end", iid=str(item_id),
                                  values=(row["name"], qty, rp(row["price"] * qty)))
        self.total_var.set(rp(self.total()))
        if self.on_change:
            self.on_change()


class OrderTab(ttk.Frame):
    def __init__(self, parent, service, user):
        super().__init__(parent, padding=8)
        self.svc, self.user = service, user
        self.paid = tk.StringVar()
        self.change_var = tk.StringVar(value="—")

        self.picker = CartPicker(self, service.menu, on_change=self.update_change)
        self.picker.pack(fill="both", expand=True)
        right = self.picker.right

        row = ttk.Frame(right)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="Cash received").pack(side="left")
        entry = ttk.Entry(row, textvariable=self.paid, width=14, justify="right")
        entry.pack(side="right")
        entry.bind("<KeyRelease>", lambda e: self.update_change())
        entry.bind("<Return>", lambda e: self.pay())
        ttk.Button(row, text="Exact", width=6, command=self.pay_exact).pack(side="right", padx=4)

        row = ttk.Frame(right)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="Change").pack(side="left")
        ttk.Label(row, textvariable=self.change_var).pack(side="right")

        bar = ttk.Frame(right)
        bar.pack(fill="x", pady=(8, 0))
        ttk.Button(bar, text="Complete sale", command=self.pay).pack(side="left", fill="x", expand=True)
        ttk.Button(bar, text="Clear", command=self.clear).pack(side="left", padx=(6, 0))
        self.refresh()

    def refresh(self):
        self.picker.refresh()

    def clear(self):
        self.paid.set("")
        self.picker.clear()

    def update_change(self):
        total = self.picker.total()
        try:
            paid = parse_int(self.paid.get(), "Cash", allow_empty=True)
        except ValueError:
            paid = None
        if paid is None:
            self.change_var.set("—")
        elif paid >= total:
            self.change_var.set(rp(paid - total))
        else:
            self.change_var.set("Short " + rp(total - paid))

    def pay_exact(self):
        self.paid.set(str(self.picker.total()))
        self.update_change()

    def pay(self):
        top = self.winfo_toplevel()
        try:
            paid = parse_int(self.paid.get(), "Cash received", allow_empty=True)
            total, change, sale_id = self.svc.checkout(
                self.picker.cart, paid, self.user["username"])
        except ValueError as e:
            messagebox.showerror("Error", str(e), parent=top)
            self.picker.refresh()
            return
        self.clear()
        show_preview(top, self.svc.income.get_sale(sale_id))

