# IMPEX Admin Panel Guide

## Overview

The IMPEX Admin Panel is a comprehensive web-based administration interface for managing the attendance system. It runs on a **separate port (5001)** to reduce load on the main dashboard (port 5000).

## Features

### 📊 Dashboard
- Real-time statistics:
  - Total staff count
  - Present/Absent today
  - Checked out count
  - Late arrivals
  - Attendance rate
- Weekly attendance chart
- Auto-refreshing statistics

### 👥 Staff Management
- **Add Staff**: Register new staff members with photos
- **Edit Staff**: Update staff information, photos, and employee IDs
- **Delete Staff**: Remove staff members from the system
- **View All Staff**: See complete staff list with today's attendance status
- Photo management with preview
- Department assignment

### 📋 Attendance Sheet
- View attendance for any date
- Filter by status (Present/Absent/Late)
- Search by name or employee ID
- Export attendance data to CSV
- View check-in/check-out times
- Confidence scores for each record

### 📷 Camera Configuration
- Configure camera source:
  - USB Webcam (with index selection)
  - RTSP Camera (with URL configuration)
  - IP Camera
- Adjust settings:
  - Resolution (640x480, 1280x720, 1920x1080)
  - FPS (5-60)
  - Buffer size
  - Transport protocol (TCP/UDP)
- Test camera connection
- Save and load configurations

### ⚡ Real-Time Data
- Live attendance updates (refreshes every 5 seconds)
- Recent check-ins list
- Total present count
- Status indicator
- Last update timestamp

### 📈 Reports
- Generate attendance reports for date ranges
- Export to CSV format
- Custom date selection
- Comprehensive attendance data

## Starting the Admin Server

### Option 1: Using Batch File (Windows)
```bash
start_admin.bat
```

### Option 2: Using Python Script
```bash
python start_admin_server.py
```

### Option 3: Direct Python
```bash
python admin_app.py --port 5001
```

## Accessing the Admin Panel

Once the server is running, access the admin panel at:
- **Local**: http://localhost:5001
- **Network**: http://<your-ip>:5001

## Port Configuration

- **Main Dashboard**: Port 5000 (for attendance display)
- **Admin Panel**: Port 5001 (for management)

This separation reduces load and allows both interfaces to run simultaneously.

## API Endpoints

### Staff Management
- `GET /api/admin/staff/all` - Get all staff
- `POST /api/admin/staff/add` - Add new staff
- `POST /api/admin/staff/update` - Update staff
- `POST /api/admin/staff/delete` - Delete staff
- `GET /api/admin/staff/<staff_id>/photo` - Get staff photo

### Attendance
- `GET /api/admin/attendance/today?date=YYYY-MM-DD` - Get today's attendance
- `GET /api/admin/attendance/range?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD` - Get date range
- `GET /api/admin/attendance/export?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD` - Export CSV

### Camera Configuration
- `GET /api/admin/camera/config` - Get camera config
- `POST /api/admin/camera/config` - Save camera config
- `POST /api/admin/camera/test` - Test camera connection

### Statistics
- `GET /api/admin/statistics/dashboard` - Get dashboard stats

### Real-Time
- `GET /api/admin/realtime/attendance` - Get real-time attendance

## Usage Tips

1. **Staff Management**: Always upload clear face photos for better recognition accuracy
2. **Attendance Sheet**: Use filters to quickly find specific staff or status
3. **Camera Config**: Test camera connection before saving configuration
4. **Real-Time Data**: Monitor recent check-ins to track attendance in real-time
5. **Reports**: Export attendance data regularly for record-keeping

## Security Notes

- The admin panel has full access to the system
- Consider adding authentication in production environments
- Keep the admin panel on a secure network
- Regularly backup the database

## Troubleshooting

### Admin server won't start
- Check if port 5001 is available
- Ensure Flask is installed: `pip install Flask flask-cors`
- Check database file exists and is accessible

### Camera configuration not saving
- Verify camera settings are correct
- Test camera connection first
- Check file permissions for config directory

### Staff photos not displaying
- Ensure photos are uploaded in valid image formats (JPG, PNG)
- Check file size (recommended: under 2MB)
- Verify database has write permissions

## Additional Features

The admin panel includes several extra features:
- **Auto-refresh**: Real-time data updates automatically
- **Search & Filter**: Quick access to specific records
- **Export Functionality**: Easy data export for reporting
- **Visual Statistics**: Charts and graphs for better insights
- **Responsive Design**: Works on desktop and tablet devices

## Next Steps

1. Start the admin server
2. Access the admin panel in your browser
3. Configure camera settings
4. Add staff members
5. Monitor attendance in real-time
6. Generate reports as needed

For more information, refer to the main README.md file.

