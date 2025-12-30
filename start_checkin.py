#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
IMPEX Attendance System - Check-In Server
Runs on port 5000, locked to check-in mode
"""

import sys
import os

# Explicitly mark this process as the CHECK-IN server so configuration
# (especially camera selection) can be mode-specific without conflicts.
os.environ["IMPEX_SYSTEM_MODE"] = "checkin"

# Add current directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Import and run web_app with check-in configuration
if __name__ == '__main__':
    # Import web_app module
    import web_app
    from core.config_manager import ConfigManager
    
    # Get port from config before initializing
    config = ConfigManager()
    system_config = config.get_system_config()
    port = system_config.get('checkin_port', 5000)
    
    # Initialize system with check-in mode locked
    if not web_app.init_system(forced_mode='checkin'):
        print("❌ Failed to initialize check-in system")
        sys.exit(1)
    
    host = '0.0.0.0'
    
    print("=" * 70)
    print("🌐 IMPEX ATTENDANCE SYSTEM - CHECK-IN SERVER")
    print("=" * 70)
    print(f"📍 Check-In Server: http://localhost:{port}")
    print(f"📍 Network access: http://<your-ip>:{port}")
    print(f"📍 Mode: CHECK-IN (LOCKED)")
    print("=" * 70)
    print(f"💡 Access Check-In at: http://localhost:{port}/checkin")
    print("=" * 70)
    
    # Run Flask app
    web_app.app.run(host=host, port=port, debug=False, threaded=True)

