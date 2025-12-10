#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
IMPEX Attendance System - Check-Out Server
Runs on port 8000, locked to check-out mode
"""

import sys
import os

# Add current directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Import and run web_app with check-out configuration
if __name__ == '__main__':
    # Import web_app module
    import web_app
    
    # Initialize system with check-out mode locked
    if not web_app.init_system(forced_mode='checkout'):
        print("❌ Failed to initialize check-out system")
        sys.exit(1)
    
    # Run on port 8000
    host = '0.0.0.0'
    port = 8000
    
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

