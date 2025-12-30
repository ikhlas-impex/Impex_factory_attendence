#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
IMPEX Attendance System - Check-Out Server
Runs on port 8000, locked to check-out mode
"""

import sys
import os

# Explicitly mark this process as the CHECK-OUT server so configuration
# (especially camera selection) can be mode-specific without conflicts.
os.environ["IMPEX_SYSTEM_MODE"] = "checkout"

# Add current directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Import and run web_app with check-out configuration
if __name__ == '__main__':
    # Import web_app module
    import web_app
    from core.config_manager import ConfigManager
    
    # Get port from config before initializing
    config = ConfigManager()
    system_config = config.get_system_config()
    port = system_config.get('checkout_port', 8000)
    
    # Initialize system with check-out mode locked
    if not web_app.init_system(forced_mode='checkout'):
        print("❌ Failed to initialize check-out system")
        sys.exit(1)
    
    host = '0.0.0.0'
    
    print("=" * 70)
    print("🌐 IMPEX ATTENDANCE SYSTEM - CHECK-OUT SERVER")
    print("=" * 70)
    print(f"📍 Check-Out Server: http://localhost:{port}")
    print(f"📍 Network access: http://<your-ip>:{port}")
    print(f"📍 Mode: CHECK-OUT (LOCKED)")
    print("=" * 70)
    print(f"💡 Access Check-Out at: http://localhost:{port}/checkout")
    print("=" * 70)
    
    # Run Flask app
    web_app.app.run(host=host, port=port, debug=False, threaded=True)

