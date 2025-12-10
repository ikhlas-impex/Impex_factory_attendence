# 🌐 IMPEX Attendance System - Web Version

## Quick Start

```bash
# Install dependencies (if not already installed)
pip install -r requirements.txt

# Start the web server
python start_web_server.py
```

Then open your browser and go to: **http://localhost:5000**

## 📍 Access URLs

- **Main Dashboard**: http://localhost:5000
- **Check-In Only**: http://localhost:5000/checkin
- **Check-Out Only**: http://localhost:5000/checkout

## 🌍 Network Access

To access from other devices on your network:
1. Find your computer's IP address
2. Access: http://YOUR_IP_ADDRESS:5000

Example: http://192.168.1.100:5000

## ✅ Features

- ✅ Live camera feed streaming
- ✅ Real-time face recognition
- ✅ Attendance tracking (Check-In/Check-Out)
- ✅ Employee cards with photos
- ✅ Mobile-friendly responsive design
- ✅ Works on any device with a browser

## 🔧 Requirements

- Python 3.7+
- All dependencies from `requirements.txt`
- Camera configured in `config/camera_settings.json`
- Database file (created automatically)

## 📱 Usage

1. Start the web server
2. Open the dashboard in your browser
3. Click "Start" to begin face recognition
4. View attendance in real-time
5. Click "Stop" when done

## 📚 Full Documentation

See `WEB_DEPLOYMENT_GUIDE.md` for complete documentation.

