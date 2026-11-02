"""Receipts: build the text, show a print preview, print it or save it.

Edit STORE_NAME, STORE_LINES, FOOTER and WIDTH below to match your canteen
and your printer (32 characters fits a 58 mm thermal printer, 48 fits 80 mm).
"""
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, ttk

from common import TS_FMT, rp

STORE_NAME = "Telkom School Canteen"
STORE_LINES = []
FOOTER = "Thank you!"
WIDTH = 32


def build_receipt(sale, width=WIDTH):
    """Turn a sale dict (see IncomeService.get_sale) into fixed-width receipt text."""
    out = []
    rule = "-" * width

    def center(text):
        for part in textwrap.wrap(text, width) or [""]:
            out.append(part.center(width))

    def pair(left, right):
        out.append(left[:max(0, width - len(right) - 1)].ljust(width - len(right)) + right)

    center(STORE_NAME)
    for line in STORE_LINES:
        center(line)
    out.append(rule)
    when = datetime.strptime(sale["ts"], TS_FMT)
    pair("Receipt", f"#{sale['id']:05d}")
    pair("Date", when.strftime("%d/%m/%Y %H:%M"))
    if sale["cashier"]:
        pair("Cashier", sale["cashier"])
    if sale["source"] == "preorder":
        pair("Type", "Pre-order")
    out.append(rule)
    for name, price, qty in sale["items"]:
        out.extend(textwrap.wrap(name, width) or [""])
        pair(f"  {qty} x {rp(price)}", rp(price * qty))
    out.append(rule)
    pair("TOTAL", rp(sale["total"]))
    pair("Cash", rp(sale["paid"]))
    pair("Change", rp(sale["paid"] - sale["total"]))
    out.append(rule)
    center(FOOTER)
    return "\n".join(out)


def print_text(text):
    """Send plain text to the default printer.

    Windows uses the system's "print" action for .txt files; Linux and macOS use
    the lp / lpr command. Raises RuntimeError or OSError if printing fails.
    """
    fd, path = tempfile.mkstemp(suffix=".txt", prefix="receipt_")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text + "\n")
    if sys.platform.startswith("win"):
        os.startfile(path, "print")
        return
    for cmd in ("lp", "lpr"):
        exe = shutil.which(cmd)
        if exe:
            result = subprocess.run([exe, path], capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(result.stderr.strip() or "The print command failed.")
            return
    raise RuntimeError("No printer command found (lp / lpr). Use \"Save as .txt\" instead.")


class ReceiptPreview(tk.Toplevel):
    """Shows the receipt as it will be printed, with Print / Save / Close."""

    def __init__(self, parent, sale):
        super().__init__(parent)
        self.sale = sale
        self.text = build_receipt(sale)
        self.status = tk.StringVar()
        self.title(f"Receipt #{sale['id']:05d} — print preview")
        self.transient(parent)

        body = ttk.Frame(self, padding=12)
        body.pack(fill="both", expand=True)
        paper = ttk.Frame(body)
        paper.pack(fill="both", expand=True)
        box = tk.Text(paper, width=WIDTH + 2, height=min(30, self.text.count("\n") + 3),
                      font="TkFixedFont", bg="#ffffff", fg="#111111", relief="solid", bd=1,
                      wrap="none", padx=12, pady=12)
        sb = ttk.Scrollbar(paper, orient="vertical", command=box.yview)
        box.configure(yscrollcommand=sb.set)
        box.insert("1.0", self.text)
        box.configure(state="disabled")
        box.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        ttk.Label(body, textvariable=self.status).pack(anchor="w", pady=(8, 0))
        bar = ttk.Frame(body)
        bar.pack(fill="x", pady=(8, 0))
        ttk.Button(bar, text="Print", command=self.print_now).pack(side="left")
        ttk.Button(bar, text="Save as .txt", command=self.save).pack(side="left", padx=6)
        ttk.Button(bar, text="Close", command=self.destroy).pack(side="right")
        self.bind("<Escape>", lambda e: self.destroy())
        self.update_idletasks()
        try:
            self.grab_set()
        except tk.TclError:
            pass
        self.focus_set()

    def print_now(self):
        try:
            print_text(self.text)
        except (OSError, RuntimeError) as e:
            messagebox.showerror("Print", str(e), parent=self)
            return
        self.status.set("Sent to the printer.")

    def save(self):
        path = filedialog.asksaveasfilename(
            parent=self, defaultextension=".txt", initialfile=f"receipt_{self.sale['id']:05d}.txt",
            filetypes=[("Text file", "*.txt")])
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.text + "\n")
            self.status.set("Saved.")


def show_preview(parent, sale):
    """Open the preview and wait until it is closed."""
    ReceiptPreview(parent, sale).wait_window()

