# src/core/database_manager.py - Complete Fixed Implementation

import sqlite3
import numpy as np
import pickle
from datetime import datetime, date
import threading
import os

class DatabaseManager:
    def __init__(self, db_path="data/factory_attendance.db"):
        self.db_path = db_path
        self.lock = threading.Lock()
        
        # Ensure the data directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        # Initialize database
        self.init_database()
        
        # Fix database schema on initialization
        self.fix_database_schema()
        
        print(f"Database initialized at: {self.db_path}")

    def init_database(self):
        """Initialize database tables with proper schema"""
        try:
            with self.lock:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                # Enable foreign keys
                cursor.execute("PRAGMA foreign_keys = ON")
                
                # Customers table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS customers (
                        customer_id TEXT PRIMARY KEY,
                        name TEXT,
                        embedding BLOB,
                        first_visit TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        total_visits INTEGER DEFAULT 0,
                        last_visit TIMESTAMP,
                        is_active BOOLEAN DEFAULT 1
                    )
                ''')
                
                # Staff table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS staff (
                        staff_id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        department TEXT,
                        embedding BLOB,
                        added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        is_active BOOLEAN DEFAULT 1
                    )
                ''')
                
                # Enhanced visits table with all required columns
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS visits (
                        visit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        customer_id TEXT,
                        visit_date DATE DEFAULT (DATE('now')),
                        visit_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        confidence REAL,
                        is_first_visit_today BOOLEAN DEFAULT 1,
                        FOREIGN KEY (customer_id) REFERENCES customers (customer_id),
                        UNIQUE(customer_id, visit_date)
                    )
                ''')
                
                # Daily visit summary table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS daily_visit_summary (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        customer_id TEXT,
                        visit_date DATE,
                        first_visit_time TIMESTAMP,
                        total_visits_today INTEGER DEFAULT 1,
                        total_visits_overall INTEGER DEFAULT 1,
                        FOREIGN KEY (customer_id) REFERENCES customers (customer_id),
                        UNIQUE(customer_id, visit_date)
                    )
                ''')
                
                # Staff detections table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS staff_detections (
                        detection_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        staff_id TEXT,
                        detection_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        confidence REAL,
                        FOREIGN KEY (staff_id) REFERENCES staff (staff_id)
                    )
                ''')
                
                # System logs table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS system_logs (
                        log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        log_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        log_level TEXT,
                        message TEXT
                    )
                ''')
                
                # Staff attendance table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS staff_attendance (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        staff_id TEXT NOT NULL,
                        date DATE NOT NULL,
                        check_in_time TIME,
                        check_out_time TIME,
                        hours_worked REAL DEFAULT 0,
                        status TEXT DEFAULT 'Present',
                        recognition_confidence REAL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (staff_id) REFERENCES staff (staff_id),
                        UNIQUE(staff_id, date)
                    )
                ''')

                # Staff check-in events table (multiple entries per day)
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS staff_checkins (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        staff_id TEXT NOT NULL,
                        date TEXT NOT NULL,
                        check_time TEXT NOT NULL,
                        status TEXT,
                        late_minutes INTEGER,
                        recognition_confidence REAL,
                        photo BLOB,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (staff_id) REFERENCES staff (staff_id)
                    )
                ''')
                
                conn.commit()
                conn.close()
                print("✅ Database tables created successfully")
                
        except Exception as e:
            print(f"❌ Database initialization error: {e}")
            raise

    def fix_database_schema(self):
        """Fix database schema by adding missing columns"""
        try:
            with self.lock:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                # Check existing columns in visits table
                cursor.execute("PRAGMA table_info(visits)")
                existing_columns = [row[1] for row in cursor.fetchall()]
                print(f"Existing columns in visits table: {existing_columns}")
                
                # Add missing columns if they don't exist
                missing_columns = [
                    ('visit_date', 'DATE DEFAULT (DATE(\'now\'))'),
                    ('visit_time', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP'),
                    ('is_first_visit_today', 'BOOLEAN DEFAULT 1')
                ]
                
                for col_name, col_def in missing_columns:
                    if col_name not in existing_columns:
                        print(f"Adding missing column: {col_name}")
                        cursor.execute(f"ALTER TABLE visits ADD COLUMN {col_name} {col_def}")
                
                # Add employee_id and photo columns to staff table
                cursor.execute("PRAGMA table_info(staff)")
                staff_columns = [row[1] for row in cursor.fetchall()]
                
                if 'employee_id' not in staff_columns:
                    print("Adding employee_id column to staff table")
                    cursor.execute("ALTER TABLE staff ADD COLUMN employee_id TEXT")
                
                if 'photo' not in staff_columns:
                    print("Adding photo column to staff table")
                    cursor.execute("ALTER TABLE staff ADD COLUMN photo BLOB")
                
                conn.commit()
                conn.close()
                print("✅ Database schema fixed successfully")
                
        except Exception as e:
            print(f"❌ Database schema fix error: {e}")

    def record_customer_visit(self, customer_id, confidence=1.0):
        """Fixed customer visit recording with proper error handling"""
        try:
            with self.lock:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                today = date.today()
                now = datetime.now()
                
                # Check if customer exists
                cursor.execute('SELECT customer_id, total_visits FROM customers WHERE customer_id = ?', (customer_id,))
                customer_result = cursor.fetchone()
                
                if not customer_result:
                    conn.close()
                    print(f"❌ Cannot record visit: customer {customer_id} not found")
                    return {'success': False, 'reason': 'customer_not_found'}
                
                current_total_visits = customer_result[1]
                
                # Check if already visited today
                cursor.execute('''
                    SELECT id, total_visits_today, total_visits_overall
                    FROM daily_visit_summary
                    WHERE customer_id = ? AND visit_date = ?
                ''', (customer_id, today))
                
                daily_result = cursor.fetchone()
                
                if daily_result:
                    conn.close()
                    return {
                        'success': False,
                        'reason': 'already_visited_today',
                        'visits_today': daily_result[1],
                        'total_visits': daily_result[2],
                        'customer_id': customer_id
                    }
                
                new_total_visits = current_total_visits + 1
                
                # **FIXED: Use try-catch for insert with fallback**
                try:
                    # Try with all columns first
                    cursor.execute('''
                        INSERT INTO visits (customer_id, visit_date, visit_time, confidence, is_first_visit_today)
                        VALUES (?, ?, ?, ?, 1)
                    ''', (customer_id, today, now, confidence))
                except sqlite3.OperationalError as e:
                    if "no column named" in str(e):
                        # Fallback: insert with basic columns only
                        print("⚠️ Using fallback insert method for visits table")
                        cursor.execute('''
                            INSERT INTO visits (customer_id, confidence)
                            VALUES (?, ?)
                        ''', (customer_id, confidence))
                    else:
                        raise e
                
                # Insert daily summary
                cursor.execute('''
                    INSERT INTO daily_visit_summary
                    (customer_id, visit_date, first_visit_time, total_visits_today, total_visits_overall)
                    VALUES (?, ?, ?, 1, ?)
                ''', (customer_id, today, now, new_total_visits))
                
                # Update customer total visits
                cursor.execute('''
                    UPDATE customers
                    SET total_visits = ?, last_visit = ?
                    WHERE customer_id = ?
                ''', (new_total_visits, now, customer_id))
                
                conn.commit()
                conn.close()
                
                print(f"✅ Customer visit recorded successfully: {customer_id}")
                
                return {
                    'success': True,
                    'reason': 'visit_recorded',
                    'visits_today': 1,
                    'total_visits': new_total_visits,
                    'customer_id': customer_id,
                    'is_new_visit': True
                }
                
        except Exception as e:
            print(f"❌ Error recording customer visit: {e}")
            return {'success': False, 'reason': f'database_error: {e}'}

    def check_daily_visit_status(self, customer_id):
        """Check if customer already visited today and get visit statistics"""
        try:
            with self.lock:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                today = date.today()
                
                cursor.execute('''
                    SELECT
                        dvs.total_visits_today,
                        dvs.total_visits_overall,
                        dvs.first_visit_time,
                        c.total_visits as customer_total_visits
                    FROM daily_visit_summary dvs
                    JOIN customers c ON dvs.customer_id = c.customer_id
                    WHERE dvs.customer_id = ? AND dvs.visit_date = ?
                ''', (customer_id, today))
                
                result = cursor.fetchone()
                
                if result:
                    conn.close()
                    return {
                        'visited_today': True,
                        'visits_today': result[0],
                        'total_visits': result[1],
                        'first_visit_time': result[2],
                        'customer_total_visits': result[3]
                    }
                
                # Get total visits from customers table if no daily record
                cursor.execute('SELECT total_visits FROM customers WHERE customer_id = ?', (customer_id,))
                total_result = cursor.fetchone()
                conn.close()
                
                total = total_result[0] if total_result else 0
                
                return {
                    'visited_today': False,
                    'visits_today': 0,
                    'total_visits': total,
                    'first_visit_time': None,
                    'customer_total_visits': total
                }
                
        except Exception as e:
            print(f"❌ Error checking daily visit status: {e}")
            return {
                'visited_today': False,
                'visits_today': 0,
                'total_visits': 0,
                'first_visit_time': None,
                'customer_total_visits': 0
            }

    def register_new_customer(self, embedding, image=None):
        """Register a new customer with proper embedding storage"""
        try:
            with self.lock:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                # Generate customer ID
                cursor.execute("SELECT COUNT(*) FROM customers")
                count = cursor.fetchone()[0]
                customer_id = f"CUST_{count + 1:06d}"
                
                # Store embedding with dtype and shape preserved
                embedding_blob = pickle.dumps(embedding.astype(np.float32)) if embedding is not None else None
                
                cursor.execute('''
                    INSERT INTO customers (customer_id, embedding, total_visits)
                    VALUES (?, ?, 0)
                ''', (customer_id, embedding_blob))
                
                conn.commit()
                conn.close()
                
                print(f"✅ New customer registered: {customer_id}")
                return customer_id
                
        except Exception as e:
            print(f"❌ Error registering customer: {e}")
            return None

    def add_staff_member(self, staff_id, name, department, embedding, image=None):
        """Add a staff member with proper embedding storage"""
        try:
            with self.lock:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                # Store embedding properly
                embedding_blob = pickle.dumps(embedding.astype(np.float32)) if embedding is not None else None
                
                cursor.execute('''
                    INSERT OR REPLACE INTO staff (staff_id, name, department, embedding)
                    VALUES (?, ?, ?, ?)
                ''', (staff_id, name, department, embedding_blob))
                
                conn.commit()
                conn.close()
                
                print(f"✅ Staff member added: {staff_id} - {name}")
                return True
                
        except Exception as e:
            print(f"❌ Error adding staff member: {e}")
            return False

    def load_customers(self):
        """Load all active customers and their embeddings"""
        try:
            with self.lock:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                cursor.execute("SELECT customer_id, embedding FROM customers WHERE is_active = 1 AND embedding IS NOT NULL")
                customers = []
                
                for row in cursor.fetchall():
                    customer_id, embedding_blob = row
                    try:
                        embedding = pickle.loads(embedding_blob)
                        customers.append({'id': customer_id, 'embedding': embedding})
                    except Exception as e:
                        print(f"⚠️ Error loading embedding for customer {customer_id}: {e}")
                        continue
                
                conn.close()
                print(f"✅ Loaded {len(customers)} customers")
                return customers
                
        except Exception as e:
            print(f"❌ Error loading customers: {e}")
            return []

    def load_staff(self):
        """Load all active staff and their embeddings - FIXED"""
        try:
            with self.lock:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT staff_id, embedding FROM staff WHERE is_active = 1 AND embedding IS NOT NULL")
                
                staff = []
                for row in cursor.fetchall():
                    staff_id, embedding_blob = row
                    try:
                        if embedding_blob:
                            # FIXED: Use pickle.loads consistently
                            embedding = pickle.loads(embedding_blob)
                            if isinstance(embedding, np.ndarray) and embedding.size > 0:
                                staff.append({'id': staff_id, 'embedding': embedding})
                    except Exception as e:
                        print(f"⚠️ Embedding error for {staff_id}: {e}")
                        continue
                
                conn.close()
                print(f"✅ Loaded {len(staff)} staff members")
                return staff
                
        except Exception as e:
            print(f"❌ Error loading staff: {e}")
            return []


    def get_all_customers(self):
        """Get all customers with detailed information"""
        try:
            with self.lock:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT customer_id, name, embedding, first_visit, total_visits, last_visit
                    FROM customers WHERE is_active = 1
                ''')
                
                customers = []
                for row in cursor.fetchall():
                    customers.append({
                        'customer_id': row[0],
                        'name': row[1],
                        'embedding': row[2],
                        'first_visit': row[3],
                        'total_visits': row[4],
                        'last_visit': row[5]
                    })
                
                conn.close()
                return customers
                
        except Exception as e:
            print(f"❌ Error getting customers: {e}")
            return []

    def get_all_staff(self):
        """Get all staff members with detailed information"""
        try:
            with self.lock:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT staff_id, name, department, embedding, added_date, employee_id, photo
                    FROM staff WHERE is_active = 1
                ''')
                
                staff_members = []
                for row in cursor.fetchall():
                    staff_members.append({
                        'staff_id': row[0],
                        'name': row[1],
                        'department': row[2],
                        'embedding': row[3],
                        'added_date': row[4],
                        'employee_id': row[5] if len(row) > 5 else None,
                        'photo': row[6] if len(row) > 6 else None
                    })
                
                conn.close()
                return staff_members
                
        except Exception as e:
            print(f"❌ Error getting staff: {e}")
            return []

    def get_customer_info(self, customer_id):
        """Get customer information"""
        try:
            with self.lock:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT customer_id, name, total_visits, last_visit
                    FROM customers WHERE customer_id = ?
                ''', (customer_id,))
                
                row = cursor.fetchone()
                conn.close()
                
                if row:
                    return {
                        'customer_id': row[0],
                        'name': row[1],
                        'total_visits': row[2],
                        'last_visit': row[3]
                    }
                return None
                
        except Exception as e:
            print(f"❌ Error getting customer info: {e}")
            return None

    def get_staff_info(self, staff_id):
        """Get staff information"""
        try:
            with self.lock:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT staff_id, name, department
                    FROM staff WHERE staff_id = ?
                ''', (staff_id,))
                
                row = cursor.fetchone()
                conn.close()
                
                if row:
                    return {
                        'staff_id': row[0],
                        'name': row[1],
                        'department': row[2]
                    }
                return None
                
        except Exception as e:
            print(f"❌ Error getting staff info: {e}")
            return None

    def record_staff_detection(self, staff_id, confidence=1.0):
        """Record a staff detection"""
        try:
            with self.lock:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT INTO staff_detections (staff_id, confidence)
                    VALUES (?, ?)
                ''', (staff_id, confidence))
                
                conn.commit()
                conn.close()
                return True
                
        except Exception as e:
            print(f"❌ Error recording staff detection: {e}")
            return False

    def record_staff_attendance(self, staff_id, attendance_type='check_in', confidence=1.0):
        """Record staff check-in or check-out and return status information"""
        try:
            # Normalize types to avoid SQLite binding errors
            staff_id = str(staff_id) if staff_id is not None else ''
            confidence = float(confidence) if confidence is not None else 1.0
            
            with self.lock:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                current_date = date.today()
                current_time = datetime.now().time()
                time_str = current_time.strftime('%H:%M:%S')
                date_str = current_date.isoformat()
                already_checked_in = False
                
                if attendance_type == 'check_in':
                    # Check if already checked in today
                    cursor.execute(
                        "SELECT id FROM staff_attendance WHERE staff_id = ? AND date = ?",
                        (staff_id, current_date)
                    )
                    existing = cursor.fetchone()
                    
                    if existing:
                        already_checked_in = True
                        # Update existing record
                        cursor.execute('''
                            UPDATE staff_attendance
                            SET check_in_time = ?, recognition_confidence = ?
                            WHERE staff_id = ? AND date = ?
                        ''', (time_str, confidence, staff_id, date_str))
                    else:
                        # Insert new record
                        status = 'Late' if current_time > datetime.strptime('09:00:00', '%H:%M:%S').time() else 'Present'
                        cursor.execute('''
                            INSERT INTO staff_attendance (staff_id, date, check_in_time, status, recognition_confidence)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (staff_id, date_str, time_str, status, confidence))

                # Persist check-in event (always for attendance recording)
                if attendance_type == 'check_in':
                    late_minutes = max(0, int((datetime.combine(current_date, current_time) - datetime.combine(current_date, datetime.strptime('09:00:00', '%H:%M:%S').time())).total_seconds() // 60))
                    status_label = 'Late' if late_minutes > 0 else 'Present'
                    # Insert event row (photo optional; stored separately)
                    cursor.execute('''
                        INSERT INTO staff_checkins (staff_id, date, check_time, status, late_minutes, recognition_confidence, photo)
                        VALUES (?, ?, ?, ?, ?, ?, NULL)
                    ''', (staff_id, date_str, time_str, status_label, late_minutes, confidence))
                
                elif attendance_type == 'check_out':
                    # Update check-out time and calculate hours
                    cursor.execute('''
                        UPDATE staff_attendance
                        SET check_out_time = ?,
                            hours_worked = CASE
                                WHEN check_in_time IS NOT NULL THEN
                                    (julianday(date || ' ' || ?) - julianday(date || ' ' || check_in_time)) * 24
                                ELSE 0
                            END
                        WHERE staff_id = ? AND date = ?
                    ''', (time_str, time_str, staff_id, date_str))
                    
                    # If no existing record (rowcount == 0), insert a minimal record for checkout
                    if cursor.rowcount == 0:
                        cursor.execute('''
                            INSERT INTO staff_attendance (staff_id, date, check_out_time, status, recognition_confidence)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (staff_id, date_str, time_str, 'Present', confidence))
                
                # Get total visits for staff member
                cursor.execute(
                    "SELECT COUNT(*) FROM staff_attendance WHERE staff_id = ?",
                    (staff_id,)
                )
                total_visits = cursor.fetchone()[0]
                
                conn.commit()
                conn.close()
                
                return {
                    'success': True,
                    'already_checked_in': already_checked_in,
                    'total_visits': total_visits
                }
                
        except Exception as e:
            print(f"❌ Error recording staff attendance: {e}")
            return {'success': False, 'already_checked_in': False, 'total_visits': 0}

    def get_today_visit_stats(self):
        """Get today's visit statistics"""
        try:
            with self.lock:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                today = date.today()
                
                # Unique visitors today
                cursor.execute('''
                    SELECT COUNT(DISTINCT customer_id)
                    FROM daily_visit_summary
                    WHERE visit_date = ?
                ''', (today,))
                unique_visitors_today = cursor.fetchone()[0]
                
                # Total visits today
                cursor.execute('''
                    SELECT SUM(total_visits_today)
                    FROM daily_visit_summary
                    WHERE visit_date = ?
                ''', (today,))
                total_visits_today = cursor.fetchone()[0] or 0
                
                # New customers today
                cursor.execute('''
                    SELECT COUNT(*)
                    FROM customers
                    WHERE DATE(first_visit) = ?
                ''', (today,))
                new_customers_today = cursor.fetchone()[0]
                
                returning_customers_today = unique_visitors_today - new_customers_today
                
                conn.close()
                
                return {
                    'unique_visitors_today': unique_visitors_today,
                    'total_visits_today': total_visits_today,
                    'new_customers_today': new_customers_today,
                    'returning_customers_today': max(0, returning_customers_today)
                }
                
        except Exception as e:
            print(f"❌ Error getting today's visit stats: {e}")
            return {
                'unique_visitors_today': 0,
                'total_visits_today': 0,
                'new_customers_today': 0,
                'returning_customers_today': 0
            }

    def get_monthly_statistics(self, year, month):
        """Get monthly statistics"""
        try:
            with self.lock:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                # Total visits in month
                cursor.execute('''
                    SELECT COUNT(*) FROM visits
                    WHERE strftime('%Y', visit_time) = ? AND strftime('%m', visit_time) = ?
                ''', (str(year), f"{month:02d}"))
                total_visits = cursor.fetchone()[0]
                
                # Unique customers in month
                cursor.execute('''
                    SELECT COUNT(DISTINCT customer_id) FROM visits
                    WHERE strftime('%Y', visit_time) = ? AND strftime('%m', visit_time) = ?
                ''', (str(year), f"{month:02d}"))
                unique_customers = cursor.fetchone()[0]
                
                # New customers in month
                cursor.execute('''
                    SELECT COUNT(*) FROM customers
                    WHERE strftime('%Y', first_visit) = ? AND strftime('%m', first_visit) = ?
                ''', (str(year), f"{month:02d}"))
                new_customers = cursor.fetchone()[0]
                
                conn.close()
                
                return {
                    'total_visits': total_visits,
                    'unique_customers': unique_customers,
                    'new_customers': new_customers,
                    'avg_visits_per_day': total_visits / 30.0,
                    'daily_breakdown': []
                }
                
        except Exception as e:
            print(f"❌ Error getting monthly statistics: {e}")
            return {
                'total_visits': 0,
                'unique_customers': 0,
                'new_customers': 0,
                'avg_visits_per_day': 0.0,
                'daily_breakdown': []
            }

    def delete_staff_member(self, staff_id):
        """Delete a staff member"""
        try:
            with self.lock:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                cursor.execute("DELETE FROM staff WHERE staff_id = ?", (staff_id,))
                
                conn.commit()
                conn.close()
                
                print(f"✅ Staff member deleted: {staff_id}")
                return True
                
        except Exception as e:
            print(f"❌ Error deleting staff member: {e}")
            return False

    def reset_recognition_data(self):
        """Reset all recognition data while keeping system structure"""
        try:
            # Create backup first
            import shutil
            backup_path = f"{self.db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            shutil.copy2(self.db_path, backup_path)
            print(f"✅ Backup created: {backup_path}")
            
            # Tables to reset (keep structure, clear data)
            tables_to_reset = [
                'customers',
                'visits',
                'staff_detections',
                'staff_attendance',
                'daily_visit_summary'
            ]
            
            with self.lock:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                # Disable foreign key constraints temporarily
                cursor.execute('PRAGMA foreign_keys = OFF')
                
                for table in tables_to_reset:
                    try:
                        # Clear all data
                        cursor.execute(f'DELETE FROM {table}')
                        # Reset auto-increment
                        cursor.execute(f'DELETE FROM sqlite_sequence WHERE name = ?', (table,))
                        print(f"✅ Reset table: {table}")
                    except sqlite3.OperationalError as e:
                        if "no such table" not in str(e).lower():
                            print(f"⚠️ Could not reset {table}: {e}")
                
                # Re-enable foreign key constraints
                cursor.execute('PRAGMA foreign_keys = ON')
                
                conn.commit()
                conn.close()
                
            print("🎉 Recognition data reset successfully!")
            return True
            
        except Exception as e:
            print(f"❌ Database reset failed: {e}")
            return False

    def test_database_connection(self):
        """Test database connection and tables"""
        try:
            with self.lock:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                # Check if tables exist
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = cursor.fetchall()
                print(f"Database tables: {[table[0] for table in tables]}")
                
                # Check customer count
                cursor.execute("SELECT COUNT(*) FROM customers")
                customer_count = cursor.fetchone()[0]
                
                # Check staff count
                cursor.execute("SELECT COUNT(*) FROM staff")
                staff_count = cursor.fetchone()[0]
                
                # Check visits count
                cursor.execute("SELECT COUNT(*) FROM visits")
                visits_count = cursor.fetchone()[0]
                
                print(f"Database Stats - Customers: {customer_count}, Staff: {staff_count}, Visits: {visits_count}")
                
                conn.close()
                return True
                
        except Exception as e:
            print(f"❌ Database test failed: {e}")
            return False

    def get_database_stats(self):
        """Get current database statistics"""
        try:
            stats = {}
            tables = ['customers', 'visits', 'staff_detections', 'staff', 'staff_attendance', 'daily_visit_summary']
            
            with self.lock:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                for table in tables:
                    try:
                        cursor.execute(f'SELECT COUNT(*) FROM {table}')
                        count = cursor.fetchone()[0]
                        stats[table] = count
                    except sqlite3.OperationalError:
                        stats[table] = 'Table not found'
                
                conn.close()
                
            return stats
            
        except Exception as e:
            print(f"❌ Error getting database stats: {e}")
            return {}

    def execute_query(self, query, params=None, fetch=False):
        """Execute SQL query with proper error handling"""
        try:
            with self.lock:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)
                
                if fetch:
                    result = cursor.fetchall()
                    conn.close()
                    return result
                else:
                    conn.commit()
                    conn.close()
                    return True
                    
        except Exception as e:
            print(f"❌ Database query error: {e}")
            if 'conn' in locals():
                conn.close()
            return False if not fetch else []

    # Compatibility methods
    def record_visit(self, customer_id, confidence=1.0):
        """Compatibility wrapper for record_customer_visit"""
        result = self.record_customer_visit(customer_id, confidence)
        if result.get('success'):
            return True, result.get('total_visits', 0)
        return False, result.get('total_visits', 0)

    def is_new_visit_today(self, customer_id):
        """Check if this is a new visit today"""
        visit_status = self.check_daily_visit_status(customer_id)
        return not visit_status['visited_today']
    
    def get_today_attendance(self, target_date=None):
        """Get today's attendance records"""
        try:
            with self.lock:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                if target_date is None:
                    target_date = date.today()
                
                cursor.execute('''
                    SELECT staff_id, date, check_in_time, check_out_time, status, recognition_confidence
                    FROM staff_attendance
                    WHERE date = ?
                    ORDER BY check_in_time
                ''', (target_date,))
                
                records = []
                for row in cursor.fetchall():
                    records.append({
                        'staff_id': row[0],
                        'date': row[1],
                        'check_in_time': datetime.strptime(f"{row[1]} {row[2]}", "%Y-%m-%d %H:%M:%S") if row[2] else None,
                        'check_out_time': datetime.strptime(f"{row[1]} {row[3]}", "%Y-%m-%d %H:%M:%S") if row[3] else None,
                        'status': row[4],
                        'confidence': row[5]
                    })

                # Also load today check-in events
                cursor.execute('''
                    SELECT staff_id, date, check_time, status, late_minutes, recognition_confidence
                    FROM staff_checkins
                    WHERE date = ?
                    ORDER BY check_time DESC
                ''', (target_date.isoformat() if isinstance(target_date, date) else target_date,))

                checkins = []
                for row in cursor.fetchall():
                    checkins.append({
                        'staff_id': row[0],
                        'date': row[1],
                        'check_time': row[2],
                        'status': row[3],
                        'late_minutes': row[4],
                        'confidence': row[5]
                    })
                
                conn.close()
                return {'attendance': records, 'checkins': checkins}
                
        except Exception as e:
            print(f"❌ Error getting today's attendance: {e}")
            return []
    
    def update_staff_employee_id(self, staff_id, employee_id):
        """Update employee ID for staff member"""
        try:
            with self.lock:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                cursor.execute('''
                    UPDATE staff SET employee_id = ? WHERE staff_id = ?
                ''', (employee_id, staff_id))
                
                conn.commit()
                conn.close()
                return True
                
        except Exception as e:
            print(f"❌ Error updating employee ID: {e}")
            return False
    
    def update_staff_photo(self, staff_id, photo_data):
        """Update photo for staff member"""
        try:
            import cv2
            with self.lock:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                # Convert image to bytes
                if isinstance(photo_data, np.ndarray):
                    success, buffer = cv2.imencode('.jpg', photo_data)
                    if success:
                        photo_blob = buffer.tobytes()
                        cursor.execute('''
                            UPDATE staff SET photo = ? WHERE staff_id = ?
                        ''', (photo_blob, staff_id))
                        conn.commit()
                        conn.close()
                        return True
                
                conn.close()
                return False
                
        except Exception as e:
            print(f"❌ Error updating staff photo: {e}")
            return False
    
    def get_staff_photo(self, staff_id):
        """Get staff photo"""
        try:
            import cv2
            with self.lock:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                cursor.execute('SELECT photo FROM staff WHERE staff_id = ?', (staff_id,))
                row = cursor.fetchone()
                conn.close()
                
                if row and row[0]:
                    # Convert bytes back to image
                    nparr = np.frombuffer(row[0], np.uint8)
                    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                    return img if img is not None else None
                
                return None
                
        except Exception as e:
            print(f"❌ Error getting staff photo: {e}")
            return None

# Test the database manager if run directly
if __name__ == "__main__":
    print("🧪 Testing Database Manager...")
    db = DatabaseManager()
    
    # Test connection
    if db.test_database_connection():
        print("✅ Database connection test passed")
        
        # Test stats
        stats = db.get_database_stats()
        print(f"📊 Database statistics: {stats}")
        
        # Test customer registration
        test_embedding = np.random.rand(512).astype(np.float32)
        customer_id = db.register_new_customer(test_embedding)
        if customer_id:
            print(f"✅ Test customer registered: {customer_id}")
            
            # Test visit recording
            result = db.record_customer_visit(customer_id, 0.95)
            if result['success']:
                print(f"✅ Test visit recorded successfully")
            else:
                print(f"⚠️ Visit recording result: {result}")
        
        print("🎉 All tests completed!")
    else:
        print("❌ Database connection test failed")
