from modules.database import init_db, populate_initial_types
from modules.scanner import insert_new_files
from modules.ui import DocumentApp

def main():
    init_db()
    insert_new_files()
    populate_initial_types()
    app = DocumentApp()
    app.mainloop()

if __name__ == "__main__":
    main()