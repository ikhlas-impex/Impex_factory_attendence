# main.py - IMPEX Head Office Attendance System
# Simplified version using only the new attendance dashboard

import os
import sys
import tkinter as tk
from tkinter import messagebox
from datetime import datetime
import logging

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
# Force optimal backends for performance
os.environ['OPENCV_VIDEOIO_PRIORITY_FFMPEG'] = '1000'
os.environ['OPENCV_VIDEOIO_PRIORITY_DIRECTSHOW'] = '900'

# Setup Python path and ensure __init__.py files exist
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, 'src')

# Add both directories to Python path
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

def ensure_init_files():
    """Ensure __init__.py files exist in all necessary directories"""
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
                with open(init_file, 'w') as f:
                    f.write('# Auto-generated __init__.py\n')
                print(f"Created {init_file}")

def create_directories():
    """Create necessary directories"""
    directories = [
        "data",
        "data/reports", 
        "data/backups",
        "config",
        "assets",
        "assets/icons",
        "logs",
        "src",
        "src/core",
        "src/ui",
        "src/utils"
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)

def check_requirements():
    """Check if all required packages are installed"""
    required_packages = [
        'cv2', 'numpy', 'sklearn', 'scipy', 'PIL', 'pandas'
    ]
    
    missing_packages = []
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"❌ Missing packages: {missing_packages}")
        return False
    
    # Check optional packages
    optional_packages = ['insightface', 'onnxruntime']
    for package in optional_packages:
        try:
            __import__(package)
            print(f"✅ {package} available")
        except ImportError:
            print(f"⚠️ {package} not available (optional)")
    
    return True

