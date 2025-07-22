# modules/detail_panel.py

import os
import shutil
import tkinter as tk
from tkinter import ttk, messagebox
from tkcalendar import DateEntry

from .database import (
    db,
    get_linked_docs,
    get_document_numbers,
    save_document_numbers
)
from .utils import rename_file, delete_file
from .context_menu import build_context_menu, open_selected
from config import DOCUMENTS_DIR


class DetailPanel(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.doc_id = None
        self.bulk_ids = None
        self.folder_rel = None
        self._is_folder_mode = False
        self._fields = {}
        self._labels = {}

        self._load_types_and_categories()

        form = tk.Frame(self)
        form.pack(fill=tk.X, padx=5, pady=5)

        specs = [
            ("Назва файлу",    tk.Entry,        "filename",      {"width":30}),
            ("Напрямок",       ttk.Combobox,    "status",        {"values":["Вхідний","Вихідний"], "width":20}),
            ("Тип документа",  ttk.Combobox,    "doc_type",      {"values":list(self.types_to_categories), "width":30}),
            ("Категорія",      tk.Label,        "category",      {"width":30,"anchor":"w","fg":"gray"}),
            ("Номер",          tk.Entry,        "doc_number",    {"width":30}),
            ("Дата",           DateEntry,       "doc_date",      {"date_pattern":"yyyy-mm-dd", "width":20}),
            ("Автор",          tk.Entry,        "sender",        {"width":30}),
            ("Гриф",           ttk.Combobox,    "tags",          {"values":["НТ","ДСК","Т","ЦТ"], "width":20}),
            ("Контроль",       ttk.Checkbutton, "is_controlled", {"text":""}),
            ("Термін",         DateEntry,       "deadline",      {"date_pattern":"yyyy-mm-dd", "width":20}),
            ("Опис",           tk.Text,         "description",   {"width":44, "height":4}),
        ]

        for r, (lbl_text, ctor, name, opts) in enumerate(specs):
            lbl = tk.Label(form, text=f"{lbl_text}:")
            lbl.grid(row=r, column=0, sticky="w", pady=2)
            self._labels[name] = lbl

            if ctor is tk.Text:
                w = ctor(form, **opts)
            elif ctor is ttk.Checkbutton:
                var = tk.IntVar()
                w = ctor(form, variable=var, **opts)
                self._fields[f"{name}_var"] = var
            else:
                w = ctor(form, **opts)
                if name == "doc_type":
                    w.bind("<<ComboboxSelected>>", self._update_category)
            w.grid(row=r, column=1, sticky="we", pady=2)
            if ctor is not ttk.Checkbutton:
                self._fields[name] = w

        form.columnconfigure(1, weight=1)

        btn_frame = tk.Frame(self)
        btn_frame.pack(fill=tk.X, pady=5)
        self.save_btn = tk.Button(btn_frame, text="Зберегти", command=self._on_save)
        self.save_btn.pack(side="left", padx=5)
        self.cancel_btn = tk.Button(btn_frame, text="Скасувати", command=self._on_cancel)
        self.cancel_btn.pack(side="left", padx=5)
        self.delete_btn = tk.Button(btn_frame, text="Видалити файл", command=self._on_delete_file)
        self.delete_btn.pack(side="right", padx=5)

        ttk.Separator(self, orient="horizontal").pack(fill="x", pady=5)

        tk.Label(self, text="Зв'язки з документами:").pack(anchor="w", padx=5)
        self.links_tree = ttk.Treeview(self, columns=("filename","link_type"), show="headings", height=6)
        self.links_tree.heading("filename",  text="Назва документа")
        self.links_tree.heading("link_type", text="Тип зв'язку")
        self.links_tree.column("filename", width=180)
        self.links_tree.column("link_type", width=120)
        self.links_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.links_tree.bind("<Button-3>", lambda e: build_context_menu(self.app, tree=self.links_tree).tk_popup(e.x_root, e.y_root))
        self.links_tree.bind("<Double-1>", self._on_link_double_click)

        self._clear_fields()

    def _load_types_and_categories(self):
        rows = db.query("SELECT type_name, category FROM document_types")
        self.types_to_categories = {t:cat for t,cat in rows}

    def _update_category(self, event=None):
        val = self._fields["doc_type"].get().strip()
        self._fields["category"].config(text=self.types_to_categories.get(val, "Інше"))

    def load_links(self, doc_id_or_list):
        self._clear_fields()
        if isinstance(doc_id_or_list, str):
            self._enter_folder_mode(doc_id_or_list)
            return
        self._exit_folder_mode()
        if isinstance(doc_id_or_list, list):
            self.bulk_ids = doc_id_or_list
            self._enter_bulk_mode(len(self.bulk_ids))
            return
        self.doc_id = doc_id_or_list
        self._exit_bulk_mode()
        self._load_document_details()
        self._populate_links()

    def _clear_fields(self):
        for name, w in self._fields.items():
            if isinstance(w, tk.Text):
                w.delete("1.0", tk.END)
            elif isinstance(w, (tk.Entry, ttk.Combobox)):
                w.delete(0, tk.END)
        for iid in self.links_tree.get_children():
            self.links_tree.delete(iid)

    def _enter_folder_mode(self, folder_rel):
        self._is_folder_mode = True
        self.folder_rel = folder_rel
        self._labels["filename"].config(text="Назва папки:")
        self._fields["filename"].delete(0, tk.END)
        self._fields["filename"].insert(0, os.path.basename(folder_rel))
        for k, w in self._fields.items():
            if k != "filename":
                try: w.config(state="disabled")
                except: pass
        self.links_tree.state(("disabled",))
        self.save_btn.config(state="disabled")
        self.cancel_btn.config(state="disabled")
        self.delete_btn.config(text="Видалити папку", command=self._on_delete_file)

    def _exit_folder_mode(self):
        if not self._is_folder_mode: return
        self._is_folder_mode = False
        self.folder_rel = None
        self._labels["filename"].config(text="Назва файлу:")
        for w in self._fields.values():
            try: w.config(state="normal")
            except: pass
        self.links_tree.state(("!disabled",))
        self.save_btn.config(text="Зберегти", state="normal", command=self._on_save)
        self.cancel_btn.config(text="Скасувати", state="normal", command=self._on_cancel)
        self.delete_btn.config(text="Видалити файл", command=self._on_delete_file)

    def _enter_bulk_mode(self, count):
        placeholder = f"({count})"
        for name, w in self._fields.items():
            if name.endswith("_var"): continue
            state = "normal" if name in ("status","doc_type","tags","sender","description") else "disabled"
            try:
                w.config(state=state)
                if state == "normal":
                    if isinstance(w, tk.Text):
                        w.delete("1.0", tk.END)
                        w.insert("1.0", f"{placeholder} файлів…")
                    else:
                        w.delete(0, tk.END)
                        w.insert(0, placeholder)
            except: pass
        self._fields["category"].config(state="disabled")

    def _exit_bulk_mode(self):
        for name, w in self._fields.items():
            if name.endswith("_var"): continue
            try: w.config(state="normal")
            except: pass

    def _load_document_details(self):
        row = db.query(
            "SELECT filename,status,doc_type,doc_number,doc_date,sender,tags,is_controlled,deadline,description FROM documents WHERE id=?",
            (self.doc_id,)
        )
        if not row: return
        filename,status,doc_type,num,date,sender,tags,ctrl,deadline,desc = row[0]
        base,_ = os.path.splitext(filename)
        self._fields["filename"].delete(0,tk.END); self._fields["filename"].insert(0,base)
        self._fields["status"].set(status or "")
        self._fields["doc_type"].set(doc_type or ""); self._update_category()
        self._fields["doc_number"].delete(0,tk.END); self._fields["doc_number"].insert(0,num or "")
        if date: self._fields["doc_date"].set_date(date)
        self._fields["sender"].delete(0,tk.END); self._fields["sender"].insert(0,sender or "")
        self._fields["tags"].set(tags or "")
        self._fields["is_controlled_var"].set(ctrl)
        if ctrl and deadline: self._fields["deadline"].set_date(deadline)
        self._fields["description"].delete("1.0",tk.END); self._fields["description"].insert("1.0",desc or "")

    def _populate_links(self):
        for iid in self.links_tree.get_children():
            self.links_tree.delete(iid)
        for oid, fn, lt in get_linked_docs(self.doc_id):
            self.links_tree.insert("", "end", iid=str(oid), values=(fn, lt))

    def _on_link_double_click(self, event):
        sel = self.links_tree.selection()
        if not sel: return
        oid = int(sel[0])
        self.app.selected_id = oid
        open_selected(self.app)

    def _on_save(self):
        if self._is_folder_mode:
            return

        try:
            ids = self.bulk_ids if self.bulk_ids else [self.doc_id]
            for did in ids:
                # Перевірка існування документа перед будь-якою дією
                row = db.query("SELECT filepath FROM documents WHERE id=?", (did,))
                if not row:
                    continue
                filepath = row[0][0]

                # У bulk-режимі не змінюємо назву файлу
                if not self.bulk_ids:
                    base = self._fields["filename"].get().strip()
                    if base and filepath:
                        if os.path.exists(filepath):
                            ext = os.path.splitext(filepath)[1]
                            new_name = base + ext
                            new_path = rename_file(filepath, new_name)
                            db.execute("UPDATE documents SET filename=?, filepath=? WHERE id=?",
                                       (new_name, new_path, did))

                params = (
                    self._fields["status"].get().strip(),
                    self._fields["doc_type"].get().strip(),
                    self._fields["doc_number"].get().strip(),
                    self._fields["doc_date"].get_date().isoformat(),
                    self._fields["sender"].get().strip(),
                    self._fields["tags"].get().strip(),
                    int(self._fields["is_controlled_var"].get()),
                    (self._fields["deadline"].get_date().isoformat()
                     if self._fields["is_controlled_var"].get() else None),
                    self._fields["description"].get("1.0", "end-1c").strip(),
                    did
                )
                db.execute(
                    "UPDATE documents SET status=?,doc_type=?,doc_number=?,doc_date=?,sender=?,tags=?,is_controlled=?,deadline=?,description=? WHERE id=?",
                    params
                )

                nums = get_document_numbers(did)
                save_document_numbers(did, nums)

        except Exception as e:
            import traceback
            traceback.print_exc()
            messagebox.showerror("Помилка", f"Не вдалося зберегти документ(и):\n{e}")
            return

        self.bulk_ids = None
        self.doc_id = None
        self.app.load_registry_data()

    def _on_cancel(self):
        if self.doc_id:
            self._load_document_details()

    def _on_delete_file(self):
        if self._is_folder_mode:
            full = os.path.join(DOCUMENTS_DIR, self.folder_rel)
            if not messagebox.askyesno("Підтвердження", f"Видалити папку та усі файли?\n{full}"):
                return
            db.execute("DELETE FROM documents WHERE folder=? OR folder LIKE ?",
                       (self.folder_rel, f"{self.folder_rel}{os.sep}%"))
            try:
                shutil.rmtree(full)
            except Exception as e:
                messagebox.showerror("Помилка", str(e))
                return
            self._exit_folder_mode()
            self.app.load_registry_data()
            messagebox.showinfo("Готово", f"Папку видалено: {full}")
        else:
            ids = self.bulk_ids or [self.doc_id]
            count = len(ids)
            if not messagebox.askyesno("Підтвердження", f"Видалити {count} файлів?" ):
                return
            with db.transaction():
                for did in ids:
                    old = db.query("SELECT filepath FROM documents WHERE id=?", (did,))[0][0]
                    db.execute("DELETE FROM document_numbers WHERE document_id=?", (did,))
                    db.execute("DELETE FROM documents WHERE id=?", (did,))
                    if os.path.exists(old):
                        try: delete_file(old)
                        except PermissionError:
                            messagebox.showerror("Помилка", f"Не вдалося видалити файл {os.path.basename(old)}")
            self.bulk_ids = None
            self.doc_id = None
            self._exit_bulk_mode()
            self.app.load_registry_data()
            messagebox.showinfo("Готово", f"Видалено {count} файлів")
