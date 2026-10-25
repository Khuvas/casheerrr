"""Canteen Cashier — run this file:  python main.py

Merges the separate modules into one application:
    common.py      shared database + helpers
    theme.py       colors (Red / White / Light gray) and the right-hand options panel
    login.py       sign-in and user management
    make_order.py  counter orders and totals
    preorder.py    pre-orders, queue, waiting time, ready notice
    Storage.py     stock management
    addmenu.py     menu items
    income.py      sales records and income reports

Roles:  cashier -> Cashier, New pre-order, Pre-order queue, Storage
        admin   -> everything above + Menu, Income, Users
"""
import tkinter as tk
from tkinter import ttk

from Storage import StorageService, StorageTab
from addmenu import MenuService, MenuTab
from common import get_db
from income import IncomeService, IncomeTab
from login import AuthService, UsersTab, run_login
from make_order import OrderService, OrderTab
from preorder import NewPreorderTab, PreorderQueueTab, PreorderService
from theme import SideNav, ThemePicker, apply_theme, load_theme


class App(tk.Tk):
    def __init__(self, user, db, auth):
        super().__init__()
        self.user = user
        self.logged_out = False
        self.title("Canteen Cashier")
        self.geometry("1100x680")
        self.minsize(900, 560)
        apply_theme(self, load_theme())

        menu = MenuService(db)
        income = IncomeService(db)
        orders = OrderService(db, menu, income)
        preorders = PreorderService(db, orders, income)
        storage = StorageService(db)

        nav = self.nav = SideNav(self, width=200)
        nav.pack(fill="both", expand=True)
        ttk.Label(nav.header, text="Canteen Cashier", style="SideTitle.TLabel").pack(anchor="w")
        ttk.Label(nav.header, text=f"{user['username']} · {user['role']}",
                  style="Side.TLabel").pack(anchor="w", pady=(2, 0))

        tabs = [("Cashier", OrderTab(nav.body, orders, user)),
                ("New pre-order", NewPreorderTab(nav.body, preorders)),
                ("Pre-order queue", PreorderQueueTab(nav.body, preorders, user)),
                ("Storage", StorageTab(nav.body, storage, menu))]
        if user["role"] == "admin":
            tabs += [("Menu", MenuTab(nav.body, menu)),
                     ("Income", IncomeTab(nav.body, income)),
                     ("Users", UsersTab(nav.body, auth, user))]
        for label, page in tabs:
            nav.add(label, page)
        nav.select(tabs[0][0])

        ThemePicker(nav.footer, self).pack(fill="x")
        ttk.Button(nav.footer, text="Log out", command=self.logout).pack(fill="x", pady=(12, 0))

    def logout(self):
        self.logged_out = True
        self.destroy()


def main():
    db = get_db()
    auth = AuthService(db)
    while True:
        user = run_login(auth)
        if user is None:
            break
        app = App(user, db, auth)
        app.mainloop()
        if not app.logged_out:
            break


if __name__ == "__main__":
    main()
