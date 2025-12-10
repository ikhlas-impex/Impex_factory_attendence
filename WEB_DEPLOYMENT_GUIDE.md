# IMPEX Attendance System - Web Deployment Guide

## 🌐 Overview

The IMPEX Attendance System can now be accessed through a web browser! This allows you to:
- Access the system from any device on your network
- Use tablets, phones, or computers to view the dashboard
- Share access via a simple URL link
- Deploy on a server for remote access

## 🚀 Quick Start

### Method 1: Simple Launcher (Recommended)
```bash
python start_web_server.py
```

### Method 2: Direct Flask Launch
```bash
python web_app.py
```

### Method 3: Manual Flask
```bash
python -m flask --app web_app run --host=0.0.0.0 --port=5000
```

## 📋 Prerequisites

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```
   
   This will install:
   - Flask (web framework)
   - flask-cors (cross-origin support)
   - All existing dependencies (OpenCV, InsightFace, etc.)

2. **Ensure Camera is Configured**
   - Camera settings in `config/camera_settings.json` must be correct
   - Test camera connection before starting web server

3. **Database Must Exist**
   - System will use the database specified in `config/system_config.json`
   - Default: `data/factory_attendance.db`

## 🌍 Accessing the Web Interface

### Local Access
- **Main Dashboard**: http://localhost:5000
- **Check-In Only**: http://localhost:5000/checkin
- **Check-Out Only**: http://localhost:5000/checkout

### Network Access
1. Find your computer's IP address:
   - Windows: `ipconfig` (look for IPv4 Address)
   - Linux/Mac: `ifconfig` or `ip addr`

2. Access from other devices on the same network:
   - http://YOUR_IP_ADDRESS:5000
   - Example: http://192.168.1.100:5000

### Internet Access (Advanced)
For remote access outside your network, you'll need:
- Port forwarding on your router (port 5000)
- Or use a reverse proxy (nginx, Apache)
- Or deploy on a cloud server (AWS, Azure, etc.)

## 📱 Features

### Web Dashboard Features
- ✅ Live camera feed streaming
- ✅ Real-time attendance cards
- ✅ Start/Stop system controls
- ✅ Check-In/Check-Out mode switching (if not locked)
- ✅ Employee photos displayed in cards
- ✅ Status indicators (Late, On Time, etc.)
- ✅ Responsive design (works on mobile/tablet)

### API Endpoints

#### System Control
- `POST /api/system/start` - Start face recognition
- `POST /api/system/stop` - Stop face recognition
- `GET /api/system/status` - Get system status

#### Attendance Data
- `GET /api/attendance/today` - Get today's attendance records
- `GET /api/staff/all` - Get all staff members

#### Mode Control
- `POST /api/system/mode` - Set attendance mode (checkin/checkout)

## 🔧 Configuration

### Change Port
Edit `web_app.py` and change:
```python
port = 5000  # Change to your desired port
```

### Change Host
Default: `0.0.0.0` (listens on all interfaces)
- Use `127.0.0.1` for local-only access
- Use `0.0.0.0` for network access

### System Mode
The web server respects `config/system_config.json`:
- `system_mode`: "checkin", "checkout", or "unified"
- `locked_mode`: If true, mode switching is disabled

## 🖥️ Deployment Options

### Option 1: Local Network Server
1. Run on a dedicated computer
2. Access from any device on the network
3. Use static IP address for reliability

### Option 2: Production Server
For production use, consider:
- **WSGI Server**: Use Gunicorn or uWSGI
- **Reverse Proxy**: Nginx or Apache
- **HTTPS**: SSL certificate for security
- **Process Manager**: systemd, supervisor, or PM2

### Option 3: Docker Deployment
Create a `Dockerfile`:
```dockerfile
FROM python:3.9
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "web_app.py"]
```

## 🔒 Security Considerations

1. **Firewall**: Only open necessary ports
2. **Authentication**: Add login system for production
3. **HTTPS**: Use SSL certificates for encrypted connections
4. **Access Control**: Implement user permissions
5. **Rate Limiting**: Prevent abuse of API endpoints

## 🐛 Troubleshooting

### Camera Not Showing
- Check camera settings in `config/camera_settings.json`
- Verify camera is accessible
- Check console logs for errors

### Cannot Access from Network
- Check firewall settings (allow port 5000)
- Verify IP address is correct
- Ensure devices are on the same network

### Performance Issues
- Reduce video stream quality in camera settings
- Limit number of attendance cards displayed
- Use GPU acceleration if available

### Port Already in Use
- Change port number in `web_app.py`
- Or kill the process using port 5000:
  - Windows: `netstat -ano | findstr :5000`
  - Linux: `lsof -i :5000`

## 📊 Monitoring

The web interface automatically:
- Refreshes attendance every 2 seconds
- Checks system status every 5 seconds
- Updates date/time every second

## 🆚 Desktop vs Web

| Feature | Desktop App | Web Interface |
|---------|-------------|---------------|
| Camera Feed | ✅ | ✅ |
| Face Recognition | ✅ | ✅ |
| Attendance Cards | ✅ | ✅ |
| Admin Panel | ✅ | ⚠️ (API only) |
| Staff Management | ✅ | ⚠️ (API only) |
| Reports | ✅ | ⚠️ (API only) |
| Network Access | ❌ | ✅ |
| Mobile Access | ❌ | ✅ |
| Multi-Device | ❌ | ✅ |

## 🎯 Next Steps

1. **Add Authentication**: Implement login system
2. **Add Admin Panel**: Full web-based admin interface
3. **Add Reports**: Web-based report viewing
4. **Mobile App**: Native mobile apps using the API
5. **Real-time Updates**: WebSocket for instant updates

## 📝 Notes

- The web server runs on port 5000 by default
- Video streaming uses MJPEG format
- API responses are in JSON format
- CORS is enabled for cross-origin requests
- Background images and icons are served from `/static/`

## 💡 Tips

1. **Bookmark the URL** for easy access
2. **Use a static IP** for the server computer
3. **Monitor logs** for troubleshooting
4. **Backup database** regularly
5. **Test on mobile** devices for responsive design

---

For issues or questions, check the main README.md or contact support.

