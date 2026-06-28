"""
Import data from local SQLite export into server database.
Usage: python3 import_data.py <server_testuser_id>
"""
import sqlite3, json, sys, os, shutil, uuid
from datetime import datetime

EXPORT_FILE = "export_data.json"
DB_PATH = "data/app.db"
DOC_DIR = "data/documents"

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 import_data.py <server_testuser_id>")
        print("Get the ID by running in python:")
        print("  import sqlite3; db=sqlite3.connect('data/app.db')")
        print("  print(db.execute('SELECT id FROM users WHERE username=\"testuser\"').fetchone()[0])")
        sys.exit(1)

    server_user_id = sys.argv[1]

    with open(EXPORT_FILE, 'r', encoding='utf-8') as f:
        export = json.load(f)

    # Build old->new user ID mapping
    old_users = export.get('users', [])
    old_to_new_user = {}
    for u in old_users:
        old_id = u['id']
        old_to_new_user[old_id] = server_user_id  # All data goes to server testuser

    print(f"User mapping: {old_to_new_user}")
    print(f"Data tables: {list(export.keys())}")

    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row

    def table_has_column(table, colname):
        cur = db.cursor()
        cur.execute(f'PRAGMA table_info({table})')
        return any(r[1] == colname for r in cur.fetchall())

    def insert_rows(table, rows, id_col='id', user_col='user_id'):
        if not rows:
            print(f"  {table}: 0 rows (skip)")
            return

        # Get table columns
        cur = db.cursor()
        cur.execute(f'PRAGMA table_info({table})')
        table_cols = [r[1] for r in cur.fetchall()]

        inserted = 0
        skipped = 0
        for row in rows:
            # Remap user_id
            if user_col and user_col in row and row[user_col] in old_to_new_user:
                row[user_col] = old_to_new_user[row[user_col]]

            # Check if already exists
            if id_col and id_col in row:
                cur.execute(f'SELECT COUNT(*) FROM {table} WHERE {id_col} = ?', (row[id_col],))
                if cur.fetchone()[0] > 0:
                    skipped += 1
                    continue

            # Filter to columns that exist in table
            valid_cols = [c for c in row.keys() if c in table_cols]
            values = [row[c] for c in valid_cols]
            placeholders = ','.join(['?'] * len(valid_cols))
            columns = ','.join(valid_cols)

            try:
                db.execute(f'INSERT OR REPLACE INTO {table} ({columns}) VALUES ({placeholders})', values)
                inserted += 1
            except Exception as e:
                print(f"  Error inserting into {table}: {e}")
                print(f"    Columns: {valid_cols}")

        db.commit()
        print(f"  {table}: {inserted} inserted, {skipped} skipped")

    # Import order (respect foreign keys)
    order = [
        'documents', 'document_chunks', 'knowledge_trees', 'knowledge_summaries',
        'outlines', 'knowledge_edges', 'question_bank', 'flashcards', 'decks',
        'exam_papers', 'study_plans', 'study_goals', 'game_levels', 'game_progress',
        'conversations', 'messages', 'review_queue', 'review_schedule', 'review_log',
        'answer_records',
    ]

    for table in order:
        if table in export:
            has_user = table_has_column(table, 'user_id')
            has_owner = table_has_column(table, 'owner_id')
            insert_rows(table, export[table],
                       user_col='user_id' if has_user else ('owner_id' if has_owner else None))

    # Import document files
    doc_dir = DOC_DIR
    os.makedirs(doc_dir, exist_ok=True)
    for doc in export.get('documents', []):
        sha = doc.get('sha256', '')
        if sha:
            src = f"uploaded_docs/{sha}"
            dst = f"{doc_dir}/{sha[:2]}/{sha}"
            if os.path.exists(src):
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
                print(f"  Copied document file: {sha[:16]}...")

    db.close()
    print("\nImport complete!")

if __name__ == '__main__':
    main()
