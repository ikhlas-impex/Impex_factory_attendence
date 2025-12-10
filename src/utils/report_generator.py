import csv
import os
from datetime import datetime, date
import pandas as pd
from core.database_manager import DatabaseManager

class ReportGenerator:
    def __init__(self):
        self.db_manager = DatabaseManager()
        self.reports_dir = "data/reports"
        os.makedirs(self.reports_dir, exist_ok=True)
    
    def generate_daily_report(self, target_date=None):
        """Generate daily visit report"""
        if target_date is None:
            target_date = date.today()
        
        # Get daily data
        visits = self.db_manager.get_daily_visits(target_date)
        staff_detections = self.db_manager.get_daily_staff_detections(target_date)
        
        # Create CSV report
        filename = f"daily_report_{target_date.strftime('%Y%m%d')}.csv"
        filepath = os.path.join(self.reports_dir, filename)
        
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            
            # Header
            writer.writerow([f"Daily Report - {target_date.strftime('%Y-%m-%d')}"])
            writer.writerow([])
            
            # Summary
            writer.writerow(["SUMMARY"])
            writer.writerow(["Total Customer Visits", len(visits)])
            writer.writerow(["Unique Customers", len(set(v['customer_id'] for v in visits))])
            writer.writerow(["Staff Detections", len(staff_detections)])
            writer.writerow([])
            
            # Customer visits
            writer.writerow(["CUSTOMER VISITS"])
            writer.writerow(["Time", "Customer ID", "Customer Name", "Visit Count"])
            
            for visit in visits:
                writer.writerow([
                    visit['visit_time'].strftime('%H:%M:%S'),
                    visit['customer_id'],
                    visit['customer_name'] or 'Unknown',
                    visit['total_visits']
                ])
            
            writer.writerow([])
            
            # Staff detections
            writer.writerow(["STAFF DETECTIONS"])
            writer.writerow(["Time", "Staff ID", "Staff Name", "Department"])
            
            for detection in staff_detections:
                writer.writerow([
                    detection['detection_time'].strftime('%H:%M:%S'),
                    detection['staff_id'],
                    detection['staff_name'],
                    detection['department']
                ])
        
        return filepath
    
    def generate_monthly_report(self, year=None, month=None):
        """Generate monthly summary report"""
        if year is None:
            year = datetime.now().year
        if month is None:
            month = datetime.now().month
        
        # Get monthly data
        monthly_data = self.db_manager.get_monthly_statistics(year, month)
        
        filename = f"monthly_report_{year}_{month:02d}.csv"
        filepath = os.path.join(self.reports_dir, filename)
        
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            
            # Header
            writer.writerow([f"Monthly Report - {year}-{month:02d}"])
            writer.writerow([])
            
            # Summary statistics
            writer.writerow(["MONTHLY SUMMARY"])
            writer.writerow(["Total Visits", monthly_data['total_visits']])
            writer.writerow(["Unique Customers", monthly_data['unique_customers']])
            writer.writerow(["New Customers", monthly_data['new_customers']])
            writer.writerow(["Average Visits per Day", f"{monthly_data['avg_visits_per_day']:.1f}"])
            writer.writerow([])
            
            # Daily breakdown
            writer.writerow(["DAILY BREAKDOWN"])
            writer.writerow(["Date", "Visits", "Unique Customers", "New Customers"])
            
            for day_data in monthly_data['daily_breakdown']:
                writer.writerow([
                    day_data['date'].strftime('%Y-%m-%d'),
                    day_data['visits'],
                    day_data['unique_customers'],
                    day_data['new_customers']
                ])
        
        return filepath
    
    def generate_end_of_day_report(self):
        """Generate automatic end-of-day report"""
        today = date.today()
        
        # Generate daily report
        daily_report = self.generate_daily_report(today)
        
        # Create summary for dashboard
        visits = self.db_manager.get_daily_visits(today)
        summary = {
            'date': today,
            'total_visits': len(visits),
            'unique_customers': len(set(v['customer_id'] for v in visits)),
            'new_customers': len([v for v in visits if v['is_first_visit']]),
            'report_file': daily_report
        }
        
        return summary
