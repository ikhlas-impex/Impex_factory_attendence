# checkin_main.py - IMPEX Check-In System Entry Point
# This is the dedicated entry point for the Check-In system
# Can be hosted on a separate IP/computer from Check-Out system

import os
import sys
import tkinter as tk
from tkinter import messagebox

# CRITICAL: Set environment variables BEFORE any imports
os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = (
    'rtsp_transport;tcp|'
    'rtsp_flags;prefer_tcp|'
    'fflags;nobuffer|'
    'flags;low_delay|'
    'fflags;flush_packets|'
    'max_delay;500000|'
    'reorder_queue_size;0|'
    'buffer_size;32768'
)

# Disable problematic camera backends
os.environ['OPENCV_VIDEOIO_PRIORITY_MSMF'] = '0'
os.environ['OPENCV_VIDEOIO_PRIORITY_OBSENSOR'] = '0'
os.environ['OPENCV_VIDEOIO_DEBUG'] = '0'
os.environ['OPENCV_VIDEOIO_PRIORITY_FFMPEG'] = '1000'
os.environ['OPENCV_VIDEOIO_PRIORITY_DIRECTSHOW'] = '900'

# Setup Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, 'src')

if current_dir not in sys.path:
    sys.path.insert(0, current_dir)
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

def ensure_init_files():
    """Ensure __init__.py files exist"""
    import os
    init_dirs = [
        src_dir,
        os.path.join(src_dir, 'core'),
        os.path.join(src_dir, 'ui'),
        os.path.join(src_dir, 'utils')
    ]
    
    for dir_path in init_dirs:
        if os.path.exists(dir_path):
            init_file = os.path.join(dir_path, '__init__.py')
            if not os.path.exists(init_file):
                try:
                    with open(init_file, 'w') as f:
                        f.write('# Auto-generated\n')
                    print(f"Created {init_file}")
                except Exception as e:
                    print(f"Warning: Could not create {init_file}: {e}")

ensure_init_files()

def main():
    """Main entry point for Check-In System"""
    try:
        print("🚀 Starting IMPEX Check-In System...")
        
        # Import after path setup
        from core.config_manager import ConfigManager
        from utils.gpu_utils import detect_gpu_capability
        from ui.attendance_dashboard import ImpexAttendanceDashboard
        
        # Load system configuration and set to check-in mode
        config = ConfigManager()
        system_config = config.get_system_config()
        
        # Ensure system is set to check-in mode and locked
        system_config['system_mode'] = 'checkin'
        system_config['system_name'] = 'IMPEX Check-In System'
        system_config['locked_mode'] = True  # Lock to check-in only
        system_config['allow_mode_switch'] = False
        
        # Save configuration
        config.save_system_config(system_config)
        
        print(f"✅ System Mode: CHECK-IN (Locked)")
        print(f"📁 Database: {system_config.get('database_path', 'data/factory_attendance.db')}")
        
        # Create main window
        root = tk.Tk()
        root.title("IMPEX Head Office - Check-In System")
        root.geometry("1400x900")
        
        # Detect GPU
        gpu_available = detect_gpu_capability()
        print(f"🎮 GPU Available: {gpu_available}")
        
        # Initialize dashboard in check-in mode
        dashboard = ImpexAttendanceDashboard(root, gpu_available=gpu_available, system_mode='checkin')
        
        # Handle window closing
        def on_closing():
            if messagebox.askokcancel("Quit", "Do you want to quit the Check-In System?"):
                dashboard.stop_recognition()
                root.destroy()
        
        root.protocol("WM_DELETE_WINDOW", on_closing)
        
        # Start GUI
        print("✅ Check-In System initialized successfully")
        root.mainloop()
        
    except ImportError as e:
        error_msg = str(e)
        print(f"❌ Import error: {error_msg}")
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Import Error", 
            f"Failed to import required modules:\n{error_msg}\n\n"
            "Please ensure all dependencies are installed.")
        sys.exit(1)
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Critical error: {error_msg}")
        import traceback
        traceback.print_exc()
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Critical Error", 
            f"Failed to start Check-In System:\n{error_msg}")
        sys.exit(1)

if __name__ == "__main__":
    main()

