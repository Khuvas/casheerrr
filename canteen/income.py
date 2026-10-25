"""Record income (sales) and show income reports."""
import csv
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, ttk

from common import make_tree, now, rp


class IncomeService:
    def __init__(self, db):
        self.db = db

    def record_sale(self, lines, total, paid, cashier, source="counter"):
        """Insert one sale. `lines` is a list of (name, price, qty).

        Does NOT commit: call it inside a `with db:` block so the sale and the
        stock change it belongs to succeed or fail together.
        """
        cur = self.db.execute(
            "INSERT INTO sales(ts, total, paid, cashier, source) VALUES(?,?,?,?,?)",
            (now(), total, paid, cashier, source))
        self.db.executemany(
            "INSERT INTO sale_items(sale_id, name, price, qty) VALUES(?,?,?,?)",
            [(cur.lastrowid, n, p, q) for n, p, q in lines])
        return cur.lastrowid

    def today(self):
        """(number of sales, income) for today."""
        d = datetime.now().strftime("%Y-%m-%d")
        r = self.db.execute(
            "SELECT COUNT(*) n, COALESCE(SUM(total),0) t FROM sales WHERE substr(ts,1,10)=?",
            (d,)).fetchone()
        return r["n"], r["t"]

    def total(self):
        return self.db.execute("SELECT COALESCE(SUM(total),0) FROM sales").fetchone()[0]

    def daily_summary(self):
        return self.db.execute(
            "SELECT substr(ts,1,10) d, COUNT(*) n, SUM(total) t "
            "FROM sales GROUP BY d ORDER BY d DESC").fetchall()

    def recent_sales(self, limit=50):
        return self.db.execute(
            "SELECT s.ts, s.total, s.cashier, s.source, "
            "(SELECT group_concat(name || ' x' || qty, ', ') FROM sale_items WHERE sale_id=s.id) items "
            "FROM sales s ORDER BY s.id DESC LIMIT ?", (limit,)).fetchall()

    def export_csv(self, path):
        rows = self.db.execute(
            "SELECT s.ts, s.cashier, s.source, s.total, s.paid, "
            "(SELECT group_concat(name || ' x' || qty, '; ') FROM sale_items WHERE sale_id=s.id) items "
            "FROM sales s ORDER BY s.id").fetchall()
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["time", "cashier", "source", "items", "total", "paid"])
            for r in rows:
                w.writerow([r["ts"], r["cashier"], r["source"], r["items"], r["total"], r["paid"]])

    def reset(self):
        with self.db:
            self.db.execute("DELETE FROM sale_items")
            self.db.execute("DELETE FROM sales")


class IncomeTab(ttk.Frame):
    def __init__(self, parent, service):
        super().__init__(parent, padding=8)
        self.svc = service
        self.stats = {k: tk.StringVar(value="—") for k in ("today", "count", "all")}

        row = ttk.Frame(self)
        row.pack(fill="x")
        for key, label in [("today", "Today's income"), ("count", "Sales today"),
                           ("all", "All-time income")]:
            box = ttk.LabelFrame(row, text=label, padding=8)
            box.pack(side="left", fill="x", expand=True, padx=(0, 8))
            ttk.Label(box, textvariable=self.stats[key],
                      font=("TkDefaultFont", 15, "bold")).pack(anchor="w")

        panes = ttk.Frame(self)
        panes.pack(fill="both", expand=True, pady=8)
        panes.columnconfigure(0, weight=1)
        panes.columnconfigure(1, weight=3)
        panes.rowconfigure(0, weight=1)
        f, self.day_tree = make_tree(
            panes, [("d", "Date"), ("n", "Sales"), ("t", "Income")],
            {"d": 90, "n": 50, "t": 100}, height=10)
        f.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        f, self.sale_tree = make_tree(
            panes, [("ts", "Time"), ("items", "Items"), ("by", "By"), ("total", "Total")],
            {"ts": 130, "items": 240, "by": 110, "total": 90}, height=10)
        f.grid(row=0, column=1, sticky="nsew")

        bar = ttk.Frame(self)
        bar.pack(fill="x")
        ttk.Button(bar, text="Export CSV", command=self.export).pack(side="left")
        ttk.Button(bar, text="Reset income records", command=self.reset).pack(side="left", padx=6)
        self.refresh()

    def refresh(self):
        n, today = self.svc.today()
        self.stats["today"].set(rp(today))
        self.stats["count"].set(str(n))
        self.stats["all"].set(rp(self.svc.total()))
        self.day_tree.delete(*self.day_tree.get_children())
        for r in self.svc.daily_summary():
            self.day_tree.insert("", "end", values=(r["d"], r["n"], rp(r["t"])))
        self.sale_tree.delete(*self.sale_tree.get_children())
        for r in self.svc.recent_sales():
            by = (r["cashier"] or "—") + (" · pre-order" if r["source"] == "preorder" else "")
            self.sale_tree.insert("", "end", values=(r["ts"], r["items"], by, rp(r["total"])))

    def export(self):
        top = self.winfo_toplevel()
        path = filedialog.asksaveasfilename(
            parent=top, defaultextension=".csv", initialfile="income.csv",
            filetypes=[("CSV file", "*.csv")])
        if path:
            self.svc.export_csv(path)
            messagebox.showinfo("Export", "Income exported.", parent=top)

    def reset(self):
        if messagebox.askyesno("Reset", "Delete ALL income records?\nThis cannot be undone.",
                               icon="warning", parent=self.winfo_toplevel()):
            self.svc.reset()
            self.refresh()
