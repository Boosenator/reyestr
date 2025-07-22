import tkinter as tk
from tkinter import ttk, messagebox

from config import DB_PATH
from .database import db
from .utils import delete_file

LINK_TYPES = [
    "універсальний",
    "попередник",
    "наступник",
    "копія",
    "додаток",
    "довідка",
    "відповідь",
    "відсилання",
    "архів",
    "зміна",
    "скасування",
    "контрольний",
    "доручення",
    "заява/рапорт",
    "протокол/акт"
]

REVERSE_LINKS = {
    "попередник": "наступник",
    "наступник": "попередник",
    "копія": "копія",
    "додаток": "основний документ",
    "основний документ": "додаток",
    "відповідь": "запит",
    "запит": "відповідь",
    "відсилання": "відсилання",
    "архів": "актуальний",
    "актуальний": "архів",
    "зміна": "змінений",
    "змінений": "зміна",
    "скасування": "скасовується",
    "скасовується": "скасування",
    "контрольний": "контрольований",
    "контрольований": "контрольний",
    "доручення": "виконано",
    "виконано": "доручення",
    "заява/рапорт": "рекомендація",
    "рекомендація": "заява/рапорт",
    "протокол/акт": "реєстр",
    "реєстр": "протокол/акт"
}

class LinksWindow(tk.Toplevel):
    def __init__(self, parent, doc_id):
        super().__init__(parent)
        self.title(f"Зв’язки документа #{doc_id}")
        self.geometry("900x450")
        self.doc_id = int(doc_id)

        # Відкрити з’єднання з БД на весь життєвий цикл
        self._conn_ctx = db._get_connection()
        self.conn = self._conn_ctx.__enter__()
        self.cur = self.conn.cursor()

        container = tk.Frame(self)
        container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Ліва панель: всі документи
        left = tk.Frame(container)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tk.Label(left, text="Усі документи:").pack(anchor="w")
        self.search_var = tk.StringVar()
        search = ttk.Entry(left, textvariable=self.search_var)
        search.pack(fill=tk.X, pady=(0,5))
        search.bind("<KeyRelease>", lambda e: self._populate_all())

        self.all_tree = ttk.Treeview(left, columns=("id","filename"), show="headings", selectmode="extended")
        self.all_tree.heading("id", text="ID")
        self.all_tree.heading("filename", text="Назва")
        self.all_tree.column("id", width=50, anchor="center")
        self.all_tree.column("filename", width=250, anchor="w")
        self.all_tree.pack(fill=tk.BOTH, expand=True)

        # Середня панель: тип зв’язку + кнопки
        mid = tk.Frame(container)
        mid.pack(side=tk.LEFT, fill=tk.Y, padx=10)
        tk.Label(mid, text="Тип зв’язку:").pack(pady=(0,10))
        self.link_type = tk.StringVar(value=LINK_TYPES[0])
        ttk.Combobox(mid, textvariable=self.link_type, values=LINK_TYPES, state="readonly").pack(fill=tk.X)
        ttk.Button(mid, text="Додати →",   command=self._add).pack(fill=tk.X, pady=5)
        ttk.Button(mid, text="← Видалити", command=self._remove).pack(fill=tk.X, pady=5)
        ttk.Button(mid, text="Оновити всі", command=self._populate_all).pack(fill=tk.X, pady=(20,0))

        # Права панель: існуючі зв’язки
        right = tk.Frame(container)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tk.Label(right, text="Зв’язані документи:").pack(anchor="w")
        self.links_tree = ttk.Treeview(
            right, columns=("id","filename","type"), show="headings", selectmode="extended"
        )
        self.links_tree.heading("id", text="ID")
        self.links_tree.heading("filename", text="Назва")
        self.links_tree.heading("type", text="Тип зв’язку")
        self.links_tree.column("id", width=50, anchor="center")
        self.links_tree.column("filename", width=200, anchor="w")
        self.links_tree.column("type", width=120, anchor="center")
        self.links_tree.pack(fill=tk.BOTH, expand=True)

        # Ініціалізація даних
        self._populate_all()
        self._populate_links()

    def destroy(self):
        try:
            self.conn.commit()
            self._conn_ctx.__exit__(None, None, None)
        except Exception:
            pass
        super().destroy()

    def _populate_all(self):
        term = self.search_var.get().lower()
        self.all_tree.delete(*self.all_tree.get_children())
        self.cur.execute(
            "SELECT id, filename, status, doc_type, doc_number, doc_date, sender, tags, description FROM documents WHERE id!=?",
            (self.doc_id,)
        )
        for did, fn, status, typ, num, date, sender, tags, desc in self.cur.fetchall():
            flat = " ".join(filter(None, [fn, status, typ, num, date, sender, tags, desc])).lower()
            if term and term not in flat:
                continue
            self.all_tree.insert("", "end", iid=str(did), values=(did, fn))

    def _populate_links(self):
        links_map = {}
        # прямі
        self.cur.execute(
            "SELECT to_doc_id, filename, link_type FROM document_links dl JOIN documents d ON d.id=dl.to_doc_id WHERE dl.from_doc_id=?",
            (self.doc_id,)
        )
        for did, fn, lt in self.cur.fetchall():
            links_map[did] = (fn, lt)
        # зворотні
        self.cur.execute(
            "SELECT from_doc_id, filename, link_type FROM document_links dl JOIN documents d ON d.id=dl.from_doc_id WHERE dl.to_doc_id=?",
            (self.doc_id,)
        )
        for did, fn, lt in self.cur.fetchall():
            links_map[did] = (fn, lt)

        self.links_tree.delete(*self.links_tree.get_children())
        for did, (fn, lt) in links_map.items():
            self.links_tree.insert("", "end", iid=f"l{did}", values=(did, fn, lt))

    def _add(self):
        sel = self.all_tree.selection()
        if not sel:
            return
        lt  = self.link_type.get()
        rev = REVERSE_LINKS.get(lt, lt)
        to_add = [int(i) for i in sel]
        for other in to_add:
            # перевірити існування зв’язку
            self.cur.execute(
                "SELECT 1 FROM document_links WHERE (from_doc_id=? AND to_doc_id=?) OR (from_doc_id=? AND to_doc_id=?)",
                (self.doc_id, other, other, self.doc_id)
            )
            if self.cur.fetchone():
                continue
            # вставка прямого
            self.cur.execute(
                "INSERT INTO document_links (from_doc_id,to_doc_id,link_type) VALUES (?,?,?)",
                (self.doc_id, other, lt)
            )
            # вставка зворотного
            self.cur.execute(
                "INSERT INTO document_links (from_doc_id,to_doc_id,link_type) VALUES (?,?,?)",
                (other, self.doc_id, rev)
            )
        self.conn.commit()
        self._populate_links()

    def _remove(self):
        sel = self.links_tree.selection()
        if not sel:
            return
        to_remove = [int(i[1:]) for i in sel]
        for other in to_remove:
            self.cur.execute(
                "DELETE FROM document_links WHERE (from_doc_id=? AND to_doc_id=?) OR (from_doc_id=? AND to_doc_id=?)",
                (self.doc_id, other, other, self.doc_id)
            )
        self.conn.commit()
        self._populate_links()
