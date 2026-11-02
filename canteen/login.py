"""Login: password hashing, the sign-in window, and the admin's user-management tab.

Passwords are never stored: only a random salt and a PBKDF2-SHA256 hash.
On the very first run there are no users, so the window asks you to create the
admin account (there is no default password).
"""
import hashlib
import hmac
import os
import sqlite3
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from common import make_tree, selected_id
from theme import apply_theme, load_theme

ITERATIONS = 200_000
MIN_PASSWORD = 6
ROLES = ("cashier", "admin")


def _hash(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS)


class AuthService:
    def __init__(self, db):
        self.db = db

    def has_users(self):
        return self.db.execute("SELECT COUNT(*) FROM users").fetchone()[0] > 0

    def create_user(self, username, password, role="cashier"):
        username = username.strip()
        if len(username) < 3:
            raise ValueError("Username must be at least 3 characters.")
        if len(password) < MIN_PASSWORD:
            raise ValueError(f"Password must be at least {MIN_PASSWORD} characters.")
        if role not in ROLES:
            raise ValueError("Unknown role.")
        salt = os.urandom(16)
        try:
            with self.db:
                self.db.execute(
                    "INSERT INTO users(username, salt, pw_hash, role) VALUES(?,?,?,?)",
                    (username, salt, _hash(password, salt), role))
        except sqlite3.IntegrityError:
            raise ValueError(f'The username "{username}" is taken.')

    def verify(self, username, password):
        """Returns the user row if the credentials are right, else None."""
        row = self.db.execute("SELECT * FROM users WHERE username=?",
                              (username.strip(),)).fetchone()
        if row is None:
            _hash(password, b"x" * 16)
            return None
        return row if hmac.compare_digest(_hash(password, row["salt"]), row["pw_hash"]) else None

    def users(self):
        return self.db.execute("SELECT id, username, role FROM users ORDER BY username").fetchall()

    def set_password(self, user_id, password):
        if len(password) < MIN_PASSWORD:
            raise ValueError(f"Password must be at least {MIN_PASSWORD} characters.")
        salt = os.urandom(16)
        with self.db:
            self.db.execute("UPDATE users SET salt=?, pw_hash=? WHERE id=?",
                            (salt, _hash(password, salt), user_id))

    def delete_user(self, user_id, current_user_id):
        if user_id == current_user_id:
            raise ValueError("You cannot delete the account you are signed in with.")
        row = self.db.execute("SELECT role FROM users WHERE id=?", (user_id,)).fetchone()
        if row is None:
            raise ValueError("User not found.")
        admins = self.db.execute("SELECT COUNT(*) FROM users WHERE role='admin'").fetchone()[0]
        if row["role"] == "admin" and admins <= 1:
            raise ValueError("There must be at least one admin.")
        with self.db:
            self.db.execute("DELETE FROM users WHERE id=?", (user_id,))


