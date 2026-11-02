"""Pre-orders: place an order ahead, track its status and waiting time,
notify when it is ready, and take payment at pickup.

Flow:  pending -> preparing -> ready -> picked_up      (or cancelled)
Stock is reserved when the pre-order is placed and given back if it is cancelled.
Income is recorded only when the customer picks up and pays.
"""
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, simpledialog, ttk

from common import TS_FMT, make_tree, now, parse_int, rp, selected_id
from make_order import CartPicker
from receipt import show_preview

ACTIVE = ("pending", "preparing", "ready")
LABELS = {"pending": "Pending", "preparing": "Preparing", "ready": "READY",
          "picked_up": "Picked up", "cancelled": "Cancelled"}


class PreorderService:
    def __init__(self, db, orders, income):
        self.db, self.orders, self.income = db, orders, income

    def create(self, customer, cart, note="", pickup=""):
        customer = customer.strip()
        if not customer:
            raise ValueError("Customer name is required.")
        with self.db:
            lines, total = self.orders.reserve_stock(cart)
            cur = self.db.execute(
                "INSERT INTO preorders(customer, note, pickup, status, total, created_at) "
                "VALUES(?,?,?,?,?,?)",
                (customer, note.strip(), pickup.strip(), "pending", total, now()))
            self.db.executemany(
                "INSERT INTO preorder_items(preorder_id, item_id, name, price, qty) VALUES(?,?,?,?,?)",
                [(cur.lastrowid, i, n, p, q) for i, n, p, q in lines])
        return cur.lastrowid

    def list(self, active_only=True):
        where = "WHERE p.status IN ('pending','preparing','ready')" if active_only else ""
        order = "ASC" if active_only else "DESC"
        return self.db.execute(
            "SELECT p.*, (SELECT group_concat(name || ' x' || qty, ', ') "
            f"FROM preorder_items WHERE preorder_id=p.id) items FROM preorders p {where} "
            f"ORDER BY p.id {order}").fetchall()

    def _get(self, pid):
        row = self.db.execute("SELECT * FROM preorders WHERE id=?", (pid,)).fetchone()
        if row is None:
            raise ValueError("Pre-order not found.")
        return row

    @staticmethod
    def wait_minutes(row):
        """Minutes from order to ready (live for orders not ready yet); None if cancelled."""
        if row["status"] == "cancelled":
            return None
        start = datetime.strptime(row["created_at"], TS_FMT)
        end = datetime.strptime(row["ready_at"], TS_FMT) if row["ready_at"] else datetime.now()
        return max(0, int((end - start).total_seconds() // 60))

    def avg_wait_today(self):
        r = self.db.execute(
            "SELECT AVG((julianday(ready_at) - julianday(created_at)) * 1440) a FROM preorders "
            "WHERE ready_at IS NOT NULL AND substr(created_at,1,10) = ?",
            (datetime.now().strftime("%Y-%m-%d"),)).fetchone()
        return None if r["a"] is None else round(r["a"])

    def start_preparing(self, pid):
        if self._get(pid)["status"] != "pending":
            raise ValueError("Only pending orders can be started.")
        with self.db:
            self.db.execute("UPDATE preorders SET status='preparing' WHERE id=?", (pid,))

    def mark_ready(self, pid):
        if self._get(pid)["status"] not in ("pending", "preparing"):
            raise ValueError("This order is already ready, finished or cancelled.")
        with self.db:
            self.db.execute("UPDATE preorders SET status='ready', ready_at=? WHERE id=?",
                            (now(), pid))
        return self._get(pid)

    def cancel(self, pid):
        if self._get(pid)["status"] not in ACTIVE:
            raise ValueError("Only active orders can be cancelled.")
        with self.db:
            for r in self.db.execute(
                    "SELECT item_id, qty FROM preorder_items WHERE preorder_id=?", (pid,)):
                self.db.execute("UPDATE menu SET stock = stock + ? WHERE id=?",
                                (r["qty"], r["item_id"]))
            self.db.execute("UPDATE preorders SET status='cancelled', done_at=? WHERE id=?",
                            (now(), pid))

    def complete(self, pid, paid, cashier):
        """Customer picks up and pays. paid=None means exact. Returns (total, change, sale_id)."""
        with self.db:
            row = self._get(pid)
            if row["status"] != "ready":
                raise ValueError("Mark the order as READY before pickup.")
            total = row["total"]
            if paid is None:
                paid = total
            if paid < total:
                raise ValueError(f"Cash received is short by {rp(total - paid)}.")
            lines = [(r["name"], r["price"], r["qty"]) for r in self.db.execute(
                "SELECT name, price, qty FROM preorder_items WHERE preorder_id=?", (pid,))]
            sale_id = self.income.record_sale(lines, total, paid, cashier, "preorder")
            self.db.execute("UPDATE preorders SET status='picked_up', done_at=? WHERE id=?",
                            (now(), pid))
        return total, paid - total, sale_id


class NewPreorderTab(ttk.Frame):
    def __init__(self, parent, service):
        super().__init__(parent, padding=8)
        self.svc = service
        self.customer, self.pickup, self.note = tk.StringVar(), tk.StringVar(), tk.StringVar()
        self.picker = CartPicker(self, service.orders.menu, cart_height=6)
        self.picker.pack(fill="both", expand=True)
        right = self.picker.right
        for label, var in [("Customer / class", self.customer),
                           ("Pickup time", self.pickup), ("Note", self.note)]:
            row = ttk.Frame(right)
            row.pack(fill="x", pady=2)
            ttk.Label(row, text=label, width=15).pack(side="left")
            ttk.Entry(row, textvariable=var).pack(side="left", fill="x", expand=True)
        bar = ttk.Frame(right)
        bar.pack(fill="x", pady=(8, 0))
        ttk.Button(bar, text="Place pre-order", command=self.place).pack(side="left", fill="x", expand=True)
        ttk.Button(bar, text="Clear", command=self.clear_new).pack(side="left", padx=(6, 0))
        self.refresh()

    def refresh(self):
        self.picker.refresh()

    def clear_new(self):
        for v in (self.customer, self.pickup, self.note):
            v.set("")
        self.picker.clear()

    def place(self):
        top = self.winfo_toplevel()
        try:
            pid = self.svc.create(self.customer.get(), self.picker.cart,
                                  self.note.get(), self.pickup.get())
        except ValueError as e:
            messagebox.showerror("Error", str(e), parent=top)
            self.picker.refresh()
            return
        name = self.customer.get().strip()
        self.clear_new()
        messagebox.showinfo("Pre-order placed", f"Order #{pid} for {name} has been queued.", parent=top)


class PreorderQueueTab(ttk.Frame):
    REFRESH_MS = 30_000

    def __init__(self, parent, service, user):
        super().__init__(parent, padding=8)
        self.svc, self.user = service, user
        self.active_only = tk.BooleanVar(value=True)
        self.avg_var = tk.StringVar()

        top = ttk.Frame(self)
        top.pack(fill="x")
        ttk.Checkbutton(top, text="Active orders only", variable=self.active_only,
                        command=self.refresh).pack(side="left")
        ttk.Label(top, textvariable=self.avg_var).pack(side="right")

        f, self.tree = make_tree(
            self,
            [("id", "#"), ("customer", "Customer"), ("items", "Items"), ("pickup", "Pickup"),
             ("status", "Status"), ("wait", "Wait"), ("total", "Total")],
            {"id": 40, "customer": 130, "items": 260, "pickup": 80, "status": 90,
             "wait": 70, "total": 90}, height=14)
        f.pack(fill="both", expand=True, pady=6)
        self.tree.tag_configure("ready", background="#d1fae5", foreground="#065f46")
        self.tree.tag_configure("done", foreground="#6b7280")

        bar = ttk.Frame(self)
        bar.pack(fill="x")
        ttk.Button(bar, text="Start preparing", command=self.start).pack(side="left")
        ttk.Button(bar, text="Mark READY", command=self.ready).pack(side="left", padx=6)
        ttk.Button(bar, text="Picked up & paid", command=self.pickup_paid).pack(side="left")
        ttk.Button(bar, text="Cancel order", command=self.cancel).pack(side="left", padx=6)
        self.refresh()
        self.after(self.REFRESH_MS, self._tick)

    def _do(self, action):
        top = self.winfo_toplevel()
        pid = selected_id(self.tree)
        if pid is None:
            messagebox.showinfo("Pre-orders", "Select an order first.", parent=top)
            return None
        try:
            result = action(pid)
        except ValueError as e:
            messagebox.showerror("Error", str(e), parent=top)
            return None
        self.refresh()
        return pid, result

    def start(self):
        self._do(self.svc.start_preparing)

    def ready(self):
        res = self._do(self.svc.mark_ready)
        if res:
            row = res[1]
            messagebox.showinfo(
                "Order ready",
                f"Order #{row['id']} for {row['customer']} is READY.\nNotify the customer now.",
                parent=self.winfo_toplevel())

    def cancel(self):
        if selected_id(self.tree) is None:
            messagebox.showinfo("Pre-orders", "Select an order first.", parent=self.winfo_toplevel())
            return
        if messagebox.askyesno("Cancel order", "Cancel this order and return its items to stock?",
                               parent=self.winfo_toplevel()):
            self._do(self.svc.cancel)

    def pickup_paid(self):
        top = self.winfo_toplevel()
        pid = selected_id(self.tree)
        if pid is None:
            messagebox.showinfo("Pre-orders", "Select an order first.", parent=top)
            return
        total = self.svc._get(pid)["total"]
        text = simpledialog.askstring(
            "Payment", f"Total {rp(total)}\nCash received (leave empty for exact):", parent=top)
        if text is None:
            return
        try:
            paid = parse_int(text, "Cash received", allow_empty=True)
            total, change, sale_id = self.svc.complete(pid, paid, self.user["username"])
        except ValueError as e:
            messagebox.showerror("Error", str(e), parent=top)
            return
        self.refresh()
        show_preview(top, self.svc.income.get_sale(sale_id))

    def refresh(self):
        keep = self.tree.selection()
        self.tree.delete(*self.tree.get_children())
        for r in self.svc.list(self.active_only.get()):
            wait = self.svc.wait_minutes(r)
            tag = "ready" if r["status"] == "ready" else \
                  "done" if r["status"] in ("picked_up", "cancelled") else ""
            self.tree.insert("", "end", iid=str(r["id"]), tags=(tag,), values=(
                r["id"], r["customer"], r["items"], r["pickup"], LABELS[r["status"]],
                "—" if wait is None else f"{wait} min", rp(r["total"])))
        if keep and self.tree.exists(keep[0]):
            self.tree.selection_set(keep[0])
        avg = self.svc.avg_wait_today()
        self.avg_var.set("Average wait today: " + ("—" if avg is None else f"{avg} min"))

    def _tick(self):
        if not self.winfo_exists():
            return
        self.refresh()
        self.after(self.REFRESH_MS, self._tick)

