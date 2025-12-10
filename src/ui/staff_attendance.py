import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, date, timedelta
import pandas as pd
from core.database_manager import DatabaseManager


class StaffAttendanceWindow:
    def __init__(self, parent):
        self.parent = parent
        self.db_manager = DatabaseManager()

        self.window = tk.Toplevel(parent)
        self.window.title("Elkitch Factory - Staff Attendance Management")
        self.window.geometry("1200x800")
        self.window.transient(parent)

        self.setup_gui()
        self.load_attendance_data()

    def setup_gui(self):
        # Main notebook for tabs
        notebook = ttk.Notebook(self.window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Tab 1: Daily Attendance
        self.daily_tab = ttk.Frame(notebook)
        notebook.add(self.daily_tab, text="📅 Daily Attendance")
        self.setup_daily_tab()

        # Tab 2: Attendance Reports
        self.reports_tab = ttk.Frame(notebook)
        notebook.add(self.reports_tab, text="📊 Attendance Reports")
        self.setup_reports_tab()

        # Tab 3: Staff Performance
        self.performance_tab = ttk.Frame(notebook)
        notebook.add(self.performance_tab, text="⭐ Staff Performance")
        self.setup_performance_tab()

    def setup_daily_tab(self):
        """Setup daily attendance tracking tab"""
        # Control frame
        control_frame = ttk.LabelFrame(self.daily_tab, text="Daily Attendance Controls", padding=10)
        control_frame.pack(fill=tk.X, padx=5, pady=5)

        # Date selection
        ttk.Label(control_frame, text="Select Date:").pack(side=tk.LEFT, padx=5)
        self.date_var = tk.StringVar(value=date.today().strftime('%Y-%m-%d'))
        date_entry = ttk.Entry(control_frame, textvariable=self.date_var, width=12)
        date_entry.pack(side=tk.LEFT, padx=5)

        ttk.Button(control_frame, text="🔍 Load Attendance",
                   command=self.load_daily_attendance).pack(side=tk.LEFT, padx=10)

        ttk.Button(control_frame, text="📊 Generate Report",
                   command=self.generate_daily_report).pack(side=tk.LEFT, padx=5)

        ttk.Button(control_frame, text="📤 Export to Excel",
                   command=self.export_attendance).pack(side=tk.LEFT, padx=5)

        # Attendance list frame
        list_frame = ttk.LabelFrame(self.daily_tab, text="Staff Attendance Records", padding=5)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Attendance treeview
        columns = ('Staff ID', 'Name', 'Department', 'Check In', 'Check Out', 'Hours Worked', 'Status')
        self.attendance_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=20)

        # Configure columns
        column_widths = {'Staff ID': 100, 'Name': 150, 'Department': 120,
                         'Check In': 120, 'Check Out': 120, 'Hours Worked': 100, 'Status': 100}

        for col in columns:
            self.attendance_tree.heading(col, text=col)
            self.attendance_tree.column(col, width=column_widths.get(col, 100))

        # Scrollbars
        v_scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.attendance_tree.yview)
        h_scrollbar = ttk.Scrollbar(list_frame, orient=tk.HORIZONTAL, command=self.attendance_tree.xview)
        self.attendance_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        # Pack treeview and scrollbars
        self.attendance_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)

        # Statistics frame
        stats_frame = ttk.LabelFrame(self.daily_tab, text="Daily Statistics", padding=10)
        stats_frame.pack(fill=tk.X, padx=5, pady=5)

        self.total_staff_label = ttk.Label(stats_frame, text="Total Staff: 0", font=('Arial', 10, 'bold'))
        self.total_staff_label.pack(side=tk.LEFT, padx=20)

        self.present_label = ttk.Label(stats_frame, text="Present: 0", font=('Arial', 10, 'bold'), foreground='green')
        self.present_label.pack(side=tk.LEFT, padx=20)

        self.absent_label = ttk.Label(stats_frame, text="Absent: 0", font=('Arial', 10, 'bold'), foreground='red')
        self.absent_label.pack(side=tk.LEFT, padx=20)

        self.late_label = ttk.Label(stats_frame, text="Late: 0", font=('Arial', 10, 'bold'), foreground='orange')
        self.late_label.pack(side=tk.LEFT, padx=20)

    def setup_reports_tab(self):
        """Setup attendance reports tab"""
        # Report controls
        control_frame = ttk.LabelFrame(self.reports_tab, text="Report Generation", padding=10)
        control_frame.pack(fill=tk.X, padx=5, pady=5)

        # Date range selection
        ttk.Label(control_frame, text="From Date:").grid(row=0, column=0, padx=5, pady=5)
        self.from_date_var = tk.StringVar(value=(date.today() - timedelta(days=30)).strftime('%Y-%m-%d'))
        ttk.Entry(control_frame, textvariable=self.from_date_var, width=12).grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(control_frame, text="To Date:").grid(row=0, column=2, padx=5, pady=5)
        self.to_date_var = tk.StringVar(value=date.today().strftime('%Y-%m-%d'))
        ttk.Entry(control_frame, textvariable=self.to_date_var, width=12).grid(row=0, column=3, padx=5, pady=5)

        ttk.Button(control_frame, text="📊 Generate Monthly Report",
                   command=self.generate_monthly_report).grid(row=0, column=4, padx=10, pady=5)

        # Report display
        report_frame = ttk.LabelFrame(self.reports_tab, text="Attendance Summary Report", padding=5)
        report_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Report treeview
        report_columns = ('Staff ID', 'Name', 'Department', 'Total Days', 'Present Days',
                          'Absent Days', 'Late Days', 'Attendance %', 'Avg Hours/Day')
        self.report_tree = ttk.Treeview(report_frame, columns=report_columns, show='headings', height=15)

        for col in report_columns:
            self.report_tree.heading(col, text=col)
            self.report_tree.column(col, width=110)

        report_scrollbar = ttk.Scrollbar(report_frame, orient=tk.VERTICAL, command=self.report_tree.yview)
        self.report_tree.configure(yscrollcommand=report_scrollbar.set)

        self.report_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        report_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def setup_performance_tab(self):
        """Setup staff performance analysis tab"""
        # Performance metrics frame
        metrics_frame = ttk.LabelFrame(self.performance_tab, text="Performance Metrics", padding=10)
        metrics_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(metrics_frame, text="🏆 Top Performers",
                   command=self.show_top_performers).pack(side=tk.LEFT, padx=10)

        ttk.Button(metrics_frame, text="⚠️ Attendance Issues",
                   command=self.show_attendance_issues).pack(side=tk.LEFT, padx=10)

        ttk.Button(metrics_frame, text="📈 Trend Analysis",
                   command=self.show_trend_analysis).pack(side=tk.LEFT, padx=10)

        # Performance display
        performance_frame = ttk.LabelFrame(self.performance_tab, text="Performance Analysis", padding=5)
        performance_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.performance_text = tk.Text(performance_frame, wrap=tk.WORD, font=('Arial', 11))
        performance_scrollbar = ttk.Scrollbar(performance_frame, orient=tk.VERTICAL,
                                              command=self.performance_text.yview)
        self.performance_text.configure(yscrollcommand=performance_scrollbar.set)

        self.performance_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        performance_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def load_attendance_data(self):
        """Load initial attendance data"""
        self.load_daily_attendance()

    def load_daily_attendance(self):
        """Load attendance for selected date"""
        try:
            selected_date = self.date_var.get()

            # Clear existing data
            for item in self.attendance_tree.get_children():
                self.attendance_tree.delete(item)

            # Get all staff members
            all_staff = self.db_manager.get_all_staff()

            # Get attendance records for the date
            attendance_records = self.get_daily_attendance_records(selected_date)

            total_staff = len(all_staff)
            present_count = 0
            absent_count = 0
            late_count = 0

            for staff in all_staff:
                staff_id = staff['staff_id']
                name = staff['name']
                department = staff['department'] or 'N/A'

                # Find attendance record for this staff
                attendance = next((r for r in attendance_records if r['staff_id'] == staff_id), None)

                if attendance:
                    check_in = attendance.get('check_in', 'N/A')
                    check_out = attendance.get('check_out', 'N/A')
                    hours_worked = attendance.get('hours_worked', 0)
                    status = attendance.get('status', 'Present')

                    present_count += 1
                    if status == 'Late':
                        late_count += 1
                else:
                    check_in = 'N/A'
                    check_out = 'N/A'
                    hours_worked = 0
                    status = 'Absent'
                    absent_count += 1

                # Insert into treeview
                self.attendance_tree.insert('', tk.END, values=(
                    staff_id, name, department, check_in, check_out,
                    f"{hours_worked:.2f}h" if hours_worked > 0 else "0h", status
                ))

            # Update statistics
            self.total_staff_label.config(text=f"Total Staff: {total_staff}")
            self.present_label.config(text=f"Present: {present_count}")
            self.absent_label.config(text=f"Absent: {absent_count}")
            self.late_label.config(text=f"Late: {late_count}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load attendance data: {e}")

    def get_daily_attendance_records(self, date_str):
        """Get attendance records for a specific date"""
        try:
            # This would query your database for staff attendance records
            # For now, return empty list - you need to implement this based on your database schema
            return []
        except Exception as e:
            print(f"Error getting attendance records: {e}")
            return []

    def generate_daily_report(self):
        """Generate daily attendance report"""
        try:
            selected_date = self.date_var.get()

            report_text = f"""
            DAILY ATTENDANCE REPORT
            ======================
            Date: {selected_date}
            Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

            SUMMARY:
            --------
            {self.total_staff_label.cget('text')}
            {self.present_label.cget('text')}
            {self.absent_label.cget('text')}
            {self.late_label.cget('text')}

            Attendance Rate: {(int(self.present_label.cget('text').split(': ')[1]) / max(1, int(self.total_staff_label.cget('text').split(': ')[1])) * 100):.1f}%

            DETAILED RECORDS:
            ----------------
            """

            # Add detailed records
            for child in self.attendance_tree.get_children():
                values = self.attendance_tree.item(child)['values']
                report_text += f"{values[0]:<10} {values[1]:<20} {values[2]:<15} {values[3]:<10} {values[4]:<10} {values[5]:<8} {values[6]}\n"

            # Show report in new window
            self.show_report_window("Daily Attendance Report", report_text)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate report: {e}")

    def show_report_window(self, title, content):
        """Show report in a new window"""
        report_window = tk.Toplevel(self.window)
        report_window.title(title)
        report_window.geometry("800x600")

        text_widget = tk.Text(report_window, wrap=tk.WORD, font=('Courier', 10))
        scrollbar = ttk.Scrollbar(report_window, orient=tk.VERTICAL, command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar.set)

        text_widget.insert('1.0', content)
        text_widget.config(state=tk.DISABLED)

        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
