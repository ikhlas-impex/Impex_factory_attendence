# src/ui/camera_setup.py
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import cv2
import json
import os
from core.config_manager import ConfigManager

class CameraSetupWindow:
    def __init__(self, parent):
        self.parent = parent
        self.config = ConfigManager()
        
        self.window = tk.Toplevel(parent)
        self.window.title("Camera Setup")
        self.window.geometry("700x600")
        self.window.resizable(True, True)
        self.window.transient(parent)
        self.window.grab_set()
        
        self.setup_gui()
        self.load_presets()
        self.load_current_settings()
    
    def setup_gui(self):
        # Main container
        main_frame = ttk.Frame(self.window, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Camera configuration section
        config_frame = ttk.LabelFrame(main_frame, text="Camera Configuration", padding=10)
        config_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Source type selection
        ttk.Label(config_frame, text="Camera Source:").grid(row=0, column=0, sticky=tk.W, pady=5)
        
        self.source_var = tk.StringVar(value="rtsp")
        source_frame = ttk.Frame(config_frame)
        source_frame.grid(row=0, column=1, columnspan=3, sticky=tk.W, pady=5)
        
        ttk.Radiobutton(source_frame, text="RTSP Camera", variable=self.source_var, 
                       value="rtsp", command=self.on_source_changed).pack(side=tk.LEFT)
        ttk.Radiobutton(source_frame, text="USB Webcam", variable=self.source_var, 
                       value="usb", command=self.on_source_changed).pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(source_frame, text="IP Camera", variable=self.source_var, 
                       value="ip", command=self.on_source_changed).pack(side=tk.LEFT)
        
        # RTSP/IP Camera settings
        self.rtsp_frame = ttk.Frame(config_frame)
        self.rtsp_frame.grid(row=1, column=0, columnspan=4, sticky=tk.W+tk.E, pady=10)
        
        ttk.Label(self.rtsp_frame, text="Camera URL:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.url_var = tk.StringVar(value="rtsp://admin:password@192.168.1.100:554/stream1")
        self.url_entry = ttk.Entry(self.rtsp_frame, textvariable=self.url_var, width=60)
        self.url_entry.grid(row=0, column=1, columnspan=2, sticky=tk.W+tk.E, pady=2, padx=5)
        
        # Camera presets
        ttk.Label(self.rtsp_frame, text="Presets:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.preset_var = tk.StringVar()
        self.preset_combo = ttk.Combobox(self.rtsp_frame, textvariable=self.preset_var, width=25)
        self.preset_combo.grid(row=1, column=1, sticky=tk.W, pady=5, padx=5)
        self.preset_combo.bind('<<ComboboxSelected>>', self.on_preset_selected)
        
        ttk.Button(self.rtsp_frame, text="Use Preset", 
                  command=self.apply_preset).grid(row=1, column=2, padx=5, pady=5)
        
        # USB Camera settings
        self.usb_frame = ttk.Frame(config_frame)
        self.usb_frame.grid(row=2, column=0, columnspan=4, sticky=tk.W+tk.E, pady=10)
        
        ttk.Label(self.usb_frame, text="Camera Index:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.usb_index_var = tk.StringVar(value="0")
        usb_spin = ttk.Spinbox(self.usb_frame, from_=0, to=10, textvariable=self.usb_index_var, width=8)
        usb_spin.grid(row=0, column=1, sticky=tk.W, pady=2, padx=5)
        
        ttk.Button(self.usb_frame, text="Detect Cameras", 
                  command=self.detect_usb_cameras).grid(row=0, column=2, padx=10, pady=2)
        
        # Advanced settings
        advanced_frame = ttk.LabelFrame(main_frame, text="Advanced Settings", padding=10)
        advanced_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Resolution
        ttk.Label(advanced_frame, text="Resolution:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.resolution_var = tk.StringVar(value="1920x1080")
        resolution_combo = ttk.Combobox(
            advanced_frame,
            textvariable=self.resolution_var,
            values=["640x480", "1280x720", "1920x1080"],
            width=12,
        )
        resolution_combo.grid(row=0, column=1, sticky=tk.W, pady=5, padx=5)
        
        # FPS
        ttk.Label(advanced_frame, text="Target FPS:").grid(row=0, column=2, sticky=tk.W, padx=(20,0), pady=5)
        self.fps_var = tk.StringVar(value="60")  # Default to 60 FPS for smooth video
        fps_spin = ttk.Spinbox(advanced_frame, from_=5, to=60, textvariable=self.fps_var, width=8)
        fps_spin.grid(row=0, column=3, sticky=tk.W, pady=5, padx=5)
        
        # Buffer size
        ttk.Label(advanced_frame, text="Buffer Size:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.buffer_var = tk.StringVar(value="5")
        buffer_spin = ttk.Spinbox(advanced_frame, from_=1, to=20, textvariable=self.buffer_var, width=8)
        buffer_spin.grid(row=1, column=1, sticky=tk.W, pady=5, padx=5)
        
        # Transport protocol
        ttk.Label(advanced_frame, text="Transport:").grid(row=1, column=2, sticky=tk.W, padx=(20,0), pady=5)
        self.transport_var = tk.StringVar(value="TCP")
        transport_combo = ttk.Combobox(advanced_frame, textvariable=self.transport_var,
                                      values=["TCP", "UDP"], width=8)
        transport_combo.grid(row=1, column=3, sticky=tk.W, pady=5, padx=5)
        
        # Test connection section
        test_frame = ttk.LabelFrame(main_frame, text="Connection Test", padding=10)
        test_frame.pack(fill=tk.X, pady=(0, 10))
        
        test_button_frame = ttk.Frame(test_frame)
        test_button_frame.pack(fill=tk.X)
        
        ttk.Button(test_button_frame, text="🔍 Test Connection", 
                  command=self.test_connection).pack(side=tk.LEFT, padx=5)
        ttk.Button(test_button_frame, text="📹 Preview", 
                  command=self.preview_camera).pack(side=tk.LEFT, padx=5)
        
        self.test_status = ttk.Label(test_frame, text="Status: Not tested", foreground="gray")
        self.test_status.pack(anchor=tk.W, pady=5)
        
        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(button_frame, text="💾 Save Settings", 
                  command=self.save_settings).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="❌ Cancel", 
                  command=self.window.destroy).pack(side=tk.RIGHT)
        
        # Configure grid weights
        config_frame.columnconfigure(1, weight=1)
        self.rtsp_frame.columnconfigure(1, weight=1)
        
        # Initial state
        self.on_source_changed()
    
    def load_presets(self):
        """Load camera presets"""
        presets = {
            "EZVIZ CS-H6c Pro (Main Stream)": "rtsp://admin:{password}@{ip}:554/Streaming/Channels/101",
            "EZVIZ CS-H6c Pro (Sub Stream)": "rtsp://admin:{password}@{ip}:554/Streaming/Channels/102",
            "Hikvision (Main Stream)": "rtsp://{username}:{password}@{ip}:554/Streaming/Channels/1",
            "Hikvision (Sub Stream)": "rtsp://{username}:{password}@{ip}:554/Streaming/Channels/101",
            "Dahua (Main Stream)": "rtsp://{username}:{password}@{ip}:554/cam/realmonitor?channel=1&subtype=0",
            "Dahua (Sub Stream)": "rtsp://{username}:{password}@{ip}:554/cam/realmonitor?channel=1&subtype=1",
            "Generic RTSP": "rtsp://{username}:{password}@{ip}:554/stream1",
            "Axis Camera": "rtsp://{username}:{password}@{ip}/axis-media/media.amp",
            "Foscam": "rtsp://{username}:{password}@{ip}:554/videoMain",
            "TP-Link": "rtsp://{username}:{password}@{ip}:554/stream1"
        }
        
        self.preset_combo['values'] = list(presets.keys())
        self.presets = presets
    
    def load_current_settings(self):
        """Load current camera settings"""
        settings = self.config.get_camera_settings()
        
        if settings:
            # Source type
            if 'source_type' in settings:
                self.source_var.set(settings['source_type'])
            
            # URL or index
            if 'rtsp_url' in settings:
                self.url_var.set(settings['rtsp_url'])
            if 'usb_index' in settings:
                self.usb_index_var.set(str(settings['usb_index']))
            
            # Advanced settings
            if 'resolution' in settings:
                self.resolution_var.set(settings['resolution'])
            if 'fps' in settings:
                self.fps_var.set(str(settings['fps']))
            if 'buffer_size' in settings:
                self.buffer_var.set(str(settings['buffer_size']))
            if 'transport' in settings:
                self.transport_var.set(settings['transport'])
        
        self.on_source_changed()
    
    def on_source_changed(self):
        """Handle source type change"""
        source_type = self.source_var.get()
        
        if source_type == "rtsp" or source_type == "ip":
            self.rtsp_frame.grid()
            self.usb_frame.grid_remove()
        else:  # USB
            self.rtsp_frame.grid_remove()
            self.usb_frame.grid()
    
    def on_preset_selected(self, event):
        """Handle preset selection"""
        # This method will be called when apply_preset is clicked
        pass
    
    def apply_preset(self):
        """Apply selected preset"""
        preset_name = self.preset_var.get()
        if not preset_name or preset_name not in self.presets:
            messagebox.showwarning("Warning", "Please select a preset first")
            return
        
        template = self.presets[preset_name]
        
        # Get connection details
        setup_dialog = CameraSetupDialog(self.window, template)
        if setup_dialog.result:
            self.url_var.set(setup_dialog.result)

    def detect_usb_cameras(self):
        """Detect available USB cameras with proper backend"""
        # Set environment to avoid OBSENSOR
        import os
        os.environ['OPENCV_VIDEOIO_PRIORITY_OBSENSOR'] = '0'

        available_cameras = []

        # Also check if IP camera is configured
        current_settings = self.config.get_camera_settings()
        if current_settings.get('source_type') in ['rtsp', 'ip']:
            rtsp_url = current_settings.get('rtsp_url', '')
            if rtsp_url:
                messagebox.showinfo("Camera Info",
                                    f"IP Camera Configured:\n{rtsp_url}\n\n"
                                    f"Also checking for USB cameras...")

        # Test camera indices 0-5 with DirectShow backend
        for i in range(6):
            try:
                print(f"Testing USB camera index: {i}")
                cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)  # Force DirectShow
                if cap.isOpened():
                    ret, frame = cap.read()
                    if ret and frame is not None:
                        available_cameras.append(i)
                        print(f"✅ USB Camera {i} working")
                    cap.release()
            except Exception as e:
                print(f"USB Camera {i} test failed: {e}")
                if 'cap' in locals():
                    cap.release()
                continue

        if available_cameras:
            camera_list = ", ".join(map(str, available_cameras))
            messagebox.showinfo("USB Cameras", f"Available USB cameras at indices: {camera_list}")
            if available_cameras:
                self.usb_index_var.set(str(available_cameras[0]))
        else:
            messagebox.showinfo("USB Cameras",
                                "No USB cameras detected.\n\n"
                                "If you're using an IP camera, this is normal.\n"
                                "Your IP camera configuration will be used instead.")

    def test_connection(self):
        """Test camera connection"""
        try:
            self.test_status.config(text="Status: Testing...", foreground="orange")
            self.window.update()

            # Get camera source
            source_type = self.source_var.get()

            if source_type == "usb":
                camera_source = int(self.usb_index_var.get())
            else:
                camera_source = self.url_var.get()

            # Test connection
            cap = cv2.VideoCapture(camera_source)

            if cap.isOpened():
                ret, frame = cap.read()
                if ret:
                    height, width = frame.shape[:2]
                    fps = cap.get(cv2.CAP_PROP_FPS)

                    self.test_status.config(
                        text=f"Status: ✅ Connected - {width}x{height} @ {fps:.1f}FPS",
                        foreground="green"
                    )

                    cap.release()
                    return True
                else:
                    self.test_status.config(text="Status: ❌ Cannot read from camera", foreground="red")
            else:
                self.test_status.config(text="Status: ❌ Cannot connect to camera", foreground="red")

            cap.release()
            return False

        except Exception as e:
            self.test_status.config(text=f"Status: ❌ Error - {str(e)}", foreground="red")
            return False

    def preview_camera(self):
        """Preview camera feed"""
        if not self.test_connection():
            messagebox.showerror("Error", "Cannot connect to camera. Please check settings.")
            return
        
        # Open preview window
        preview_window = CameraPreviewWindow(self.window, self.get_camera_source())
    
    def get_camera_source(self):
        """Get camera source based on current settings"""
        source_type = self.source_var.get()
        
        if source_type == "usb":
            return int(self.usb_index_var.get())
        else:
            return self.url_var.get()
    
    def save_settings(self):
        """Save camera settings"""
        try:
            source_type = self.source_var.get()
            
            settings = {
                'source_type': source_type,
                'resolution': self.resolution_var.get(),
                'fps': int(self.fps_var.get()),
                'buffer_size': int(self.buffer_var.get()),
                'transport': self.transport_var.get()
            }
            
            if source_type == "usb":
                settings['usb_index'] = int(self.usb_index_var.get())
            else:
                settings['rtsp_url'] = self.url_var.get()
            
            self.config.save_camera_settings(settings)
            
            messagebox.showinfo("Success", "Camera settings saved successfully!")
            self.window.destroy()
            
        except ValueError as e:
            messagebox.showerror("Error", f"Invalid input: {e}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save settings: {e}")

class CameraSetupDialog:
    def __init__(self, parent, url_template):
        self.result = None
        
        dialog = tk.Toplevel(parent)
        dialog.title("Camera Connection Details")
        dialog.geometry("400x300")
        dialog.transient(parent)
        dialog.grab_set()
        
        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="Enter camera connection details:", 
                 font=("Arial", 10, "bold")).pack(pady=10)
        
        # IP Address
        ttk.Label(frame, text="IP Address:").pack(anchor=tk.W)
        self.ip_var = tk.StringVar(value="192.168.1.100")
        ttk.Entry(frame, textvariable=self.ip_var, width=30).pack(fill=tk.X, pady=2)
        
        # Username
        ttk.Label(frame, text="Username:").pack(anchor=tk.W, pady=(10,0))
        self.username_var = tk.StringVar(value="admin")
        ttk.Entry(frame, textvariable=self.username_var, width=30).pack(fill=tk.X, pady=2)
        
        # Password
        ttk.Label(frame, text="Password:").pack(anchor=tk.W, pady=(10,0))
        self.password_var = tk.StringVar(value="password")
        ttk.Entry(frame, textvariable=self.password_var, show="*", width=30).pack(fill=tk.X, pady=2)
        
        # Port (optional)
        ttk.Label(frame, text="Port (optional):").pack(anchor=tk.W, pady=(10,0))
        self.port_var = tk.StringVar(value="554")
        ttk.Entry(frame, textvariable=self.port_var, width=30).pack(fill=tk.X, pady=2)
        
        # Button frame
        button_frame = ttk.Frame(frame)
        button_frame.pack(fill=tk.X, pady=20)
        
        ttk.Button(button_frame, text="OK", 
                  command=lambda: self.apply_settings(dialog, url_template)).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", 
                  command=dialog.destroy).pack(side=tk.RIGHT)
        
        # Center dialog
        dialog.transient(parent)
        dialog.wait_window()
    
    def apply_settings(self, dialog, url_template):
        """Apply the settings and generate URL"""
        ip = self.ip_var.get().strip()
        username = self.username_var.get().strip()
        password = self.password_var.get().strip()
        port = self.port_var.get().strip()
        
        if not ip or not username or not password:
            messagebox.showerror("Error", "Please fill in all required fields")
            return
        
        # Generate URL from template
        url = url_template.format(
            ip=ip,
            username=username,
            password=password,
            port=port if port else "554"
        )
        
        self.result = url
        dialog.destroy()

class CameraPreviewWindow:
    def __init__(self, parent, camera_source):
        self.camera_source = camera_source
        self.running = False
        
        self.window = tk.Toplevel(parent)
        self.window.title("Camera Preview")
        self.window.geometry("800x600")
        
        # Video display
        self.video_label = tk.Label(self.window, bg='black')
        self.video_label.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Control frame
        control_frame = ttk.Frame(self.window)
        control_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.start_btn = ttk.Button(control_frame, text="Start Preview", 
                                   command=self.start_preview)
        self.start_btn.pack(side=tk.LEFT, padx=5)
        
        self.stop_btn = ttk.Button(control_frame, text="Stop Preview", 
                                  command=self.stop_preview, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(control_frame, text="Close", 
                  command=self.close_window).pack(side=tk.RIGHT, padx=5)
        
        self.window.protocol("WM_DELETE_WINDOW", self.close_window)
    
    def start_preview(self):
        """Start camera preview"""
        try:
            self.cap = cv2.VideoCapture(self.camera_source)
            if not self.cap.isOpened():
                messagebox.showerror("Error", "Cannot open camera")
                return
            
            self.running = True
            self.start_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.NORMAL)
            
            self.update_preview()
            
        except Exception as e:
            messagebox.showerror("Error", f"Preview error: {e}")
    
    def stop_preview(self):
        """Stop camera preview"""
        self.running = False
        
        if hasattr(self, 'cap'):
            self.cap.release()
        
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        
        self.video_label.config(image='')
    
    def update_preview(self):
        """Update preview frame"""
        if self.running and hasattr(self, 'cap'):
            ret, frame = self.cap.read()
            if ret:
                # Resize frame
                height, width = frame.shape[:2]
                max_height = 500
                if height > max_height:
                    scale = max_height / height
                    new_width = int(width * scale)
                    frame = cv2.resize(frame, (new_width, max_height))
                
                # Convert and display
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                from PIL import Image, ImageTk
                pil_image = Image.fromarray(frame_rgb)
                photo = ImageTk.PhotoImage(pil_image)
                
                self.video_label.config(image=photo)
                self.video_label.image = photo
            
            # Schedule next update
            self.window.after(30, self.update_preview)
    
    def close_window(self):
        """Close preview window"""
        self.stop_preview()
        self.window.destroy()
