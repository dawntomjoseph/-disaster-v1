#!/usr/bin/env python3
"""Terminal command to view the project's SQLite DB tables.

Usage:
  python view_db.py            # print all main tables
  python view_db.py taluk      # print only `taluk` table
  python view_db.py --json     # print all tables as JSON
"""
import sqlite3
import argparse
import json
from config import DATABASE_PATH


def get_conn():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def fetch_table(conn, table):
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM {table}")
    rows = cur.fetchall()
    return [dict(r) for r in rows]


def pretty_table_print(rows):
    if not rows:
        print('(empty)')
        return
    cols = list(rows[0].keys())
    widths = [len(c) for c in cols]
    for r in rows:
        for i, c in enumerate(cols):
            widths[i] = max(widths[i], len(str(r.get(c, ''))))

    hdr = ' | '.join(c.ljust(widths[i]) for i, c in enumerate(cols))
    sep = '-+-'.join('-' * widths[i] for i in range(len(cols)))
    print(hdr)
    print(sep)
    for r in rows:
        print(' | '.join(str(r.get(c, '')).ljust(widths[i]) for i, c in enumerate(cols)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('table', nargs='?', help='table name to show (optional)')
    parser.add_argument('--json', action='store_true', help='output JSON instead of pretty tables')
    args = parser.parse_args()

    tables = ['taluk', 'taluk_contact', 'resources', 'volunteers', 'rainfall_history']

    conn = get_conn()

    if args.table:
        try:
            rows = fetch_table(conn, args.table)
        except Exception as e:
            print(f'Error reading table {args.table}:', e)
            return
        if args.json:
            print(json.dumps({args.table: rows}, indent=2))
        else:
            print(f'== {args.table} ==')
            pretty_table_print(rows)
        return

    out = {}
    for t in tables:
        try:
            rows = fetch_table(conn, t)
        except Exception:
            rows = []
        out[t] = rows

    if args.json:
        print(json.dumps(out, indent=2))
        return

    for t, rows in out.items():
        print()
        print('==', t, '==')
        pretty_table_print(rows)


if __name__ == '__main__':
    main()
