import os
import tkinter as tk
from tkinter import ttk, messagebox
from tkcalendar import DateEntry

from .database import db, get_document_numbers, save_document_numbers
from .utils import rename_file, delete_file


class EditWindow(tk.Toplevel):
    def __init__(self, parent, doc_id):
        super().__init__(parent)
        self.title("Редагування документа")
        self.geometry("640x820")
        self.configure(padx=30, pady=25)
        self.doc_id = doc_id

        # Завантажити типи та категорії
        self._load_types_and_categories()

        # Словники для віджетів та змінних
        self._fields = {}
        self._vars = {}

        # Побудова форми
        form = tk.Frame(self)
        form.pack(fill=tk.BOTH, expand=True)

        specs = [
            ("Назва файлу",    tk.Entry,        "filename",     {"width":44}),
            ("Напрямок",       ttk.Combobox,    "status",       {"values":["Вхідний","Вихідний"],"width":42}),
            ("Тип документа",  ttk.Combobox,    "doc_type",     {"values":list(self.types_to_categories),"width":42}),
            ("Категорія",      tk.Label,        "category",     {"width":44,"anchor":"w","fg":"blue"}),
            ("Номер",          tk.Entry,        "doc_number",   {"width":44}),
            ("Дата документа", DateEntry,       "doc_date",     {"date_pattern":"yyyy-mm-dd","width":42}),
            ("Автор",          tk.Entry,        "sender",       {"width":44}),
            ("Гриф",           ttk.Combobox,    "tags",         {"values":["НТ","ДСК","Т","ЦТ"],"width":42}),
            ("Контроль",       ttk.Checkbutton, "is_controlled",{}),
            ("Термін",         DateEntry,       "deadline",     {"date_pattern":"yyyy-mm-dd","width":42}),
            ("Опис",           tk.Text,         "description",  {"width":44,"height":6}),
        ]

        for idx, (label, ctor, name, opts) in enumerate(specs):
            tk.Label(form, text=f"{label}:").grid(row=idx, column=0, sticky="e", padx=8, pady=6)
            if ctor is tk.Text:
                w = ctor(form, **opts)
            elif ctor is tk.Label:
                w = ctor(form, **opts)
            elif ctor is ttk.Checkbutton:
                var = tk.IntVar()
                w = ctor(form, variable=var, text="Контроль", **opts)
                self._vars[name] = var
            else:
                w = ctor(form, **opts)
                if name == "doc_type":
                    w.bind("<<ComboboxSelected>>", self._update_category)
            w.grid(row=idx, column=1, sticky="w", padx=5, pady=6)
            if ctor is not ttk.Checkbutton:
                self._fields[name] = w

        form.columnconfigure(1, weight=1)

        # Кнопки
        btns = tk.Frame(self)
        btns.pack(pady=20)
        tk.Button(btns, text="Зберегти",    command=self._on_save,        width=16).pack(side="left", padx=5)
        tk.Button(btns, text="Відмінити",    command=self.destroy,         width=16).pack(side="left", padx=5)
        tk.Button(btns, text="Видалити файл",command=self._on_delete_file,width=16).pack(side="right", padx=5)

        # Завантажити дані
        self._load_existing_data()

    def _load_types_and_categories(self):
        rows = db.query("SELECT type_name, category FROM document_types")
        self.types_to_categories = {t: cat for t, cat in rows}

    def _update_category(self, event=None):
        val = self._fields["doc_type"].get().strip()
        self._fields["category"].config(text=self.types_to_categories.get(val, "Інше"))

    def _load_existing_data(self):
        row = db.query(
            "SELECT filename, status, doc_type, doc_number, doc_date, sender, tags, is_controlled, deadline, description, filepath FROM documents WHERE id=?",
            (self.doc_id,)
        )
        if not row:
            return
        filename, status, doc_type, num, date, sender, tags, ctrl, deadline, desc, filepath = row[0]
        base, ext = os.path.splitext(filename)
        # Заповнення полів
        self._fields["filename"].insert(0, base)
        self._fields["status"].set(status or "")
        self._fields["doc_type"].set(doc_type or "")
        self._update_category()
        self._fields["doc_number"].insert(0, num or "")
        self._fields["doc_date"].set_date(date)
        self._fields["sender"].insert(0, sender or "")
        self._fields["tags"].set(tags or "")
        self._vars["is_controlled"].set(ctrl)
        if ctrl and deadline:
            self._fields["deadline"].set_date(deadline)
        self._fields["description"].insert("1.0", desc or "")

        # TODO: додати додаткові номери з get_document_numbers

    def _on_save(self):
        # Перейменування файлу
        base = self._fields["filename"].get().strip()
        if base:
            old = db.query("SELECT filepath FROM documents WHERE id=?", (self.doc_id,))[0][0]
            if os.path.exists(old):
                new_name = base + os.path.splitext(old)[1]
                new_path = rename_file(old, new_name)
                db.execute("UPDATE documents SET filename=?, filepath=? WHERE id=?",
                           (new_name, new_path, self.doc_id))
        # Оновлення полів
        data = (
            self._fields["status"].get().strip(),
            self._fields["doc_type"].get().strip(),
            self._fields["doc_number"].get().strip(),
            self._fields["doc_date"].get_date().isoformat(),
            self._fields["sender"].get().strip(),
            self._fields["tags"].get().strip(),
            int(self._vars["is_controlled"].get()),
            (self._fields["deadline"].get_date().isoformat()
             if self._vars["is_controlled"].get() else None),
            self._fields["description"].get("1.0", "end-1c").strip(),
            self.doc_id
        )
        db.execute(
            "UPDATE documents SET status=?,doc_type=?,doc_number=?,doc_date=?,sender=?,tags=?,is_controlled=?,deadline=?,description=? WHERE id=?",
            data
        )
        save_document_numbers(self.doc_id, get_document_numbers(self.doc_id))
        self.destroy()
        if hasattr(self.master, "load_registry_data"):
            self.master.load_registry_data()

    def _on_delete_file(self):
        if not messagebox.askyesno("Підтвердження", "Видалити файл?" ):
            return
        db.execute("DELETE FROM document_numbers WHERE document_id=?", (self.doc_id,))
        old = db.query("SELECT filepath FROM documents WHERE id=?", (self.doc_id,))[0][0]
        db.execute("DELETE FROM documents WHERE id=?", (self.doc_id,))
        if os.path.exists(old):
            try:
                delete_file(old)
            except PermissionError:
                messagebox.showerror(
                    "Не вдалося видалити файл",
                    f"Файл `{os.path.basename(old)}` використовується іншою програмою."
                )
        self.destroy()
        if hasattr(self.master, "load_registry_data"):
            self.master.load_registry_data()