class ImpexAttendanceApp:
    """IMPEX Head Office Attendance System - Main Application"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("IMPEX Head Office - Attendance Register System")
        self.root.geometry("1600x900")
        self.root.minsize(1400, 800)
        
        # Maximize window
        try:
            self.root.state('zoomed') if os.name == 'nt' else self.root.attributes('-zoomed', True)
        except:
            pass
        
        # Initialize components
        self.config = None
        self.gpu_available = False
        self.dashboard = None
        
        # Setup menu bar
        self.setup_menu()
        
        # Initialize system after GUI is created
        self.initialize_system()

    def setup_menu(self):
        """Setup the menu bar"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="🔧 Camera Setup", command=self.open_camera_setup)
        file_menu.add_command(label="🌐 Network Setup", command=self.open_network_setup)
        file_menu.add_separator()
        file_menu.add_command(label="❌ Exit", command=self.on_closing)
        
        # Staff menu
        staff_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Staff", menu=staff_menu)
        staff_menu.add_command(label="👥 Manage Staff", command=self.open_staff_management)
        staff_menu.add_command(label="👤 Admin Panel", command=self.open_admin_panel)
        
        # Reports menu
        reports_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Reports", menu=reports_menu)
        reports_menu.add_command(label="📊 View Reports", command=self.open_reports)
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="ℹ️ About", command=self.show_about)

    def initialize_system(self):
        """Initialize system components safely"""
        try:
            print("🚀 Initializing IMPEX Head Office Attendance System...")
            
            # Import modules after GUI is created
            try:
                from core.config_manager import ConfigManager
                from utils.gpu_utils import detect_gpu_capability
                
                self.config = ConfigManager()
                self.gpu_available = detect_gpu_capability()
                
                print(f"✅ GPU Available: {self.gpu_available}")
                
                # Import UI modules
                from ui.attendance_dashboard import ImpexAttendanceDashboard
                from ui.camera_setup import CameraSetupWindow
                from ui.network_setup import NetworkSetupWindow
                from ui.staff_management import StaffManagementWindow
                
                # Store classes for later use
                self.ImpexAttendanceDashboard = ImpexAttendanceDashboard
                self.CameraSetupWindow = CameraSetupWindow
                self.NetworkSetupWindow = NetworkSetupWindow
                self.StaffManagementWindow = StaffManagementWindow
                
                # Initialize new attendance dashboard
                print("🎯 Initializing IMPEX Attendance Dashboard...")
                self.dashboard = self.ImpexAttendanceDashboard(self.root, gpu_available=self.gpu_available)
                
                print("✅ IMPEX Head Office Attendance System initialized successfully!")
                
            except ImportError as e:
                error_msg = f"Failed to import system modules: {e}"
                print(f"❌ {error_msg}")
                self.show_import_error(error_msg)
                
            except Exception as e:
                error_msg = f"System initialization failed: {e}"
                print(f"❌ {error_msg}")
                messagebox.showerror("Initialization Error", 
                                   f"System initialization failed:\n\n{error_msg}\n\n"
                                   f"Please check the console for more details.")
                
        except Exception as e:
            error_msg = str(e)
            print(f"❌ Critical initialization error: {error_msg}")
            messagebox.showerror("Critical Error",
                               f"A critical error occurred:\n\n{error_msg}\n\n"
                               f"Please check the console for more details.")

    def show_import_error(self, error_msg):
        """Show import error with helpful message"""
        error_dialog = tk.Toplevel(self.root)
        error_dialog.title("Import Error")
        error_dialog.geometry("600x400")
        error_dialog.transient(self.root)
        error_dialog.grab_set()
        
        frame = tk.Frame(error_dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)
        
        tk.Label(frame, text="❌ Import Error", font=('Arial', 16, 'bold'), 
                fg='red').pack(pady=10)
        
        error_text = tk.Text(frame, wrap=tk.WORD, height=15)
        scrollbar = tk.Scrollbar(frame, orient=tk.VERTICAL, command=error_text.yview)
        error_text.configure(yscrollcommand=scrollbar.set)
        
        error_content = f"""System modules could not be imported properly.

Error Details:
{error_msg}

Possible Solutions:
1. Install missing packages:
   pip install opencv-python numpy scikit-learn scipy insightface Pillow pandas

2. Check if all source files exist:
   - src/core/config_manager.py
   - src/core/database_manager.py
   - src/core/face_engine.py
   - src/ui/attendance_dashboard.py
   - src/utils/gpu_utils.py

3. Verify Python path configuration

The system will continue to run with limited functionality."""
        
        error_text.insert('1.0', error_content)
        error_text.config(state=tk.DISABLED)
        
        error_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        tk.Button(frame, text="Continue Anyway", command=error_dialog.destroy).pack(pady=10)

    def open_camera_setup(self):
        """Open camera setup window"""
        try:
            if hasattr(self, 'CameraSetupWindow'):
                self.CameraSetupWindow(self.root)
            else:
                messagebox.showerror("Error", "Camera setup module not available")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open camera setup: {e}")

    def open_network_setup(self):
        """Open network setup window"""
        try:
            if hasattr(self, 'NetworkSetupWindow'):
                self.NetworkSetupWindow(self.root)
            else:
                messagebox.showerror("Error", "Network setup module not available")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open network setup: {e}")

    def open_staff_management(self):
        """Open staff management window"""
        try:
            if hasattr(self, 'StaffManagementWindow'):
                self.StaffManagementWindow(self.root)
            else:
                messagebox.showerror("Error", "Staff management module not available")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open staff management: {e}")

    def open_admin_panel(self):
        """Open admin panel for managing employees"""
        try:
            # Create admin panel window
            admin_window = tk.Toplevel(self.root)
            admin_window.title("Admin Panel - Employee Management")
            admin_window.geometry("800x600")
            admin_window.transient(self.root)
            
            # Simple admin panel interface
            frame = tk.Frame(admin_window, padding=20)
            frame.pack(fill=tk.BOTH, expand=True)
            
            tk.Label(frame, text="Admin Panel - Employee Management", 
                    font=('Arial', 16, 'bold')).pack(pady=10)
            
            tk.Label(frame, 
                    text="Use 'Staff → Manage Staff' to add/edit employees with photos and IDs.",
                    font=('Arial', 10)).pack(pady=10)
            
            tk.Label(frame, 
                    text="The system will automatically register employees when detected by the camera.",
                    font=('Arial', 10)).pack(pady=5)
            
            tk.Button(frame, text="Open Staff Management", 
                     command=lambda: [admin_window.destroy(), self.open_staff_management()],
                     bg='#4CAF50', fg='white', font=('Arial', 12, 'bold'),
                     padx=20, pady=10).pack(pady=20)
            
            tk.Button(frame, text="Close", command=admin_window.destroy,
                     bg='#f44336', fg='white', font=('Arial', 10),
                     padx=20, pady=5).pack(pady=10)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open admin panel: {e}")

    def open_reports(self):
        """Open reports window"""
        try:
            from ui.reports import ReportsWindow
            ReportsWindow(self.root)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open reports: {e}")

    def show_about(self):
        """Show about dialog"""
        messagebox.showinfo("About",
                          "🏢 IMPEX HEAD OFFICE ATTENDANCE SYSTEM\n\n"
                          "👥 Employee Recognition & Attendance Tracking\n"
                          "🚀 AI-Powered Face Recognition\n"
                          "📊 Real-time Attendance Monitoring\n"
                          "⏰ Automatic Check-in/Check-out\n\n"
                          "Powered by Innovation & Industry 4.0 Department")

    def on_closing(self):
        """Handle application closing"""
        try:
            # Check if recognition is running
            if (hasattr(self, 'dashboard') and self.dashboard and 
                hasattr(self.dashboard, 'running') and self.dashboard.running):
                result = messagebox.askyesno("Confirm Exit",
                                           "Attendance recognition is running.\n\n"
                                           "Stop recognition and exit?")
                if not result:
                    return
                
                # Stop recognition
                self.dashboard.stop_recognition()
            
            print("🏁 Shutting down IMPEX Attendance System...")
            self.root.update()
            
            # Close application
            self.root.quit()
            self.root.destroy()
            print("✅ Application closed successfully")
            
        except Exception as e:
            print(f"Error during shutdown: {e}")
            self.root.destroy()

    def run(self):
        """Run the application"""
        try:
            self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
            
            # Center window
            self.root.update_idletasks()
            width = self.root.winfo_width()
            height = self.root.winfo_height()
            x = (self.root.winfo_screenwidth() // 2) - (width // 2)
            y = (self.root.winfo_screenheight() // 2) - (height // 2)
            self.root.geometry(f'{width}x{height}+{x}+{y}')
            
            print("🚀 Starting IMPEX Head Office Attendance System GUI...")
            self.root.mainloop()
            
        except KeyboardInterrupt:
            print("\n🛑 Application interrupted by user")
            self.on_closing()
        except Exception as e:
            print(f"❌ Application error: {e}")
            messagebox.showerror("Application Error", f"Fatal error: {e}")


def main():
    """Main function to run the application"""
    print("=" * 70)
    print("🏢 IMPEX HEAD OFFICE ATTENDANCE REGISTER SYSTEM")
    print("👥 Employee Recognition & Attendance Tracking")
    print("=" * 70)
    
    try:
        # Create directories and init files
        create_directories()
        ensure_init_files()
        
        # Check requirements
        if not check_requirements():
            print("⚠️ Some requirements are missing, but continuing...")
        
        # Initialize logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('logs/factory_attendance.log'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        
        # Create and run application
        app = ImpexAttendanceApp()
        app.run()
        
    except Exception as e:
        print(f"❌ Fatal error starting application: {e}")
        try:
            messagebox.showerror("Fatal Error",
                               f"Could not start IMPEX Attendance System:\n\n{e}")
        except:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
