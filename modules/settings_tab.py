# modules/settings_tab.py

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from .settings import SettingsManager
from .database import db

class SettingsTab(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.sm = SettingsManager()

        # Список каталогів
        self.tree = ttk.Treeview(self, columns=("path",), show="headings")
        self.tree.heading("path", text="Каталог для сканування")
        self.tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Кнопки
        btns = tk.Frame(self)
        btns.pack(fill=tk.X, padx=5, pady=(0,5))
        tk.Button(btns, text="Додати", command=self._add).pack(side=tk.LEFT)
        tk.Button(btns, text="Видалити", command=self._remove).pack(side=tk.LEFT, padx=5)
        tk.Button(btns, text="Встановити активним", command=self._set_active).pack(side=tk.LEFT, padx=5)
        tk.Button(btns, text="Повторно сканувати", command=self._rescan).pack(side=tk.LEFT, padx=5)
        tk.Button(btns, text="Видалити всі значення", command=self._clear_all).pack(side=tk.LEFT, padx=5)

        self._populate()

    def _populate(self):
        self.tree.delete(*self.tree.get_children())
        for idx, path in enumerate(self.sm.get_folders()):
            tag = "active" if path == self.sm.get_active() else ""
            self.tree.insert("", "end", iid=str(idx), values=(path,), tags=(tag,))
        self.tree.tag_configure("active", background="#d0f0c0")

    def _add(self):
        path = filedialog.askdirectory()
        if not path:
            return
        if not self.sm.add_folder(path):
            messagebox.showinfo("Увага", "Цей каталог вже додано.")
        self._populate()

    def _remove(self):
        sel = self.tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        path = self.sm.get_folders()[idx]
        if messagebox.askyesno("Підтвердження", f"Видалити каталог?\n{path}"):
            self.sm.remove_folder(path)
            self._populate()

    def _set_active(self):
        sel = self.tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        path = self.sm.get_folders()[idx]
        self.sm.set_active(path)
        self._populate()
        messagebox.showinfo("Готово", f"Активний каталог:\n{path}")
        self.app.current_scan_folder = path
        self.app.load_registry_data()

    def _rescan(self):
        # Ручний запуск сканування
        self.app._scan_and_update()
        self.app.load_registry_data()
        messagebox.showinfo("Готово", "Сканування завершено.")

    def _clear_all(self):
        # Підрахунок записів
        row = db.query("SELECT COUNT(*) FROM documents")
        count = row[0][0] if row else 0
        prompt = (
            f"Якщо ви впевнені, що хочете видалити інформацію про {count} записів, "
            "то введіть кількість записів та натисніть ОК / СКАСУВАТИ"
        )
        ans = simpledialog.askstring("Підтвердження", prompt)
        if ans is None:
            return
        if ans.strip() != str(count):
            messagebox.showerror("Помилка", "Введена кількість не співпадає. Операцію скасовано.")
            return
        # Видалення всіх даних
        db.execute("DELETE FROM document_numbers")
        db.execute("DELETE FROM document_links")
        db.execute("DELETE FROM documents")
        messagebox.showinfo("Готово", f"Видалено інформацію про {count} записів.")
        self.app.load_registry_data()
