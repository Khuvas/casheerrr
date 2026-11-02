"""Color themes (Red, White, Light gray) and the right-hand navigation panel.

The chosen theme is remembered in theme.txt next to this file.
"""
import tkinter as tk
from pathlib import Path
from tkinter import ttk

THEME_FILE = Path(__file__).with_name("theme.txt")
DEFAULT_THEME = "Red"
INK = "#1b1f24"
FIELD = "#ffffff"

THEMES = {
    "Red": dict(
        swatch="#c8102e", bg="#fdf2f3", fg="#2a1215", border="#e5b9bf", head="#f6d5d9",
        btn="#c8102e", btn_hover="#a30d26", btn_press="#8f0b21", btn_fg="#ffffff",
        sel="#c8102e", sel_fg="#ffffff",
        side="#c8102e", side_fg="#ffffff", side_hover="#a30d26", on="#ffffff", on_fg="#c8102e"),
    "White": dict(
        swatch="#ffffff", bg="#ffffff", fg=INK, border="#d9dce1", head="#f3f4f6",
        btn="#c8102e", btn_hover="#a30d26", btn_press="#8f0b21", btn_fg="#ffffff",
        sel="#c8102e", sel_fg="#ffffff",
        side="#ffffff", side_fg=INK, side_hover="#f3f4f6", on="#c8102e", on_fg="#ffffff"),
    "Light gray": dict(
        swatch="#e5e7eb", bg="#e9ebee", fg=INK, border="#c4c8ce", head="#d9dce1",
        btn="#c8102e", btn_hover="#a30d26", btn_press="#8f0b21", btn_fg="#ffffff",
        sel="#c8102e", sel_fg="#ffffff",
        side="#d9dce1", side_fg=INK, side_hover="#cbd0d6", on="#c8102e", on_fg="#ffffff"),
}


def load_theme():
    try:
        name = THEME_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return DEFAULT_THEME
    return name if name in THEMES else DEFAULT_THEME


def save_theme(name):
    try:
        THEME_FILE.write_text(name, encoding="utf-8")
    except OSError:
        pass


def apply_theme(root, name):
    """Restyle every ttk widget of `root` immediately."""
    p = THEMES[name]
    st = ttk.Style(root)
    st.theme_use("clam")
    root.configure(bg=p["bg"])
    root.option_add("*TCombobox*Listbox.background", FIELD)
    root.option_add("*TCombobox*Listbox.foreground", INK)

    st.configure(".", background=p["bg"], foreground=p["fg"], bordercolor=p["border"],
                 lightcolor=p["bg"], darkcolor=p["bg"], troughcolor=p["head"])
    st.configure("TFrame", background=p["bg"])
    st.configure("TLabel", background=p["bg"], foreground=p["fg"])
    st.configure("TSeparator", background=p["border"])
    st.configure("TLabelframe", background=p["bg"], bordercolor=p["border"],
                 lightcolor=p["border"], darkcolor=p["border"])
    st.configure("TLabelframe.Label", background=p["bg"], foreground=p["fg"])
    st.configure("TCheckbutton", background=p["bg"], foreground=p["fg"], focuscolor=p["bg"])
    st.map("TCheckbutton", background=[("active", p["bg"])])

    st.configure("TButton", background=p["btn"], foreground=p["btn_fg"], bordercolor=p["btn"],
                 lightcolor=p["btn"], darkcolor=p["btn"], focuscolor=p["btn"],
                 padding=(10, 5), relief="flat")
    st.map("TButton",
           background=[("disabled", "#b8bcc3"), ("pressed", p["btn_press"]), ("active", p["btn_hover"])],
           foreground=[("disabled", "#ffffff")])

    st.configure("TEntry", fieldbackground=FIELD, foreground=INK, insertcolor=INK,
                 bordercolor=p["border"], lightcolor=p["border"], darkcolor=p["border"])
    st.configure("TCombobox", fieldbackground=FIELD, foreground=INK, background=p["head"],
                 arrowcolor=INK, bordercolor=p["border"], lightcolor=p["border"],
                 darkcolor=p["border"])
    st.map("TCombobox", fieldbackground=[("readonly", FIELD)], foreground=[("readonly", INK)])

    st.configure("Treeview", background=FIELD, fieldbackground=FIELD, foreground=INK,
                 rowheight=24, borderwidth=0)
    st.map("Treeview", background=[("selected", p["sel"])], foreground=[("selected", p["sel_fg"])])
    st.configure("Treeview.Heading", background=p["head"], foreground=p["fg"], relief="flat",
                 bordercolor=p["border"])
    st.map("Treeview.Heading", background=[("active", p["border"])])
    st.configure("TScrollbar", background=p["head"], troughcolor=p["bg"], arrowcolor=p["fg"],
                 bordercolor=p["border"], lightcolor=p["head"], darkcolor=p["head"])

    st.configure("Side.TFrame", background=p["side"])
    st.configure("Side.TLabel", background=p["side"], foreground=p["side_fg"])
    st.configure("SideTitle.TLabel", background=p["side"], foreground=p["side_fg"],
                 font=("TkDefaultFont", 14, "bold"))
    for style, bg, fg in (("Nav.TButton", p["side"], p["side_fg"]),
                          ("NavOn.TButton", p["on"], p["on_fg"])):
        st.configure(style, background=bg, foreground=fg, bordercolor=bg, lightcolor=bg,
                     darkcolor=bg, focuscolor=bg, anchor="w", padding=(14, 9), relief="flat")
    st.map("Nav.TButton", background=[("pressed", p["side_hover"]), ("active", p["side_hover"])])
    st.map("NavOn.TButton", background=[("pressed", p["on"]), ("active", p["on"])],
           foreground=[("active", p["on_fg"])])


