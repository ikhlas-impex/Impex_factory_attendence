# IMPEX Head Office Attendance System - Startup Guide

## 🚀 How to Start the System

### Quick Start
1. **Open Command Prompt or PowerShell** in the project directory
2. **Run the following command:**
   ```bash
   python main.py
   ```

### Requirements
Make sure you have all required packages installed:
```bash
pip install opencv-python numpy scikit-learn scipy insightface Pillow pandas onnxruntime
```

### First Time Setup

1. **Configure Camera:**
   - Go to **File → Camera Setup**
   - Configure your camera (RTSP/IP/USB)
   - Test connection before saving
   - Settings are saved in `config/camera_settings.json`

2. **Add Employees:**
   - Go to **Staff → Manage Staff**
   - Add employee details with photos
   - Assign Employee ID numbers
   - Capture multiple photos for better recognition

3. **Start Attendance Tracking:**
   - Click **▶ Start** button on the dashboard
   - System will automatically detect and register employees
   - View real-time attendance in the right panel

### Features

#### Check-In Mode
- Shows all employees with check-in status
- Displays check-in time
- Shows "On Time" or "X min Late" status
- Captured photos appear in employee cards

#### Check-Out Mode
- Shows employees who checked in today
- Tracks check-out times
- Displays remaining count
- Photos from check-in are shown

#### Auto-Registration
- System automatically captures photos when employees are detected
- Photos are saved and displayed in employee cards
- No manual intervention needed

### Menu Options

- **File → Camera Setup**: Configure camera settings
- **File → Network Setup**: Configure network camera settings
- **Staff → Manage Staff**: Add/edit employee details and IDs
- **Staff → Admin Panel**: Access admin functions
- **Reports → View Reports**: View attendance reports

### Configuration Files

- `config/camera_settings.json` - Camera configuration (RTSP URL, transport, etc.)
- `config/network_settings.json` - Network settings
- `config/settings.json` - General settings
- `data/factory_attendance.db` - Database with employee data and attendance records

### Troubleshooting

1. **Camera not connecting:**
   - Check camera_settings.json for correct RTSP URL
   - Verify network connection
   - Test camera in Camera Setup

2. **Faces not being recognized:**
   - Ensure good lighting
   - Add more photos per employee (multiple angles)
   - Check face recognition threshold in settings

3. **System running slowly:**
   - Enable GPU acceleration if available
   - Reduce camera resolution
   - Close other applications

### Database

All employee data and attendance records are stored in:
- `data/factory_attendance.db`

The database includes:
- Employee profiles with photos and IDs
- Daily attendance records
- Check-in/check-out times
- Recognition confidence scores

### Support

For issues or questions, check:
- Console output for error messages
- Logs in `logs/factory_attendance.log`

---

**Power by Innovation & Industry 4.0 Department**

