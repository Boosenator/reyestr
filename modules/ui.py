# modules/ui.py

import os
import threading
import queue
import tkinter as tk
from tkinter import ttk, messagebox

from config import DB_PATH
from .database import db, init_db, get_new_files_count, get_new_file_ids, mark_all_as_old
from .filter_frame import FilterFrame
from .context_menu import build_context_menu, open_selected
from .tree_setup import setup_tree_widget, load_documents_into_tree
from .scanner import insert_new_files
from .utils import compute_file_hash
from .calendar_tab import CalendarTab
from .settings_tab import SettingsTab
from .settings import SettingsManager
from .detail_panel import DetailPanel


class DocumentApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Реєстр документів")
        self.state('zoomed')
        self.geometry("1600x780")

        init_db()

        # Стиль прогрес-бару
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure(
            'Custom.Horizontal.TProgressbar',
            troughcolor='#e0e0e0',
            bordercolor='#a0a0a0',
            background='#4caf50',
            lightcolor='#6fbf73',
            darkcolor='#388e3c',
            thickness=18,
            borderwidth=1
        )
        style.map(
            'Custom.Horizontal.TProgressbar',
            background=[('active', '#81c784')],
            troughcolor=[('disabled', '#f0f0f0')]
        )

        # --- стан ---
        self.selected_id      = None
        self.sort_by_col      = None
        self.sort_reverse     = False
        self.search_term      = ""
        self.show_incomplete  = False
        self.filter_direction = ""
        self.filter_type      = ""
        self.filter_tags      = ""
        self.filter_date_from = ""
        self.filter_date_to   = ""
        self.filter_num_main  = ""
        self.filter_num_extra = ""
        self.filter_new       = False

        # Ієрархія/плоский
        self.show_hierarchy = tk.BooleanVar(value=True)

        # Очікуюча черга оновлень UI
        self._ui_queue = queue.Queue()
        self.after(100, self._process_ui_queue)

        # --- вкладки ---
        self.notebook     = ttk.Notebook(self)
        self.tab_registry = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_registry, text="Реєстр")

        self.tab_calendar = CalendarTab(
            self.notebook,
            self,
            on_date_selected_callback=lambda doc_id:
                open_selected(self) if isinstance(doc_id, int) else None
        )
        self.notebook.add(self.tab_calendar, text="Календар")

        self.tab_settings = SettingsTab(self.notebook, self)
        self.notebook.add(self.tab_settings, text="Налаштування")

        self.notebook.pack(fill=tk.BOTH, expand=True)

        # --- статус-бар ---
        status_frame = ttk.Frame(self)
        status_frame.pack(fill=tk.X, padx=5, pady=(0,5))
        self.progress = ttk.Progressbar(
            status_frame,
            style='Custom.Horizontal.TProgressbar',
            orient="horizontal",
            mode="indeterminate"
        )
        self.progress.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.status_label = ttk.Label(status_frame, text="Готовий", anchor='w')
        self.status_label.pack(side=tk.LEFT, padx=(10,0))

        # Папка для сканування
        sm = SettingsManager()
        self.current_scan_folder = sm.get_active()

        # --- вкладка «Реєстр» ---
        self._setup_registry_tab()

        # Запуск первинного сканування
        self.after(200, lambda: threading.Thread(
                target=self._scan_and_update,
                daemon=True
            ).start())
    def _process_ui_queue(self):
        """Обробляє чергу оновлень від фонового потоку."""
        try:
            while True:
                callback = self._ui_queue.get_nowait()
                callback()
        except queue.Empty:
            pass
        self.after(100, self._process_ui_queue)

    def _setup_registry_tab(self):
        top = ttk.Frame(self.tab_registry)
        top.pack(fill=tk.X, padx=5, pady=5)

        doc_types = self._load_doc_types()
        griffes   = ["НТ", "ДСК", "Т", "ЦТ"]
        self.filter_frame = FilterFrame(top, self.apply_filters, doc_types, griffes)
        self.filter_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

        cb = ttk.Checkbutton(
            top,
            text="Дерево каталогу",
            variable=self.show_hierarchy,
            command=self.load_registry_data
        )
        cb.pack(side=tk.RIGHT, padx=(0, 10))

        self.new_files_btn = ttk.Button(
            top,
            text=f"Нові файли ({get_new_files_count()})",
            command=self.show_new_files
        )
        self.new_files_btn.pack(side=tk.RIGHT, padx=(0, 10))

        paned = ttk.Panedwindow(self.tab_registry, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(paned)
        paned.add(left, weight=3)
        self.tree_class = lambda *a, **k: ttk.Treeview(left, **k)
        setup_tree_widget(self)

        vsb = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        hsb = ttk.Scrollbar(left, orient="horizontal", command=self.tree.xview)
        self.tree.configure(xscrollcommand=hsb.set)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)

        self.tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        right = ttk.Frame(paned)
        paned.add(right, weight=2)
        self.detail = DetailPanel(right, self)
        self.detail.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.load_registry_data()

        self.tree.bind("<<TreeviewSelect>>", self.on_select)
        self.tree.bind("<Button-3>",        self.on_right_click)
        self.tree.bind("<Double-1>", lambda e: open_selected(self))

    def _load_doc_types(self):
        rows = db.query("SELECT type_name FROM document_types ORDER BY type_name")
        return [r[0] for r in rows]

    def _scan_and_update(self):
        total = 0
        def cb(done, total_count):
            nonlocal total
            total = total_count
            self._ui_queue.put(lambda: self._update_progress(done, total))

        # Оновлюємо UI перед скануванням
        self._ui_queue.put(lambda: self.new_files_btn.config(state="disabled"))
        self._ui_queue.put(lambda: self.status_label.config(text="Сканування…"))

        try:
            insert_new_files(base_dir=self.current_scan_folder, progress_callback=cb)
        finally:
            self._ui_queue.put(self._finish_scan)

    def _update_progress(self, done, total):
        if self.progress['mode'] != 'determinate':
            self.progress.config(mode="determinate", maximum=total)
        self.progress['value'] = done
        self.status_label.config(text=f"Сканування: {done}/{total}")

    def _finish_scan(self):
        # Завершуємо сканування
        self.progress.stop()
        self.progress.config(mode="indeterminate", value=0)
        self.status_label.config(text="Готово")
        self.new_files_btn.config(state="normal")
        self.load_registry_data()
        cnt = get_new_files_count()
        self.new_files_btn.config(text=f"Нові файли ({cnt})")

        # Тепер запускаємо обчислення хешів з прогресом
        ##threading.Thread(target=self._hash_and_update, daemon=True).start()


    def show_new_files(self):
        new_ids = set(get_new_file_ids())
        if not new_ids:
            return

        def prune(node):
            for child in list(self.tree.get_children(node)):
                if not child.isdigit():
                    prune(child)
                elif int(child) not in new_ids:
                    self.tree.delete(child)
                if not self.tree.get_children(node) and node != "":
                    self.tree.delete(node)

        prune("")
        mark_all_as_old()
        self.new_files_btn.config(text="Нові файли (0)")

    def sort_column(self, col):
        self.sort_reverse = not self.sort_reverse if self.sort_by_col == col else False
        self.sort_by_col  = col
        self.load_registry_data()

    def load_registry_data(self):
        self.progress.start()
        threading.Thread(target=self._bg_load_registry, daemon=True).start()

    def _bg_load_registry(self):
        hierarchical = self.show_hierarchy.get()
        self._ui_queue.put(lambda: load_documents_into_tree(self, hierarchical=hierarchical))
        self._ui_queue.put(lambda: self.progress.stop())

    def apply_filters(self,
                      search_text=None, show_incomplete=False,
                      direction=None, doc_type=None, griff=None,
                      date_from=None, date_to=None,
                      num_main=None, num_extra=None):
        self.search_term      = (search_text or "").lower()
        self.show_incomplete  = show_incomplete
        self.filter_direction = "" if direction in (None, "Усі") else direction
        self.filter_type      = "" if doc_type  in (None, "Усі") else doc_type
        self.filter_tags      = "" if griff     in (None, "Усі") else griff
        self.filter_date_from = date_from or ""
        self.filter_date_to   = date_to or ""
        self.filter_num_main  = (num_main or "").lower()
        self.filter_num_extra = (num_extra or "").lower()
        self.load_registry_data()

    def on_select(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        ids = [int(iid) for iid in sel if iid.isdigit()]
        if not ids:
            return
        self.selected_id = ids[0] if len(ids) == 1 else None
        self.detail.load_links(ids[0] if len(ids)==1 else ids)

    def on_right_click(self, event):
        iid = self.tree.identify_row(event.y)
        if not iid:
            return
        self.tree.selection_set(iid)
        self.tree.focus(iid)
        self.selected_id = iid
        menu = build_context_menu(self)
        menu.tk_popup(event.x_root, event.y_root)
