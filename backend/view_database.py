"""
Quick script to view database data
"""

import psycopg2
from tabulate import tabulate

# Database connection
conn = psycopg2.connect(
    host="localhost",
    database="everest_db",
    user="postgres",
    password="Kevin22melgar@"
)

def view_table(table_name):
    """View all data in a table"""
    cursor = conn.cursor()
    
    # Get column names
    cursor.execute(f"""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = '{table_name}'
        ORDER BY ordinal_position
    """)
    columns = [row[0] for row in cursor.fetchall()]
    
    # Get data
    cursor.execute(f"SELECT * FROM {table_name}")
    rows = cursor.fetchall()
    
    print(f"\n{'='*80}")
    print(f"TABLE: {table_name.upper()}")
    print(f"{'='*80}")
    print(f"Total rows: {len(rows)}\n")
    
    if rows:
        print(tabulate(rows, headers=columns, tablefmt="grid"))
    else:
        print("No data in this table")
    
    cursor.close()

def main():
    """Main function to view all important tables"""
    print("\n" + "="*80)
    print(" EVEREST DATABASE VIEWER ".center(80, "="))
    print("="*80)
    
    tables = [
        'users',
        'user_roles', 
        'departments',
        'events',
        'registrations'
    ]
    
    for table in tables:
        try:
            view_table(table)
        except Exception as e:
            print(f"\n❌ Error viewing {table}: {e}")
    
    conn.close()
    print("\n" + "="*80)
    print("Done!")
    print("="*80 + "\n")

if __name__ == "__main__":
    main()
