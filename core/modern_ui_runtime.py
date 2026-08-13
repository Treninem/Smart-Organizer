from __future__ import annotations

import ctypes
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk
from tkinter.scrolledtext import ScrolledText

from core.windows_paths import downloads_path

BG = "#080A0F"
SURFACE = "#101521"
SURFACE_2 = "#171D2A"
BORDER = "#293246"
TEXT = "#F7F9FF"
MUTED = "#9BA7BB"
PURPLE = "#8B5CF6"
PURPLE_HOVER = "#9F7AEA"
TEAL = "#2DD4BF"
TEAL_HOVER = "#5EEAD4"
CYAN = "#38BDF8"
CYAN_HOVER = "#67D3FF"
DISABLED = "#343B4A"


def _rounded_rect(canvas: tk.Canvas, x1: int, y1: int, x2: int, y2: int, radius: int, **kwargs):
    radius = max(2, min(radius, (x2 - x1) // 2, (y2 - y1) // 2))
    points = [
        x1 + radius, y1,
        x2 - radius, y1,
        x2, y1,
        x2, y1 + radius,
        x2, y2 - radius,
        x2, y2,
        x2 - radius, y2,
        x1 + radius, y2,
        x1, y2,
        x1, y2 - radius,
        x1, y1 + radius,
        x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, splinesteps=24, **kwargs)


class RoundedButton(tk.Canvas):
    """Drop-in visual replacement for ttk.Button with real rounded corners."""

    def __init__(
        self,
        master=None,
        text: str = "",
        command=None,
        style: str = "",
        state: str = "normal",
        width=None,
        padding=None,
        **kwargs,
    ):
        self._text = str(text)
        self._command = command
        self._style = str(style or "")
        self._state = str(state or "normal")
        self._hover = False
        self._pressed = False
        self._width_hint = width
        self._padding = padding
        parent_bg = SURFACE if isinstance(master, ttk.LabelFrame) else BG
        px_width = self._measure_width(width)
        super().__init__(
            master,
            width=px_width,
            height=38,
            background=parent_bg,
            highlightthickness=0,
            borderwidth=0,
            relief="flat",
            takefocus=True,
            cursor="hand2" if self._state != "disabled" else "arrow",
        )
        self.bind("<Configure>", lambda _event: self._draw())
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Return>", lambda _event: self.invoke())
        self.bind("<space>", lambda _event: self.invoke())
        self.bind("<FocusIn>", lambda _event: self._draw())
        self.bind("<FocusOut>", lambda _event: self._draw())
        self.after_idle(self._draw)

    def _measure_width(self, width) -> int:
        if isinstance(width, int) and width > 0:
            return max(90, width * 9 + 28)
        return max(112, min(310, len(self._text) * 8 + 34))

    def _colors(self):
        text = self._text.casefold()
        style = self._style.casefold()
        if self._state == "disabled":
            return DISABLED, DISABLED, MUTED, DISABLED
        if "navactive" in style:
            return PURPLE, PURPLE_HOVER, TEXT, CYAN
        if "nav" in style:
            return SURFACE_2, "#20283A", TEXT, BORDER
        if any(token in text for token in ("применить", "обнов", "github")):
            return PURPLE, PURPLE_HOVER, TEXT, PURPLE
        if any(token in text for token in ("undo", "журнал", "память")):
            return TEAL, TEAL_HOVER, "#04110F", TEAL
        if any(token in text for token in ("анализ", "выбрать", "план", "диагност", "загрузк")):
            return CYAN, CYAN_HOVER, "#041018", CYAN
        return SURFACE_2, "#20283A", TEXT, PURPLE

    def _draw(self):
        self.delete("all")
        width = max(2, self.winfo_width())
        height = max(2, self.winfo_height())
        normal, hover, fg, outline = self._colors()
        fill = hover if (self._hover or self._pressed) and self._state != "disabled" else normal
        if self._pressed and self._state != "disabled":
            fill = hover
        border = CYAN if self.focus_get() is self and self._state != "disabled" else outline
        _rounded_rect(self, 1, 1, width - 1, height - 1, 12, fill=border, outline="")
        _rounded_rect(self, 2, 2, width - 2, height - 2, 11, fill=fill, outline="")
        self.create_text(
            width // 2,
            height // 2,
            text=self._text,
            fill=fg,
            font=("Segoe UI", 10, "bold"),
            anchor="center",
        )

    def _on_enter(self, _event=None):
        if self._state != "disabled":
            self._hover = True
            self._draw()

    def _on_leave(self, _event=None):
        self._hover = False
        self._pressed = False
        self._draw()

    def _on_press(self, _event=None):
        if self._state != "disabled":
            self.focus_set()
            self._pressed = True
            self._draw()

    def _on_release(self, event=None):
        if self._state == "disabled":
            return
        inside = True
        if event is not None:
            inside = 0 <= event.x <= self.winfo_width() and 0 <= event.y <= self.winfo_height()
        was_pressed = self._pressed
        self._pressed = False
        self._draw()
        if was_pressed and inside:
            self.invoke()

    def invoke(self):
        if self._state != "disabled" and callable(self._command):
            return self._command()
        return None

    def configure(self, cnf=None, **kwargs):
        if cnf:
            kwargs.update(cnf)
        if "text" in kwargs:
            self._text = str(kwargs.pop("text"))
        if "command" in kwargs:
            self._command = kwargs.pop("command")
        if "style" in kwargs:
            self._style = str(kwargs.pop("style") or "")
        if "state" in kwargs:
            self._state = str(kwargs.pop("state") or "normal")
            super().configure(cursor="arrow" if self._state == "disabled" else "hand2")
        kwargs.pop("padding", None)
        kwargs.pop("width", None)
        if kwargs:
            try:
                super().configure(**kwargs)
            except tk.TclError:
                pass
        self._draw()

    config = configure

    def cget(self, key):
        if key == "text":
            return self._text
        if key == "command":
            return self._command
        if key == "style":
            return self._style
        if key == "state":
            return self._state
        return super().cget(key)


NAV_TEXTS = {
    "🏠 Главная",
    "📂 Файлы",
    "🤖 Проекты",
    "🧠 Память ИИ",
    "🐙 GitHub",
    "📦 Архивы",
    "⚙ Настройки",
}


def _walk(widget):
    for child in widget.winfo_children():
        yield child
        yield from _walk(child)


def _dark_titlebar(window) -> None:
    if not hasattr(ctypes, "windll"):
        return
    try:
        window.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        enabled = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(enabled), ctypes.sizeof(enabled))
    except Exception:
        pass


def install_modern_ui_runtime(main_window) -> None:
    """Install the black/white/purple/teal/cyan desktop theme."""

    cls = main_window.SmartOrganizerApp
    if getattr(cls, "_modern_ui_runtime_installed", False):
        return
    cls._modern_ui_runtime_installed = True

    # Existing modules build buttons through tkinter.ttk at runtime. Replacing
    # the class once gives every section the same rounded button implementation.
    ttk.Button = RoundedButton
    main_window.ttk.Button = RoundedButton

    original_setup_style = cls._setup_style
    original_init = cls.__init__
    original_result_box = cls._result_box
    original_show_section = cls.show_section
    original_show_files = cls.show_files

    def _setup_style(self):
        try:
            original_setup_style(self)
        except Exception:
            pass
        self.configure(background=BG)
        style = ttk.Style(self)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("Title.TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 22, "bold"))
        style.configure("SubTitle.TLabel", background=BG, foreground=CYAN, font=("Segoe UI", 11, "bold"))
        style.configure("Big.TLabel", background=BG, foreground=TEAL, font=("Segoe UI", 20, "bold"))
        style.configure("Monitor.TLabel", background=BG, foreground=MUTED, font=("Segoe UI", 9))
        style.configure(
            "TLabelframe",
            background=BG,
            foreground=TEXT,
            bordercolor=BORDER,
            lightcolor=BORDER,
            darkcolor=BORDER,
            relief="solid",
            borderwidth=1,
        )
        style.configure("TLabelframe.Label", background=BG, foreground=CYAN, font=("Segoe UI", 9, "bold"))
        style.configure("TSeparator", background=BORDER)
        style.configure("TCheckbutton", background=BG, foreground=TEXT, font=("Segoe UI", 10))
        style.map("TCheckbutton", background=[("active", BG)], foreground=[("disabled", MUTED)])
        style.configure(
            "TEntry",
            fieldbackground=SURFACE,
            foreground=TEXT,
            insertcolor=TEXT,
            bordercolor=BORDER,
            lightcolor=BORDER,
            darkcolor=BORDER,
            padding=7,
        )
        style.configure("TScrollbar", background=SURFACE_2, troughcolor=BG, bordercolor=BG, arrowcolor=CYAN)

    def __init__(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self.geometry("1280x820")
        self.minsize(1040, 680)
        self.title(f"Smart Organizer v{main_window.APP_VERSION}")
        self.after(50, lambda: _dark_titlebar(self))
        self.after_idle(lambda: self._set_active_navigation("🏠 Главная"))

    def _result_box(self) -> ScrolledText:
        box = original_result_box(self)
        box.configure(
            background=SURFACE,
            foreground=TEXT,
            insertbackground=TEXT,
            selectbackground=PURPLE,
            selectforeground=TEXT,
            relief="flat",
            borderwidth=0,
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=CYAN,
            padx=12,
            pady=10,
        )
        return box

    def _set_active_navigation(self, title: str) -> None:
        for widget in _walk(self):
            if isinstance(widget, RoundedButton):
                text = str(widget.cget("text"))
                if text in NAV_TEXTS:
                    widget.configure(style="NavActive.TButton" if text == title else "Nav.TButton")

    def show_section(self, title: str):
        self._set_active_navigation(title)
        return original_show_section(self, title)

    def scan_downloads(self) -> None:
        path = downloads_path()
        self.status_var.set(f"Загрузки Windows: {path}")
        self.start_scan(path)

    def scan_drive_or_folder(self) -> None:
        selected = filedialog.askdirectory(title="Выберите диск или папку для анализа")
        if selected:
            self.start_scan(Path(selected))

    def show_files(self) -> None:
        original_show_files(self)
        toolbar = None
        for widget in self.content.winfo_children():
            if isinstance(widget, ttk.Frame):
                buttons = [child for child in widget.winfo_children() if isinstance(child, RoundedButton)]
                if buttons:
                    toolbar = widget
                    break
        if toolbar is not None:
            RoundedButton(toolbar, text="⬇ Загрузки", command=self.scan_downloads).pack(side="left", padx=6)
            RoundedButton(toolbar, text="💽 Диск / папка", command=self.scan_drive_or_folder).pack(side="left", padx=6)

    cls._setup_style = _setup_style
    cls.__init__ = __init__
    cls._result_box = _result_box
    cls._set_active_navigation = _set_active_navigation
    cls.show_section = show_section
    cls.scan_downloads = scan_downloads
    cls.scan_drive_or_folder = scan_drive_or_folder
    cls.show_files = show_files
