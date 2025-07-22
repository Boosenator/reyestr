# modules/calendar_tab.py

import tkinter as tk
from tkinter import ttk
from tkcalendar import Calendar
import sqlite3
from datetime import datetime, timedelta
from config import DB_PATH
from .context_menu import build_context_menu, open_selected

class CalendarTab(tk.Frame):
    def __init__(self, parent, app, on_date_selected_callback=None):
        """
        parent — Notebook
        app — інстанс DocumentApp
        on_date_selected_callback — колбек, приймає або рядок дати, або int(doc_id)
        """
        super().__init__(parent)
        self.app = app
        self.on_date_selected_callback = on_date_selected_callback

        paned = ttk.Panedwindow(self, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        # Master: календар (60% ширини)
        left = ttk.Frame(paned)
        paned.add(left, weight=3)  # було weight=1, тепер 3 → 3/(3+2)=60%
        self.calendar = Calendar(left, selectmode='day', date_pattern='yyyy-mm-dd')
        self.calendar.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.calendar.bind("<<CalendarSelected>>", self._on_date_selected)

        # Detail: список документів (40% ширини)
        right = ttk.Frame(paned)
        paned.add(right, weight=2)
        cols = ('filename', 'doc_type', 'deadline')
        self.list = ttk.Treeview(right, columns=cols, show='headings')
        for col, title in zip(cols, ("Назва", "Тип", "Термін")):
            self.list.heading(col, text=title, anchor='w')
            self.list.column(col, width=200, anchor='w')
        self.list.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Подвійний клік — відкриваємо документ
        self.list.bind("<Double-1>", self._on_row_double)
        # Правий клік — контекстне меню
        self.list.bind("<Button-3>", self._on_right_click)

        # Теги підсвітки
        for tag, color in (('overdue','#c33'), ('upcoming','#f90'), ('deadline','#e33')):
            self.calendar.tag_config(tag, background=color)

        # Початкова підсвітка дат
        self._highlight_deadlines()

    def _on_date_selected(self, event=None):
        date_str = self.calendar.get_date()
        self._populate_list(date_str)
        if self.on_date_selected_callback:
            self.on_date_selected_callback(date_str)

    def _populate_list(self, date_str):
        for iid in self.list.get_children():
            self.list.delete(iid)
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("""
            SELECT id, filename, doc_type, deadline
              FROM documents
             WHERE deadline=?
        """, (date_str,))
        for doc_id, fn, typ, dl in cur.fetchall():
            self.list.insert('', 'end', iid=str(doc_id), values=(fn, typ, dl))
        conn.close()

    def _on_row_double(self, event):
        item = self.list.focus()
        if not item:
            return
        open_selected(self.app)

    def _on_right_click(self, event):
        iid = self.list.identify_row(event.y)
        if not iid:
            return
        self.list.selection_set(iid)
        self.list.focus(iid)
        self.app.selected_id = iid
        menu = build_context_menu(self.app, tree=self.list)
        menu.tk_popup(event.x_root, event.y_root)
    def _highlight_deadlines(self):
    # Очистити всі існуючі події
        for tag in ('overdue', 'upcoming', 'deadline', 'today'):
            for ev in self.calendar.get_calevents(tag=tag):
                self.calendar.calevent_remove(ev)

        today = datetime.today().date()
        upcoming = today + timedelta(days=3)

    # Додати тег для сьогоднішньої дати
        self.calendar.tag_config('today', background='#00bcd4', foreground='white')
        self.calendar.calevent_create(today, 'Сьогодні', 'today')

    # Підсвітити терміни
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("""
        SELECT DISTINCT deadline
          FROM documents
         WHERE is_controlled=1
           AND deadline IS NOT NULL
        """)
        for (d,) in cur.fetchall():
            try:
                dt = datetime.fromisoformat(d).date()
            except:
                continue
            if dt < today:
                tag = 'overdue'
            elif dt <= upcoming:
                tag = 'upcoming'
            else:
                tag = 'deadline'
            self.calendar.calevent_create(dt, 'Термін', tag)
        conn.close()   
