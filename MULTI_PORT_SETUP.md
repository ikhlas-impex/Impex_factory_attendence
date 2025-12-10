# Multi-Port Setup Guide

## Overview
The IMPEX Attendance System can now run on separate ports for Check-In and Check-Out, sharing the same database.

## Quick Start

### Option 1: Using Batch Files (Windows)
1. **Start Check-In Server (Port 5000)**
   - Double-click `start_checkin.bat`
   - Or run: `python start_checkin.py`
   - Access at: `http://localhost:5000/checkin` or `http://<your-ip>:5000/checkin`

2. **Start Check-Out Server (Port 8000)**
   - Double-click `start_checkout.bat`
   - Or run: `python start_checkout.py`
   - Access at: `http://localhost:8000/checkout` or `http://<your-ip>:8000/checkout`

### Option 2: Using Command-Line Arguments
```bash
# Check-In Server (Port 5000)
python web_app.py --port 5000 --mode checkin

# Check-Out Server (Port 8000)
python web_app.py --port 8000 --mode checkout
```

## Features
- ✅ **Separate Ports**: Check-In on port 5000, Check-Out on port 8000
- ✅ **Shared Database**: Both servers use the same `data/factory_attendance.db`
- ✅ **Mode Locked**: Each server is locked to its specific mode (cannot be changed)
- ✅ **Independent Operation**: Both servers can run simultaneously

## Network Access
Both servers listen on all network interfaces (`0.0.0.0`), so they can be accessed from other devices on your network:
- Check-In: `http://<your-computer-ip>:5000/checkin`
- Check-Out: `http://<your-computer-ip>:8000/checkout`

## Notes
- Both servers share the same database, so attendance data is synchronized
- Each server is locked to its mode and cannot be switched via the web interface
- You can run both servers simultaneously on the same machine
- Make sure both ports (5000 and 8000) are not blocked by your firewall

