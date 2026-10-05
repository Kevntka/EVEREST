"""
Delete ALL data (every row in every table) from the app database, keeping the tables.
Run from backend/, with the venv active:

    python reset_database.py

Uses DATABASE_URL from backend/.env and asks you to type the database name to confirm.
Afterwards there are no accounts at all, so create one with:  python create_admin.py
This can't be undone; back up first if you might need the data (pg_dump).
"""

import sys

from sqlalchemy import text

from database.config import engine

engine.echo = False  # no SQL logging in the terminal


def main():
    name = engine.url.database
    with engine.connect() as conn:
        tables = [row[0] for row in conn.execute(text(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"))]
        counts = {t: conn.execute(text(f'SELECT COUNT(*) FROM "{t}"')).scalar() for t in tables}

    print("=" * 50)
    print(f"This deletes ALL data in database: {name}")
    print("=" * 50)
    for table, count in counts.items():
        print(f"  {table:<25} {count} rows")
    print()
    if input(f'Type the database name ("{name}") to delete everything: ').strip() != name:
        sys.exit("Cancelled. Nothing was deleted.")

    with engine.begin() as conn:
        # One statement so foreign keys don't get in the way; ids start again at 1
        conn.execute(text("TRUNCATE " + ", ".join(f'"{t}"' for t in tables) + " RESTART IDENTITY CASCADE"))

    print(f"Done: All data deleted from {name}. Create an admin next:  python create_admin.py")


if __name__ == "__main__":
    main()