class SideNav(ttk.Frame):
    """Content on the left, the option buttons on the right.

    Create pages with `nav.body` as their parent, then call nav.add(label, page).
    Put extra widgets in nav.header (top) and nav.footer (bottom) of the panel.
    """

    def __init__(self, parent, width=190):
        super().__init__(parent)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.body = ttk.Frame(self)
        self.body.grid(row=0, column=0, sticky="nsew")
        self.body.columnconfigure(0, weight=1)
        self.body.rowconfigure(0, weight=1)
        ttk.Separator(self, orient="vertical").grid(row=0, column=1, sticky="ns")
        self.side = ttk.Frame(self, style="Side.TFrame", width=width)
        self.side.grid(row=0, column=2, sticky="ns")
        self.side.pack_propagate(False)
        self.header = ttk.Frame(self.side, style="Side.TFrame", padding=(14, 16, 14, 10))
        self.header.pack(fill="x")
        self.menu = ttk.Frame(self.side, style="Side.TFrame")
        self.menu.pack(fill="x", pady=4)
        self.footer = ttk.Frame(self.side, style="Side.TFrame", padding=14)
        self.footer.pack(side="bottom", fill="x")
        self.pages, self.buttons, self.current = {}, {}, None

    def add(self, label, page):
        btn = ttk.Button(self.menu, text=label, style="Nav.TButton",
                         command=lambda: self.select(label))
        btn.pack(fill="x")
        self.pages[label], self.buttons[label] = page, btn
        page.grid(row=0, column=0, sticky="nsew")
        page.grid_remove()

    def select(self, label):
        if self.current:
            self.pages[self.current].grid_remove()
            self.buttons[self.current].configure(style="Nav.TButton")
        self.current = label
        page = self.pages[label]
        page.grid()
        self.buttons[label].configure(style="NavOn.TButton")
        if hasattr(page, "refresh"):
            page.refresh()


class ThemePicker(ttk.Frame):
    """Three color swatches; click one to restyle the whole app."""

    def __init__(self, parent, root):
        super().__init__(parent, style="Side.TFrame")
        self.root = root
        self.current = load_theme()
        self.label = tk.StringVar()
        ttk.Label(self, textvariable=self.label, style="Side.TLabel").pack(anchor="w")
        row = ttk.Frame(self, style="Side.TFrame")
        row.pack(anchor="w", pady=(6, 0))
        self.swatches = {}
        for name, p in THEMES.items():
            sw = tk.Frame(row, width=36, height=24, bg=p["swatch"], cursor="hand2",
                          highlightthickness=3)
            sw.pack(side="left", padx=(0, 6))
            sw.bind("<Button-1>", lambda e, n=name: self.choose(n))
            self.swatches[name] = sw
        self.mark()

    def mark(self):
        self.label.set("Color: " + self.current)
        for name, sw in self.swatches.items():
            sw.configure(highlightbackground="#111827" if name == self.current else "#9ca3af")

    def choose(self, name):
        self.current = name
        apply_theme(self.root, name)
        save_theme(name)
        self.mark()

