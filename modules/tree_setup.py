# modules/tree_setup.py

import os
import re
import sqlite3
from datetime import datetime
from config import DB_PATH

# Ширини колонок за замовчуванням
default_widths = {
    "filename":     250,
    "status":        60,
    "doc_type":     120,
    "doc_number":    40,
    "doc_date":      60,
    "sender":        60,
    "tags":          40,
    "is_controlled": 50,
    "deadline":      60,
    # "description" — залишаємо за замовчуванням або stretch=True
    "modified":      90,
}


def setup_tree_widget(self):
    """
    Налаштувати стовпці та заголовки Treeview.
    """
    self.columns = [
        "status", "doc_type", "doc_number", "doc_date", "sender",
        "tags", "is_controlled", "deadline", "description", "modified"
    ]
    headers = [
        "Тип руху", "Тип документа", "Номер", "Дата",
        "Автор", "Гриф", "Контроль", "Термін",
        "Опис", "Змінено"
    ]

    self.tree = self.tree_class(self, columns=self.columns, show="tree headings")
    # Колонка #0 — назва файлу
    self.tree.heading("#0", text="Назва файлу", anchor="w",
                      command=lambda: self.sort_column("filename"))
    self.tree.column("#0", width=default_widths["filename"], anchor="w")

    for col, name in zip(self.columns, headers):
        self.tree.heading(col, text=name, command=lambda c=col: self.sort_column(c))
        if col != "description":
            w = default_widths.get(col, 140)
            self.tree.column(col, width=w, anchor="w")
        else:
            self.tree.column(col, width=140, anchor="w", stretch=True)


def load_documents_into_tree(self, hierarchical=True):
    """
    Завантажити документи в дерево.
    Якщо hierarchical=True, групувати за папками (folder).
    Інакше — плоский список.
    """
    # 1) Зберегти стан відкритих вузлів
    open_nodes = set()
    def collect(n):
        if self.tree.item(n, "open"):
            open_nodes.add(n)
        for c in self.tree.get_children(n):
            collect(c)
    for rid in self.tree.get_children(""):
        collect(rid)

    # 2) Очистка treeview
    for iid in self.tree.get_children(""):
        self.tree.delete(iid)

    # 3) Зчитати дані
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT id, filename, doc_date, doc_type, doc_number,
               sender, status, tags, is_controlled, deadline,
               description, filepath, folder
          FROM documents
    """)
    docs = cur.fetchall()
    cur.execute("CREATE INDEX IF NOT EXISTS idx_num_value ON document_numbers(number_value)")
    cur.execute("SELECT document_id, number_value FROM document_numbers")
    nums = {}
    for did, val in cur.fetchall():
        nums.setdefault(did, []).append(val.lower())
    conn.close()

    # 4) Фільтрація
    term = getattr(self, 'search_term', '').lower()
    show_inc = getattr(self, 'show_incomplete', False)
    dir_f = (getattr(self, 'filter_direction', '') or '').lower()
    type_f = (getattr(self, 'filter_type', '') or '').lower()
    tags_f = (getattr(self, 'filter_tags', '') or '').lower()
    date_from = getattr(self, 'filter_date_from', '')
    date_to = getattr(self, 'filter_date_to', '')
    num_main_f = getattr(self, 'filter_num_main', '').lower()
    num_extra_f = getattr(self, 'filter_num_extra', '').lower()

    rows = []  # will hold tuples (did, name, values, ctrl, folder)
    for did, name, date, typ, num, sender, status, tags, ctrl, deadline, desc, path, folder in docs:
        vals = [
            status or '', typ or '', num or '', date or '',
            sender or '', tags or '', '✅' if ctrl else '',
            deadline or '', desc or '',
            datetime.fromtimestamp(os.path.getmtime(path)).strftime('%d-%m-%Y %H:%M')
            if os.path.exists(path) else ''
        ]
        base, _ = os.path.splitext(name)
        flat = f"{folder} {base.lower()} " + ' '.join(v.lower() for v in vals)
        extra = nums.get(did, [])
        if extra:
            flat += ' ' + ' '.join(extra)
        # пошук + фільтри
        if term and term not in flat: continue
        inc = not all((vals[1], vals[2], vals[3], vals[4], vals[8]))
        if show_inc and not inc: continue
        if dir_f and status.lower() != dir_f: continue
        if type_f and type_f not in typ.lower(): continue
        if tags_f and tags_f not in tags.lower(): continue
        if date_from and (not date or date < date_from): continue
        if date_to and (not date or date > date_to): continue
        if num_main_f and num_main_f not in num.lower(): continue
        if num_extra_f and all(num_extra_f not in ex for ex in extra): continue
        rows.append((did, name, vals, ctrl, folder))

    # 5) Сортування рядків
    def natural_key(s):
        return [int(tok) if tok.isdigit() else tok.lower()
                for tok in re.split(r'(\d+)', s)]

    if self.sort_by_col:
        def sort_key(item):
            did, name, vals, ctrl, folder = item
            col = self.sort_by_col
            if col == 'filename':
                return natural_key(name)
            idx = self.columns.index(col)
            v = vals[idx]
            if col == 'doc_number':
                try: return float(v)
                except: return v.lower()
            if col in ('doc_date','deadline'):
                try:
                    fmt = '%Y-%m-%d' if '-' in v and v.index('-')==4 else '%d-%m-%Y'
                    return datetime.strptime(v, fmt)
                except: return datetime.min
            if col=='is_controlled': return 1 if ctrl else 0
            if col=='modified':
                try: return datetime.strptime(vals[-1], '%d-%m-%Y %H:%M')
                except: return datetime.min
            return v.lower()
        rows.sort(key=sort_key, reverse=self.sort_reverse)

    # 6) Створити структуру папок + документів
    tree_map = {'subfolders': {}, 'docs': []}
    for did, name, vals, ctrl, folder in rows:
        node = tree_map
        for part in folder.split(os.sep) if folder else []:
            node = node['subfolders'].setdefault(part, {'subfolders':{}, 'docs':[]})
        node['docs'].append((did,name,vals,ctrl))

    # 7) Рекурсивна вставка з сортуванням папок та файлів
    root_id = '__ROOT__'
    self.tree.insert('', 'end', iid=root_id, text='📁 [Корінь]', open=False)
    def insert_node(node, parent):
        # папки
        for fname, subtree in sorted(node['subfolders'].items(), key=lambda x: natural_key(x[0])):
            prefix = os.path.join(parent, fname) if parent!='' else fname
            nid = f"folder::{prefix}"
            self.tree.insert(parent, 'end', iid=nid, text=fname, open=False)
            insert_node(subtree, nid)
        # файли
        for did, name, vals, ctrl in sorted(node['docs'], key=lambda x: natural_key(x[1])):
            tag = 'controlled' if ctrl else ''
            self.tree.insert(parent, 'end', iid=str(did), text=name, values=vals, tags=(tag,))
    if hierarchical:
        insert_node(tree_map, root_id)
    else:
        for did,name,vals,ctrl,folder in rows:
            tag = 'controlled' if ctrl else ''
            self.tree.insert('', 'end', iid=str(did), text=name, values=vals, tags=(tag,))

    # 8) Відновити вузли
    for n in open_nodes:
        if self.tree.exists(n): self.tree.item(n, open=True)

    # 9) Підсвітка контрольних
    self.tree.tag_configure('controlled', background='#ffe5e5')
