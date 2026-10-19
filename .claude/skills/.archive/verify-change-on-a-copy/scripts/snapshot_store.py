"""Print one line per SQLite store under ROOT: its path, a hash of its schema, and every table's row count.

Run it before and after a cleanup and diff the two outputs. A row-only cleanup changes the count lines of the
tables it touched and nothing else; a changed schema hash, or a count that moved in a table the cleanup never
writes, is a stop. Stores are opened read-only. Usage: python -I snapshot_store.py ROOT
"""
import glob
import hashlib
import sqlite3
import sys


def snapshot(path):
    db = sqlite3.connect(f'file:{path}?mode=ro', uri=True)
    try:
        schema = '\n'.join(str(row) for row in db.execute('SELECT type, name, sql FROM sqlite_master ORDER BY 1, 2'))
        tables = [row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY 1")]
        counts = {t: db.execute(f'SELECT count(*) FROM "{t}"').fetchone()[0] for t in tables}
    finally:
        db.close()
    return hashlib.sha256(schema.encode()).hexdigest()[:12], counts


def main(root):
    for path in sorted(glob.glob(f'{root}/**/*.sqlite3', recursive=True)):
        try:
            digest, counts = snapshot(path)
        except sqlite3.DatabaseError as error:
            print(path[len(root):], 'unreadable', error)
            continue
        print(path[len(root):], digest, counts)


if __name__ == '__main__':
    main(sys.argv[1])
