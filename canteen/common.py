"""Shared helpers: database connection + schema, formatting, small Tk helpers."""
import sqlite3
from datetime import datetime
from pathlib import Path
from tkinter import ttk

DB_PATH = Path(__file__).with_name("canteen.db")
LOW_STOCK = 5
TS_FMT = "%Y-%m-%d %H:%M:%S"

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
    salt     BLOB NOT NULL,
    pw_hash  BLOB NOT NULL,
    role     TEXT NOT NULL CHECK(role IN ('admin','cashier'))
);
CREATE TABLE IF NOT EXISTS menu(
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    name  TEXT NOT NULL UNIQUE,
    price INTEGER NOT NULL CHECK(price >= 0),
    stock INTEGER NOT NULL DEFAULT 0 CHECK(stock >= 0)
);
CREATE TABLE IF NOT EXISTS sales(
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    ts      TEXT NOT NULL,
    total   INTEGER NOT NULL,
    paid    INTEGER NOT NULL,
    cashier TEXT NOT NULL DEFAULT '',
    source  TEXT NOT NULL DEFAULT 'counter'
);
CREATE TABLE IF NOT EXISTS sale_items(
    sale_id INTEGER NOT NULL REFERENCES sales(id) ON DELETE CASCADE,
    name    TEXT NOT NULL,
    price   INTEGER NOT NULL,
    qty     INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS preorders(
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    customer   TEXT NOT NULL,
    note       TEXT NOT NULL DEFAULT '',
    pickup     TEXT NOT NULL DEFAULT '',
    status     TEXT NOT NULL DEFAULT 'pending',
    total      INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    ready_at   TEXT,
    done_at    TEXT
);
CREATE TABLE IF NOT EXISTS preorder_items(
    preorder_id INTEGER NOT NULL REFERENCES preorders(id) ON DELETE CASCADE,
    item_id     INTEGER,
    name        TEXT NOT NULL,
    price       INTEGER NOT NULL,
    qty         INTEGER NOT NULL
);
"""


def now():
    return datetime.now().strftime(TS_FMT)


def get_db(path=DB_PATH):
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.executescript(SCHEMA)
    _migrate(db)
    db.commit()
    return db


def _migrate(db):
    """Upgrade a canteen.db created by the first single-file version."""
    cols = {r["name"] for r in db.execute("PRAGMA table_info(sales)")}
    if "cashier" not in cols:
        db.execute("ALTER TABLE sales ADD COLUMN cashier TEXT NOT NULL DEFAULT ''")
    if "source" not in cols:
        db.execute("ALTER TABLE sales ADD COLUMN source TEXT NOT NULL DEFAULT 'counter'")


def rp(n):
    """Format a number as Indonesian Rupiah."""
    return "Rp" + f"{int(round(n)):,}".replace(",", ".")


def parse_int(text, field, allow_empty=False):
    text = text.strip().replace(".", "").replace(",", "")
    if not text:
        if allow_empty:
            return None
        raise ValueError(f"{field} is required.")
    if not text.isdigit():
        raise ValueError(f"{field} must be a whole number.")
    return int(text)


def make_tree(parent, columns, widths=None, height=12):
    """A Treeview with a scrollbar. Returns (frame, tree); pack/grid the frame."""
    frame = ttk.Frame(parent)
    tree = ttk.Treeview(frame, columns=[c[0] for c in columns], show="headings",
                        height=height, selectmode="browse")
    for key, title in columns:
        tree.heading(key, text=title)
        tree.column(key, width=(widths or {}).get(key, 100), anchor="w")
    sb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=sb.set)
    tree.pack(side="left", fill="both", expand=True)
    sb.pack(side="right", fill="y")
    return frame, tree


def selected_id(tree):
    """Row id (as int) of the selected Treeview row, or None."""
    sel = tree.selection()
    return int(sel[0]) if sel else None

