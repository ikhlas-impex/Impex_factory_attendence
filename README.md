# Elkitch Factory Attendance System

## Features
- ✅ GPU/CPU automatic detection and switching
- ✅ Staff face recognition and identification
- ✅ Real-time attendance tracking
- ✅ Automatic check-in/check-out recording
- ✅ Multi-angle photo capture for better recognition
- ✅ Easy camera setup with presets
- ✅ DeepSORT tracking
- ✅ Automatic daily reports
- ✅ Staff attendance dashboard

## Quick Installation

### Method 1: Executable (Recommended)
1. Download `ElkitchFactoryAttendance.exe`
2. Run the executable
3. Follow the setup wizard
4. Configure your camera in Settings > Camera Setup

### Method 2: From Source
Install Python 3.7-3.9
Clone repository
```
git clone <repository-url>
cd Impex_factory_attendence
```

Install requirements
```
pip install -r requirements.txt
```

Run application
```
python main.py
```

## Camera Setup Guide

### Supported Cameras
- EZVIZ CS-H6c Pro
- Hikvision IP cameras
- Dahua IP cameras
- Any RTSP-compatible camera
- USB webcams

### RTSP URL Format
`rtsp://username:password@ip_address:port/stream_path`

### Common Examples
- EZVIZ: `rtsp://admin:password@192.168.1.100:554/Streaming/Channels/101`
- Hikvision: `rtsp://admin:password@192.168.1.100:554/Streaming/Channels/1`
- Dahua: `rtsp://admin:password@192.168.1.100:554/cam/realmonitor?channel=1&subtype=0`

## First Time Setup

1. **Launch Application**
2. **Camera Setup**: Go to File > Camera Setup
   - Select your camera brand from presets
   - Enter IP address, username, password
   - Test connection
   - Save settings
3. **Staff Management**: Go to Staff > Manage Staff
   - Add staff members
   - Capture photos from multiple angles (Front, Right, Left, Up, Down)
   - Set departments and roles
4. **Start Recognition**: Click "Start Attendance Recognition"

## Usage

### Daily Operation
1. Start the application
2. Click "Start Attendance Recognition"
3. System will automatically:
   - Detect and track staff faces
   - Recognize staff members
   - Record check-in times
   - Track attendance throughout the day
   - Display attendance status
   - Generate reports at day end

### Staff Registration
When adding a new staff member:
1. Go to Staff > Manage Staff
2. Click "Add Staff"
3. Enter Staff ID, Name, and Department
4. Click "Take Photo"
5. Capture 5 photos from different angles:
   - Photo 1: Front view (straight)
   - Photo 2: Turn head right →
   - Photo 3: Turn head left ←
   - Photo 4: Tilt head up ↑
   - Photo 5: Look down ↓
6. Click "Finish Capture" when done
7. Save the staff member

### Reports
- **Daily Reports**: Automatic CSV generation
- **Monthly Reports**: Summary statistics
- **Real-time Dashboard**: Live attendance information

## Recognition Tuning

### Confidence Threshold
Adjust how strictly face embeddings must match to identify a staff member. Lower values
such as `0.55` increase matches but risk false positives, while higher values
around `0.7` improve precision at the cost of missed identifications. The
default can be modified via the `confidence_threshold` setting in
`config/settings.json` to reflect real-world performance.

## Troubleshooting

### Camera Issues
- Check IP address and credentials
- Ensure camera is on same network
- Try different stream channels (101, 102)
- Test with VLC media player first

### Performance Issues
- Use GPU mode if available
- Reduce camera resolution for CPU mode
- Check network bandwidth
- Close unnecessary applications

### Recognition Issues
- Ensure staff photos are clear and well-lit
- Capture photos from multiple angles as instructed
- Check lighting conditions in factory
- Adjust detection threshold if needed

## Support
For technical support, contact: support@elkitchfactory.com
