# start_web_server.py - Simple launcher for web server
# This script makes it easy to start the web server

import os
import sys
import subprocess

def main():
    print("=" * 70)
    print("🌐 IMPEX ATTENDANCE SYSTEM - WEB SERVER LAUNCHER")
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
    
    # Start the web server
    print("🚀 Starting web server...")
    print()
    
    try:
        # Import and run the web app
        from web_app import app, init_system
        
        if not init_system():
            print("❌ Failed to initialize system")
            sys.exit(1)
        
        print()
        print("=" * 70)
        print("✅ Server is running!")
        print("=" * 70)
        print()
        print("📍 Access the dashboard at:")
        print("   • Local:     http://localhost:5000")
        print("   • Network:   http://<your-ip>:5000")
        print()
        print("📍 Specific pages:")
        print("   • Check-In:  http://localhost:5000/checkin")
        print("   • Check-Out: http://localhost:5000/checkout")
        print()
        print("💡 Press Ctrl+C to stop the server")
        print("=" * 70)
        print()
        
        # Run Flask app
        app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
        
    except KeyboardInterrupt:
        print("\n\n⚠️ Server stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error starting server: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()

