# IMPEX Attendance System - Deployment Guide

## System Architecture

The IMPEX Attendance System can be deployed in two ways:

1. **Unified System** - Single installation with both Check-In and Check-Out modes (switchable)
2. **Split System** - Separate installations on different IPs/computers (dedicated Check-In and Check-Out)

## Split System Deployment

### Overview

The split system allows you to:
- Host Check-In system on one IP/computer
- Host Check-Out system on another IP/computer
- Both systems share the same database (centralized storage)
- Each system is locked to its specific mode

### Prerequisites

- Python 3.8+ installed on both systems
- Network access between systems (if using shared database)
- Same camera_settings.json configuration (if using same camera)

### Step 1: Database Configuration

Both systems MUST use the same database path. Configure this in `config/system_config.json`:

#### Option A: Local Database (Same Computer)
```json
{
    "system_mode": "checkin",
    "database_path": "data/factory_attendance.db",
    "locked_mode": true
}
```

#### Option B: Shared Database (Network Path)
```json
{
    "system_mode": "checkin",
    "database_path": "\\\\192.168.1.100\\shared\\factory_attendance.db",
    "locked_mode": true
}
```

**Note:** Ensure both systems point to the same database path.

### Step 2: Check-In System Setup

1. **Copy the entire project folder** to the Check-In system computer

2. **Edit `config/system_config.json`** (or it will be auto-created):
```json
{
    "system_mode": "checkin",
    "system_name": "IMPEX Check-In System",
    "database_path": "data/factory_attendance.db",
    "allow_mode_switch": false,
    "locked_mode": true
}
```

3. **Run the Check-In system:**
```bash
python checkin_main.py
```

4. **Configure camera settings** in `config/camera_settings.json` for the Check-In location

### Step 3: Check-Out System Setup

1. **Copy the entire project folder** to the Check-Out system computer

2. **Edit `config/system_config.json`** (or it will be auto-created):
```json
{
    "system_mode": "checkout",
    "system_name": "IMPEX Check-Out System",
    "database_path": "data/factory_attendance.db",
    "allow_mode_switch": false,
    "locked_mode": true
}
```

**IMPORTANT:** Use the SAME database path as Check-In system

3. **Run the Check-Out system:**
```bash
python checkout_main.py
```

4. **Configure camera settings** in `config/camera_settings.json` for the Check-Out location

### Step 4: Network Database Setup (Optional)

If using a shared network database:

1. **Choose one computer** to host the database (e.g., Check-In system)

2. **Create a shared folder** and place the database there:
   - Windows: Share a folder and set permissions
   - Path example: `\\SERVER-IP\shared\factory_attendance.db`

3. **Configure both systems** to use the network path:
   ```json
   {
       "database_path": "\\\\192.168.1.100\\shared\\factory_attendance.db"
   }
   ```

4. **Ensure network permissions** allow read/write access from both systems

### Configuration Files

Each system has its own configuration directory:

- `config/system_config.json` - System mode and database path
- `config/camera_settings.json` - Camera configuration (can be different)
- `config/network_settings.json` - Network settings
- `config/settings.json` - General application settings

### Entry Points

- `checkin_main.py` - Check-In system entry point
- `checkout_main.py` - Check-Out system entry point  
- `main.py` - Unified system (both modes switchable)

### Verification

After setup, verify:

1. ✅ Check-In system shows "Check In" mode only
2. ✅ Check-Out system shows "Check Out" mode only
3. ✅ Mode toggle buttons are hidden (locked mode)
4. ✅ Both systems can access the same database
5. ✅ Attendance records from Check-In appear in Check-Out system
6. ✅ Check-Out records update the same database

### Troubleshooting

#### Database Access Issues

**Problem:** Check-Out system cannot access database

**Solutions:**
- Verify database path is identical in both `system_config.json` files
- Check network connectivity if using network path
- Verify file permissions on shared database folder
- Ensure database file exists and is accessible

#### Mode Switching Still Available

**Problem:** Mode toggle buttons still visible

**Solutions:**
- Verify `locked_mode: true` in `system_config.json`
- Restart the application after configuration changes
- Check that `checkin_main.py` or `checkout_main.py` was used (not `main.py`)

#### Different Data Showing

**Problem:** Systems show different attendance data

**Solutions:**
- Verify both systems use the same database path
- Check database file location matches in both configs
- Ensure database is shared correctly (network setup)
- Restart both systems

### Network Database Best Practices

1. **Use UNC paths** for Windows: `\\SERVER\share\database.db`
2. **Use absolute paths** for Linux/Mac: `/mnt/shared/database.db`
3. **Ensure write permissions** for both systems
4. **Use network file locking** - SQLite handles this automatically
5. **Consider database backup** - Backup the shared database regularly

### IP Address Configuration

Each system can have different:
- IP address (Check-In: 192.168.1.10, Check-Out: 192.168.1.11)
- Camera settings (different cameras for each location)
- Network settings

But they MUST share:
- Database path (same file)
- System configuration structure

### Example Deployment

```
┌─────────────────────────┐      ┌─────────────────────────┐
│  Check-In System        │      │  Check-Out System       │
│  IP: 192.168.1.10       │      │  IP: 192.168.1.11       │
│                         │      │                         │
│  ┌───────────────────┐  │      │  ┌───────────────────┐  │
│  │ checkin_main.py   │  │      │  │ checkout_main.py  │  │
│  │ Camera 1          │  │      │  │ Camera 2          │  │
│  │ Mode: Check-In    │  │      │  │ Mode: Check-Out   │  │
│  │ Locked: Yes       │  │      │  │ Locked: Yes       │  │
│  └───────────────────┘  │      │  └───────────────────┘  │
│           │             │      │           │             │
│           │             │      │           │             │
│           └─────────────┼──────┼───────────┘             │
│                         │      │                         │
│                         │      │                         │
└─────────────────────────┘      └─────────────────────────┘
           │                              │
           │                              │
           └──────────────┬───────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │   Shared Database     │
              │  (Network/Server)     │
              │ factory_attendance.db │
              └───────────────────────┘
```

## Maintenance

- Regular database backups
- Monitor network connectivity (if using network database)
- Keep both systems updated with same codebase
- Test after any configuration changes