def run_login(auth):
    """Show the sign-in window. Returns the user row, or None if the window was closed."""
    root = tk.Tk()
    root.title("Canteen Cashier — Sign in")
    apply_theme(root, load_theme())
    root.resizable(False, False)
    first_run = not auth.has_users()
    state = {"user": None, "fails": 0}
    username, password, confirm = tk.StringVar(), tk.StringVar(), tk.StringVar()
    msg = tk.StringVar()

    frm = ttk.Frame(root, padding=18)
    frm.pack()
    ttk.Label(frm, text="Canteen Cashier", font=("TkDefaultFont", 15, "bold")).grid(
        row=0, column=0, columnspan=2, pady=(0, 4))
    ttk.Label(frm, text=("First run — create the admin account" if first_run else "Please sign in"),
              foreground="#6b7280").grid(row=1, column=0, columnspan=2, pady=(0, 10))

    fields = [("Username", username, ""), ("Password", password, "•")]
    if first_run:
        fields.append(("Confirm password", confirm, "•"))
    entries = []
    for i, (label, var, mask) in enumerate(fields, start=2):
        ttk.Label(frm, text=label).grid(row=i, column=0, sticky="w", pady=3, padx=(0, 10))
        e = ttk.Entry(frm, textvariable=var, show=mask, width=26)
        e.grid(row=i, column=1, pady=3)
        entries.append(e)
    entries[0].focus()

    ttk.Label(frm, textvariable=msg, foreground="#c8102e").grid(
        row=10, column=0, columnspan=2, pady=(6, 0))
    btn = ttk.Button(frm, text="Create admin & sign in" if first_run else "Sign in")
    btn.grid(row=11, column=0, columnspan=2, sticky="ew", pady=(8, 0))

    def unlock():
        state["fails"] = 0
        btn.state(["!disabled"])
        msg.set("")

    def submit(event=None):
        if "disabled" in btn.state():
            return
        try:
            if first_run:
                if password.get() != confirm.get():
                    raise ValueError("Passwords do not match.")
                auth.create_user(username.get(), password.get(), "admin")
            user = auth.verify(username.get(), password.get())
            if user is None:
                raise PermissionError
        except ValueError as e:
            msg.set(str(e))
            return
        except PermissionError:
            state["fails"] += 1
            password.set("")
            if state["fails"] >= 5:
                msg.set("Too many attempts. Wait 10 seconds.")
                btn.state(["disabled"])
                root.after(10_000, unlock)
            else:
                msg.set("Wrong username or password.")
            return
        state["user"] = user
        root.destroy()

    btn.configure(command=submit)
    root.bind("<Return>", submit)
    root.mainloop()
    return state["user"]


class UsersTab(ttk.Frame):
    """Admin only: add cashiers/admins, reset passwords, delete users."""

    def __init__(self, parent, auth, current_user):
        super().__init__(parent, padding=8)
        self.auth, self.me = auth, current_user
        self.v_name, self.v_pw, self.v_role = tk.StringVar(), tk.StringVar(), tk.StringVar(value="cashier")

        box = ttk.LabelFrame(self, text="Add user", padding=8)
        box.pack(fill="x")
        ttk.Label(box, text="Username").pack(side="left", padx=(0, 4))
        ttk.Entry(box, textvariable=self.v_name, width=16).pack(side="left", padx=(0, 10))
        ttk.Label(box, text="Password").pack(side="left", padx=(0, 4))
        ttk.Entry(box, textvariable=self.v_pw, show="•", width=16).pack(side="left", padx=(0, 10))
        ttk.Combobox(box, textvariable=self.v_role, values=ROLES, state="readonly",
                     width=9).pack(side="left", padx=(0, 10))
        ttk.Button(box, text="Add", command=self.add).pack(side="left")

        f, self.tree = make_tree(self, [("name", "Username"), ("role", "Role")],
                                 {"name": 240, "role": 120}, height=12)
        f.pack(fill="both", expand=True, pady=8)
        bar = ttk.Frame(self)
        bar.pack(fill="x")
        ttk.Button(bar, text="Reset password", command=self.reset_pw).pack(side="left")
        ttk.Button(bar, text="Delete user", command=self.delete).pack(side="left", padx=6)
        self.refresh()

    def _err(self, e):
        messagebox.showerror("Error", str(e), parent=self.winfo_toplevel())

    def add(self):
        try:
            self.auth.create_user(self.v_name.get(), self.v_pw.get(), self.v_role.get())
        except ValueError as e:
            self._err(e)
            return
        self.v_name.set("")
        self.v_pw.set("")
        self.refresh()

    def reset_pw(self):
        uid = selected_id(self.tree)
        if uid is None:
            return
        pw = simpledialog.askstring("Reset password", "New password:", show="•",
                                    parent=self.winfo_toplevel())
        if pw is None:
            return
        try:
            self.auth.set_password(uid, pw)
        except ValueError as e:
            self._err(e)
            return
        messagebox.showinfo("Password", "Password updated.", parent=self.winfo_toplevel())

    def delete(self):
        uid = selected_id(self.tree)
        if uid is None:
            return
        if not messagebox.askyesno("Delete user", "Delete this user?", parent=self.winfo_toplevel()):
            return
        try:
            self.auth.delete_user(uid, self.me["id"])
        except ValueError as e:
            self._err(e)
            return
        self.refresh()

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        for u in self.auth.users():
            self.tree.insert("", "end", iid=str(u["id"]), values=(u["username"], u["role"]))

