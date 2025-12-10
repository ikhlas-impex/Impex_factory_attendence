# fix_database.py - Run this once to fix your database
import sqlite3
import os

def fix_visits_table():
    db_path = "data/hotel_recognition.db"
    
    if not os.path.exists(db_path):
        print("❌ Database file not found")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check existing columns
        cursor.execute("PRAGMA table_info(visits)")
        columns = [row[1] for row in cursor.fetchall()]
        print(f"Current columns: {columns}")
        
        # Add missing columns
        missing_columns = [
            ('visit_date', 'DATE DEFAULT (DATE(\'now\'))'),
            ('visit_time', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP'),
            ('is_first_visit_today', 'BOOLEAN DEFAULT 1')
        ]
        
        for col_name, col_def in missing_columns:
            if col_name not in columns:
                print(f"Adding column: {col_name}")
                cursor.execute(f"ALTER TABLE visits ADD COLUMN {col_name} {col_def}")
        
        conn.commit()
        conn.close()
        print("✅ Database fixed successfully!")
        
    except Exception as e:
        print(f"❌ Error fixing database: {e}")

if __name__ == "__main__":
    fix_visits_table()
