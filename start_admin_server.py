# start_admin_server.py - Admin Server Launcher
# This script makes it easy to start the admin web server

import os
import sys
import subprocess

def main():
    print("=" * 70)
    print("🔐 IMPEX ATTENDANCE SYSTEM - ADMIN SERVER LAUNCHER")
    print("=" * 70)
    print()
    
    # Check if Flask is installed
    try:
        import flask
        print("✅ Flask is installed")
    except ImportError:
        print("❌ Flask is not installed!")
        print("📦 Installing Flask...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "Flask", "flask-cors"])
        print("✅ Flask installed successfully!")
        print()
    
    # Start the admin server
    print("🚀 Starting admin server...")
    print()
    
    try:
        # Import and run the admin app
        from admin_app import app, init_admin_system
        
        if not init_admin_system():
            print("❌ Failed to initialize admin system")
            sys.exit(1)
        
        print()
        print("=" * 70)
        print("✅ Admin Server is running!")
        print("=" * 70)
        print()
        print("📍 Access the admin panel at:")
        print("   • Local:     http://localhost:5001")
        print("   • Network:   http://<your-ip>:5001")
        print()
        print("💡 Press Ctrl+C to stop the server")
        print("=" * 70)
        print()
        
        # Run Flask app on port 5001 (different from main web app)
        app.run(host='0.0.0.0', port=5001, debug=False, threaded=True)
        
    except KeyboardInterrupt:
        print("\n\n⚠️ Admin server stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error starting admin server: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()

