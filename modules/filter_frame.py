import tkinter as tk
from tkinter import ttk
from tkcalendar import DateEntry

class FilterFrame(tk.Frame):
    def __init__(self, parent, on_filter_callback, doc_types, griffes):
        super().__init__(parent)
        self.on_filter_callback = on_filter_callback

        # Змінні фільтрів
        self.search_var       = tk.StringVar()
        self.incomplete_var   = tk.BooleanVar()
        self.direction_var    = tk.StringVar(value="Усі")
        self.type_var         = tk.StringVar(value="Усі")
        self.griff_var        = tk.StringVar(value="Усі")
        self.date_from_var    = tk.StringVar()
        self.date_to_var      = tk.StringVar()
        self.num_main_var     = tk.StringVar()
        self.num_extra_var    = tk.StringVar()

        # Пошук
        tk.Label(self, text="Пошук:").pack(side=tk.LEFT, padx=(5,2))
        self.search_entry = tk.Entry(self, textvariable=self.search_var, width=15)
        self.search_entry.pack(side=tk.LEFT, padx=(0,5))
        self.search_entry.bind("<Return>", self._trigger_filter)

        # Основний номер
        tk.Label(self, text="Номер:").pack(side=tk.LEFT, padx=(10,2))
        self.num_main_entry = tk.Entry(self, textvariable=self.num_main_var, width=10)
        self.num_main_entry.pack(side=tk.LEFT, padx=(0,5))
        self.num_main_entry.bind("<Return>", self._trigger_filter)

        # Додатковий номер
        tk.Label(self, text="Дод. №:").pack(side=tk.LEFT, padx=(10,2))
        self.num_extra_entry = tk.Entry(self, textvariable=self.num_extra_var, width=10)
        self.num_extra_entry.pack(side=tk.LEFT, padx=(0,5))
        self.num_extra_entry.bind("<Return>", self._trigger_filter)

        # Інші поля
        tk.Label(self, text="Рух:").pack(side=tk.LEFT, padx=(10,2))
        self.direction_cb = ttk.Combobox(self, textvariable=self.direction_var,
                                         values=["Усі","Вхідний","Вихідний"], width=10, state="readonly")
        self.direction_cb.pack(side=tk.LEFT, padx=(0,5))
        self.direction_cb.bind("<<ComboboxSelected>>", self._trigger_filter)

        tk.Label(self, text="Тип:").pack(side=tk.LEFT, padx=(10,2))
        self.type_cb = ttk.Combobox(self, textvariable=self.type_var,
                                    values=["Усі"]+doc_types, width=15, state="readonly")
        self.type_cb.pack(side=tk.LEFT, padx=(0,5))
        self.type_cb.bind("<<ComboboxSelected>>", self._trigger_filter)

        tk.Label(self, text="Гриф:").pack(side=tk.LEFT, padx=(10,2))
        self.griff_cb = ttk.Combobox(self, textvariable=self.griff_var,
                                     values=["Усі"]+griffes, width=8, state="readonly")
        self.griff_cb.pack(side=tk.LEFT, padx=(0,5))
        self.griff_cb.bind("<<ComboboxSelected>>", self._trigger_filter)

        tk.Label(self, text="Від:").pack(side=tk.LEFT, padx=(10,2))
        self.date_from = DateEntry(self, textvariable=self.date_from_var,
                                   width=10, date_pattern="yyyy-mm-dd")
        self.date_from.delete(0, tk.END)
        self.date_from._top_cal.overrideredirect(1)  # suppress calendar window warnings
        self.date_from.pack(side=tk.LEFT, padx=(0,5))
        self.date_from.bind("<<DateEntrySelected>>", self._trigger_filter)

        tk.Label(self, text="до:").pack(side=tk.LEFT, padx=(5,2))
        self.date_to = DateEntry(self, textvariable=self.date_to_var,
                                 width=10, date_pattern="yyyy-mm-dd")
        self.date_to.delete(0, tk.END)
        self.date_to._top_cal.overrideredirect(1)
        self.date_to.pack(side=tk.LEFT, padx=(0,5))
        self.date_to.bind("<<DateEntrySelected>>", self._trigger_filter)

        self.incomplete_check = tk.Checkbutton(
            self, text="Недопрацьовані", variable=self.incomplete_var,
            command=self._trigger_filter
        )
        self.incomplete_check.pack(side=tk.LEFT, padx=(10,0))

        self.search_btn = ttk.Button(self, text="🔍", command=self._trigger_filter)
        self.search_btn.pack(side=tk.LEFT, padx=(10,2))
        self.reset_btn  = ttk.Button(self, text="Скинути", command=self._reset_filters)
        self.reset_btn.pack(side=tk.LEFT, padx=(5,2))

    def _trigger_filter(self, event=None):
        self.on_filter_callback(
            search_text     = self.search_var.get(),
            show_incomplete = self.incomplete_var.get(),
            direction       = self.direction_var.get(),
            doc_type        = self.type_var.get(),
            griff           = self.griff_var.get(),
            date_from       = self.date_from_var.get(),
            date_to         = self.date_to_var.get(),
            num_main        = self.num_main_var.get(),
            num_extra       = self.num_extra_var.get()
        )

    def _reset_filters(self):
        for var in (self.search_var, self.incomplete_var,
                    self.direction_var, self.type_var, self.griff_var,
                    self.date_from_var, self.date_to_var,
                    self.num_main_var, self.num_extra_var):
            var.set("" if isinstance(var, tk.StringVar) else False)
        self.direction_var.set("Усі")
        self.type_var.set("Усі")
        self.griff_var.set("Усі")
        self._trigger_filter()